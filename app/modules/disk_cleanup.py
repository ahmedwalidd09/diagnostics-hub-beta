from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QCheckBox, QMessageBox, QProgressBar,
    QFrame
)
from PyQt6.QtCore import Qt
from app.workers.disk_scan_worker import DiskScanWorker
from app.workers.disk_clean_worker import DiskCleanWorker
from app.utils.system_info import is_admin
from app.constants import COLOR_BG_CARD, COLOR_BORDER


def format_size(bytes_val: int) -> str:
    """Format bytes into human-readable string (KB, MB, GB)."""
    if bytes_val >= 1024 ** 3:
        return f"{bytes_val / (1024 ** 3):.2f} GB"
    elif bytes_val >= 1024 ** 2:
        return f"{bytes_val / (1024 ** 2):.1f} MB"
    elif bytes_val >= 1024:
        return f"{bytes_val / 1024:.0f} KB"
    return f"{bytes_val} B"


class DiskCleanupPage(QWidget):
    """
    Disk Cleanup & Junk Scanner module.
    Scans temp, browser, update, logs, dumps, and safely purges selected files.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MainContent")
        self._categories = []
        self._checkbox_map = {}  # category_id -> QCheckBox
        self._scan_worker = None
        self._clean_worker = None
        self._has_scanned = False
        self._init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._has_scanned:
            self._has_scanned = True
            self._start_scan()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Area
        header = QHBoxLayout()
        h_text = QVBoxLayout()
        title = QLabel("Disk Cleanup & Junk Scanner")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        sub = QLabel("Reclaim disk space by clearing temporary caches, stale browser data, and old setup files safely.")
        sub.setObjectName("SubText")
        h_text.addWidget(title)
        h_text.addWidget(sub)
        header.addLayout(h_text)
        header.addStretch()

        self.rescan_btn = QPushButton("🔄 Re-Scan")
        self.rescan_btn.clicked.connect(self._start_scan)
        header.addWidget(self.rescan_btn)

        self.clean_btn = QPushButton("🗑️ Clean Selected")
        self.clean_btn.setObjectName("PrimaryButton")
        self.clean_btn.clicked.connect(self._confirm_and_clean)
        header.addWidget(self.clean_btn)

        layout.addLayout(header)

        # Overview Stats Card
        self.stats_card = QFrame()
        self.stats_card.setObjectName("CardFrame")
        s_layout = QHBoxLayout(self.stats_card)
        s_layout.setContentsMargins(16, 12, 16, 12)

        self.reclaimable_lbl = QLabel("Total Reclaimable Space: Calculating...")
        self.reclaimable_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #00d2ff;")
        s_layout.addWidget(self.reclaimable_lbl)
        s_layout.addStretch()

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(lambda: self._set_all_checkboxes(True))
        s_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(lambda: self._set_all_checkboxes(False))
        s_layout.addWidget(self.deselect_all_btn)

        layout.addWidget(self.stats_card)

        # Progress Section
        self.progress_frame = QFrame()
        self.progress_frame.setObjectName("CardFrame")
        p_layout = QVBoxLayout(self.progress_frame)
        p_layout.setContentsMargins(12, 8, 12, 8)
        self.status_lbl = QLabel("Scanning disk categories...")
        self.status_lbl.setObjectName("SubText")
        p_layout.addWidget(self.status_lbl)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        p_layout.addWidget(self.progress_bar)
        self.progress_frame.hide()
        layout.addWidget(self.progress_frame)

        # Category Table
        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(["Select", "Category", "Files", "Size", "Description"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

    def _start_scan(self):
        self.rescan_btn.setEnabled(False)
        self.clean_btn.setEnabled(False)
        self.progress_frame.show()
        self.progress_bar.setValue(0)
        self.table.setRowCount(0)
        self._categories.clear()
        self._checkbox_map.clear()

        self._scan_worker = DiskScanWorker(self)
        self._scan_worker.progress_signal.connect(self._on_progress)
        self._scan_worker.scan_complete_signal.connect(self._on_scan_complete)
        self._scan_worker.start()

    def _on_progress(self, percent: int, text: str):
        self.progress_bar.setValue(percent)
        self.status_lbl.setText(text)

    def _on_scan_complete(self, categories: list, summary: dict):
        self.rescan_btn.setEnabled(True)
        self.clean_btn.setEnabled(True)
        self.progress_frame.hide()
        self._categories = categories

        has_admin = is_admin()
        self.table.setRowCount(len(categories))

        for row, cat in enumerate(categories):
            cat_id = cat.get("id")
            req_admin = cat.get("requires_admin", False)

            # Checkbox
            cb = QCheckBox()
            # Default check temp, browser, thumbnail, logs
            cb.setChecked(cat_id in ["temp_files", "browser_cache", "thumbnail_cache", "windows_logs"])
            if req_admin and not has_admin:
                cb.setEnabled(False)
                cb.setChecked(False)
            cb.toggled.connect(self._update_total_selected)
            self._checkbox_map[cat_id] = cb
            self.table.setCellWidget(row, 0, cb)

            # Category Name + Admin lock indicator
            name_text = f"{cat.get('icon', '📁')}  {cat.get('name', '')}"
            if req_admin and not has_admin:
                name_text += " 🔒 (Requires Admin)"
            self.table.setItem(row, 1, QTableWidgetItem(name_text))

            # File count
            count_item = QTableWidgetItem(f"{cat.get('count', 0):,}")
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 2, count_item)

            # Size
            size_item = QTableWidgetItem(format_size(cat.get("bytes", 0)))
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 3, size_item)

            # Description
            self.table.setItem(row, 4, QTableWidgetItem(cat.get("description", "")))

        self._update_total_selected()

    def _set_all_checkboxes(self, checked: bool):
        for cat in self._categories:
            cat_id = cat.get("id")
            cb = self._checkbox_map.get(cat_id)
            if cb and cb.isEnabled():
                cb.setChecked(checked)
        self._update_total_selected()

    def _update_total_selected(self):
        selected_bytes = 0
        selected_files = 0
        for cat in self._categories:
            cb = self._checkbox_map.get(cat.get("id"))
            if cb and cb.isChecked():
                selected_bytes += cat.get("bytes", 0)
                selected_files += cat.get("count", 0)

        self.reclaimable_lbl.setText(
            f"Selected Reclaimable Space: {format_size(selected_bytes)} across {selected_files:,} files"
        )

    def _confirm_and_clean(self):
        selected_cats = [c for c in self._categories if self._checkbox_map.get(c.get("id")) and self._checkbox_map[c.get("id")].isChecked()]
        if not selected_cats:
            QMessageBox.information(self, "No Selection", "Please check at least one category to clean.")
            return

        total_bytes = sum(c.get("bytes", 0) for c in selected_cats)
        reply = QMessageBox.question(
            self,
            "Confirm Disk Cleanup",
            f"Are you sure you want to clean {len(selected_cats)} categories ({format_size(total_bytes)})?\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.rescan_btn.setEnabled(False)
            self.clean_btn.setEnabled(False)
            self.progress_frame.show()
            self.progress_bar.setValue(0)
            self.status_lbl.setText("Cleaning selected junk files...")

            self._clean_worker = DiskCleanWorker(selected_cats, self)
            self._clean_worker.progress_signal.connect(self._on_progress)
            self._clean_worker.clean_complete_signal.connect(self._on_clean_complete)
            self._clean_worker.start()

    def _on_clean_complete(self, summary: dict):
        self.rescan_btn.setEnabled(True)
        self.clean_btn.setEnabled(True)
        self.progress_frame.hide()

        cleaned_gb = summary.get("cleaned_gb", 0)
        cats = summary.get("categories_cleaned", 0)
        skipped = summary.get("skipped_count", 0)

        QMessageBox.information(
            self,
            "Cleanup Complete",
            f"✅ Cleaned {cleaned_gb:.2f} GB across {cats} categories.\n"
            f"({skipped} locked/in-use files were safely skipped)."
        )
        self._start_scan()
