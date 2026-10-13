from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QCheckBox, QMessageBox, QDialog,
    QProgressBar, QFrame
)
from PyQt6.QtCore import Qt
from app.widgets.severity_badge import SeverityBadge
from app.workers.startup_scan_worker import StartupScanWorker
from app.utils.registry_utils import (
    toggle_registry_entry,
    toggle_startup_folder_entry,
    toggle_task_scheduler_entry
)
from app.database import db
from app.constants import COLOR_BG_CARD, COLOR_BORDER


class StartupManagerPage(QWidget):
    """
    Windows Startup Applications & Scheduled Tasks Manager.
    Toggles startup programs across registry, folders, and scheduler, with undo history.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MainContent")
        self._entries = []
        self._worker = None
        self._has_scanned = False
        self._init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._has_scanned:
            self._has_scanned = True
            self._refresh_startup()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header bar
        header_box = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Startup Program Manager")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        sub = QLabel("Control software that runs automatically during Windows boot to accelerate login time.")
        sub.setObjectName("SubText")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        header_box.addLayout(title_box)
        header_box.addStretch()

        self.undo_btn = QPushButton("↩️ Undo Last Change")
        self.undo_btn.clicked.connect(self._undo_last_change)
        header_box.addWidget(self.undo_btn)

        self.history_btn = QPushButton("📜 Change History")
        self.history_btn.clicked.connect(self._show_change_history)
        header_box.addWidget(self.history_btn)

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self._refresh_startup)
        header_box.addWidget(self.refresh_btn)

        self.optimize_btn = QPushButton("⚡ Optimize Startup")
        self.optimize_btn.setObjectName("PrimaryButton")
        self.optimize_btn.clicked.connect(self._optimize_startup)
        header_box.addWidget(self.optimize_btn)

        layout.addLayout(header_box)

        # Progress / Status
        self.progress_frame = QFrame()
        self.progress_frame.setObjectName("CardFrame")
        p_layout = QVBoxLayout(self.progress_frame)
        p_layout.setContentsMargins(12, 8, 12, 8)
        self.status_lbl = QLabel("Scanning startup items...")
        self.status_lbl.setObjectName("SubText")
        p_layout.addWidget(self.status_lbl)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        p_layout.addWidget(self.progress_bar)
        self.progress_frame.hide()
        layout.addWidget(self.progress_frame)

        # Startup Table
        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels(["Status", "Name", "Source", "Recommendation", "Impact", "Path / Command"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Bottom info bar
        self.info_bar = QLabel("Loading startup items...")
        self.info_bar.setStyleSheet("""
            background-color: #0d1017;
            border: 1px solid #1a2130;
            border-radius: 6px;
            padding: 8px 14px;
            font-weight: 600;
            color: #00d2ff;
        """)
        layout.addWidget(self.info_bar)

    def _refresh_startup(self):
        self.refresh_btn.setEnabled(False)
        self.optimize_btn.setEnabled(False)
        self.progress_frame.show()
        self.progress_bar.setValue(0)
        self.table.setRowCount(0)

        self._worker = StartupScanWorker(self)
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.scan_complete_signal.connect(self._on_scan_complete)
        self._worker.start()

    def _on_progress(self, percent: int, text: str):
        self.progress_bar.setValue(percent)
        self.status_lbl.setText(text)

    def _on_scan_complete(self, entries: list):
        self.refresh_btn.setEnabled(True)
        self.optimize_btn.setEnabled(True)
        self.progress_frame.hide()
        self._entries = entries
        self._populate_table()

    def _populate_table(self):
        self.table.setRowCount(len(self._entries))

        enabled_count = 0
        disable_recs_count = 0

        for row, entry in enumerate(self._entries):
            is_service = (entry.get("source") == "Windows Service")
            is_enabled = entry.get("enabled", True)
            if is_enabled:
                enabled_count += 1
            if not entry.get("essential", False) and not is_service and is_enabled:
                disable_recs_count += 1

            # Checkbox Toggle
            cb = QCheckBox("Enabled" if is_enabled else "Disabled")
            cb.setChecked(is_enabled)
            if is_service:
                cb.setEnabled(False)
                cb.setText("Auto (Service)")
            else:
                cb.toggled.connect(lambda chk, e=entry, c=cb: self._on_toggle_entry(e, chk, c))
            self.table.setCellWidget(row, 0, cb)

            self.table.setItem(row, 1, QTableWidgetItem(entry.get("name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(entry.get("source", "")))

            # Recommendation Badge
            lvl = entry.get("badge_level", "warning")
            txt = entry.get("badge_text", "Optional")
            badge = SeverityBadge(level=lvl, text=txt)
            self.table.setCellWidget(row, 3, badge)

            # Impact
            impact_lbl = QTableWidgetItem(entry.get("impact", "Medium"))
            self.table.setItem(row, 4, impact_lbl)

            # Path
            self.table.setItem(row, 5, QTableWidgetItem(entry.get("path", "")))

        self.info_bar.setText(f"Active Startup Items: {enabled_count} | Recommended to Disable: {disable_recs_count} non-essential apps")

    def _on_toggle_entry(self, entry: dict, enable: bool, checkbox: QCheckBox):
        src = entry.get("source")
        name = entry.get("name")
        prev_state = "Enabled" if not enable else "Disabled"
        new_state = "Enabled" if enable else "Disabled"

        success = False
        if src == "Registry":
            success = toggle_registry_entry(entry, enable)
        elif src == "Startup Folder":
            success = toggle_startup_folder_entry(entry, enable)
        elif src == "Scheduled Task":
            success = toggle_task_scheduler_entry(entry.get("raw_name", name), enable)

        if success:
            entry["enabled"] = enable
            checkbox.setText(new_state)
            # Log to DB for undo
            db.log_startup_change(name=name, source=src, previous_state=prev_state, new_state=new_state)
        else:
            # Revert checkbox without triggering event loop recursion
            checkbox.blockSignals(True)
            checkbox.setChecked(not enable)
            checkbox.blockSignals(False)
            QMessageBox.warning(self, "Permission Denied", f"Could not toggle {name}. Administrator privileges may be required.")

    def _optimize_startup(self):
        candidates = [e for e in self._entries if not e.get("essential", False) and e.get("source") != "Windows Service" and e.get("enabled", True)]
        if not candidates:
            QMessageBox.information(self, "Optimized", "All non-essential startup programs are already disabled!")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Optimize Windows Startup")
        dialog.resize(520, 360)
        d_layout = QVBoxLayout(dialog)

        desc = QLabel(f"The following {len(candidates)} programs are safe to disable. Disabling them will improve Windows boot time significantly:")
        desc.setWordWrap(True)
        d_layout.addWidget(desc)

        check_widgets = []
        for cand in candidates:
            cb = QCheckBox(f"{cand['name']} ({cand.get('impact', 'Medium')} impact) — {cand.get('recommendation', '')}")
            cb.setChecked(True)
            d_layout.addWidget(cb)
            check_widgets.append((cb, cand))

        d_layout.addStretch()
        btn_box = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        confirm_btn = QPushButton("Disable Selected")
        confirm_btn.setObjectName("PrimaryButton")
        confirm_btn.clicked.connect(dialog.accept)
        btn_box.addStretch()
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(confirm_btn)
        d_layout.addLayout(btn_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            disabled_count = 0
            for cb, cand in check_widgets:
                if cb.isChecked():
                    if cand.get("source") == "Registry":
                        if toggle_registry_entry(cand, False):
                            disabled_count += 1
                            db.log_startup_change(cand["name"], cand["source"], "Enabled", "Disabled")
                    elif cand.get("source") == "Startup Folder":
                        if toggle_startup_folder_entry(cand, False):
                            disabled_count += 1
                            db.log_startup_change(cand["name"], cand["source"], "Enabled", "Disabled")
                    elif cand.get("source") == "Scheduled Task":
                        if toggle_task_scheduler_entry(cand.get("raw_name", cand["name"]), False):
                            disabled_count += 1
                            db.log_startup_change(cand["name"], cand["source"], "Enabled", "Disabled")

            est_sec = disabled_count * 3
            QMessageBox.information(
                self,
                "Optimization Complete",
                f"Successfully disabled {disabled_count} startup programs.\nEstimated boot time improvement: {est_sec}-{est_sec + 15} seconds."
            )
            self._refresh_startup()

    def _undo_last_change(self):
        last_change = db.get_last_startup_change()
        if not last_change:
            QMessageBox.information(self, "Undo", "No recorded startup changes to undo.")
            return

        name = last_change["name"]
        src = last_change["source"]
        prev = last_change["previous_state"]  # what to restore to
        should_enable = (prev == "Enabled")

        entry = next((e for e in self._entries if e["name"] == name), None)
        if not entry:
            QMessageBox.warning(self, "Undo Failed", f"Could not find startup item '{name}' in current configuration.")
            return

        success = False
        if src == "Registry":
            success = toggle_registry_entry(entry, should_enable)
        elif src == "Startup Folder":
            success = toggle_startup_folder_entry(entry, should_enable)
        elif src == "Scheduled Task":
            success = toggle_task_scheduler_entry(entry.get("raw_name", name), should_enable)

        if success:
            db.delete_startup_change(last_change["id"])
            QMessageBox.information(self, "Restored", f"Restored {name} to {prev}.")
            self._refresh_startup()
        else:
            QMessageBox.critical(self, "Undo Failed", f"Failed to restore {name} to {prev}.")

    def _show_change_history(self):
        history = db.get_startup_history(50)
        dialog = QDialog(self)
        dialog.setWindowTitle("Startup Modification History")
        dialog.resize(600, 350)
        d_layout = QVBoxLayout(dialog)

        table = QTableWidget(len(history), 4)
        table.setHorizontalHeaderLabels(["Timestamp", "Program Name", "Previous State", "New State"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        for row, h in enumerate(history):
            table.setItem(row, 0, QTableWidgetItem(str(h["timestamp"])))
            table.setItem(row, 1, QTableWidgetItem(str(h["name"])))
            table.setItem(row, 2, QTableWidgetItem(str(h["previous_state"])))
            table.setItem(row, 3, QTableWidgetItem(str(h["new_state"])))

        d_layout.addWidget(table)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        d_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()
