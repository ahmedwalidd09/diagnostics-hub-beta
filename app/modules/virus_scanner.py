import os
import psutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from app.widgets.severity_badge import SeverityBadge
from app.workers.virus_scan_worker import VirusScanWorker
from app.constants import COLOR_BG_CARD, COLOR_BORDER


class VirusScannerPage(QWidget):
    """
    Multi-layered supplementary malware and threat scanner.
    Heuristic process analysis, file hashing with VirusTotal, and network connection audits.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MainContent")
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Top Disclaimer Banner
        banner = QFrame()
        banner.setStyleSheet("""
            background-color: rgba(210, 153, 34, 0.12);
            border: 1px solid #bb8009;
            border-radius: 6px;
            padding: 8px 14px;
        """)
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(0, 0, 0, 0)
        banner_lbl = QLabel("⚠️ <b>Notice:</b> This scanner is a supplementary heuristic audit tool. For full real-time protection, always maintain an active antivirus such as Microsoft Defender.")
        banner_lbl.setStyleSheet("color: #e6edf3; font-size: 12px;")
        b_layout.addWidget(banner_lbl)
        layout.addWidget(banner)

        # Tabs for Scan Modes
        self.tabs = QTabWidget(self)

        # Tab 1: Quick Scan (Processes)
        self.quick_tab = QWidget()
        quick_layout = QVBoxLayout(self.quick_tab)
        quick_top = QHBoxLayout()
        quick_desc = QLabel("Scans all memory-resident processes for known signatures, temp directory execution, and system binary impersonation.")
        quick_desc.setObjectName("SubText")
        quick_top.addWidget(quick_desc)
        quick_top.addStretch()
        self.quick_scan_btn = QPushButton("🚀 Run Quick Process Scan")
        self.quick_scan_btn.setObjectName("PrimaryButton")
        self.quick_scan_btn.clicked.connect(lambda: self._start_scan("quick"))
        quick_top.addWidget(self.quick_scan_btn)
        quick_layout.addLayout(quick_top)

        # Tab 2: File / Folder Scan
        self.file_tab = QWidget()
        file_layout = QVBoxLayout(self.file_tab)
        file_top = QHBoxLayout()
        file_desc = QLabel("Computes SHA-256 hashes against local signature databases and queries VirusTotal v3 cloud.")
        file_desc.setObjectName("SubText")
        file_top.addWidget(file_desc)
        file_top.addStretch()

        self.scan_file_btn = QPushButton("📄 Scan Single File")
        self.scan_file_btn.clicked.connect(self._select_and_scan_file)
        file_top.addWidget(self.scan_file_btn)

        self.scan_folder_btn = QPushButton("📁 Scan Entire Folder")
        self.scan_folder_btn.clicked.connect(self._select_and_scan_folder)
        file_top.addWidget(self.scan_folder_btn)
        file_layout.addLayout(file_top)

        # Tab 3: Network Threats
        self.net_tab = QWidget()
        net_layout = QVBoxLayout(self.net_tab)
        net_top = QHBoxLayout()
        net_desc = QLabel("Audits active sockets for connections to known malicious IPs or unusual outbound command-and-control ports.")
        net_desc.setObjectName("SubText")
        net_top.addWidget(net_desc)
        net_top.addStretch()
        self.net_scan_btn = QPushButton("🌐 Check Active Network Sockets")
        self.net_scan_btn.setObjectName("PrimaryButton")
        self.net_scan_btn.clicked.connect(lambda: self._start_scan("network"))
        net_top.addWidget(self.net_scan_btn)
        net_layout.addLayout(net_top)

        self.tabs.addTab(self.quick_tab, "Quick Process Scan")
        self.tabs.addTab(self.file_tab, "File & Folder Scan")
        self.tabs.addTab(self.net_tab, "Network Threat Audit")
        layout.addWidget(self.tabs)

        # Progress Section
        self.progress_frame = QFrame()
        self.progress_frame.setObjectName("CardFrame")
        p_layout = QVBoxLayout(self.progress_frame)
        p_layout.setContentsMargins(12, 8, 12, 8)
        self.status_lbl = QLabel("Ready to scan.")
        self.status_lbl.setObjectName("SubText")
        p_layout.addWidget(self.status_lbl)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setRange(0, 100)
        p_layout.addWidget(self.progress_bar)
        self.progress_frame.hide()
        layout.addWidget(self.progress_frame)

        # Threat Results Table
        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels(["Name", "PID", "Path / Target", "Threat Classification", "Severity", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Bottom Summary Bar
        self.summary_bar = QLabel("Scanned: 0 | Threats found: 0 | Clean: 0")
        self.summary_bar.setStyleSheet("""
            background-color: #0d1017;
            border: 1px solid #1a2130;
            border-radius: 6px;
            padding: 8px 14px;
            font-weight: 600;
            color: #00d2ff;
        """)
        layout.addWidget(self.summary_bar)

    def _select_and_scan_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Executable or File to Scan", "", "All Files (*.*)")
        if file_path:
            self._start_scan("file", file_path)

    def _select_and_scan_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder to Scan")
        if folder_path:
            self._start_scan("file", folder_path)

    def _start_scan(self, scan_type: str, target: str = ""):
        self.quick_scan_btn.setEnabled(False)
        self.scan_file_btn.setEnabled(False)
        self.scan_folder_btn.setEnabled(False)
        self.net_scan_btn.setEnabled(False)

        self.table.setRowCount(0)
        self.progress_frame.show()
        self.progress_bar.setValue(0)
        self.status_lbl.setText("Initializing security scanner...")

        self._worker = VirusScanWorker(scan_type=scan_type, target_path=target, parent=self)
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.threat_found_signal.connect(self._on_threat_found)
        self._worker.scan_complete_signal.connect(self._on_scan_complete)
        self._worker.start()

    def _on_progress(self, percent: int, text: str):
        self.progress_bar.setValue(percent)
        self.status_lbl.setText(text)

    def _on_threat_found(self, threat: dict):
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(threat.get("name", "")))
        self.table.setItem(row, 1, QTableWidgetItem(str(threat.get("pid", ""))))
        self.table.setItem(row, 2, QTableWidgetItem(threat.get("path", "")))
        self.table.setItem(row, 3, QTableWidgetItem(threat.get("threat_type", "")))

        # Severity Badge
        badge = SeverityBadge(level=threat.get("severity", "medium"), text=threat.get("severity", "Medium"))
        self.table.setCellWidget(row, 4, badge)

        # Action Button
        act_btn = QPushButton("Remediate")
        act_btn.setObjectName("DestructiveButton")
        act_btn.clicked.connect(lambda _, t=threat, r=row: self._remediate_threat(t, r))
        self.table.setCellWidget(row, 5, act_btn)

    def _remediate_threat(self, threat: dict, row: int):
        pid = threat.get("pid")
        path = threat.get("path")
        name = threat.get("name")

        reply = QMessageBox.question(
            self,
            "Remediate Threat",
            f"Terminate and remediate {name}?\nTarget: {path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            success = False
            # If PID is active process
            if isinstance(pid, int) and pid > 0:
                try:
                    p = psutil.Process(pid)
                    p.kill()
                    success = True
                except Exception as e:
                    QMessageBox.warning(self, "Action Failed", f"Could not terminate process: {e}")

            # If it's a file
            if path and os.path.isfile(path):
                try:
                    os.remove(path)
                    success = True
                except Exception as e:
                    QMessageBox.warning(self, "Action Failed", f"Could not delete file: {e}")

            if success:
                QMessageBox.information(self, "Remediated", f"Successfully terminated/removed {name}.")
                self.table.removeRow(row)

    def _on_scan_complete(self, results: list, summary: dict):
        self.quick_scan_btn.setEnabled(True)
        self.scan_file_btn.setEnabled(True)
        self.scan_folder_btn.setEnabled(True)
        self.net_scan_btn.setEnabled(True)
        self.progress_frame.hide()

        scanned = summary.get("scanned_count", 0)
        threats = summary.get("threats_count", 0)
        clean = summary.get("clean_count", 0)

        self.summary_bar.setText(f"Scanned: {scanned:,} | Threats found: {threats} | Clean: {clean:,}")
        if threats == 0:
            QMessageBox.information(self, "Scan Clean", f"Completed scan across {scanned} items. No threats detected!")
