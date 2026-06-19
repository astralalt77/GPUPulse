#!/usr/bin/env python3
"""
GPUPulse - Lightweight real-time GPU & system monitor

Run:
    python main.py

Designed to stay out of the way even when your GPU is at 100% during AI inference.
"""

import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QLabel, QPushButton, QHBoxLayout, QSpinBox, QMessageBox,
    QSystemTrayIcon, QMenu, QDialog, QFormLayout, QCheckBox,
    QComboBox
)
from PySide6.QtCore import Qt, QTimer, QSettings, QByteArray
from PySide6.QtGui import QIcon, QPalette, QColor

from gpupulse.collector import MetricsCollector
from gpupulse.widgets.performance_graphs import PerformanceGraphs
from gpupulse.widgets.process_table import ProcessTable
from gpupulse.widgets.compact_view import CompactView
from gpupulse import __version__


class GPUPulseMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"GPUPulse {__version__}")
        self.resize(900, 700)

        # Settings using QSettings (lightweight, no extra deps)
        self.settings = QSettings("GPUPulse", "GPUPulse")

        # Core lightweight collector
        history = self.settings.value("history_seconds", 180, type=int)
        default_poll = self.settings.value("poll_interval", 1.0, type=float)
        self.collector = MetricsCollector(
            history_seconds=history,
            poll_interval=default_poll
        )

        # Central widget + tabs
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # Top controls (keep very minimal)
        controls = QHBoxLayout()
        controls.setContentsMargins(4, 2, 4, 2)

        poll_label = QLabel("Poll interval (seconds):")
        self.poll_spin = QSpinBox()
        self.poll_spin.setRange(1, 10)          # 1s minimum is already quite light
        self.poll_spin.setValue(int(default_poll))
        self.poll_spin.setSingleStep(1)
        self.poll_spin.valueChanged.connect(self._on_poll_changed)

        controls.addWidget(poll_label)
        controls.addWidget(self.poll_spin)
        controls.addStretch()

        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self.show_settings)
        controls.addWidget(settings_btn)

        # Light status / hint
        hint = QLabel("Lightweight mode — designed not to steal resources from your AI workloads")
        hint.setStyleSheet("color: #666; font-size: 10pt;")
        controls.addWidget(hint)

        main_layout.addLayout(controls)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # === Performance Tab (the important one) ===
        self.perf_tab = PerformanceGraphs(
            self.collector,
            max_display_points=history
        )
        self.tabs.addTab(self.perf_tab, "Performance")

        # === Processes Tab ===
        self.process_table = ProcessTable(self.collector)
        self.tabs.addTab(self.process_table, "Processes")

        # === Footer bar ===
        footer = QHBoxLayout()
        footer.addWidget(QLabel("GPUPulse • NVIDIA first, works everywhere"))
        footer.addStretch()

        self.nvidia_label = QLabel()
        if self.collector.has_nvidia():
            self.nvidia_label.setText(f"NVIDIA: {self.collector.get_gpu_count()} GPU(s) detected")
            self.nvidia_label.setStyleSheet("color: #4CAF50;")
        elif self.collector.has_onboard_gpu():
            self.nvidia_label.setText("Onboard GPU (iGPU) monitoring active")
            self.nvidia_label.setStyleSheet("color: #9C27B0;")
        else:
            self.nvidia_label.setText("No discrete GPU (CPU + RAM only)")
            self.nvidia_label.setStyleSheet("color: #888;")
        footer.addWidget(self.nvidia_label)

        main_layout.addLayout(footer)

        # Start monitoring
        interval = int(default_poll * 1000)
        self.perf_tab.start(interval)

        # System tray + compact view
        self._setup_tray()
        self.compact_view = None

        # Restore window state if needed
        if self.settings.value("start_minimized", False, type=bool):
            self.hide()
            self.tray_icon.showMessage("GPUPulse", "Running in tray", QSystemTrayIcon.Information, 2000)

        # Restore column state for processes (after table created)
        self._restore_column_state()

        # Graceful shutdown
        self._setup_close_handler()

    def _on_poll_changed(self, value: int):
        """Change poll rate live. Lower = more overhead."""
        interval_ms = value * 1000
        self.perf_tab.stop()
        self.perf_tab.start(interval_ms)
        # Also update collector's idea of interval (mainly for history sizing)
        self.collector.poll_interval = float(value)
        self.settings.setValue("poll_interval", float(value))

    def _setup_tray(self):
        """System tray icon + menu. Lightweight."""
        self.tray_icon = QSystemTrayIcon(self)
        icon = QIcon.fromTheme("utilities-system-monitor")
        if icon.isNull():
            icon = QIcon.fromTheme("cpu")
        if icon.isNull():
            # Fallback simple icon
            from PySide6.QtGui import QPixmap, QPainter, QColor
            pix = QPixmap(32, 32)
            pix.fill(Qt.transparent)
            p = QPainter(pix)
            p.setBrush(QColor("#4CAF50"))
            p.drawEllipse(4, 4, 24, 24)
            p.end()
            icon = QIcon(pix)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("GPUPulse - GPU & System Monitor")

        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show Main Window")
        show_action.triggered.connect(self.showNormal)
        compact_action = tray_menu.addAction("Show Compact View")
        compact_action.triggered.connect(self.show_compact)
        tray_menu.addSeparator()
        settings_action = tray_menu.addAction("Settings...")
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.instance().quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # left click
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.activateWindow()

    def show_compact(self):
        """Show a small always-on-top compact monitor."""
        if self.compact_view is None or not self.compact_view.isVisible():
            self.compact_view = CompactView(self.collector)
            self.compact_view.show()
        else:
            self.compact_view.raise_()
            self.compact_view.activateWindow()

    def show_settings(self):
        """Open settings dialog."""
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            # Apply changes
            new_poll = dialog.poll_spin.value()
            self.poll_spin.setValue(new_poll)
            self._on_poll_changed(new_poll)

            if dialog.start_min_cb.isChecked() != self.settings.value("start_minimized", False, type=bool):
                self.settings.setValue("start_minimized", dialog.start_min_cb.isChecked())

            # Apply theme
            self._apply_theme(dialog.theme_combo.currentText())

            # Re-apply column state
            if hasattr(self.process_table, '_apply_saved_columns'):
                self.process_table._apply_saved_columns()

    def _apply_theme(self, theme: str):
        app = QApplication.instance()
        if theme == "Dark":
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(45, 45, 45))
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(30, 30, 30))
            palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
            palette.setColor(QPalette.ToolTipBase, Qt.white)
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(60, 60, 60))
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Highlight, QColor(76, 175, 80))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            app.setPalette(palette)
            app.setStyle("Fusion")
        else:
            app.setPalette(QApplication.style().standardPalette())
            app.setStyle("Fusion")

    def _restore_column_state(self):
        """Restore column order and visibility from settings."""
        if hasattr(self.process_table, 'table'):
            header = self.process_table.table.horizontalHeader()
            state = self.settings.value("process_columns_state", None)
            if state:
                try:
                    ba = QByteArray.fromBase64(state.encode() if isinstance(state, str) else state)
                    header.restoreState(ba)
                except Exception:
                    pass

    def _save_column_state(self):
        if hasattr(self.process_table, 'save_column_state'):
            self.process_table.save_column_state()
        elif hasattr(self.process_table, 'table'):
            header = self.process_table.table.horizontalHeader()
            state = header.saveState()
            self.settings.setValue("process_columns_state", state.toBase64().data().decode())

    def _setup_close_handler(self):
        self._close_timer = QTimer(self)
        self.destroyed.connect(self._cleanup)

    def closeEvent(self, event):
        self._save_column_state()
        if self.tray_icon.isVisible() and self.settings.value("start_minimized", False, type=bool) or \
           self.settings.value("minimize_to_tray", True, type=bool):
            event.ignore()
            self.hide()
            self.tray_icon.showMessage("GPUPulse", "Minimized to tray", QSystemTrayIcon.Information, 1500)
        else:
            self._cleanup()
            event.accept()

    def _cleanup(self):
        """Critical: shut down NVML and stop timers so we don't leak resources."""
        try:
            self.perf_tab.stop()
        except Exception:
            pass
        try:
            if self.compact_view:
                self.compact_view.close()
        except Exception:
            pass
        try:
            self.collector.shutdown()
        except Exception:
            pass


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("GPUPulse")

    # Apply saved theme or default
    # We'll create window first to access settings, then apply
    window = GPUPulseMainWindow()

    # Apply theme from settings
    saved_theme = window.settings.value("theme", "Fusion", type=str)
    window._apply_theme(saved_theme)

    # Set initial style
    app.setStyle("Fusion")

    if not window.settings.value("start_minimized", False, type=bool):
        window.show()

    sys.exit(app.exec())


class SettingsDialog(QDialog):
    """Simple settings dialog. Lightweight."""
    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("GPUPulse Settings")
        self.setModal(True)
        self.resize(380, 280)

        layout = QFormLayout(self)

        # Poll interval (note: also controlled in main, here for startup default)
        self.poll_spin = QSpinBox()
        self.poll_spin.setRange(1, 10)
        self.poll_spin.setValue(self.settings.value("poll_interval", 1, type=int))
        layout.addRow("Default poll interval (seconds):", self.poll_spin)

        self.start_min_cb = QCheckBox("Start minimized to tray")
        self.start_min_cb.setChecked(self.settings.value("start_minimized", False, type=bool))
        layout.addRow(self.start_min_cb)

        self.minimize_tray_cb = QCheckBox("Minimize to tray on close")
        self.minimize_tray_cb.setChecked(self.settings.value("minimize_to_tray", True, type=bool))
        layout.addRow(self.minimize_tray_cb)

        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Fusion", "Dark"])
        current_theme = self.settings.value("theme", "Fusion", type=str)
        idx = self.theme_combo.findText(current_theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        layout.addRow("Theme:", self.theme_combo)

        # History length
        self.history_spin = QSpinBox()
        self.history_spin.setRange(30, 600)
        self.history_spin.setSingleStep(30)
        self.history_spin.setValue(self.settings.value("history_seconds", 180, type=int))
        layout.addRow("Graph history (seconds):", self.history_spin)

        note = QLabel("Note: changing history length requires restart")
        note.setStyleSheet("color: #888; font-size: 8pt;")
        layout.addRow(note)

        # Buttons
        btn_layout = QHBoxLayout()
        ok = QPushButton("OK")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_layout.addWidget(ok)
        btn_layout.addWidget(cancel)
        layout.addRow(btn_layout)

        # Save on accept
        self.accepted.connect(self._save_settings)

    def _save_settings(self):
        self.settings.setValue("poll_interval", float(self.poll_spin.value()))
        self.settings.setValue("start_minimized", self.start_min_cb.isChecked())
        self.settings.setValue("minimize_to_tray", self.minimize_tray_cb.isChecked())
        self.settings.setValue("theme", self.theme_combo.currentText())
        self.settings.setValue("history_seconds", self.history_spin.value())


if __name__ == "__main__":
    main()
