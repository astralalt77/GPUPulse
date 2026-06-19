"""
Lightweight metrics collector for GPUPulse.

Design goals:
- Extremely low overhead (this is a monitor, not a load)
- Always works (psutil only)
- NVIDIA optional via nvidia-ml-py (pynvml)
- Fast collection, minimal syscalls per tick
"""

import time
import os
import subprocess
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

import psutil

# NVIDIA optional
try:
    import pynvml as nvml
    _NVML_AVAILABLE = True
except ImportError:
    nvml = None
    _NVML_AVAILABLE = False


@dataclass
class GPUMetrics:
    index: int
    name: str
    utilization: float          # 0-100
    memory_used: int            # MiB
    memory_total: int           # MiB
    temperature: Optional[float] = None   # Celsius
    power_draw: Optional[float] = None    # Watts
    memory_util: Optional[float] = None   # memory utilization % if available


@dataclass
class SystemSnapshot:
    timestamp: float
    cpu_percent: float
    ram_used: int               # MiB
    ram_total: int              # MiB
    ram_percent: float
    gpus: List[GPUMetrics] = field(default_factory=list)
    # Future: per-process GPU memory will live here or in separate call


class MetricsCollector:
    """Collects system + optional GPU metrics with minimal cost."""

    def __init__(self, history_seconds: int = 180, poll_interval: float = 1.0):
        self.history_seconds = history_seconds
        self.poll_interval = poll_interval
        self._max_points = int(history_seconds / poll_interval) + 10

        self.cpu_history: deque = deque(maxlen=self._max_points)
        self.ram_history: deque = deque(maxlen=self._max_points)
        self.gpu_util_history: Dict[int, deque] = {}   # gpu_index -> deque
        self.gpu_vram_history: Dict[int, deque] = {}

        self.onboard_util_history: deque = deque(maxlen=self._max_points)
        self.onboard_info = self._detect_onboard()
        if self.onboard_info:
            util = self.get_onboard_gpu_util() or 0
            self.onboard_util_history.append( (time.time(), util) )

        self._nvml_initialized = False
        self._gpu_handles: Dict[int, Any] = {}

        if _NVML_AVAILABLE:
            self._try_init_nvml()

    def _try_init_nvml(self):
        try:
            nvml.nvmlInit()
            count = nvml.nvmlDeviceGetCount()
            for i in range(count):
                handle = nvml.nvmlDeviceGetHandleByIndex(i)
                self._gpu_handles[i] = handle
                self.gpu_util_history[i] = deque(maxlen=self._max_points)
                self.gpu_vram_history[i] = deque(maxlen=self._max_points)
            self._nvml_initialized = True
        except Exception as e:
            self._nvml_initialized = False  # expected on systems without NVIDIA drivers (silent)

    def has_nvidia(self) -> bool:
        return self._nvml_initialized and len(self._gpu_handles) > 0

    def get_gpu_count(self) -> int:
        return len(self._gpu_handles)

    def _detect_onboard(self):
        """Detect onboard/integrated GPU (Intel/AMD) without NVIDIA."""
        info = None
        try:
            result = subprocess.run(['lspci'], capture_output=True, text=True, timeout=1)
            for line in result.stdout.splitlines():
                line_lower = line.lower()
                if any(x in line_lower for x in ['vga', '3d', 'display']):
                    if 'intel' in line_lower:
                        info = {'vendor': 'Intel', 'desc': line.strip()}
                        break
                    elif 'amd' in line_lower or ('ati' in line_lower and 'compat' not in line_lower):
                        info = {'vendor': 'AMD', 'desc': line.strip()}
                        break
        except:
            pass
        if not info:
            # Sysfs fallback
            for i in range(4):
                try:
                    vendor_path = f'/sys/class/drm/card{i}/device/vendor'
                    if os.path.exists(vendor_path):
                        with open(vendor_path) as f:
                            v = f.read().strip()
                            if v == '0x8086':
                                info = {'vendor': 'Intel', 'desc': 'Integrated'}
                                break
                            elif v == '0x1002':
                                info = {'vendor': 'AMD', 'desc': 'Integrated'}
                                break
                except:
                    pass
        return info

    def has_onboard_gpu(self):
        return self.onboard_info is not None

    def get_onboard_gpu_util(self):
        """Basic util for AMD (busy % via sysfs); Intel uses freq ratio as proxy.
        Tries all known locations; not gated on vendor string (more robust across misdetects and hybrids).
        """
        if not self.onboard_info:
            return None
        try:
            for i in range(4):
                # AMD direct busy % (preferred when present)
                busy_path = f'/sys/class/drm/card{i}/device/gpu_busy_percent'
                if os.path.exists(busy_path):
                    with open(busy_path) as f:
                        val = int(f.read().strip())
                        return min(100, max(0, val))

                # Intel (and similar) rough % from cur/max freq - try multiple path layouts always
                for base in [
                    f'/sys/class/drm/card{i}',
                    f'/sys/class/drm/card{i}/device',
                    f'/sys/class/drm/card{i}/device/drm/card{i}',
                    f'/sys/class/drm/card{i}/gt',
                    f'/sys/class/drm/card{i}/device/gt',
                ]:
                    cur_path = f'{base}/gt_cur_freq_mhz'
                    max_path = f'{base}/gt_max_freq_mhz'
                    if os.path.exists(cur_path) and os.path.exists(max_path):
                        with open(cur_path) as f: cur = int(f.read().strip())
                        with open(max_path) as f: maxf = int(f.read().strip())
                        if maxf > 0:
                            return min(100, max(0, int((cur / maxf) * 100)))
                    # Some layouts expose act freq too; fall back to it if cur missing
                    act_path = f'{base}/gt_act_freq_mhz'
                    if not os.path.exists(cur_path) and os.path.exists(act_path) and os.path.exists(max_path):
                        with open(act_path) as f: cur = int(f.read().strip())
                        with open(max_path) as f: maxf = int(f.read().strip())
                        if maxf > 0:
                            return min(100, max(0, int((cur / maxf) * 100)))

            # Fallback search for any gt_max or busy (last resort; walk can be finicky on sysfs so limited)
            try:
                for root, dirs, files in os.walk('/sys/class/drm'):
                    if 'gt_max_freq_mhz' in files or 'gt_cur_freq_mhz' in files:
                        try:
                            curp = os.path.join(root, 'gt_cur_freq_mhz')
                            if not os.path.exists(curp):
                                curp = os.path.join(root, 'gt_act_freq_mhz')
                            if os.path.exists(curp):
                                with open(curp) as f: cur = int(f.read().strip())
                                with open(os.path.join(root, 'gt_max_freq_mhz')) as f: maxf = int(f.read().strip())
                                if maxf > 0:
                                    return min(100, max(0, int((cur / maxf) * 100)))
                        except:
                            pass
                    if 'gpu_busy_percent' in files:
                        try:
                            with open(os.path.join(root, 'gpu_busy_percent')) as f:
                                val = int(f.read().strip())
                                return min(100, max(0, val))
                        except:
                            pass
                    # limit walk cost
                    if root.count(os.sep) - '/sys/class/drm'.count(os.sep) > 2:
                        dirs[:] = []
            except:
                pass
        except:
            pass
        return 0  # 0 if detected but currently idle / no better metric

    def collect(self) -> SystemSnapshot:
        """Single lightweight collection tick."""
        ts = time.time()

        # CPU - use non-blocking
        cpu = psutil.cpu_percent(interval=None)

        # RAM
        mem = psutil.virtual_memory()
        ram_used = mem.used // (1024 * 1024)
        ram_total = mem.total // (1024 * 1024)
        ram_pct = mem.percent

        gpus = []

        if self._nvml_initialized:
            for idx, handle in self._gpu_handles.items():
                try:
                    util = nvml.nvmlDeviceGetUtilizationRates(handle)
                    mem_info = nvml.nvmlDeviceGetMemoryInfo(handle)

                    temp = None
                    try:
                        temp = nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
                    except Exception:
                        pass

                    power = None
                    try:
                        power = nvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # mW -> W
                    except Exception:
                        pass

                    gpu_metric = GPUMetrics(
                        index=idx,
                        name=nvml.nvmlDeviceGetName(handle).decode() if isinstance(nvml.nvmlDeviceGetName(handle), bytes) else nvml.nvmlDeviceGetName(handle),
                        utilization=float(util.gpu),
                        memory_used=mem_info.used // (1024 * 1024),
                        memory_total=mem_info.total // (1024 * 1024),
                        temperature=float(temp) if temp is not None else None,
                        power_draw=power,
                    )
                    gpus.append(gpu_metric)

                    # Update histories
                    self.gpu_util_history[idx].append((ts, float(util.gpu)))
                    self.gpu_vram_history[idx].append((ts, gpu_metric.memory_used))

                except Exception:
                    # GPU went away or transient error — skip this tick
                    pass

        # Record main histories
        self.cpu_history.append((ts, cpu))
        self.ram_history.append((ts, ram_used))

        onboard_util = self.get_onboard_gpu_util()
        if onboard_util is not None:
            self.onboard_util_history.append((ts, onboard_util))

        return SystemSnapshot(
            timestamp=ts,
            cpu_percent=cpu,
            ram_used=ram_used,
            ram_total=ram_total,
            ram_percent=ram_pct,
            gpus=gpus,
        )

    def get_history(self):
        """Return current history buffers (for plotting)."""
        return {
            "cpu": list(self.cpu_history),
            "ram": list(self.ram_history),
            "gpu_util": {k: list(v) for k, v in self.gpu_util_history.items()},
            "gpu_vram": {k: list(v) for k, v in self.gpu_vram_history.items()},
            "onboard": list(self.onboard_util_history),
        }

    def shutdown(self):
        if self._nvml_initialized:
            try:
                nvml.nvmlShutdown()
            except Exception:
                pass

    def get_gpu_processes(self) -> Dict[int, dict]:
        """
        Lightweight: returns {pid: {'vram_mb': int, 'gpus': list[int]}} 
        for all processes using GPU memory.
        Enhanced to include which GPU(s) the process is using.
        """
        if not self.has_nvidia():
            return {}

        gpu_procs: Dict[int, dict] = {}
        for idx, handle in self._gpu_handles.items():
            try:
                # Compute processes (typical for AI / CUDA)
                for p in nvml.nvmlDeviceGetComputeRunningProcesses(handle):
                    if getattr(p, 'usedGpuMemory', 0):
                        pid = p.pid
                        mem_mb = p.usedGpuMemory // (1024 * 1024)
                        if pid not in gpu_procs:
                            gpu_procs[pid] = {'vram_mb': 0, 'gpus': []}
                        gpu_procs[pid]['vram_mb'] += mem_mb
                        if idx not in gpu_procs[pid]['gpus']:
                            gpu_procs[pid]['gpus'].append(idx)

                # Graphics processes too (for completeness)
                for p in nvml.nvmlDeviceGetGraphicsRunningProcesses(handle):
                    if getattr(p, 'usedGpuMemory', 0):
                        pid = p.pid
                        mem_mb = p.usedGpuMemory // (1024 * 1024)
                        if pid not in gpu_procs:
                            gpu_procs[pid] = {'vram_mb': 0, 'gpus': []}
                        gpu_procs[pid]['vram_mb'] += mem_mb
                        if idx not in gpu_procs[pid]['gpus']:
                            gpu_procs[pid]['gpus'].append(idx)
            except Exception:
                # Transient or permission issue on this device
                pass
        return gpu_procs

    def _detect_engine(self, name: str, cmdline: str) -> str:
        """
        Detect common local LLM inference backends/engines.
        This helps users quickly identify which process is running their AI workload.
        """
        name = (name or "").lower()
        cmd = (cmdline or "").lower()

        if "ollama" in name or "ollama" in cmd:
            return "Ollama"
        if "koboldcpp" in name or "kobold" in cmd:
            return "KoboldCPP"
        if "vllm" in cmd or "vllm" in name:
            return "vLLM"
        if "llama-server" in cmd or ("llama" in name and "server" in cmd):
            return "llama.cpp (server)"
        if "llama" in name or "llama" in cmd:
            # Covers llama.cpp main binary, server, etc.
            return "llama.cpp"
        if "text-generation-webui" in cmd or "oobabooga" in cmd or "textgen" in cmd:
            return "text-gen-webui"
        if "lmstudio" in name or "lm_studio" in cmd:
            return "LM Studio"
        if "gpt4all" in name or "gpt4all" in cmd:
            return "GPT4All"
        if "anything" in cmd and "llm" in cmd:
            return "AnythingLLM"
        if "localai" in name or "localai" in cmd:
            return "LocalAI"
        return ""

    def get_top_processes(self, n: int = 25, gpu_data: Optional[Dict[int, int]] = None) -> List[Dict[str, Any]]:
        """
        Lightweight top-N processes.
        Only called when the Processes tab is active or refreshed.
        If gpu_data provided, includes 'gpu_vram_mb', 'gpus', 'device' and sorts GPU-using processes higher.

        'device' is "NVIDIA 0", "NVIDIA 0,1", or "CPU" so you can see at a glance what hardware each process is using.
        Also detects common inference engines (llama.cpp, ollama, vLLM, koboldcpp, etc.)
        so you can quickly see what is driving your GPU during local AI work.
        """
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info', 'cmdline']):
            try:
                pinfo = proc.info
                mem = pinfo.get('memory_info')
                mem_mb = (mem.rss // (1024 * 1024)) if mem else 0

                gpu_vram = 0
                gpu_list = []
                if gpu_data:
                    entry = gpu_data.get(pinfo['pid'], {})
                    if isinstance(entry, dict):
                        gpu_vram = entry.get('vram_mb', 0)
                        gpu_list = entry.get('gpus', [])
                    else:
                        gpu_vram = entry

                name = pinfo['name'] or ''
                cmdline = ' '.join(pinfo.get('cmdline') or [])
                engine = self._detect_engine(name, cmdline)

                # Device column: makes it obvious which hardware a process is using
                device = "CPU"
                if gpu_list:
                    device = "NVIDIA " + ",".join(str(g) for g in gpu_list)
                elif gpu_vram > 0:
                    device = "NVIDIA"

                processes.append({
                    'pid': pinfo['pid'],
                    'name': name or 'unknown',
                    'user': pinfo.get('username') or '?',
                    'cpu': pinfo.get('cpu_percent') or 0.0,
                    'ram_mb': mem_mb,
                    'gpu_vram_mb': gpu_vram,
                    'gpus': gpu_list,
                    'device': device,
                    'engine': engine,
                    'cmdline': cmdline[:120],
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Prioritize GPU VRAM (great when running llama.cpp / ollama / vLLM etc.),
        # then CPU, then RAM.
        has_gpu = False
        if gpu_data:
            for v in gpu_data.values():
                val = v.get('vram_mb', 0) if isinstance(v, dict) else v
                if val > 0:
                    has_gpu = True
                    break
        if has_gpu:
            processes.sort(key=lambda p: (-p.get('gpu_vram_mb', 0), -p['cpu'], -p['ram_mb']))
        else:
            processes.sort(key=lambda p: (-p['cpu'], -p['ram_mb']))
        return processes[:n]


# Simple self-test
if __name__ == "__main__":
    c = MetricsCollector(history_seconds=60, poll_interval=1.0)
    for _ in range(2):
        snap = c.collect()
        print(f"CPU: {snap.cpu_percent:.1f}%  RAM: {snap.ram_used} MiB / {snap.ram_total}  GPUs: {len(snap.gpus)}")

    # Test new GPU process support (will be {} here)
    gpu_procs = c.get_gpu_processes()
    procs = c.get_top_processes(5, gpu_data=gpu_procs)
    print(f"Top procs sample (has GPU data: {bool(gpu_procs)}):")
    for p in procs[:3]:
        print(f"  PID {p['pid']}: {p['name'][:20]} CPU={p['cpu']:.1f} RAM={p['ram_mb']} VRAM={p.get('gpu_vram_mb', 0)}")

    c.shutdown()
    print("Collector test complete.")