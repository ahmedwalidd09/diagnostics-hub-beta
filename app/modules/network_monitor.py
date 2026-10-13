from collections import deque
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QFrame, QDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush
from app.widgets.severity_badge import SeverityBadge
from app.workers.network_monitor_worker import NetworkMonitorWorker, parse_dns_cache, flush_dns_cache
from app.constants import COLOR_BG_CARD, COLOR_BORDER

# Configure pyqtgraph for cyber dark theme
pg.setConfigOption('background', '#0d1017')
pg.setConfigOption('foreground', '#828d9e')
pg.setConfigOption('antialias', True)

_BRUSH_ESTABLISHED = QBrush(QColor("#00d2ff"))
_BRUSH_LISTEN = QBrush(QColor("#ff9f1a"))
_BRUSH_OTHER = QBrush(QColor("#828d9e"))
_BRUSH_RED = QBrush(QColor("#ff2a51"))


class NetworkMonitorPage(QWidget):
    """
    Real-time Network Monitor featuring live pyqtgraph bandwidth chart,
    suspicious socket alerts, active sockets table, and DNS tools.
    Optimized with in-place row reuse to prevent UI stutter.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MainContent")
        self._down_history = deque([0.0] * 60, maxlen=60)
        self._up_history = deque([0.0] * 60, maxlen=60)
        self._worker = None
        self._init_ui()
        self._start_worker()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header bar
        header = QHBoxLayout()
        h_text = QVBoxLayout()
        title = QLabel("Network & Socket Monitor")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        sub = QLabel("Real-time bandwidth throughput, active network sockets, and suspicious telemetry.")
        sub.setObjectName("SubText")
        h_text.addWidget(title)
        h_text.addWidget(sub)
        header.addLayout(h_text)
        header.addStretch()

        # DNS Cache Button
        dns_btn = QPushButton("🔍 View DNS Cache")
        dns_btn.setObjectName("SecondaryButton")
        dns_btn.clicked.connect(self._show_dns_dialog)
        header.addWidget(dns_btn)
        layout.addLayout(header)

        # -------------------------------------------------------------
        # Live Bandwidth Chart Card
        # -------------------------------------------------------------
        chart_card = QFrame()
        chart_card.setObjectName("CardFrame")
        c_layout = QVBoxLayout(chart_card)
        c_layout.setContentsMargins(16, 12, 16, 12)
        c_layout.setSpacing(6)

        c_header = QHBoxLayout()
        c_title = QLabel("Throughput (Last 60 Seconds)")
        c_title.setObjectName("CardTitle")
        c_header.addWidget(c_title)
        c_header.addStretch()

        self.legend_down = QLabel("● Download: 0.0 KB/s")
        self.legend_down.setStyleSheet("color: #00d2ff; font-weight: 700; font-size: 12px;")
        self.legend_up = QLabel("● Upload: 0.0 KB/s")
        self.legend_up.setStyleSheet("color: #ff2a51; font-weight: 700; font-size: 12px;")
        c_header.addWidget(self.legend_down)
        c_header.addWidget(self.legend_up)
        c_layout.addLayout(c_header)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setFixedHeight(140)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self.plot_widget.setLabel('left', 'KB/s')
        self.plot_widget.getAxis('bottom').setStyle(showValues=False)

        self.down_curve = self.plot_widget.plot(pen=pg.mkPen(color='#00d2ff', width=2), name="Download")
        self.up_curve = self.plot_widget.plot(pen=pg.mkPen(color='#ff2a51', width=2), name="Upload")
        c_layout.addWidget(self.plot_widget)

        layout.addWidget(chart_card)

        # -------------------------------------------------------------
        # Splitter: Suspicious Connections & Active Connections
        # -------------------------------------------------------------
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background-color: #1a2130; height: 1px; }")

        # Top half of splitter: Suspicious Connections
        suspicious_box = QFrame()
        s_layout = QVBoxLayout(suspicious_box)
        s_layout.setContentsMargins(0, 0, 0, 0)
        s_layout.setSpacing(6)

        s_header = QHBoxLayout()
        s_title = QLabel("⚠️ Suspicious / Abnormal Connections")
        s_title.setStyleSheet("font-weight: bold; color: #d29922;")
        s_header.addWidget(s_title)
        s_header.addStretch()
        self.suspicious_count_lbl = QLabel("0 flagged")
        self.suspicious_count_lbl.setObjectName("SubText")
        s_header.addWidget(self.suspicious_count_lbl)
        s_layout.addLayout(s_header)

        self.suspicious_table = QTableWidget(0, 5)
        self.suspicious_table.setHorizontalHeaderLabels(["Process", "PID", "Remote Address", "Protocol", "Reason"])
        self.suspicious_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.suspicious_table.setFixedHeight(120)
        s_layout.addWidget(self.suspicious_table)
        splitter.addWidget(suspicious_box)

        # Bottom half: Two tables side by side (Per-Process Sockets + All Connections)
        bottom_box = QWidget()
        b_layout = QHBoxLayout(bottom_box)
        b_layout.setContentsMargins(0, 6, 0, 0)
        b_layout.setSpacing(12)

        # Per-Process Open Sockets Count Table
        proc_box = QVBoxLayout()
        proc_title = QLabel("Top Socket Holders")
        proc_title.setStyleSheet("font-weight: 600; color: #ffffff;")
        proc_box.addWidget(proc_title)
        self.proc_table = QTableWidget(0, 3)
        self.proc_table.setHorizontalHeaderLabels(["Process", "PID", "Sockets"])
        self.proc_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.proc_table.setFixedWidth(260)
        proc_box.addWidget(self.proc_table)
        b_layout.addLayout(proc_box)

        # All Active Connections Table
        conns_box = QVBoxLayout()
        conns_title = QLabel("Active Network Connections")
        conns_title.setStyleSheet("font-weight: 600; color: #ffffff;")
        conns_box.addWidget(conns_title)
        self.conns_table = QTableWidget(0, 6)
        self.conns_table.setHorizontalHeaderLabels(["Process", "PID", "Protocol", "Local Address", "Remote Address", "Status"])
        self.conns_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        conns_box.addWidget(self.conns_table)
        b_layout.addLayout(conns_box)

        splitter.addWidget(bottom_box)
        layout.addWidget(splitter)

    def _start_worker(self):
        self._worker = NetworkMonitorWorker(self)
        self._worker.bandwidth_signal.connect(self._on_bandwidth)
        self._worker.connections_data_signal.connect(self._on_connections)
        self._worker.start()

    def set_active(self, active: bool):
        """Coordinate socket auditing based on tab visibility."""
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

    def _on_bandwidth(self, down_kbs: float, up_kbs: float):
        self._down_history.append(down_kbs)
        self._up_history.append(up_kbs)

        x_vals = list(range(-len(self._down_history) + 1, 1))
        self.down_curve.setData(x_vals, list(self._down_history))
        self.up_curve.setData(x_vals, list(self._up_history))

        self.legend_down.setText(f"● Download: {down_kbs:.1f} KB/s")
        self.legend_up.setText(f"● Upload: {up_kbs:.1f} KB/s")

    def _on_connections(self, all_conns: list, suspicious: list, proc_summary: list):
        # 1. Update Suspicious Table in-place
        self.suspicious_count_lbl.setText(f"{len(suspicious)} flagged")
        self.suspicious_table.setUpdatesEnabled(False)
        curr_susp = self.suspicious_table.rowCount()
        targ_susp = len(suspicious)
        if curr_susp < targ_susp:
            self.suspicious_table.setRowCount(targ_susp)
            for r in range(curr_susp, targ_susp):
                for c in range(5):
                    self.suspicious_table.setItem(r, c, QTableWidgetItem())
        elif curr_susp > targ_susp:
            self.suspicious_table.setRowCount(targ_susp)

        for row, s in enumerate(suspicious):
            self._set_cell(self.suspicious_table, row, 0, s["process"])
            self._set_cell(self.suspicious_table, row, 1, str(s["pid"]))
            self._set_cell(self.suspicious_table, row, 2, s["remote_address"])
            self._set_cell(self.suspicious_table, row, 3, s["protocol"])
            r_item = self.suspicious_table.item(row, 4)
            if not r_item:
                r_item = QTableWidgetItem()
                self.suspicious_table.setItem(row, 4, r_item)
            if r_item.text() != s["reason"]:
                r_item.setText(s["reason"])
            r_item.setForeground(_BRUSH_RED)
        self.suspicious_table.setUpdatesEnabled(True)

        # 2. Update Per-Process Sockets Table in-place
        self.proc_table.setUpdatesEnabled(False)
        curr_proc = self.proc_table.rowCount()
        targ_proc = len(proc_summary)
        if curr_proc < targ_proc:
            self.proc_table.setRowCount(targ_proc)
            for r in range(curr_proc, targ_proc):
                for c in range(3):
                    it = QTableWidgetItem()
                    if c == 2:
                        it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.proc_table.setItem(r, c, it)
        elif curr_proc > targ_proc:
            self.proc_table.setRowCount(targ_proc)

        for row, p in enumerate(proc_summary):
            self._set_cell(self.proc_table, row, 0, p["name"])
            self._set_cell(self.proc_table, row, 1, str(p["pid"]))
            self._set_cell(self.proc_table, row, 2, str(p["connections"]))
        self.proc_table.setUpdatesEnabled(True)

        # 3. Update All Connections Table in-place
        self.conns_table.setUpdatesEnabled(False)
        curr_conns = self.conns_table.rowCount()
        targ_conns = len(all_conns)
        if curr_conns < targ_conns:
            self.conns_table.setRowCount(targ_conns)
            for r in range(curr_conns, targ_conns):
                for c in range(6):
                    self.conns_table.setItem(r, c, QTableWidgetItem())
        elif curr_conns > targ_conns:
            self.conns_table.setRowCount(targ_conns)

        for row, c in enumerate(all_conns):
            status = c["status"]
            self._set_cell(self.conns_table, row, 0, c["process"])
            self._set_cell(self.conns_table, row, 1, str(c["pid"]))
            self._set_cell(self.conns_table, row, 2, c["protocol"])
            self._set_cell(self.conns_table, row, 3, c["local_address"])
            self._set_cell(self.conns_table, row, 4, c["remote_address"])

            stat_item = self.conns_table.item(row, 5)
            if not stat_item:
                stat_item = QTableWidgetItem()
                self.conns_table.setItem(row, 5, stat_item)
            if stat_item.text() != status:
                stat_item.setText(status)

            if status == "ESTABLISHED":
                stat_item.setForeground(_BRUSH_ESTABLISHED)
            elif status == "LISTEN":
                stat_item.setForeground(_BRUSH_LISTEN)
            else:
                stat_item.setForeground(_BRUSH_OTHER)

        self.conns_table.setUpdatesEnabled(True)

    def _set_cell(self, table: QTableWidget, row: int, col: int, text: str):
        item = table.item(row, col)
        if not item:
            item = QTableWidgetItem(text)
            table.setItem(row, col, item)
        elif item.text() != text:
            item.setText(text)

    def _show_dns_dialog(self):
        dns_records = parse_dns_cache()
        dialog = QDialog(self)
        dialog.setWindowTitle("Windows DNS Resolver Cache")
        dialog.resize(650, 420)
        d_layout = QVBoxLayout(dialog)

        desc = QLabel(f"Cached DNS Records ({len(dns_records)} entries found):")
        desc.setObjectName("SubText")
        d_layout.addWidget(desc)

        table = QTableWidget(len(dns_records), 4)
        table.setHorizontalHeaderLabels(["Record Name", "Type", "TTL", "Address / Data"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        for row, r in enumerate(dns_records):
            table.setItem(row, 0, QTableWidgetItem(r.get("record_name", "")))
            table.setItem(row, 1, QTableWidgetItem(r.get("record_type", "")))
            table.setItem(row, 2, QTableWidgetItem(r.get("ttl", "")))
            table.setItem(row, 3, QTableWidgetItem(r.get("data", "")))

        d_layout.addWidget(table)

        btn_box = QHBoxLayout()
        flush_btn = QPushButton("🧹 Flush DNS Cache Now")
        flush_btn.clicked.connect(lambda: (self._flush_dns(), dialog.accept()))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_box.addWidget(flush_btn)
        btn_box.addStretch()
        btn_box.addWidget(close_btn)
        d_layout.addLayout(btn_box)

        dialog.exec()

    def _flush_dns(self):
        if flush_dns_cache():
            QMessageBox.information(self, "DNS Flushed", "Successfully flushed Windows DNS Resolver Cache.")
        else:
            QMessageBox.warning(self, "Flush Failed", "Could not flush DNS cache. Administrator privileges may be required.")
