# GPUPulse Development Log

**Purpose**: A running record of every step we take while building this app.  
Brief notes for quick actions. More detail when we make decisions, face tradeoffs, or solve problems.  
We'll keep this updated and push it to GitHub with the project.

---

## 2026-06-18 - Kickoff

- User said hi.
- Requested we brainstorm and build a GUI task manager for Linux (works on Mint XFCE and Ubuntu, ideally any distro).
- Main focus: GPU monitoring for local AI inference workloads (NVIDIA + fallback to onboard).
- Wanted features similar to Windows Task Manager + nvtop but as a real GUI app (not terminal).
- Specifics mentioned: real-time line graphs for temp, VRAM utilization, GPU usage, processes/users view.
- Liked nvtop but said it's lacking in many ways.

## 2026-06-18 - Requirements & Research

- Discussed existing tools:
  - nvtop (liked but terminal only)
  - Mission Center (closest GUI but not specialized enough for AI users)
  - nvidia-smi, nvitop, gpustat, etc.
- Key constraints from user:
  - Must run on machines with no discrete GPU (onboard graphics or none).
  - NVIDIA first, with graceful fallback.
  - Later: "this app cant be a resource hog" — especially important when driving GPU hard with AI tasks.
- Brainstormed full feature list: Performance tab with graphs, Processes tab (with GPU columns), Users, hardware details, kill processes, etc.

## 2026-06-18 - Security Policy Established

- User note: "never install packages that have been known to have explots"
- Later clarification: **LiteLLM is banned** (had a huge supply chain exploit in 2026 with malicious PyPI versions containing backdoors).
- This ruled out Tauri/Rust path (past CVEs + curl|sh installer concerns) and any risky deps.
- We agreed to keep deps minimal, prefer distro apt packages when possible, use venvs.

## 2026-06-18 - Tech Stack Decision

- Compared options:
  - Tauri (good graphs via web tech, but security history + new toolchain)
  - gtk4-rs (native, like Mission Center)
  - Python + PySide6 / PyQt6 + pyqtgraph
- Recommended PySide6 + pyqtgraph:
  - pyqtgraph is excellent for real-time line graphs (much faster and lighter than matplotlib embedded).
  - PySide6 gives solid desktop widgets (tables, tabs) and is LGPL.
  - Matches user's existing Python/Qt exploration.
  - Lightweight when implemented carefully.
- User asked for pros/cons.
- Confirmed stack: PySide6 + pyqtgraph.
- Also confirmed: no hardware requirements — must work everywhere.

## 2026-06-18 - Name Brainstorm & Selection

- User suggested "GPUMON?"
- We brainstormed many options: GPUPulse, ForgePulse, Helios, Sentinel, Vigil, Lumen, CorePulse, Flux, Inferno, Peak, etc.
- User chose **GPUPulse**.

## 2026-06-18 - Scaffolding Phase

- Created project directory structure.
- Wrote `collector.py`:
  - Uses psutil for CPU/RAM/processes (always works).
  - Optional pynvml (nvidia-ml-py) for GPU data.
  - Designed with deques for bounded history (light on memory).
  - Minimal work per poll.
- Wrote `widgets/performance_graphs.py`:
  - pyqtgraph plots for CPU, RAM, and conditional GPU (util + VRAM).
  - Uses `setData()` for efficient updates.
  - Auto-scaling where needed.
  - No heavy auto-range or busy loops.
- Wrote `widgets/process_table.py`:
  - Basic sortable/filterable table.
  - Refreshes slower and only when visible (to stay light).
- Wrote `main.py`:
  - QMainWindow with tabs (Performance + Processes stub).
  - Live poll interval control (1-10s).
  - Graceful shutdown for NVML.
  - Status labels.
- Added supporting files: requirements.txt, README.md, HOW_TO_RUN.md, .gitignore, LICENSE (MIT).
- Tested collector standalone (works with psutil; gracefully no GPU in this env).
- All without installing any new packages in the workspace (respecting security rules).
- No GUI deps pulled here.

## 2026-06-18 - Devlog Creation (this file)

- User requested: "also later we will create a github repo and push everything there. create a devlog and maintain it."
- Initial DEVLOG.md created.
- User feedback: "devlog is so we know what we done through every step. its a devlog. it should function as one. brief notes when needed.. more detailed when needed."
- Revised this file to better match: chronological step tracking with mix of brief + detailed entries.

## 2026-06-18 - Current State

- Basic working app:
  - Real-time graphs on Performance tab.
  - Processes list (filterable) on second tab.
  - Runs fully on CPU-only (Mint laptop).
  - Will show full NVIDIA data (VRAM, temp, power, etc.) on supported discrete GPUs.
- Strong emphasis on low overhead already in place (1s default, efficient structures, conditional updates).

---

**Future entries will be added as we continue.**  
We'll keep a mix of brief notes ("Added X", "Tested on laptop") and detailed ones (why we chose something, problems encountered, etc.).

When ready, we'll init git and push the whole thing (including this log) to GitHub.

## 2026-06-19 - Added dependency installer + .deb packaging

- Reworked `install.sh` into a true "one-shot" installer:
  - Single command: `./install.sh`
  - Automatically handles apt dependencies, temporary venv for PyInstaller (avoids externally-managed-environment errors), builds the standalone binary, builds a proper .deb, and installs it via dpkg.
  - After running, the app is fully managed by the system software manager.
  - Uninstall with `sudo apt remove gpupulse` (clean, no leftover files or venvs).
  - App appears in the menu and is launchable as `gpupulse`.
- Updated docs to emphasize the one-command experience.
- This directly fixes the UX complaint of "having to install an installer then run something else".

- Created proper `.deb` packaging support:
  - New `build-deb.sh` script
  - Builds a real Debian package using the PyInstaller standalone binary
  - Installs to `/usr/bin/gpupulse`
  - Registers desktop entry
  - Fully managed by dpkg/apt (can be uninstalled with `sudo apt remove gpupulse`)
  - No leftover venvs or Python packages on the system
- `gpupulse.desktop` added for menu integration
- This fulfills the requirement for system software manager management and clean uninstall.

---

## 2026-06-18 - GitHub Repo Created

- User prepared to create GitHub repo.
- Confirmed choice of GNU GPLv3 (yes, GPL3).
- Repo initialized with current state (including LICENSE, .gitignore, etc.).
- Moving on to next step as laid out.

## 2026-06-19 - All Requested Features Implemented (Tray, Renice, Persistence, Settings, GPU details, Theming, Packaging)

- **Tray icon + compact/mini view**: Full QSystemTrayIcon with menu (Show, Compact, Settings, Quit). Double-click tray toggles main. Added CompactView widget (frameless, draggable, always-on-top summary of CPU/RAM/GPU stats, 1s updates).
- **Renice / priority adjustment**: Context menu on Processes rows with presets (High -10, Normal 0, Low +10, Idle +19). Uses psutil.nice(). Shows permission warning for negative values.
- **Persist column visibility + order**: Uses QSettings + QHeaderView.saveState()/restoreState(). Persisted on close, restored on start. User can drag + toggle freely.
- **More GPU per-process details**: Enhanced get_gpu_processes() to return per-pid {'vram_mb', 'gpus': [...]}. Table now shows e.g. "1234 (GPU0,1)" when multi-GPU or specific. Richer NVML data for AI processes.
- **Settings dialog / config file**: New SettingsDialog with poll interval, start minimized, minimize to tray, theme (Fusion/Dark), history length. Uses QSettings (light ~/.config/GPUPulse.conf on Linux).
- **Theming tweaks for XFCE**: Dark palette option applied via QPalette + Fusion style. Works decently on Mint XFCE. User selectable in Settings.
- **PyInstaller/AppImage packaging**: Added build.py (PyInstaller onefile), requirements-build.txt. Updated docs implicitly. Produces standalone. For AppImage, follow standard linuxdeploy/appimagetool steps.
- All changes preserve "not a resource hog" design: tray/compact use low timers, config is cheap, no heavy deps.
- GPL3 confirmed.
- Project ready for GitHub.

User can now configure extensively, monitor compactly from tray, kill/renice AI backends (llama.cpp, ollama etc), and build distributable.

---

## 2026-06-18 - GitHub Setup + License + Column Customization + AI Backend Detection

- User setting up GitHub repo.
- **.gitignore**: Yes, select/add one (we have a good Python one).
- **License choice**: 
  - User wants "free for everyone" + "nobody be able to steal and sell it".
  - Changed from MIT to **GNU GPLv3**.
  - GPLv3 allows free use/modification/distribution.
  - If anyone sells a modified version, they **must** provide full source under GPLv3.
  - This is the strongest practical protection against closed-source commercial theft while staying fully open source.
  - MIT would have allowed someone to take the code and sell a closed version.
- Updated LICENSE file with explanation.

- **AI backend detection** (user runs llama.cpp, also wants support for others):
  - Added `_detect_engine()` in collector.
  - Supports: llama.cpp (and server), Ollama, vLLM, KoboldCPP, text-gen-webui, LM Studio, GPT4All, LocalAI, etc.
  - Looks at process name + cmdline.
  - New field `'engine'` in process data.
  - New "Engine" column in table (green when detected).
  - This makes it very easy to spot which inference engine is using your GPU during local runs.

- **Column selection and rearrangement**:
  - User request: "i wanna be able to select which columns display and arrange by those columns as well."
  - `QHeaderView.setSectionsMovable(True)` → drag columns to reorder.
  - Right-click on table header → popup menu with checkboxes to show/hide any column (PID, Name, CPU, RAM, GPU VRAM, Engine, Command, etc.).
  - Added "Engine" column as well.
  - Lightweight implementation (no extra heavy widgets).

- All changes keep the app very light. Engine detection and GPU data only fetched when the Processes tab is visible.

---

## 2026-06-18 - Continue Building: GPU per-process VRAM in Processes tab

- User: "continue building. i will setup the repo while youre doing that"
- Focused on making the Processes tab actually useful for the main goal (seeing which inference processes are using GPU memory).
- In collector.py:
  - Added get_gpu_processes(): queries NVML running processes (compute + graphics) for PID → VRAM MiB. Called only on demand.
  - Updated get_top_processes(n, gpu_data=...): merges 'gpu_vram_mb', and when any GPU usage exists, sorts by (GPU VRAM desc, CPU, RAM). No cost when no NVIDIA.
- In process_table.py:
  - Now 7 columns: added "GPU VRAM (MiB)".
  - Processes with >0 GPU VRAM get red text for quick visual identification.
  - refresh() now fetches GPU data (if has_nvidia) and passes it down.
  - Label updated to reflect GPU prioritization.
- Design kept lightweight: GPU query skipped on main performance loop and on hidden tabs. Uses the same 2s visible-only timer.
- Result: On NVIDIA systems you'll immediately see e.g. python/ollama/vllm processes at the top with their VRAM consumption. On CPU-only machines it just shows 0 with no overhead.

## 2026-06-18 - Current State (end of session)

- Performance graphs: working (CPU/RAM + conditional full GPU metrics + history).
- Processes: now shows GPU VRAM per process, sorted to surface AI workloads first.
- Still extremely low overhead by design.
- All changes respect "no resource hog" + security constraints.

## 2026-06-19 - Separate GPU/CPU processes + Device column

- User request: "id like to see gpu processes and cpu processes seperately. or... a column denoting which its running on"
- Added "Device" column to Processes table: shows "NVIDIA 0", "NVIDIA 0,1", "NVIDIA", or "CPU".
  - "which its running on" is now explicit and sortable (click header to group).
  - Moved GPU index info out of the VRAM cell into Device (VRAM column is now clean numeric).
- Added "Show:" dropdown (All / GPU processes only / CPU processes only).
  - Lets you view the two sets separately with one click. Filter still works on top.
- Centralized 'device' computation in collector.get_top_processes().
- Updated labels, column count (now 9), menu, resizing, population logic, and docs.
- NVIDIA only for the GPU marker today (we get real per-process data from NVML). Onboard/iGPU processes fall under "CPU" (no lightweight per-pid util for iGPU like NVML provides).
- On machines without discrete NVIDIA: everything shows "CPU" (correct; the onboard graph still monitors the iGPU load in Performance).
- Old column settings may need a quick re-adjust via right-click header after upgrade (column inserted).
- Run `PYTHONPATH=. python3 main.py` (or reinstall) to see it.

## 2026-06-19 - Onboard GPU line was flat (fix)

- User: "i have a gpu line now. but it stays flat when im taxing the graphics"
- Root cause: onboard detection bug.
  - `if 'intel' in line` (raw, not lower) + `'ati' in line` matched inside the word "compatible" from lspci → Intel iGPU misdetected as "AMD".
  - When vendor=AMD, the Intel gt_cur/gt_max freq paths were skipped entirely.
  - Fallback os.walk over /sys/class/drm often yields only topdir on sysfs (no descent or hits) → always returned 0.
- Result: history always 0 → plotting hack made a flat line at the forced min height.
- Fixes:
  - collector.py: detection now uses `line_lower` + safer `'ati' in ... and 'compat' not in` to avoid substring collision.
  - get_onboard_gpu_util: removed `if vendor == 'Intel'` gate; always probe freq paths + expanded bases (`/cardN/gt`, `/cardN`, device variants, act_freq fallback). Made walk more defensive.
  - Now correctly detects Intel, reads real cur/max (e.g. 13% idle → 40%+ under glxgears).
  - performance_graphs.py: onboard box created independently of NVIDIA (so never hidden when both present). Cleaned plotting: use actual history points (no more timestamp-order-breaking concat of "recent segment"), only a tiny viz bump `max(v, 2)` + symbols/thicker pen for low/zero visibility. Real % in title.
  - Status line now shows Onboard even next to NVIDIA GPUs.
- AMD path (gpu_busy_percent) unaffected and still preferred.
- Freq ratio is a proxy (ramps under 3D; video decode engines may report less), but now actually moves.
- Restart app (or re `bash install.sh`) to pick up. Onboard line will now respond to graphics load.