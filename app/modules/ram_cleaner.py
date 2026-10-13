import time
import subprocess
from collections import deque
import psutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QMessageBox, QMenu
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt
from app.widgets.gauge_widget import GaugeWidget
from app.widgets.sparkline_widget import SparklineWidget
from app.workers.ram_clean_worker import RamCleanWorker
from app.workers.ram_monitor_worker import RamMonitorWorker
from app.settings_manager import settings
from app.constants import COLOR_BG_CARD, COLOR_BORDER


class RamCleanerPage(QWidget):
    """
    RAM Cleaner & Booster module with working-set trimming,
    standby purge, top consumer trends, and 5-minute memory leak detection.
    Processes are collected asynchronously by RamMonitorWorker to maintain 60 FPS GUI responsiveness.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MainContent")
        self._worker = None
        self._clean_worker = None

        self._init_ui()
        self._start_worker()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # -------------------------------------------------------------
        # TOP PANEL: RAM Overview & Clean Actions
        # -------------------------------------------------------------
        top_card = QFrame()
        top_card.setObjectName("CardFrame")
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(20, 16, 20, 16)
        top_layout.setSpacing(24)

        self.ram_gauge = GaugeWidget(title="RAM In Use", unit="%", min_value=0, max_value=100)
        self.ram_gauge.setFixedSize(140, 140)
        top_layout.addWidget(self.ram_gauge)

        v_info = QVBoxLayout()
        v_info.setSpacing(6)
        self.ram_stats_lbl = QLabel("Memory: Calculating...")
        self.ram_stats_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        v_info.addWidget(self.ram_stats_lbl)

        self.swap_stats_lbl = QLabel("Pagefile: Calculating...")
        self.swap_stats_lbl.setObjectName("SubText")
        v_info.addWidget(self.swap_stats_lbl)

        # 5-minute Sparkline
        spark_lbl = QLabel("5-Minute Memory Timeline:")
        spark_lbl.setObjectName("SubText")
        v_info.addWidget(spark_lbl)
        self.sparkline = SparklineWidget(max_points=60, line_color="#00a8ff")
        self.sparkline.setFixedHeight(40)
        v_info.addWidget(self.sparkline)
        top_layout.addLayout(v_info)

        # Clean Action & Auto-Clean settings
        actions_box = QVBoxLayout()
        actions_box.setSpacing(8)
        self.clean_btn = QPushButton("🧹 Clean & Optimize RAM")
        self.clean_btn.setObjectName("PrimaryButton")
        self.clean_btn.setFixedHeight(38)
        self.clean_btn.clicked.connect(self._start_clean)
        actions_box.addWidget(self.clean_btn)

        self.last_clean_lbl = QLabel("Ready to optimize memory.")
        self.last_clean_lbl.setObjectName("SubText")
        actions_box.addWidget(self.last_clean_lbl)

        # Auto clean checkbox & threshold
        self.autoclean_cb = QCheckBox("Auto-clean when RAM exceeds:")
        self.autoclean_cb.setChecked(settings.get("ram_autoclean_enabled", False))
        self.autoclean_cb.toggled.connect(self._on_autoclean_toggled)
        actions_box.addWidget(self.autoclean_cb)

        thresh_val = int(settings.get("ram_autoclean_threshold", 85))
        h_slider = QHBoxLayout()
        self.thresh_slider = QSlider(Qt.Orientation.Horizontal)
        self.thresh_slider.setRange(50, 95)
        self.thresh_slider.setValue(thresh_val)
        self.thresh_slider.valueChanged.connect(self._on_slider_changed)
        h_slider.addWidget(self.thresh_slider)

        self.thresh_lbl = QLabel(f"{thresh_val}%")
        self.thresh_lbl.setFixedWidth(35)
        h_slider.addWidget(self.thresh_lbl)
        actions_box.addLayout(h_slider)

        top_layout.addLayout(actions_box)
        layout.addWidget(top_card)

        # -------------------------------------------------------------
        # MIDDLE: Top Memory Consumers Table
        # -------------------------------------------------------------
        consumers_bar = QHBoxLayout()
        consumers_title = QLabel("Top 15 Memory Consuming Applications")
        consumers_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        consumers_bar.addWidget(consumers_title)
        consumers_bar.addStretch()

        self.btn_kill_consumer = QPushButton("🛑 End Selected Process")
        self.btn_kill_consumer.setObjectName("DestructiveButton")
        self.btn_kill_consumer.setToolTip("Terminate the selected process immediately")
        self.btn_kill_consumer.clicked.connect(self._on_kill_selected_consumer)
        consumers_bar.addWidget(self.btn_kill_consumer)
        layout.addLayout(consumers_bar)

        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(["Application Name", "PID", "RAM Usage (MB)", "% of Total System RAM", "Trend"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_consumer_context_menu)
        self.table.setFixedHeight(210)
        layout.addWidget(self.table)

        # -------------------------------------------------------------
        # BOTTOM: Memory Leak Detector Table
        # -------------------------------------------------------------
        leak_bar = QHBoxLayout()
        leak_title = QLabel("⚠️ Suspected Memory Leaks (Monotonic growth >50% over 5 mins)")
        leak_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #d29922;")
        leak_bar.addWidget(leak_title)
        leak_bar.addStretch()

        self.btn_kill_leak = QPushButton("🛑 End Leaking Process")
        self.btn_kill_leak.setObjectName("DestructiveButton")
        self.btn_kill_leak.setToolTip("Terminate the suspected memory leaking process")
        self.btn_kill_leak.clicked.connect(self._on_kill_selected_leak)
        leak_bar.addWidget(self.btn_kill_leak)
        layout.addLayout(leak_bar)

        self.leak_table = QTableWidget(0, 5, self)
        self.leak_table.setHorizontalHeaderLabels(["Process Name", "PID", "Current RAM (MB)", "RAM 5 Min Ago", "Growth Rate (MB/min)"])
        self.leak_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.leak_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.leak_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.leak_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.leak_table.customContextMenuRequested.connect(self._show_leak_context_menu)
        self.leak_table.setFixedHeight(120)
        layout.addWidget(self.leak_table)

    def _start_worker(self):
        self._worker = RamMonitorWorker(self)
        self._worker.ram_data_signal.connect(self._on_ram_data)
        self._worker.start()

    def stop_worker(self):
        if self._worker:
            self._worker.stop()

    def showEvent(self, event):
        super().showEvent(event)
        if self._worker:
            self._worker.set_active(True)

    def hideEvent(self, event):
        super().hideEvent(event)
        if self._worker:
            self._worker.set_active(False)

    def _on_autoclean_toggled(self, checked: bool):
        settings.set("ram_autoclean_enabled", checked)

    def _on_slider_changed(self, val: int):
        self.thresh_lbl.setText(f"{val}%")
        settings.set("ram_autoclean_threshold", float(val))

    def _start_clean(self):
        self.clean_btn.setEnabled(False)
        self.last_clean_lbl.setText("Trimming working sets and purging cache...")
        self._clean_worker = RamCleanWorker(self)
        self._clean_worker.cleaning_finished_signal.connect(self._on_clean_finished)
        self._clean_worker.start()

    def _on_clean_finished(self, result: dict):
        self.clean_btn.setEnabled(True)
        freed_mb = result.get("freed_mb", 0.0)
        freed_gb = result.get("freed_gb", 0.0)
        trimmed = result.get("trimmed_processes", 0)
        standby = result.get("standby_purged", False)

        msg = f"✅ Freed {freed_gb:.2f} GB ({freed_mb:.0f} MB) of RAM across {trimmed} processes."
        if standby:
            msg += " Standby list purged."
        self.last_clean_lbl.setText(msg)
        QMessageBox.information(self, "RAM Cleaned", msg)

    def _on_ram_data(self, overview: dict, top15: list, leaking_procs: list):
        """Update RAM widgets and tables in-place without GUI freezes."""
        pct = overview.get("percent", 0.0)
        self.ram_gauge.set_value(pct)
        self.sparkline.add_point(pct)
        self.ram_stats_lbl.setText(
            f"{overview.get('used_gb', 0)} GB used / {overview.get('total_gb', 0)} GB total "
            f"({overview.get('available_gb', 0)} GB available)"
        )
        self.swap_stats_lbl.setText(
            f"Swap / Pagefile: {overview.get('swap_used_gb', 0)} GB used ({overview.get('swap_percent', 0)}%)"
        )

        # 1. Update Top 15 consumers table in-place
        self._update_consumers_table(top15)

        # 2. Update Suspected Memory Leaks table in-place
        self._update_leaks_table(leaking_procs)

    def _update_consumers_table(self, top15: list):
        self.table.setUpdatesEnabled(False)
        current_rows = self.table.rowCount()
        target_rows = len(top15)

        if current_rows < target_rows:
            self.table.setRowCount(target_rows)
            for r in range(current_rows, target_rows):
                for c in range(5):
                    self.table.setItem(r, c, QTableWidgetItem())
        elif current_rows > target_rows:
            self.table.setRowCount(target_rows)

        for row, item in enumerate(top15):
            name_item = self.table.item(row, 0)
            if not name_item:
                name_item = QTableWidgetItem()
                self.table.setItem(row, 0, name_item)
            if name_item.text() != item["name"]:
                name_item.setText(item["name"])
            name_item.setData(Qt.ItemDataRole.UserRole, item["pid"])

            pid_item = self.table.item(row, 1)
            if not pid_item:
                pid_item = QTableWidgetItem()
                self.table.setItem(row, 1, pid_item)
            pid_str = str(item["pid"])
            if pid_item.text() != pid_str:
                pid_item.setText(pid_str)

            ram_item = self.table.item(row, 2)
            if not ram_item:
                ram_item = QTableWidgetItem()
                self.table.setItem(row, 2, ram_item)
            ram_str = f"{item['ram_mb']:.1f}"
            if ram_item.text() != ram_str:
                ram_item.setText(ram_str)

            pct_item = self.table.item(row, 3)
            if not pct_item:
                pct_item = QTableWidgetItem()
                self.table.setItem(row, 3, pct_item)
            pct_str = f"{item['pct']:.1f}%"
            if pct_item.text() != pct_str:
                pct_item.setText(pct_str)

            trend_item = self.table.item(row, 4)
            if not trend_item:
                trend_item = QTableWidgetItem()
                self.table.setItem(row, 4, trend_item)
            if trend_item.text() != item["trend"]:
                trend_item.setText(item["trend"])

        self.table.setUpdatesEnabled(True)

    def _update_leaks_table(self, leaking_procs: list):
        self.leak_table.setUpdatesEnabled(False)
        current_rows = self.leak_table.rowCount()
        target_rows = len(leaking_procs)

        if current_rows < target_rows:
            self.leak_table.setRowCount(target_rows)
            for r in range(current_rows, target_rows):
                for c in range(5):
                    self.leak_table.setItem(r, c, QTableWidgetItem())
        elif current_rows > target_rows:
            self.leak_table.setRowCount(target_rows)

        for r, lp in enumerate(leaking_procs):
            name_item = self.leak_table.item(r, 0)
            if not name_item:
                name_item = QTableWidgetItem()
                self.leak_table.setItem(r, 0, name_item)
            if name_item.text() != lp["name"]:
                name_item.setText(lp["name"])
            name_item.setData(Qt.ItemDataRole.UserRole, lp["pid"])

            pid_item = self.leak_table.item(r, 1)
            if not pid_item:
                pid_item = QTableWidgetItem()
                self.leak_table.setItem(r, 1, pid_item)
            pid_str = str(lp["pid"])
            if pid_item.text() != pid_str:
                pid_item.setText(pid_str)

            curr_item = self.leak_table.item(r, 2)
            if not curr_item:
                curr_item = QTableWidgetItem()
                self.leak_table.setItem(r, 2, curr_item)
            curr_str = f"{lp['current_mb']:.1f}"
            if curr_item.text() != curr_str:
                curr_item.setText(curr_str)

            past_item = self.leak_table.item(r, 3)
            if not past_item:
                past_item = QTableWidgetItem()
                self.leak_table.setItem(r, 3, past_item)
            past_str = f"{lp['old_mb']:.1f}"
            if past_item.text() != past_str:
                past_item.setText(past_str)

            rate_item = self.leak_table.item(r, 4)
            if not rate_item:
                rate_item = QTableWidgetItem()
                self.leak_table.setItem(r, 4, rate_item)
            rate_str = f"+{lp['growth_rate']:.1f} MB/min"
            if rate_item.text() != rate_str:
                rate_item.setText(rate_str)

        self.leak_table.setUpdatesEnabled(True)

    def _show_consumer_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        name_item = self.table.item(row, 0)
        pid_item = self.table.item(row, 1)
        if not name_item or not pid_item:
            return
        proc_name = name_item.text()
        try:
            pid = int(pid_item.text())
        except ValueError:
            return

        menu = QMenu(self)
        act_kill = QAction(f"🛑 End Process ({proc_name})", self)
        act_kill_tree = QAction("⚡ End Process Tree", self)
        act_kill.triggered.connect(lambda: self._kill_process(pid, proc_name, tree=False))
        act_kill_tree.triggered.connect(lambda: self._kill_process(pid, proc_name, tree=True))
        menu.addAction(act_kill)
        menu.addAction(act_kill_tree)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _show_leak_context_menu(self, pos):
        item = self.leak_table.itemAt(pos)
        if not item:
            return
        row = item.row()
        name_item = self.leak_table.item(row, 0)
        pid_item = self.leak_table.item(row, 1)
        if not name_item or not pid_item:
            return
        proc_name = name_item.text()
        try:
            pid = int(pid_item.text())
        except ValueError:
            return

        menu = QMenu(self)
        act_kill = QAction(f"🛑 End Leaking Process ({proc_name})", self)
        act_kill_tree = QAction("⚡ End Process Tree", self)
        act_kill.triggered.connect(lambda: self._kill_process(pid, proc_name, tree=False))
        act_kill_tree.triggered.connect(lambda: self._kill_process(pid, proc_name, tree=True))
        menu.addAction(act_kill)
        menu.addAction(act_kill_tree)
        menu.exec(self.leak_table.viewport().mapToGlobal(pos))

    def _on_kill_selected_consumer(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select Process", "Please click to select a process from the table first.")
            return
        name_item = self.table.item(row, 0)
        pid_item = self.table.item(row, 1)
        if not name_item or not pid_item:
            return
        proc_name = name_item.text()
        try:
            pid = int(pid_item.text())
            self._kill_process(pid, proc_name, tree=False)
        except ValueError:
            pass

    def _on_kill_selected_leak(self):
        row = self.leak_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select Process", "Please click to select a process from the leak table first.")
            return
        name_item = self.leak_table.item(row, 0)
        pid_item = self.leak_table.item(row, 1)
        if not name_item or not pid_item:
            return
        proc_name = name_item.text()
        try:
            pid = int(pid_item.text())
            self._kill_process(pid, proc_name, tree=False)
        except ValueError:
            pass

    def _kill_process(self, pid: int, proc_name: str, tree: bool = False):
        action_name = "End Process Tree" if tree else "End Process"
        reply = QMessageBox.question(
            self,
            f"Confirm {action_name}",
            f"Terminate {proc_name} (PID {pid}) immediately?\nThis will release its memory.",
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
                QMessageBox.warning(self, "Termination Failed", f"Unable to terminate PID {pid}. Administrator rights may be required.")
