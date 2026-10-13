import os
import subprocess
import webbrowser
import psutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMenu, QMessageBox,
    QApplication, QHeaderView, QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QAction
from app.widgets.search_bar import SearchBar
from app.workers.process_list_worker import ProcessListWorker


class NumericTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem supporting high-performance numeric sorting via UserRole."""
    def __lt__(self, other):
        val1 = self.data(Qt.ItemDataRole.UserRole)
        val2 = other.data(Qt.ItemDataRole.UserRole) if other else None
        if val1 is not None and val2 is not None:
            try:
                return float(val1) < float(val2)
            except (ValueError, TypeError):
                pass
        return super().__lt__(other)


# Pre-allocated brushes to eliminate repeated allocations in UI render loop (Cyber Palette)
_BRUSH_HIGH = QBrush(QColor(255, 42, 81, 40))       # Neon Crimson Red
_BRUSH_SUSPICIOUS = QBrush(QColor(255, 159, 26, 40)) # Cyber Amber
_BRUSH_SUSPENDED = QBrush(QColor(0, 168, 255, 40))   # Electric Cyber Blue
_BRUSH_DEFAULT = QBrush(QColor(0, 0, 0, 0))


class ProcessManagerPage(QWidget):
    """
    Advanced Process Manager with numeric sorting, real-time metrics,
    row highlighting, search filtering, and context menu process management.
    Features buttery-smooth in-place table updates with zero layout recalculation lag.
    """

    COLUMNS = [
        "Name", "PID", "CPU %", "RAM (MB)", "Disk Read (KB/s)",
        "Disk Write (KB/s)", "Status", "Publisher", "Path"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MainContent")
        self._all_processes = []
        self._search_filter = ""
        self._worker = None
        self._init_ui()
        self._start_worker()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Top Bar: Title & Search Filter
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Process Manager")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        sub = QLabel("Monitor running tasks, CPU/RAM usage, and disk activity in real-time.")
        sub.setObjectName("SubText")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        top_bar.addLayout(title_box)
        top_bar.addStretch()

        self.btn_kill = QPushButton("🛑 End Process")
        self.btn_kill.setObjectName("DestructiveButton")
        self.btn_kill.setToolTip("Terminate the selected process immediately")
        self.btn_kill.clicked.connect(self._on_toolbar_kill)
        top_bar.addWidget(self.btn_kill)

        self.btn_kill_tree = QPushButton("⚡ End Process Tree")
        self.btn_kill_tree.setObjectName("DestructiveButton")
        self.btn_kill_tree.setToolTip("Terminate the selected process and all child processes")
        self.btn_kill_tree.clicked.connect(self._on_toolbar_kill_tree)
        top_bar.addWidget(self.btn_kill_tree)

        self.search_bar = SearchBar("Search processes by name or PID...", self)
        self.search_bar.setFixedWidth(240)
        self.search_bar.search_changed.connect(self._on_search_filter)
        top_bar.addWidget(self.search_bar)
        layout.addLayout(top_bar)

        # Table Widget
        self.table = QTableWidget(0, len(self.COLUMNS), self)
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(len(self.COLUMNS) - 1, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table)

        # Summary Bar at bottom
        self.summary_bar = QLabel("Processes: -- | Threads: -- | CPU: --% | RAM: -- GB / -- GB")
        self.summary_bar.setStyleSheet("""
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 8px 14px;
            font-weight: 500;
            color: #8b949e;
        """)
        layout.addWidget(self.summary_bar)

    def _start_worker(self):
        self._worker = ProcessListWorker(self)
        self._worker.process_data_signal.connect(self._on_processes_updated)
        self._worker.start()

    def set_active(self, active: bool):
        """Throttle background worker when page is hidden."""
        if self._worker:
            self._worker.set_active(active)

    def showEvent(self, event):
        super().showEvent(event)
        self.set_active(True)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.set_active(False)

    def stop_worker(self):
        if self._worker:
            self._worker.stop()

    def _on_search_filter(self, text: str):
        self._search_filter = text.lower()
        self._populate_table()

    def _on_processes_updated(self, procs: list, summary: dict):
        self._all_processes = procs
        self._populate_table()

        # Update Summary Bar
        self.summary_bar.setText(
            f"Processes: {summary.get('process_count', 0)} | "
            f"Threads: {summary.get('thread_count', 0):,} | "
            f"CPU: {summary.get('cpu_percent', 0):.1f}% | "
            f"RAM: {summary.get('ram_used_gb', 0)} GB / {summary.get('ram_total_gb', 0)} GB"
        )

    def _populate_table(self):
        # 1. Remember selected PID and scroll position
        selected_pid = None
        selected_row = self.table.currentRow()
        if selected_row >= 0:
            name_item = self.table.item(selected_row, 0)
            if name_item:
                selected_pid = name_item.data(Qt.ItemDataRole.UserRole)

        v_scroll = self.table.verticalScrollBar().value()

        # 2. Filter processes
        filtered = []
        for p in self._all_processes:
            if not self._search_filter:
                filtered.append(p)
            else:
                if self._search_filter in p["name"].lower() or self._search_filter in str(p["pid"]):
                    filtered.append(p)

        # 3. Pre-sort in Python according to active header sort section
        sort_col = self.table.horizontalHeader().sortIndicatorSection()
        sort_order = self.table.horizontalHeader().sortIndicatorOrder()
        reverse = (sort_order == Qt.SortOrder.DescendingOrder)

        key_func = None
        if sort_col == 0:
            key_func = lambda x: x["name"].lower()
        elif sort_col == 1:
            key_func = lambda x: x["pid"]
        elif sort_col == 2:
            key_func = lambda x: x["cpu"]
        elif sort_col == 3:
            key_func = lambda x: x["ram_mb"]
        elif sort_col == 4:
            key_func = lambda x: x["read_kbs"]
        elif sort_col == 5:
            key_func = lambda x: x["write_kbs"]
        elif sort_col == 6:
            key_func = lambda x: x["status"]
        elif sort_col == 7:
            key_func = lambda x: x["publisher"].lower()
        elif sort_col == 8:
            key_func = lambda x: x["path"].lower()

        if key_func:
            filtered.sort(key=key_func, reverse=reverse)

        # 4. In-place update to prevent layout recalculation churn
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)

        current_rows = self.table.rowCount()
        target_rows = len(filtered)
        if current_rows < target_rows:
            self.table.setRowCount(target_rows)
            for r in range(current_rows, target_rows):
                for c in range(len(self.COLUMNS)):
                    if c in (1, 2, 3, 4, 5):
                        it = NumericTableWidgetItem()
                        it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    else:
                        it = QTableWidgetItem()
                    self.table.setItem(r, c, it)
        elif current_rows > target_rows:
            self.table.setRowCount(target_rows)

        found_select_row = -1

        for row, p in enumerate(filtered):
            # Column 0: Name
            item0 = self.table.item(row, 0)
            if item0.text() != p["name"]:
                item0.setText(p["name"])
            item0.setData(Qt.ItemDataRole.UserRole, p["pid"])

            # Column 1: PID
            item1 = self.table.item(row, 1)
            pid_str = str(p["pid"])
            if item1.text() != pid_str:
                item1.setText(pid_str)
            item1.setData(Qt.ItemDataRole.UserRole, p["pid"])

            # Column 2: CPU %
            item2 = self.table.item(row, 2)
            cpu_str = f"{p['cpu']:.1f}"
            if item2.text() != cpu_str:
                item2.setText(cpu_str)
            item2.setData(Qt.ItemDataRole.UserRole, p["cpu"])

            # Column 3: RAM (MB)
            item3 = self.table.item(row, 3)
            ram_str = f"{p['ram_mb']:.1f}"
            if item3.text() != ram_str:
                item3.setText(ram_str)
            item3.setData(Qt.ItemDataRole.UserRole, p["ram_mb"])

            # Column 4: Disk Read (KB/s)
            item4 = self.table.item(row, 4)
            read_str = f"{p['read_kbs']:.1f}"
            if item4.text() != read_str:
                item4.setText(read_str)
            item4.setData(Qt.ItemDataRole.UserRole, p["read_kbs"])

            # Column 5: Disk Write (KB/s)
            item5 = self.table.item(row, 5)
            write_str = f"{p['write_kbs']:.1f}"
            if item5.text() != write_str:
                item5.setText(write_str)
            item5.setData(Qt.ItemDataRole.UserRole, p["write_kbs"])

            # Column 6: Status
            item6 = self.table.item(row, 6)
            if item6.text() != p["status"]:
                item6.setText(p["status"])

            # Column 7: Publisher
            item7 = self.table.item(row, 7)
            if item7.text() != p["publisher"]:
                item7.setText(p["publisher"])

            # Column 8: Path
            item8 = self.table.item(row, 8)
            if item8.text() != p["path"]:
                item8.setText(p["path"])

            # Determine background brush
            if p["cpu"] > 20.0 or p["ram_mb"] > 1000.0:
                bg = _BRUSH_HIGH
            elif p.get("is_suspicious", False):
                bg = _BRUSH_SUSPICIOUS
            elif p["status"] == "Suspended":
                bg = _BRUSH_SUSPENDED
            else:
                bg = _BRUSH_DEFAULT

            for c in range(len(self.COLUMNS)):
                it = self.table.item(row, c)
                if it.background() != bg:
                    it.setBackground(bg)

            if selected_pid is not None and p["pid"] == selected_pid:
                found_select_row = row

        self.table.blockSignals(False)
        self.table.setUpdatesEnabled(True)
        self.table.setSortingEnabled(True)

        # Restore selection and scroll
        if found_select_row >= 0:
            self.table.selectRow(found_select_row)
        self.table.verticalScrollBar().setValue(v_scroll)

    def _show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return

        row = item.row()
        name_item = self.table.item(row, 0)
        pid_item = self.table.item(row, 1)
        path_item = self.table.item(row, 8)

        if not name_item or not pid_item:
            return

        proc_name = name_item.text()
        pid = int(pid_item.text())
        exe_path = path_item.text() if path_item else ""

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
        """)

        act_kill = QAction(f"🛑 End Process ({proc_name})", self)
        act_kill_tree = QAction("⚡ End Process Tree", self)
        act_suspend = QAction("⏸️ Suspend Process", self)
        act_resume = QAction("▶️ Resume Process", self)
        act_open_loc = QAction("📂 Open File Location", self)
        act_search = QAction("🌐 Search Online", self)
        act_copy_pid = QAction("📋 Copy PID", self)

        act_kill.triggered.connect(lambda: self._kill_process(pid, proc_name, tree=False))
        act_kill_tree.triggered.connect(lambda: self._kill_process(pid, proc_name, tree=True))
        act_suspend.triggered.connect(lambda: self._suspend_process(pid))
        act_resume.triggered.connect(lambda: self._resume_process(pid))
        act_open_loc.triggered.connect(lambda: self._open_file_location(exe_path))
        act_search.triggered.connect(lambda: webbrowser.open(f"https://www.google.com/search?q=what+is+{proc_name}+process"))
        act_copy_pid.triggered.connect(lambda: QApplication.clipboard().setText(str(pid)))

        menu.addAction(act_kill)
        menu.addAction(act_kill_tree)
        menu.addSeparator()
        menu.addAction(act_suspend)
        menu.addAction(act_resume)
        menu.addSeparator()
        if exe_path and os.path.exists(exe_path):
            menu.addAction(act_open_loc)
        menu.addAction(act_search)
        menu.addAction(act_copy_pid)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_toolbar_kill(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select Process", "Please select a process from the table first.")
            return
        name_item = self.table.item(row, 0)
        if not name_item:
            return
        pid = name_item.data(Qt.ItemDataRole.UserRole)
        proc_name = name_item.text()
        self._kill_process(pid, proc_name, tree=False)

    def _on_toolbar_kill_tree(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select Process", "Please select a process from the table first.")
            return
        name_item = self.table.item(row, 0)
        if not name_item:
            return
        pid = name_item.data(Qt.ItemDataRole.UserRole)
        proc_name = name_item.text()
        self._kill_process(pid, proc_name, tree=True)

    def _kill_process(self, pid: int, proc_name: str, tree: bool = False):
        action_name = "End Process Tree" if tree else "End Process"
        reply = QMessageBox.question(
            self,
            f"Confirm {action_name}",
            f"Terminate {proc_name} (PID {pid}){' and all child processes' if tree else ''} immediately?\nThis will release all CPU and RAM.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            killed = False
            try:
                p = psutil.Process(pid)
                if tree:
                    for child in p.children(recursive=True):
                        try:
                            child.kill()
                        except Exception:
                            pass
                p.kill()
                killed = True
            except Exception:
                pass

            if not killed:
                cmd = f"taskkill /F /PID {pid}" + (" /T" if tree else "")
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if res.returncode == 0:
                    killed = True

            if killed:
                QMessageBox.information(self, "Process Terminated", f"Successfully terminated {proc_name} (PID {pid}).")
            else:
                QMessageBox.warning(self, "Process Error", f"Unable to terminate PID {pid}. Administrator rights may be required.")

    def _suspend_process(self, pid: int):
        try:
            psutil.Process(pid).suspend()
        except Exception as e:
            QMessageBox.warning(self, "Suspend Failed", str(e))

    def _resume_process(self, pid: int):
        try:
            psutil.Process(pid).resume()
        except Exception as e:
            QMessageBox.warning(self, "Resume Failed", str(e))

    def _open_file_location(self, exe_path: str):
        if exe_path and os.path.exists(exe_path):
            clean = exe_path.replace("/", "\\")
            subprocess.Popen(f'explorer /select,"{clean}"')
