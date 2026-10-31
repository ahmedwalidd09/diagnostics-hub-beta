import time
import subprocess
from collections import deque
import psutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QMessageBox, QMenu, QTabWidget, QDialog, QTextEdit
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt
from app.widgets.gauge_widget import GaugeWidget
from app.widgets.sparkline_widget import SparklineWidget
from app.widgets.ram_bubble_canvas import RamBubbleCanvas
from app.widgets.severity_badge import SeverityBadge
from app.workers.ram_clean_worker import RamCleanWorker
from app.workers.ram_monitor_worker import RamMonitorWorker
from app.settings_manager import settings
from app.constants import COLOR_BG_CARD, COLOR_BORDER
from app.utils.idle_ram_triage import analyze_resting_memory, execute_resting_triage_fix
from app.utils.eco_qos import set_process_eco_qos, trim_process_working_set


class RestingTriageDialog(QDialog):
    """Dialog providing deep diagnostic insights on 90% idle RAM usage and 1-click remediation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resting Memory Triage Advisor")
        self.resize(560, 420)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f1117;
                color: #f1f5f9;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel("Idle & Resting Memory Diagnostic Report")
        header.setStyleSheet("font-size: 15px; font-weight: 600; color: #f1f5f9;")
        layout.addWidget(header)

        sub = QLabel("Analyzes why RAM usage remains high (~90%) even when the system is resting.")
        sub.setObjectName("SubText")
        layout.addWidget(sub)

        self.report_area = QTextEdit()
        self.report_area.setReadOnly(True)
        self.report_area.setStyleSheet("""
            QTextEdit {
                background-color: #161922;
                border: 1px solid #262a38;
                border-radius: 6px;
                color: #f1f5f9;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.report_area)

        # Buttons
        btn_box = QHBoxLayout()
        self.fix_btn = QPushButton("⚡ Execute Targeted Resting Fix")
        self.fix_btn.setObjectName("PrimaryButton")
        self.fix_btn.clicked.connect(self._on_execute_fix)
        btn_box.addWidget(self.fix_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)

        self._run_audit()

    def _run_audit(self):
        analysis = analyze_resting_memory()
        findings = analysis.get("findings", [])

        lines = [
            f"<b>Physical RAM Utilization:</b> {analysis.get('current_ram_percent')}% "
            f"({analysis.get('used_gb')} GB used of {analysis.get('total_gb')} GB)<br/>",
            f"<b>Kernel Non-Paged Pool:</b> {analysis.get('kernel_nonpaged_mb')} MB<br/>",
            f"<b>Kernel Paged Pool:</b> {analysis.get('kernel_paged_mb')} MB<br/>",
            f"<b>Standby System Cache:</b> {analysis.get('system_cache_mb')} MB<br/>",
            "<hr style='border: 1px solid #262a38;'/><br/>"
        ]

        if not findings:
            lines.append("<b>Status:</b> No severe driver memory leaks or orphan browser background tasks detected.<br/>")
        else:
            lines.append("<b>Identified Idle Memory Drivers:</b><br/>")
            for f in findings:
                sev = f.get('severity', 'info').upper()
                color = "#ef4444" if sev == "CRITICAL" else ("#f59e0b" if sev == "WARNING" else "#3b82f6")
                lines.append(f"• <span style='color:{color}; font-weight:600;'>[{sev}] {f.get('title')}</span><br/>")
                lines.append(f"  {f.get('description')}<br/><br/>")

        potential = analysis.get("potential_freed_mb", 0.0)
        if potential > 0:
            lines.append(f"<b>Estimated Reclaimable Idle RAM:</b> ~{potential:.0f} MB<br/>")

        self.report_area.setHtml("".join(lines))

    def _on_execute_fix(self):
        self.fix_btn.setEnabled(False)
        self.fix_btn.setText("Optimizing...")
        result = execute_resting_triage_fix()
        freed = result.get("freed_mb", 0.0)
        trimmed = result.get("trimmed_count", 0)
        new_pct = result.get("new_ram_percent", 0.0)

        QMessageBox.information(
            self,
            "Resting Optimization Complete",
            f"Released {freed:.0f} MB of idle RAM.\n"
            f"Trimmed and throttled {trimmed} background helper processes.\n"
            f"New RAM utilization: {new_pct}%."
        )
        self.accept()


class RamCleanerPage(QWidget):
    """
    RAM Cleaner & Memory Architecture Diagnostics workstation module.
    Features:
    - Interactive 2D Physics Bubble Canvas with Process Grouping
    - Kernel Pool Telemetry (Non-Paged Pool & Driver Leak Inspection)
    - Standby List and Modified Page Cache Flushers
    - Monotonic 5-Minute Memory Leak Detector
    - Idle Memory Triage Advisor
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MainContent")
        self._worker = None
        self._clean_worker = None
        self._latest_overview = {}
        self._latest_top15 = []
        self._latest_leaks = []
        self._latest_grouped = []

        self._init_ui()
        self._start_worker()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # -------------------------------------------------------------
        # TOP PANEL: RAM Metrics & Multi-Stage Flush Controls
        # -------------------------------------------------------------
        top_card = QFrame()
        top_card.setObjectName("CardFrame")
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(18, 14, 18, 14)
        top_layout.setSpacing(20)

        self.ram_gauge = GaugeWidget(title="RAM In Use", unit="%", min_value=0, max_value=100)
        self.ram_gauge.setFixedSize(130, 130)
        top_layout.addWidget(self.ram_gauge)

        # Middle column: Metrics & Kernel Pools
        v_info = QVBoxLayout()
        v_info.setSpacing(4)

        self.ram_stats_lbl = QLabel("Memory: Calculating...")
        self.ram_stats_lbl.setStyleSheet("font-size: 15px; font-weight: 600; color: #ffffff;")
        v_info.addWidget(self.ram_stats_lbl)

        self.swap_stats_lbl = QLabel("Commit Charge: Calculating...")
        self.swap_stats_lbl.setObjectName("SubText")
        v_info.addWidget(self.swap_stats_lbl)

        # Kernel Pool Telemetry
        self.kernel_pools_lbl = QLabel("Kernel Pools: Paged: -- | Non-Paged: --")
        self.kernel_pools_lbl.setObjectName("SubText")
        v_info.addWidget(self.kernel_pools_lbl)

        # Sparkline Timeline
        self.sparkline = SparklineWidget(max_points=60, line_color="#3b82f6")
        self.sparkline.setFixedHeight(34)
        v_info.addWidget(self.sparkline)
        top_layout.addLayout(v_info, stretch=1)

        # Right column: Clean Actions
        actions_box = QVBoxLayout()
        actions_box.setSpacing(6)

        btn_row = QHBoxLayout()
        self.clean_btn = QPushButton("🧹 Clean RAM")
        self.clean_btn.setObjectName("PrimaryButton")
        self.clean_btn.setFixedHeight(32)
        self.clean_btn.clicked.connect(lambda: self._start_clean(deep=False))
        btn_row.addWidget(self.clean_btn)

        self.deep_clean_btn = QPushButton("⚡ Deep Flush")
        self.deep_clean_btn.setObjectName("SecondaryButton")
        self.deep_clean_btn.setToolTip("Purges Standby Cache and Modified Page List (requires admin)")
        self.deep_clean_btn.setFixedHeight(32)
        self.deep_clean_btn.clicked.connect(lambda: self._start_clean(deep=True))
        btn_row.addWidget(self.deep_clean_btn)
        actions_box.addLayout(btn_row)

        self.triage_btn = QPushButton("🔍 Analyze Idle RAM (90% Idle Fix)")
        self.triage_btn.setFixedHeight(30)
        self.triage_btn.clicked.connect(self._open_resting_triage)
        actions_box.addWidget(self.triage_btn)

        self.last_clean_lbl = QLabel("Ready to optimize memory.")
        self.last_clean_lbl.setObjectName("SubText")
        actions_box.addWidget(self.last_clean_lbl)

        # Auto-clean threshold
        h_auto = QHBoxLayout()
        self.autoclean_cb = QCheckBox("Auto-clean if >")
        self.autoclean_cb.setChecked(settings.get("ram_autoclean_enabled", False))
        self.autoclean_cb.toggled.connect(self._on_autoclean_toggled)
        h_auto.addWidget(self.autoclean_cb)

        thresh_val = int(settings.get("ram_autoclean_threshold", 85))
        self.thresh_slider = QSlider(Qt.Orientation.Horizontal)
        self.thresh_slider.setRange(50, 95)
        self.thresh_slider.setValue(thresh_val)
        self.thresh_slider.valueChanged.connect(self._on_slider_changed)
        h_auto.addWidget(self.thresh_slider)

        self.thresh_lbl = QLabel(f"{thresh_val}%")
        self.thresh_lbl.setFixedWidth(30)
        h_auto.addWidget(self.thresh_lbl)
        actions_box.addLayout(h_auto)

        top_layout.addLayout(actions_box)
        layout.addWidget(top_card)

        # -------------------------------------------------------------
        # TABS: Interactive Bubble Map vs Process Tables
        # -------------------------------------------------------------
        self.tabs = QTabWidget(self)

        # TAB 1: Bubble Canvas (Visual RAM Distribution)
        tab_bubble = QWidget()
        tb_layout = QVBoxLayout(tab_bubble)
        tb_layout.setContentsMargins(8, 8, 8, 8)
        tb_layout.setSpacing(6)

        bubble_toolbar = QHBoxLayout()
        lbl_info = QLabel("Process Memory Distribution (Bubble area indicates physical RAM consumption)")
        lbl_info.setObjectName("SubText")
        bubble_toolbar.addWidget(lbl_info)
        bubble_toolbar.addStretch()

        self.group_cb = QCheckBox("Group by Application (Stack subprocesses)")
        self.group_cb.setChecked(True)
        self.group_cb.toggled.connect(self._on_group_toggled)
        bubble_toolbar.addWidget(self.group_cb)
        tb_layout.addLayout(bubble_toolbar)

        self.bubble_canvas = RamBubbleCanvas(self)
        self.bubble_canvas.process_action_triggered.connect(self._on_bubble_action)
        tb_layout.addWidget(self.bubble_canvas)

        self.tabs.addTab(tab_bubble, "🫧 Memory Distribution (Bubble View)")

        # TAB 2: Process Consumers & Leak Detector
        tab_tables = QWidget()
        tt_layout = QVBoxLayout(tab_tables)
        tt_layout.setContentsMargins(8, 8, 8, 8)
        tt_layout.setSpacing(8)

        # Top Consumers
        consumers_bar = QHBoxLayout()
        consumers_title = QLabel("Top Memory Consuming Processes")
        consumers_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #f1f5f9;")
        consumers_bar.addWidget(consumers_title)
        consumers_bar.addStretch()

        self.btn_eco_consumer = QPushButton("🍃 Efficiency Mode")
        self.btn_eco_consumer.clicked.connect(self._on_eco_selected_consumer)
        consumers_bar.addWidget(self.btn_eco_consumer)

        self.btn_kill_consumer = QPushButton("🛑 End Process")
        self.btn_kill_consumer.setObjectName("DestructiveButton")
        self.btn_kill_consumer.clicked.connect(self._on_kill_selected_consumer)
        consumers_bar.addWidget(self.btn_kill_consumer)
        tt_layout.addLayout(consumers_bar)

        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(["Application Name", "PID", "RAM Usage (MB)", "% of System RAM", "Trend"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_consumer_context_menu)
        self.table.setFixedHeight(180)
        tt_layout.addWidget(self.table)

        # Leak Detector
        leak_bar = QHBoxLayout()
        leak_title = QLabel("Suspected Memory Leaks (Monotonic growth >50% over 5 mins)")
        leak_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #f59e0b;")
        leak_bar.addWidget(leak_title)
        leak_bar.addStretch()

        self.btn_kill_leak = QPushButton("🛑 End Leaking Process")
        self.btn_kill_leak.setObjectName("DestructiveButton")
        self.btn_kill_leak.clicked.connect(self._on_kill_selected_leak)
        leak_bar.addWidget(self.btn_kill_leak)
        tt_layout.addLayout(leak_bar)

        self.leak_table = QTableWidget(0, 5, self)
        self.leak_table.setHorizontalHeaderLabels(["Process Name", "PID", "Current RAM (MB)", "RAM 5 Min Ago", "Growth Rate"])
        self.leak_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.leak_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.leak_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.leak_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.leak_table.customContextMenuRequested.connect(self._show_leak_context_menu)
        self.leak_table.setFixedHeight(120)
        tt_layout.addWidget(self.leak_table)

        self.tabs.addTab(tab_tables, "📋 Process Tables & Leaks")
        layout.addWidget(self.tabs)

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

    def _on_group_toggled(self, checked: bool):
        self.bubble_canvas.set_grouped_mode(checked)
        self.bubble_canvas.update_data(self._latest_top15, self._latest_grouped)

    def _on_bubble_action(self, action: str, pid: int):
        if action == "trim":
            self.last_clean_lbl.setText(f"Trimmed working set of PID {pid}.")
        elif action == "eco_on":
            self.last_clean_lbl.setText(f"Enabled Efficiency Mode on PID {pid}.")
        elif action == "eco_off":
            self.last_clean_lbl.setText(f"Disabled Efficiency Mode on PID {pid}.")
        elif action == "kill":
            self.last_clean_lbl.setText(f"Terminated PID {pid}.")

    def _open_resting_triage(self):
        dlg = RestingTriageDialog(self)
        dlg.exec()

    def _on_autoclean_toggled(self, checked: bool):
        settings.set("ram_autoclean_enabled", checked)

    def _on_slider_changed(self, val: int):
        self.thresh_lbl.setText(f"{val}%")
        settings.set("ram_autoclean_threshold", float(val))

    def _start_clean(self, deep: bool = False):
        self.clean_btn.setEnabled(False)
        self.deep_clean_btn.setEnabled(False)
        self.last_clean_lbl.setText("Flushing memory..." if deep else "Trimming working sets...")
        self._clean_worker = RamCleanWorker(deep_flush=deep, parent=self)
        self._clean_worker.cleaning_finished_signal.connect(self._on_clean_finished)
        self._clean_worker.start()

    def _on_clean_finished(self, result: dict):
        self.clean_btn.setEnabled(True)
        self.deep_clean_btn.setEnabled(True)
        freed_mb = result.get("freed_mb", 0.0)
        freed_gb = result.get("freed_gb", 0.0)
        trimmed = result.get("trimmed_processes", 0)
        standby = result.get("standby_purged", False)
        modified = result.get("modified_purged", False)

        msg = f"Released {freed_gb:.2f} GB ({freed_mb:.0f} MB) across {trimmed} processes."
        if standby:
            msg += " Standby cache purged."
        if modified:
            msg += " Modified pages flushed."
        self.last_clean_lbl.setText(msg)
        QMessageBox.information(self, "Memory Optimized", msg)

    def _on_ram_data(self, overview: dict, top_consumers: list, leaking_procs: list, grouped_consumers: list):
        self._latest_overview = overview
        self._latest_top15 = top_consumers
        self._latest_leaks = leaking_procs
        self._latest_grouped = grouped_consumers

        pct = overview.get("percent", 0.0)
        self.ram_gauge.set_value(pct)
        self.sparkline.add_point(pct)

        self.ram_stats_lbl.setText(
            f"{overview.get('used_gb', 0)} GB used / {overview.get('total_gb', 0)} GB total "
            f"({overview.get('available_gb', 0)} GB available)"
        )

        commit_total = overview.get("commit_total_gb", overview.get("swap_used_gb", 0))
        commit_limit = overview.get("commit_limit_gb", overview.get("swap_total_gb", 0))
        self.swap_stats_lbl.setText(
            f"Commit Charge: {commit_total} GB / {commit_limit} GB ({overview.get('commit_percent', overview.get('swap_percent', 0))}%)"
        )

        npp = overview.get("kernel_nonpaged_mb", 0.0)
        pp = overview.get("kernel_paged_mb", 0.0)
        sc = overview.get("system_cache_mb", 0.0)
        npp_warn = " ⚠️ High Non-Paged Pool" if overview.get("nonpaged_warning") else ""

        self.kernel_pools_lbl.setText(
            f"Kernel Pools: Paged: {pp:.0f} MB | Non-Paged: {npp:.0f} MB{npp_warn} | Standby Cache: {sc:.0f} MB"
        )

        # Update Bubble Canvas
        self.bubble_canvas.update_data(top_consumers, grouped_consumers)

        # Update Tables in-place
        self._update_consumers_table(top_consumers[:15])
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
        act_trim = QAction("🧹 Trim Working Set", self)
        act_eco = QAction("🍃 Enable Efficiency Mode (EcoQoS)", self)
        act_kill = QAction(f"🛑 End Process ({proc_name})", self)
        act_kill_tree = QAction("⚡ End Process Tree", self)

        act_trim.triggered.connect(lambda: trim_process_working_set(pid))
        act_eco.triggered.connect(lambda: set_process_eco_qos(pid, True))
        act_kill.triggered.connect(lambda: self._kill_process(pid, proc_name, tree=False))
        act_kill_tree.triggered.connect(lambda: self._kill_process(pid, proc_name, tree=True))

        menu.addAction(act_trim)
        menu.addAction(act_eco)
        menu.addSeparator()
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

    def _on_eco_selected_consumer(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select Process", "Please select a process from the table first.")
            return
        pid_item = self.table.item(row, 1)
        name_item = self.table.item(row, 0)
        if pid_item and name_item:
            try:
                pid = int(pid_item.text())
                if set_process_eco_qos(pid, True):
                    QMessageBox.information(self, "Efficiency Mode Enabled", f"Efficiency Mode (EcoQoS) enabled for {name_item.text()} (PID {pid}).")
                else:
                    QMessageBox.warning(self, "Action Failed", f"Unable to set Efficiency Mode on PID {pid}.")
            except ValueError:
                pass

    def _on_kill_selected_consumer(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select Process", "Please select a process from the table first.")
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
            QMessageBox.information(self, "Select Process", "Please select a process from the leak table first.")
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
