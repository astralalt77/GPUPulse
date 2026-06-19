"""
Lightweight real-time performance graphs using pyqtgraph.

Key for low resource usage:
- Update only with setData()
- Limited history points
- No unnecessary auto-range on every tick
- Timer-driven from main (no busy loops)
"""

from collections import deque
from typing import List, Tuple, Dict

import pyqtgraph as pg
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGroupBox

from ..collector import MetricsCollector, SystemSnapshot


class PerformanceGraphs(QWidget):
    """Efficient live graphs for CPU, RAM, and GPU(s)."""

    def __init__(self, collector: MetricsCollector, parent=None, max_display_points: int = 180):
        super().__init__(parent)
        self.collector = collector
        self.max_display_points = max_display_points

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Status row
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Monitoring... Poll: 1.0s")
        self.status_label.setStyleSheet("color: #888;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        # Graphs container
        self.graphs_layout = QVBoxLayout()
        layout.addLayout(self.graphs_layout)

        # Setup plots
        self._setup_plots()

        # Timer (will be started by parent)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update)

        self._last_snapshot: SystemSnapshot = None

    def _setup_plots(self):
        pg.setConfigOptions(antialias=False)  # small perf win for live data

        self.plots = {}          # name -> PlotWidget
        self.curves = {}         # name -> PlotCurveItem

        # CPU plot
        cpu_box = self._create_plot_group("CPU Utilization", "cpu", "%", 0, 100, color="#4CAF50")
        self.graphs_layout.addWidget(cpu_box)

        # RAM plot
        ram_box = self._create_plot_group("Memory (RAM)", "ram", "MiB", 0, None, color="#2196F3")
        self.graphs_layout.addWidget(ram_box)

        # GPU plots (NVIDIA + onboard iGPU if present)
        self.gpu_util_boxes = {}
        self.gpu_vram_boxes = {}
        self.onboard_box = None

        if self.collector.has_nvidia():
            for i in range(self.collector.get_gpu_count()):
                util_box = self._create_plot_group(f"GPU {i} Utilization", f"gpu{i}_util", "%", 0, 100, color="#FF9800")
                self.gpu_util_boxes[i] = util_box
                self.graphs_layout.addWidget(util_box)

                vram_box = self._create_plot_group(f"GPU {i} VRAM Used", f"gpu{i}_vram", "MiB", 0, None, color="#E91E63")
                self.gpu_vram_boxes[i] = vram_box
                self.graphs_layout.addWidget(vram_box)

        # Onboard / iGPU always shown if detected (never hidden)
        if self.collector.has_onboard_gpu():
            self.onboard_box = self._create_plot_group("Onboard GPU Util", "onboard", "%", 0, 100, color="#9C27B0")
            self.graphs_layout.addWidget(self.onboard_box)
            note = QLabel("Onboard shares system RAM (no dedicated VRAM – see RAM graph)")
            note.setStyleSheet("color: #888; font-size: 8pt; padding: 2px;")
            self.graphs_layout.addWidget(note)
        elif not self.collector.has_nvidia():
            no_gpu = QLabel("No NVIDIA discrete GPU detected.\n"
                            "CPU + RAM graphs always shown (onboard shares RAM).\n"
                            "Onboard GPU util graph added if detected (AMD real, Intel proxy).")
            no_gpu.setStyleSheet("color: #888; font-style: italic; padding: 4px;")
            self.graphs_layout.addWidget(no_gpu)

    def _create_plot_group(self, title: str, key: str, unit: str, y_min: int, y_max, color: str) -> QGroupBox:
        box = QGroupBox(title)
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(4, 4, 4, 4)

        plot = pg.PlotWidget()
        plot.setBackground("#1e1e1e")
        plot.showGrid(x=True, y=True, alpha=0.2)
        plot.setLabel("left", unit)
        plot.setLabel("bottom", "seconds ago")

        # Lock range where makes sense
        if y_max is not None:
            plot.setYRange(y_min, y_max, padding=0.05)

        plot.setMouseEnabled(x=False, y=False)  # keep it simple and light
        plot.setMenuEnabled(False)

        curve = plot.plot(pen=pg.mkPen(color=color, width=1.8))

        box_layout.addWidget(plot)

        self.plots[key] = plot
        self.curves[key] = curve

        return box

    def start(self, interval_ms: int = 1000):
        """Start the update timer."""
        self.timer.start(interval_ms)
        self.status_label.setText(f"Monitoring — poll every {interval_ms/1000:.1f}s")

    def stop(self):
        self.timer.stop()

    def _update(self):
        """Called on timer. Collect + refresh graphs with minimal work."""
        snap = self.collector.collect()
        self._last_snapshot = snap

        history = self.collector.get_history()

        now = snap.timestamp

        # === CPU ===
        cpu_data = history["cpu"]
        if cpu_data:
            x = [(now - t) for t, _ in cpu_data][-self.max_display_points:]
            y = [v for _, v in cpu_data][-self.max_display_points:]
            self.curves["cpu"].setData(x, y)

        # === RAM ===
        ram_data = history["ram"]
        if ram_data:
            x = [(now - t) for t, _ in ram_data][-self.max_display_points:]
            y = [v for _, v in ram_data][-self.max_display_points:]
            self.curves["ram"].setData(x, y)

            # Auto-scale RAM y range based on total (cheap)
            if snap.ram_total:
                self.plots["ram"].setYRange(0, snap.ram_total * 1.05, padding=0)

        # === GPUs ===
        if self.collector.has_nvidia():
            for idx in range(self.collector.get_gpu_count()):
                # GPU Util
                util_key = f"gpu{idx}_util"
                if util_key in self.curves and idx in history["gpu_util"]:
                    gdata = history["gpu_util"][idx]
                    if gdata:
                        x = [(now - t) for t, _ in gdata][-self.max_display_points:]
                        y = [v for _, v in gdata][-self.max_display_points:]
                        self.curves[util_key].setData(x, y)

                # VRAM
                vram_key = f"gpu{idx}_vram"
                if vram_key in self.curves and idx in history["gpu_vram"]:
                    gdata = history["gpu_vram"][idx]
                    if gdata:
                        x = [(now - t) for t, _ in gdata][-self.max_display_points:]
                        y = [v for _, v in gdata][-self.max_display_points:]
                        self.curves[vram_key].setData(x, y)

                        # Set y range to GPU total memory
                        if snap.gpus:
                            for g in snap.gpus:
                                if g.index == idx:
                                    self.plots[vram_key].setYRange(0, g.memory_total * 1.05, padding=0)
                                    break

        if self.onboard_box and 'onboard' in self.curves:
            current = self.collector.get_onboard_gpu_util() or 0
            odata = history.get("onboard", []) or []
            if odata:
                x = [(now - t) for t, _ in odata][-self.max_display_points:]
                # light visual bump so the line is visible above axis at idle/low values;
                # real value always shown in the box title
                y = [max(v, 2) for _, v in odata][-self.max_display_points:]
                self.curves["onboard"].setData(x, y)
            self.curves["onboard"].setSymbol('o')
            self.curves["onboard"].setSymbolSize(5)
            self.curves["onboard"].setSymbolBrush(pg.mkBrush("#9C27B0"))
            self.curves["onboard"].setPen(pg.mkPen("#9C27B0", width=2))
            self.onboard_box.setTitle(f"Onboard GPU Util: {current}%")

        # Update status with current values
        parts = []
        if snap.gpus:
            parts.append(" | ".join(
                f"GPU{g.index}: {g.utilization:.0f}% {g.memory_used}MiB" for g in snap.gpus
            ))
        if self.collector.has_onboard_gpu():
            onboard_util = self.collector.get_onboard_gpu_util()
            if onboard_util is not None:
                parts.append(f"Onboard: {onboard_util}%")
            else:
                parts.append("Onboard: detected")
        gpu_str = (" | " + " | ".join(parts)) if parts else ""

        self.status_label.setText(
            f"CPU: {snap.cpu_percent:.1f}%  |  RAM: {snap.ram_used} MiB ({snap.ram_percent:.1f}%)  {gpu_str}"
        )


# Standalone test (useful while developing)
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    collector = MetricsCollector(history_seconds=120, poll_interval=1.0)
    w = PerformanceGraphs(collector, max_display_points=120)
    w.show()
    w.start(1000)
    sys.exit(app.exec())
