import os
import sys
import json
import winreg
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QCheckBox, QLineEdit, QComboBox, QFrame, QFileDialog, QMessageBox,
    QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from app.settings_manager import settings
from app.utils.virustotal_api import VirusTotalClient
from app.database import db
from app.constants import (
    APP_NAME, APP_VERSION, APP_AUTHOR,
    COLOR_BG_CARD, COLOR_BORDER
)
from app.utils.registry_utils import disable_windows_widgets


def toggle_run_at_startup(enable: bool) -> bool:
    """Create or remove Windows startup registry entry under HKCU Run."""
    run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_key_name = "DiagnosticsHub"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                if getattr(sys, "frozen", False):
                    cmd = f'"{sys.executable}"'
                else:
                    script = os.path.abspath(sys.argv[0])
                    cmd = f'"{sys.executable}" "{script}"'
                winreg.SetValueEx(key, app_key_name, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, app_key_name)
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        print(f"Failed to update startup registry: {e}")
        return False


class SettingsPage(QWidget):
    """
    Application Settings Page for theme selection, VirusTotal API key,
    RAM thresholds, startup registration, and database management.
    """
    theme_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MainContent")
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(container)
        c_layout.setSpacing(16)

        # Title
        title_box = QVBoxLayout()
        title = QLabel("Settings & Preferences")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        sub = QLabel("Configure automation, visual theme, API credentials, and application preferences.")
        sub.setObjectName("SubText")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        c_layout.addLayout(title_box)

        # 1. Appearance / Theme Card
        c_layout.addWidget(self._build_theme_card())

        # 2. VirusTotal Card
        c_layout.addWidget(self._build_virustotal_card())

        # 3. RAM Automation Card
        c_layout.addWidget(self._build_ram_card())

        # 4. Windows Startup & System Card
        c_layout.addWidget(self._build_startup_card())

        # 5. Notifications Card
        c_layout.addWidget(self._build_notifications_card())

        # 6. Data Management Card
        c_layout.addWidget(self._build_data_card())

        # 7. About Card
        c_layout.addWidget(self._build_about_card())

        c_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _build_card_frame(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("CardFrame")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(18, 14, 18, 14)
        c_layout.setSpacing(10)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        c_layout.addWidget(t_lbl)
        return card, c_layout

    def _build_theme_card(self) -> QFrame:
        card, layout = self._build_card_frame("🎨 Appearance & Interface Theme")
        h = QHBoxLayout()
        lbl = QLabel("Color Theme:")
        h.addWidget(lbl)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark (Default)", "Light"])
        current_theme = settings.get("theme", "dark")
        self.theme_combo.setCurrentIndex(1 if current_theme == "light" else 0)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        h.addWidget(self.theme_combo)
        h.addStretch()
        layout.addLayout(h)
        return card

    def _on_theme_changed(self, idx: int):
        new_theme = "light" if idx == 1 else "dark"
        settings.set("theme", new_theme)
        self.theme_changed.emit(new_theme)

    def _build_virustotal_card(self) -> QFrame:
        card, layout = self._build_card_frame("🛡️ VirusTotal v3 Cloud API")
        desc = QLabel("Enter your free VirusTotal API key to enable cloud malware hash lookup for the Virus Scanner.")
        desc.setObjectName("SubText")
        layout.addWidget(desc)

        h = QHBoxLayout()
        self.vt_key_input = QLineEdit()
        self.vt_key_input.setPlaceholderText("Enter 64-character VirusTotal API Key...")
        self.vt_key_input.setText(settings.get("virustotal_api_key", ""))
        self.vt_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        h.addWidget(self.vt_key_input)

        save_btn = QPushButton("Save Key")
        save_btn.clicked.connect(self._save_vt_key)
        h.addWidget(save_btn)

        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._test_vt_key)
        h.addWidget(test_btn)
        layout.addLayout(h)

        warn_lbl = QLabel("⚠️ Note: API keys are stored locally on this computer in settings.json.")
        warn_lbl.setStyleSheet("color: #d29922; font-size: 11px;")
        layout.addWidget(warn_lbl)
        return card

    def _save_vt_key(self):
        key = self.vt_key_input.text().strip()
        settings.set("virustotal_api_key", key)
        QMessageBox.information(self, "Saved", "VirusTotal API key successfully saved.")

    def _test_vt_key(self):
        key = self.vt_key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Key Required", "Please enter an API key first.")
            return
        client = VirusTotalClient(key)
        res = client.test_connection()
        if res.get("valid"):
            QMessageBox.information(self, "VirusTotal Connected", f"✅ {res.get('message')}")
        else:
            QMessageBox.critical(self, "Connection Failed", f"❌ {res.get('message')}")

    def _build_ram_card(self) -> QFrame:
        card, layout = self._build_card_frame("⚡ Memory Optimization Automation")
        self.autoclean_cb = QCheckBox("Automatically optimize and purge RAM when threshold is reached")
        self.autoclean_cb.setChecked(settings.get("ram_autoclean_enabled", False))
        self.autoclean_cb.toggled.connect(lambda c: settings.set("ram_autoclean_enabled", c))
        layout.addWidget(self.autoclean_cb)

        h = QHBoxLayout()
        lbl = QLabel("Threshold:")
        h.addWidget(lbl)

        thresh = int(settings.get("ram_autoclean_threshold", 85))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(50, 95)
        self.slider.setValue(thresh)
        h.addWidget(self.slider)

        self.slider_val_lbl = QLabel(f"{thresh}%")
        self.slider_val_lbl.setFixedWidth(35)
        h.addWidget(self.slider_val_lbl)

        self.slider.valueChanged.connect(self._on_thresh_slider)
        layout.addLayout(h)
        return card

    def _on_thresh_slider(self, val: int):
        self.slider_val_lbl.setText(f"{val}%")
        settings.set("ram_autoclean_threshold", float(val))

    def _build_startup_card(self) -> QFrame:
        card, layout = self._build_card_frame("🪟 Windows Integration")
        self.startup_cb = QCheckBox("Launch Diagnostics Hub automatically on Windows startup")
        self.startup_cb.setChecked(settings.get("startup_with_windows", False))
        self.startup_cb.toggled.connect(self._on_startup_toggled)
        layout.addWidget(self.startup_cb)

        self.tray_cb = QCheckBox("Minimize application to system tray on window close")
        self.tray_cb.setChecked(settings.get("minimize_to_tray", True))
        self.tray_cb.toggled.connect(lambda c: settings.set("minimize_to_tray", c))
        layout.addWidget(self.tray_cb)

        # Permanent Windows Widgets Blocker
        w_box = QVBoxLayout()
        w_box.setSpacing(6)
        w_lbl = QLabel("Bloatware Prevention:")
        w_lbl.setStyleSheet("font-weight: 600; color: #ffffff; margin-top: 6px;")
        w_box.addWidget(w_lbl)

        self.btn_disable_widgets = QPushButton("🚫 Permanently Block Windows 11 Widgets (Free 2.2 GB RAM)")
        self.btn_disable_widgets.setStyleSheet("""
            background-color: #da3633;
            color: #ffffff;
            font-weight: bold;
            padding: 8px 16px;
            border-radius: 6px;
        """)
        self.btn_disable_widgets.setToolTip("Applies Group Policy, removes Appx packages, and disables taskbar widgets permanently")
        self.btn_disable_widgets.clicked.connect(self._on_disable_widgets_clicked)
        w_box.addWidget(self.btn_disable_widgets)

        w_desc = QLabel("Applies HKLM/HKCU Group Policy (AllowNewsAndInterests=0), uninstalls WebExperience, and terminates background WidgetService.")
        w_desc.setObjectName("SubText")
        w_desc.setWordWrap(True)
        w_box.addWidget(w_desc)
        layout.addLayout(w_box)

        return card

    def _on_disable_widgets_clicked(self):
        reply = QMessageBox.question(
            self,
            "Block Windows 11 Widgets",
            "This will permanently disable Windows 11 Widgets across the system:\n\n"
            "• Terminate runaway WidgetService.exe\n"
            "• Remove WebExperience and Widget runtime packages\n"
            "• Apply Group Policy to prevent Windows from restarting them\n"
            "• Remove the Widget weather button from your taskbar\n\n"
            "Do you want to proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            res = disable_windows_widgets()
            QMessageBox.information(
                self,
                "Widgets Permanently Blocked",
                "Windows 11 Widgets have been permanently disabled!\n\n"
                "• Background processes terminated\n"
                "• Group Policy applied\n"
                "• Taskbar widget removed\n\n"
                "WidgetService will no longer launch or consume memory."
            )

    def _on_startup_toggled(self, checked: bool):
        if toggle_run_at_startup(checked):
            settings.set("startup_with_windows", checked)
        else:
            self.startup_cb.setChecked(not checked)
            QMessageBox.warning(self, "Error", "Failed to update Windows startup registry.")

    def _build_notifications_card(self) -> QFrame:
        card, layout = self._build_card_frame("🔔 Notification Alerts")
        self.notif_cpu = QCheckBox("Alert when CPU exceeds 90% load")
        self.notif_cpu.setChecked(settings.get("notify_cpu_alert", True))
        self.notif_cpu.toggled.connect(lambda c: settings.set("notify_cpu_alert", c))
        layout.addWidget(self.notif_cpu)

        self.notif_ram = QCheckBox("Alert when RAM exceeds 85% utilization")
        self.notif_ram.setChecked(settings.get("notify_ram_alert", True))
        self.notif_ram.toggled.connect(lambda c: settings.set("notify_ram_alert", c))
        layout.addWidget(self.notif_ram)

        self.notif_threat = QCheckBox("Immediate notification when security threat is flagged")
        self.notif_threat.setChecked(settings.get("notify_threat_detected", True))
        self.notif_threat.toggled.connect(lambda c: settings.set("notify_threat_detected", c))
        layout.addWidget(self.notif_threat)

        self.notif_scan = QCheckBox("Notify upon diagnostic and scan completion")
        self.notif_scan.setChecked(settings.get("notify_scan_complete", True))
        self.notif_scan.toggled.connect(lambda c: settings.set("notify_scan_complete", c))
        layout.addWidget(self.notif_scan)
        return card

    def _build_data_card(self) -> QFrame:
        card, layout = self._build_card_frame("💾 Data Management & Export")
        h = QHBoxLayout()

        clear_btn = QPushButton("🗑️ Clear Diagnostic History")
        clear_btn.setObjectName("DestructiveButton")
        clear_btn.clicked.connect(self._clear_history)
        h.addWidget(clear_btn)

        export_btn = QPushButton("📦 Export All App Telemetry (JSON)")
        export_btn.clicked.connect(self._export_all_data)
        h.addWidget(export_btn)
        h.addStretch()

        layout.addLayout(h)
        return card

    def _clear_history(self):
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Are you sure you want to delete all historical diagnostic scan records from SQLite?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            db.clear_scan_history()
            QMessageBox.information(self, "Cleared", "Diagnostic scan history has been cleared.")

    def _export_all_data(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Diagnostics Hub Data", "diagnostics_hub_backup.json", "JSON (*.json)")
        if file_path:
            try:
                data = db.export_all_data()
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                QMessageBox.information(self, "Exported", f"Data exported successfully to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", str(e))

    def _build_about_card(self) -> QFrame:
        card, layout = self._build_card_frame(f"ℹ️ About {APP_NAME}")
        layout.addWidget(QLabel(f"<b>{APP_NAME}</b> — Version {APP_VERSION}"))
        layout.addWidget(QLabel("Engineered with PyQt6, Python 3.11+, and Windows Native Win32 APIs."))
        layout.addWidget(QLabel("Designed for Windows 10/11 x64 systems."))
        return card
