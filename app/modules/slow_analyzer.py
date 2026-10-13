import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QScrollArea, QFrame, QFileDialog, QMessageBox, QDialog, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
from app.widgets.gauge_widget import GaugeWidget
from app.widgets.severity_badge import SeverityBadge
from app.workers.slow_scan_worker import SlowScanWorker
from app.utils.report_generator import generate_html_report, generate_pdf_report
from app.database import db
from app.constants import (
    COLOR_BG_CARD,
    COLOR_BORDER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY
)


class SlowAnalyzerPage(QWidget):
    """
    'Why Is My PC Slow?' Diagnostic Analyzer module.
    Evaluates 8 system categories, computes health score, and provides actionable remedies.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MainContent")
        self._worker = None
        self._last_scan_data = None
        self._category_frames = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header bar
        header_box = QHBoxLayout()
        header_text = QVBoxLayout()
        title = QLabel("Why Is My PC Slow? — Deep Diagnostic Analyzer")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        subtitle = QLabel("Evaluates 8 performance pillars: CPU, RAM, Disk, Startup, Services, Thermals, Impostors & Junk.")
        subtitle.setObjectName("SubText")
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header_box.addLayout(header_text)
        header_box.addStretch()

        self.history_btn = QPushButton("📜 Scan History")
        self.history_btn.clicked.connect(self._show_history_dialog)
        header_box.addWidget(self.history_btn)

        self.export_btn = QPushButton("💾 Export Report")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_report)
        header_box.addWidget(self.export_btn)

        self.scan_btn = QPushButton("🔍 Run Diagnostic Scan")
        self.scan_btn.setObjectName("PrimaryButton")
        self.scan_btn.setFixedHeight(36)
        self.scan_btn.clicked.connect(self._start_scan)
        header_box.addWidget(self.scan_btn)

        layout.addLayout(header_box)

        # Progress Section
        self.progress_frame = QFrame()
        self.progress_frame.setObjectName("CardFrame")
        prog_layout = QVBoxLayout(self.progress_frame)
        prog_layout.setContentsMargins(14, 10, 14, 10)
        self.status_lbl = QLabel("Ready to diagnose. Click 'Run Diagnostic Scan' to begin.")
        self.status_lbl.setObjectName("SubText")
        prog_layout.addWidget(self.status_lbl)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        prog_layout.addWidget(self.progress_bar)
        self.progress_frame.hide()
        layout.addWidget(self.progress_frame)

        # Main Scrollable Results Area
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")

        self.results_container = QWidget()
        self.results_container.setStyleSheet("background: transparent;")
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setSpacing(14)
        self.results_layout.setContentsMargins(0, 0, 0, 0)

        # Overall Score Banner
        self.score_card = QFrame()
        self.score_card.setObjectName("CardFrame")
        score_layout = QHBoxLayout(self.score_card)
        score_layout.setContentsMargins(20, 16, 20, 16)
        score_layout.setSpacing(20)

        self.score_gauge = GaugeWidget(title="Health Score", unit="", min_value=0, max_value=100, invert_colors=True)
        self.score_gauge.setFixedSize(140, 140)
        score_layout.addWidget(self.score_gauge)

        score_info = QVBoxLayout()
        score_info.setSpacing(6)
        self.overall_status_lbl = QLabel("No Scan Performed Yet")
        self.overall_status_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #ffffff;")
        score_info.addWidget(self.overall_status_lbl)

        self.score_badge = SeverityBadge(level="info", text="Awaiting Scan")
        score_info.addWidget(self.score_badge, alignment=Qt.AlignmentFlag.AlignLeft)

        self.overall_desc_lbl = QLabel("Click the 'Run Diagnostic Scan' button above to comprehensively analyze system bottlenecks.")
        self.overall_desc_lbl.setWordWrap(True)
        self.overall_desc_lbl.setObjectName("SubText")
        score_info.addWidget(self.overall_desc_lbl)
        score_layout.addLayout(score_info)
        score_layout.addStretch()

        self.results_layout.addWidget(self.score_card)

        # Categories list container
        self.cat_list_layout = QVBoxLayout()
        self.cat_list_layout.setSpacing(10)
        self.results_layout.addLayout(self.cat_list_layout)

        # Recommendations Box
        self.recs_card = QFrame()
        self.recs_card.setObjectName("CardFrame")
        recs_layout = QVBoxLayout(self.recs_card)
        recs_layout.setContentsMargins(18, 14, 18, 14)
        recs_title = QLabel("💡 Actionable Recommendations")
        recs_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        recs_layout.addWidget(recs_title)
        self.recs_content_lbl = QLabel("Scan recommendations will appear here after diagnostic completion.")
        self.recs_content_lbl.setWordWrap(True)
        self.recs_content_lbl.setStyleSheet("color: #c9d1d9; line-height: 1.4;")
        recs_layout.addWidget(self.recs_content_lbl)
        self.recs_card.hide()
        self.results_layout.addWidget(self.recs_card)

        self.results_layout.addStretch()
        self.scroll_area.setWidget(self.results_container)
        layout.addWidget(self.scroll_area)

    def _start_scan(self):
        self.scan_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.progress_frame.show()
        self.progress_bar.setValue(0)
        self.status_lbl.setText("Starting comprehensive diagnostic scan...")

        # Clear previous category cards
        for f in self._category_frames.values():
            f.deleteLater()
        self._category_frames.clear()
        self.recs_card.hide()

        self._worker = SlowScanWorker(self)
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.category_done_signal.connect(self._on_category_done)
        self._worker.scan_complete_signal.connect(self._on_scan_complete)
        self._worker.start()

    def _on_progress(self, percent: int, text: str):
        self.progress_bar.setValue(percent)
        self.status_lbl.setText(text)

    def _on_category_done(self, cat_name: str, cat_data: dict):
        score = cat_data.get("score", 0)
        status = cat_data.get("status", "Good")
        findings = cat_data.get("findings", "")

        level = "healthy" if score >= 80 else ("warning" if score >= 50 else "critical")

        frame = QFrame()
        frame.setObjectName("CardFrame")
        f_layout = QVBoxLayout(frame)
        f_layout.setContentsMargins(16, 12, 16, 12)
        f_layout.setSpacing(6)

        top_h = QHBoxLayout()
        name_lbl = QLabel(cat_name)
        name_lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #ffffff;")
        top_h.addWidget(name_lbl)
        top_h.addStretch()

        badge = SeverityBadge(level=level, text=f"{score}/100 — {status}")
        top_h.addWidget(badge)
        f_layout.addLayout(top_h)

        findings_lbl = QLabel(findings)
        findings_lbl.setWordWrap(True)
        findings_lbl.setStyleSheet("color: #c9d1d9; font-size: 13px;")
        f_layout.addWidget(findings_lbl)

        self.cat_list_layout.addWidget(frame)
        self._category_frames[cat_name] = frame

    def _on_scan_complete(self, data: dict):
        self.scan_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.progress_frame.hide()
        self._last_scan_data = data

        score = data.get("score", 0)
        status = data.get("status", "Healthy")
        self.score_gauge.set_value(score)
        self.overall_status_lbl.setText(status)

        level = "healthy" if score >= 85 else ("warning" if score >= 60 else "critical")
        self.score_badge.set_severity(level, f"{score}/100 — {status}")
        self.overall_desc_lbl.setText(f"Diagnostic completed on {data.get('timestamp')}. Review the category breakdown below for remediation steps.")

        recs = data.get("recommendations", [])
        if recs:
            rec_text = "<br>".join([f"• <b>{r}</b>" for r in recs])
            self.recs_content_lbl.setText(rec_text)
            self.recs_card.show()
        else:
            self.recs_content_lbl.setText("✅ No critical issues detected! Your computer is running at peak performance.")
            self.recs_card.show()

    def _export_report(self):
        if not self._last_scan_data:
            return

        docs_dir = str(Path.home() / "Documents")
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Diagnostic Report",
            os.path.join(docs_dir, f"PC_Diagnostics_Report_{int(self._last_scan_data.get('score', 0))}.html"),
            "HTML Report (*.html);;PDF Document (*.pdf)"
        )
        if not file_path:
            return

        try:
            if file_path.lower().endswith(".pdf"):
                saved = generate_pdf_report(self._last_scan_data, file_path)
            else:
                saved = generate_html_report(self._last_scan_data, file_path)
            QMessageBox.information(self, "Report Exported", f"Diagnostic report saved successfully to:\n{saved}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to save report: {e}")

    def _show_history_dialog(self):
        history = db.get_scan_history(30)
        dialog = QDialog(self)
        dialog.setWindowTitle("Past Diagnostic Scans")
        dialog.resize(650, 400)
        d_layout = QVBoxLayout(dialog)

        table = QTableWidget(len(history), 4)
        table.setHorizontalHeaderLabels(["ID", "Timestamp", "Score", "Overall Status"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        for row, entry in enumerate(history):
            table.setItem(row, 0, QTableWidgetItem(str(entry["id"])))
            table.setItem(row, 1, QTableWidgetItem(str(entry["timestamp"])))
            table.setItem(row, 2, QTableWidgetItem(f"{entry['score']}/100"))
            table.setItem(row, 3, QTableWidgetItem(str(entry["status"])))

        d_layout.addWidget(table)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        d_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()
