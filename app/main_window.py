import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QStackedWidget, QLabel, QPushButton, QFrame, QApplication
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QCloseEvent

from app.constants import APP_NAME, APP_VERSION
from app.theme import get_stylesheet
from app.settings_manager import settings
from app.utils.system_info import is_admin, restart_as_admin
from app.utils.ram_api import clean_ram

from app.widgets.toast_notification import ToastNotification
from app.widgets.live_beacon import LiveBeaconWidget
from app.widgets.profile_switcher import ProfileSwitcherWidget
from app.tray import SystemTray, create_tray_pixmap

from app.modules.dashboard import DashboardPage
from app.modules.slow_analyzer import SlowAnalyzerPage
from app.modules.process_manager import ProcessManagerPage
from app.modules.virus_scanner import VirusScannerPage
from app.modules.ram_cleaner import RamCleanerPage
from app.modules.startup_manager import StartupManagerPage
from app.modules.disk_cleanup import DiskCleanupPage
from app.modules.network_monitor import NetworkMonitorPage
from app.modules.settings_page import SettingsPage

from app.workers.system_monitor_worker import SystemMonitorWorker


class MainWindow(QMainWindow):
    """
    Main workstation application shell hosting the sidebar navigation,
    stacked module pages, admin banner, tray integration, and global toast alerts.
    """

    MODULES = [
        ("Dashboard", "System Overview & Vitals"),
        ("Diagnostic Analyzer", "Bottleneck & Slowdown Diagnosis"),
        ("Process Controller", "Advanced Process Manager"),
        ("Security Audit", "Threat & Impersonation Scanner"),
        ("RAM & Memory Map", "Kernel Pools & Interactive Bubble Map"),
        ("Startup Manager", "Boot Items & Task Scheduler"),
        ("Disk Cleanup", "Junk Files & Cache Purge"),
        ("Network Activity", "Bandwidth Chart & Active Sockets"),
        ("Settings", "Preferences & Persistence")
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setWindowIcon(QIcon(create_tray_pixmap()))
        self.resize(1200, 800)
        self.setMinimumSize(980, 660)

        self._force_exit = False
        self._init_ui()
        self._init_workers()
        self._init_tray()

    def _init_ui(self):
        central_widget = QWidget(self)
        central_widget.setObjectName("MainContent")
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # -------------------------------------------------------------
        # Admin Privileges Warning Banner (If Not Elevated)
        # -------------------------------------------------------------
        self._is_admin = is_admin()
        if not self._is_admin:
            self.admin_banner = QFrame()
            self.admin_banner.setObjectName("AdminBanner")
            b_layout = QHBoxLayout(self.admin_banner)
            b_layout.setContentsMargins(16, 6, 16, 6)
            b_lbl = QLabel("Running under standard privileges. Elevate to Administrator for complete Standby memory purge and Task Scheduler control.")
            b_lbl.setStyleSheet("font-weight: 500; font-size: 12px; color: #f1f5f9;")
            b_layout.addWidget(b_lbl)
            b_layout.addStretch()

            restart_btn = QPushButton("Restart as Administrator")
            restart_btn.setStyleSheet("""
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 600;
                padding: 4px 12px;
                border: 1px solid #3b82f6;
                border-radius: 4px;
            """)
            restart_btn.clicked.connect(self._restart_admin)
            b_layout.addWidget(restart_btn)
            root_layout.addWidget(self.admin_banner)

        # -------------------------------------------------------------
        # Main Horizontal Layout: Sidebar + Stacked Pages
        # -------------------------------------------------------------
        main_content = QHBoxLayout()
        main_content.setContentsMargins(0, 0, 0, 0)
        main_content.setSpacing(0)

        # 1. Left Navigation Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        s_layout = QVBoxLayout(sidebar)
        s_layout.setContentsMargins(8, 16, 8, 16)
        s_layout.setSpacing(10)

        # App Brand Header
        brand_box = QVBoxLayout()
        brand_box.setContentsMargins(8, 0, 8, 8)
        brand_title = QLabel("Diagnostics Hub")
        brand_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #f1f5f9; letter-spacing: 0.3px;")
        brand_sub = QLabel("Workstation Diagnostics")
        brand_sub.setStyleSheet("font-size: 11px; font-weight: 500; color: #64748b;")
        brand_box.addWidget(brand_title)
        brand_box.addWidget(brand_sub)
        s_layout.addLayout(brand_box)

        # Nav List
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("SidebarList")
        for title, tooltip in self.MODULES:
            item = QListWidgetItem(title)
            item.setToolTip(tooltip)
            item.setSizeHint(QSize(200, 36))
            self.nav_list.addItem(item)

        self.nav_list.currentRowChanged.connect(self._on_page_changed)
        s_layout.addWidget(self.nav_list)
        s_layout.addStretch()

        # Admin Badge indicator in Sidebar footer
        mode_text = "Shield: Elevated (Admin)" if self._is_admin else "Shield: Standard User"
        mode_color = "#3b82f6" if self._is_admin else "#f59e0b"
        footer_lbl = QLabel(mode_text)
        footer_lbl.setStyleSheet(f"color: {mode_color}; font-weight: 600; font-size: 11px; padding: 6px;")
        s_layout.addWidget(footer_lbl)

        main_content.addWidget(sidebar)

        # 2. Right Workspace Panel (Top Header Strip + Stacked Content Pages)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Top Strip
        top_hud = QFrame()
        top_hud.setObjectName("TopHudStrip")
        top_hud.setStyleSheet("""
            QFrame#TopHudStrip {
                background-color: #12151e;
                border-bottom: 1px solid #262a38;
                padding: 4px 16px;
            }
        """)
        th_layout = QHBoxLayout(top_hud)
        th_layout.setContentsMargins(16, 6, 16, 6)
        th_layout.setSpacing(16)

        self.active_module_lbl = QLabel("Dashboard — System Vitals")
        self.active_module_lbl.setStyleSheet("font-weight: 600; font-size: 13px; color: #f1f5f9;")
        th_layout.addWidget(self.active_module_lbl)

        th_layout.addStretch()

        self.live_beacon = LiveBeaconWidget("Telemetry Active • 1000ms", self)
        th_layout.addWidget(self.live_beacon)

        self.profile_switcher = ProfileSwitcherWidget(self)
        self.profile_switcher.profile_changed.connect(self._on_profile_changed)
        th_layout.addWidget(self.profile_switcher)

        right_layout.addWidget(top_hud)

        # Stacked Content Pages
        self.stack = QStackedWidget()
        self.dashboard_page = DashboardPage(self)
        self.slow_analyzer_page = SlowAnalyzerPage(self)
        self.process_manager_page = ProcessManagerPage(self)
        self.virus_scanner_page = VirusScannerPage(self)
        self.ram_cleaner_page = RamCleanerPage(self)
        self.startup_manager_page = StartupManagerPage(self)
        self.disk_cleanup_page = DiskCleanupPage(self)
        self.network_monitor_page = NetworkMonitorPage(self)
        self.settings_page = SettingsPage(self)
        self.settings_page.theme_changed.connect(self._apply_theme)

        self.stack.addWidget(self.dashboard_page)         # Index 0
        self.stack.addWidget(self.slow_analyzer_page)     # Index 1
        self.stack.addWidget(self.process_manager_page)   # Index 2
        self.stack.addWidget(self.virus_scanner_page)     # Index 3
        self.stack.addWidget(self.ram_cleaner_page)       # Index 4
        self.stack.addWidget(self.startup_manager_page)   # Index 5
        self.stack.addWidget(self.disk_cleanup_page)      # Index 6
        self.stack.addWidget(self.network_monitor_page)   # Index 7
        self.stack.addWidget(self.settings_page)          # Index 8

        right_layout.addWidget(self.stack)
        main_content.addWidget(right_panel)
        root_layout.addLayout(main_content)

        # Toast notification floating overlay
        self.toast = ToastNotification(self)

        # Select Dashboard by default
        self.nav_list.setCurrentRow(0)

    def _init_workers(self):
        self.monitor_worker = SystemMonitorWorker(self)
        self.monitor_worker.data_signal.connect(self.dashboard_page.update_metrics)
        self.monitor_worker.auto_clean_signal.connect(self._on_auto_clean_triggered)
        self.monitor_worker.start()

    def _init_tray(self):
        self.tray = SystemTray(self)
        self.tray.open_hub_requested.connect(self._restore_from_tray)
        self.tray.quick_ram_clean_requested.connect(self._quick_ram_clean)
        self.tray.quick_scan_requested.connect(self._quick_scan_shortcut)
        self.tray.exit_requested.connect(self._exit_app)
        self.tray.show()

    def _restart_admin(self):
        restart_as_admin()

    def _on_profile_changed(self, mode: str):
        if mode == "turbo":
            clean_ram()
            self.toast.show_message("Performance Profile", "Memory caches trimmed. Real-time telemetry active.", level="success")
        elif mode == "stealth":
            self.toast.show_message("Eco Profile", "Throttled polling profile active.", level="info")
        else:
            self.toast.show_message("Balanced Profile", "Standard balanced performance profile active.", level="info")

    def _on_page_changed(self, index: int):
        self.stack.setCurrentIndex(index)
        if 0 <= index < len(self.MODULES):
            title, desc = self.MODULES[index]
            if hasattr(self, "active_module_lbl"):
                self.active_module_lbl.setText(f"{title} — {desc}")

        # Coordinate worker activity based on active tab to maintain ~0% idle CPU
        if hasattr(self, "process_manager_page"):
            self.process_manager_page.set_active(index == 2)
        if hasattr(self, "ram_cleaner_page") and hasattr(self.ram_cleaner_page, "_worker") and self.ram_cleaner_page._worker:
            self.ram_cleaner_page._worker.set_active(index == 4)
        if hasattr(self, "network_monitor_page"):
            self.network_monitor_page.set_active(index == 7)

    def _apply_theme(self, theme_name: str):
        qss = get_stylesheet(theme_name)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(qss)

    def _on_auto_clean_triggered(self, result: dict):
        freed = result.get("freed_gb", 0.0)
        self.toast.show_message("RAM Auto-Cleaned", f"Freed {freed:.2f} GB memory automatically.", level="success")
        self.tray.show_notification("RAM Auto-Cleaned", f"Freed {freed:.2f} GB memory automatically.")

    def _quick_ram_clean(self):
        res = clean_ram()
        freed = res.get("freed_gb", 0.0)
        self.toast.show_message("Quick RAM Clean", f"Freed {freed:.2f} GB of RAM.", level="success")
        self.tray.show_notification("RAM Cleaned", f"Freed {freed:.2f} GB of RAM.")

    def _quick_scan_shortcut(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.nav_list.setCurrentRow(3)
        self.virus_scanner_page._start_scan("quick")

    def _restore_from_tray(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.raise_()
        self.activateWindow()

    def _exit_app(self):
        self._force_exit = True
        self.close()

    def closeEvent(self, event: QCloseEvent):
        if not self._force_exit and settings.get("minimize_to_tray", True):
            event.ignore()
            self.hide()
            self.tray.show_notification(APP_NAME, "Application is running in the system tray.")
        else:
            if hasattr(self, "monitor_worker"):
                self.monitor_worker.stop()
            if hasattr(self, "process_manager_page"):
                self.process_manager_page.stop_worker()
            if hasattr(self, "ram_cleaner_page"):
                self.ram_cleaner_page.stop_worker()
            if hasattr(self, "network_monitor_page"):
                self.network_monitor_page.stop_worker()
            event.accept()
            QApplication.quit()
