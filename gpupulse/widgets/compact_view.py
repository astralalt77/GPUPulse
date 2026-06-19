"""
Compact always-on-top mini view for GPUPulse.
Lightweight summary of key metrics.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from ..collector import MetricsCollector


class CompactView(QWidget):
    """Small always-on-top window showing live key stats."""

    def __init__(self, collector: MetricsCollector, parent=None):
        super().__init__(parent)
        self.collector = collector
        self.setWindowTitle("GPUPulse Compact")
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.resize(280, 120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        # Title
        title = QLabel("GPUPulse")
        title.setFont(QFont("sans-serif", 9, QFont.Bold))
        title.setStyleSheet("color: #aaa;")
        layout.addWidget(title)

        # Stats row
        self.stats_label = QLabel()
        self.stats_label.setFont(QFont("monospace", 11))
        self.stats_label.setStyleSheet("""
            QLabel {
                background: #1e1e1e;
                color: #ddd;
                padding: 6px;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.stats_label)

        # Optional GPU line
        self.gpu_label = QLabel()
        self.gpu_label.setFont(QFont("monospace", 9))
        self.gpu_label.setStyleSheet("color: #4CAF50;")
        layout.addWidget(self.gpu_label)

        self.setStyleSheet("background-color: #2b2b2b; border: 1px solid #444; border-radius: 6px;")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(1000)  # 1s update, lightweight

        self.update_stats()

        # Make draggable
        self._drag_pos = None

    def update_stats(self):
        snap = self.collector.collect()

        cpu = snap.cpu_percent
        ram_pct = snap.ram_percent

        text = f"CPU: {cpu:5.1f}%   RAM: {ram_pct:5.1f}%"

        self.stats_label.setText(text)

        if snap.gpus:
            g = snap.gpus[0]
            gpu_text = f"GPU: {g.utilization:3.0f}%  VRAM: {g.memory_used}/{g.memory_total}MiB"
            if g.temperature:
                gpu_text += f"  {g.temperature:.0f}°C"
            self.gpu_label.setText(gpu_text)
            self.gpu_label.show()
        elif self.collector.has_onboard_gpu():
            u = self.collector.get_onboard_gpu_util() or 0
            self.gpu_label.setText(f"Onboard: {u:3.0f}%  (shares RAM)")
            self.gpu_label.show()
        else:
            self.gpu_label.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)
