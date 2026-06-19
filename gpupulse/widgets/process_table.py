"""
Very lightweight process table.

Updated only when the tab is visible to save CPU.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QHBoxLayout, QPushButton, QLineEdit, QMenu, QMessageBox, QComboBox
)

import psutil
from PySide6.QtCore import QSettings, QByteArray

from ..collector import MetricsCollector


class ProcessTable(QWidget):
    def __init__(self, collector: MetricsCollector, parent=None):
        super().__init__(parent)
        self.collector = collector

        layout = QVBoxLayout(self)

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("Top processes (GPU prioritized). Device column shows NVIDIA vs CPU. Use 'Show' to view GPU/CPU separately. Right-click header: columns. Drag to reorder."))
        self.refresh_btn = QPushButton("Refresh now")
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn)
        header.addStretch()
        layout.addLayout(header)

        # Filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("python, ollama, etc.")
        self.filter_edit.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.filter_edit)
        layout.addLayout(filter_layout)

        # View selector: easily see GPU vs CPU processes separately
        view_layout = QHBoxLayout()
        view_layout.addWidget(QLabel("Show:"))
        self.view_combo = QComboBox()
        self.view_combo.addItems(["All processes", "GPU processes only", "CPU processes only"])
        self.view_combo.currentTextChanged.connect(self._apply_filters)
        view_layout.addWidget(self.view_combo)
        view_layout.addStretch()
        layout.addLayout(view_layout)

        # Table - keep columns minimal for speed
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "PID", "Name", "User", "CPU %", "RAM (MiB)", "Device", "GPU VRAM (MiB)", "Engine", "Command"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Device
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)  # GPU VRAM
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Engine

        # Allow user to drag columns to rearrange them
        self.table.horizontalHeader().setSectionsMovable(True)

        # Right-click on header to toggle column visibility
        self.table.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.horizontalHeader().customContextMenuRequested.connect(self._show_column_menu)
        self.table.itemSelectionChanged.connect(self._update_button_states)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)

        layout.addWidget(self.table)

        # Context menu for renice etc.
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_process_menu)

        # Process management buttons - keep simple and lightweight
        btn_layout = QHBoxLayout()
        self.terminate_btn = QPushButton("Terminate (graceful)")
        self.terminate_btn.clicked.connect(lambda: self._kill_selected(force=False))
        btn_layout.addWidget(self.terminate_btn)

        self.kill_btn = QPushButton("Kill (force)")
        self.kill_btn.clicked.connect(lambda: self._kill_selected(force=True))
        btn_layout.addWidget(self.kill_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Initial button state
        self._update_button_states()

        self._all_rows = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)

        self.visible = False

        # Restore columns from settings if possible
        self._apply_saved_columns()

        # Initial population so Processes tab has data immediately (even before first show)
        self.refresh()

    def _show_column_menu(self, pos):
        """Right-click on table header to choose which columns to display."""
        menu = QMenu(self)
        header = self.table.horizontalHeader()

        column_names = [
            "PID", "Name", "User", "CPU %", "RAM (MiB)", "Device", "GPU VRAM (MiB)", "Engine", "Command"
        ]

        for i, name in enumerate(column_names):
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(not self.table.isColumnHidden(i))
            action.triggered.connect(lambda checked, col=i: self._toggle_column(col))

        menu.exec(self.table.mapToGlobal(pos))

    def _toggle_column(self, column: int):
        """Toggle visibility of a column."""
        hidden = self.table.isColumnHidden(column)
        self.table.setColumnHidden(column, not hidden)
        self.save_column_state()  # persist immediately

    def _update_button_states(self):
        """Enable/disable kill buttons based on selection."""
        has_selection = bool(self.table.selectedItems())
        if hasattr(self, 'terminate_btn'):
            self.terminate_btn.setEnabled(has_selection)
        if hasattr(self, 'kill_btn'):
            self.kill_btn.setEnabled(has_selection)

    def showEvent(self, event):
        super().showEvent(event)
        self.visible = True
        if not self._timer.isActive():
            self._timer.start(2000)  # Slower refresh than graphs — lighter
        self.refresh()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.visible = False
        self._timer.stop()

    def refresh(self):
        # Always populate on initial or when visible; timer updates only while visible
        try:
            # Get GPU process data only if NVIDIA is present (very lightweight call)
            gpu_data = self.collector.get_gpu_processes() if self.collector.has_nvidia() else None
            procs = self.collector.get_top_processes(30, gpu_data=gpu_data)
        except Exception as e:
            procs = []
            print("Process collection error:", e)

        self._all_rows = procs
        self._apply_filters()

    def _apply_filters(self):
        """Apply text filter + the GPU/CPU view selector."""
        text = self.filter_edit.text().lower().strip()
        mode = self.view_combo.currentText() if hasattr(self, 'view_combo') else "All processes"

        filtered = self._all_rows
        if text:
            filtered = [p for p in filtered
                        if text in p['name'].lower() or text in p['cmdline'].lower()]

        if "GPU processes" in mode:
            filtered = [p for p in filtered if p.get('gpu_vram_mb', 0) > 0]
        elif "CPU processes" in mode:
            filtered = [p for p in filtered if p.get('gpu_vram_mb', 0) == 0]

        self._populate_table(filtered)

    def _populate_table(self, procs):
        self.table.setRowCount(0)
        self.table.setSortingEnabled(False)

        for p in procs:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(str(p['pid'])))
            self.table.setItem(row, 1, QTableWidgetItem(p['name']))
            self.table.setItem(row, 2, QTableWidgetItem(p['user']))
            cpu_item = QTableWidgetItem(f"{p['cpu']:.1f}")
            cpu_item.setTextAlignment(Qt.AlignRight)
            self.table.setItem(row, 3, cpu_item)

            ram_item = QTableWidgetItem(str(p['ram_mb']))
            ram_item.setTextAlignment(Qt.AlignRight)
            self.table.setItem(row, 4, ram_item)

            # Device column: clearly shows what the process is running on (GPU or CPU)
            device = p.get('device', 'CPU')
            dev_item = QTableWidgetItem(device)
            if device != "CPU":
                dev_item.setForeground(Qt.red)
            self.table.setItem(row, 5, dev_item)

            # GPU VRAM column (numeric for easy sorting). "which GPU" is now in Device column.
            gpu_vram = p.get('gpu_vram_mb', 0)
            vram_item = QTableWidgetItem(str(gpu_vram))
            vram_item.setTextAlignment(Qt.AlignRight)
            if gpu_vram > 0:
                # Light visual cue for processes actively using GPU VRAM (very useful during AI inference)
                vram_item.setForeground(Qt.red)
            self.table.setItem(row, 6, vram_item)

            # Engine / backend (llama.cpp, ollama, vLLM, koboldcpp, etc.)
            engine = p.get('engine', '')
            engine_item = QTableWidgetItem(engine)
            if engine:
                engine_item.setForeground(Qt.darkGreen)
            self.table.setItem(row, 7, engine_item)

            self.table.setItem(row, 8, QTableWidgetItem(p['cmdline']))

        self.table.setSortingEnabled(True)

    def _kill_selected(self, force: bool = False):
        """Kill selected processes. force=True uses SIGKILL, else SIGTERM (graceful)."""
        selected_rows = set(item.row() for item in self.table.selectedItems())
        if not selected_rows:
            return

        pids = []
        for row in sorted(selected_rows):
            pid_item = self.table.item(row, 0)
            if pid_item:
                try:
                    pids.append(int(pid_item.text()))
                except ValueError:
                    pass

        if not pids:
            return

        action = "Force kill" if force else "Terminate"
        msg = f"{action} these PIDs?\n{pids}\n\nWarning: This may stop running AI inference (llama.cpp, ollama, vLLM, etc.)."
        reply = QMessageBox.question(
            self, "Confirm Kill",
            msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        for pid in pids:
            try:
                proc = psutil.Process(pid)
                if force:
                    proc.kill()
                else:
                    proc.terminate()
            except psutil.NoSuchProcess:
                pass
            except psutil.AccessDenied as e:
                QMessageBox.warning(self, "Permission Denied", f"Cannot kill PID {pid}: {e}\nYou may need to run GPUPulse with higher privileges or use sudo.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to kill PID {pid}: {e}")

    def _apply_saved_columns(self):
        """Restore column visibility and order from QSettings."""
        settings = QSettings("GPUPulse", "GPUPulse")
        header = self.table.horizontalHeader()
        state = settings.value("process_columns_state", None)
        if state:
            try:
                if isinstance(state, str):
                    ba = QByteArray.fromBase64(state.encode())
                else:
                    ba = QByteArray(state)
                header.restoreState(ba)
            except Exception:
                pass  # ignore bad state

    def save_column_state(self):
        """Save current column state."""
        settings = QSettings("GPUPulse", "GPUPulse")
        header = self.table.horizontalHeader()
        state = header.saveState()
        settings.setValue("process_columns_state", state.toBase64().data().decode())

    def _show_process_menu(self, pos):
        """Context menu for selected process(es) - renice etc."""
        selected_rows = set(item.row() for item in self.table.selectedItems())
        if not selected_rows:
            return

        pids = []
        for row in selected_rows:
            pid_item = self.table.item(row, 0)
            if pid_item:
                try:
                    pids.append(int(pid_item.text()))
                except:
                    pass
        if not pids:
            return

        menu = QMenu(self)
        for label, nice_val in [
            ("High priority (-10)", -10),
            ("Normal (0)", 0),
            ("Low priority (+10)", 10),
            ("Idle (+19)", 19),
        ]:
            act = menu.addAction(label)
            act.triggered.connect(lambda checked=False, v=nice_val: self._renice_pids(pids, v))

        menu.addSeparator()
        # Kill options already have buttons, but for completeness
        kill_act = menu.addAction("Terminate (graceful)")
        kill_act.triggered.connect(lambda: self._kill_selected(force=False))
        force_act = menu.addAction("Kill (force)")
        force_act.triggered.connect(lambda: self._kill_selected(force=True))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _renice_pids(self, pids: list, nice_value: int):
        """Change priority (nice) for pids."""
        for pid in pids:
            try:
                proc = psutil.Process(pid)
                current = proc.nice()
                proc.nice(nice_value)
                print(f"Reniced PID {pid} from {current} to {nice_value}")
            except psutil.AccessDenied:
                QMessageBox.warning(self, "Permission Denied",
                    f"Cannot change priority for PID {pid}. Negative nice values usually require root/sudo.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to renice PID {pid}: {e}")
        self.refresh()

        self.refresh()
