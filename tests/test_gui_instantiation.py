from unittest.mock import MagicMock
import pytest
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt

from app.modules.dashboard import DashboardPage
from app.modules.slow_analyzer import SlowAnalyzerPage
from app.modules.process_manager import ProcessManagerPage
from app.modules.virus_scanner import VirusScannerPage
from app.modules.ram_cleaner import RamCleanerPage, RestingTriageDialog
from app.modules.startup_manager import StartupManagerPage
from app.modules.disk_cleanup import DiskCleanupPage
from app.modules.network_monitor import NetworkMonitorPage
from app.modules.settings_page import SettingsPage

from app.widgets.gauge_widget import GaugeWidget
from app.widgets.sparkline_widget import SparklineWidget
from app.widgets.ram_bubble_canvas import RamBubbleCanvas
from app.widgets.live_beacon import LiveBeaconWidget
from app.widgets.profile_switcher import ProfileSwitcherWidget
from app.widgets.search_bar import SearchBar
from app.widgets.severity_badge import SeverityBadge
from app.widgets.toast_notification import ToastNotification
from app.widgets.access_modal import AccessGateDialog, TelegramConfigDialog


# =========================================================================
# 9 Application Pages Headless Instantiation Tests
# =========================================================================

def test_dashboard_page_instantiation(qapp):
    """Verify DashboardPage instantiates headlessly without errors."""
    page = DashboardPage()
    assert isinstance(page, QWidget)
    assert page.objectName() == "MainContent"
    assert hasattr(page, "cpu_gauge")
    assert hasattr(page, "ram_gauge")


def test_slow_analyzer_page_instantiation(qapp):
    """Verify SlowAnalyzerPage instantiates headlessly without errors."""
    page = SlowAnalyzerPage()
    assert isinstance(page, QWidget)
    assert hasattr(page, "score_card")
    assert hasattr(page, "scan_btn")


def test_process_manager_page_instantiation(qapp):
    """Verify ProcessManagerPage instantiates headlessly with mocked worker."""
    page = ProcessManagerPage()
    assert isinstance(page, QWidget)
    assert hasattr(page, "table")
    assert hasattr(page, "search_bar")
    page.stop_worker()


def test_virus_scanner_page_instantiation(qapp):
    """Verify VirusScannerPage instantiates headlessly without errors."""
    page = VirusScannerPage()
    assert isinstance(page, QWidget)
    assert hasattr(page, "table")
    assert hasattr(page, "progress_bar")


def test_ram_cleaner_page_instantiation(qapp):
    """Verify RamCleanerPage instantiates headlessly with mocked worker."""
    page = RamCleanerPage()
    assert isinstance(page, QWidget)
    assert hasattr(page, "clean_btn")
    assert hasattr(page, "bubble_canvas")
    page.stop_worker()


def test_startup_manager_page_instantiation(qapp):
    """Verify StartupManagerPage instantiates headlessly without errors."""
    page = StartupManagerPage()
    assert isinstance(page, QWidget)
    assert hasattr(page, "table")
    assert hasattr(page, "refresh_btn")


def test_disk_cleanup_page_instantiation(qapp):
    """Verify DiskCleanupPage instantiates headlessly without errors."""
    page = DiskCleanupPage()
    assert isinstance(page, QWidget)
    assert hasattr(page, "clean_btn")
    assert hasattr(page, "reclaimable_lbl")


def test_network_monitor_page_instantiation(qapp):
    """Verify NetworkMonitorPage instantiates headlessly with mocked worker."""
    page = NetworkMonitorPage()
    assert isinstance(page, QWidget)
    assert hasattr(page, "conns_table")
    assert hasattr(page, "suspicious_table")
    page.stop_worker()


def test_settings_page_instantiation(qapp):
    """Verify SettingsPage instantiates headlessly and exposes theme_changed signal."""
    page = SettingsPage()
    assert isinstance(page, QWidget)
    assert hasattr(page, "theme_combo")
    assert hasattr(page, "theme_changed")


# =========================================================================
# Custom Widgets Instantiation & API Tests
# =========================================================================

def test_gauge_widget(qapp):
    """Verify GaugeWidget instantiates, sets values and renders without error."""
    gauge = GaugeWidget(title="CPU Usage", unit="%", min_value=0.0, max_value=100.0)
    assert isinstance(gauge, QWidget)
    gauge.set_value(75.5, animated=False)
    assert gauge._value == 75.5


def test_sparkline_widget(qapp):
    """Verify SparklineWidget accepts point additions and data sequences."""
    spark = SparklineWidget(max_points=30, line_color="#3b82f6")
    assert isinstance(spark, QWidget)
    spark.add_point(42.0)
    spark.set_data([10.0, 20.0, 30.0, 40.0])
    assert len(spark.history) == 4


def test_ram_bubble_canvas(qapp):
    """Verify RamBubbleCanvas instantiates and updates process nodes."""
    canvas = RamBubbleCanvas()
    assert isinstance(canvas, QWidget)
    procs = [
        {"pid": 100, "name": "System", "ram_mb": 150.0},
        {"pid": 200, "name": "Code.exe", "ram_mb": 850.0},
    ]
    canvas.update_data(procs, procs)
    assert len(canvas._nodes) == 2


def test_live_beacon_widget(qapp):
    """Verify LiveBeaconWidget text setting and status display."""
    beacon = LiveBeaconWidget(text="Live Telemetry")
    assert isinstance(beacon, QWidget)
    beacon.set_text("System Nominal")
    assert beacon._text == "System Nominal"


def test_profile_switcher_widget(qapp):
    """Verify ProfileSwitcherWidget handles selection and emits profile_changed signal."""
    switcher = ProfileSwitcherWidget()
    assert isinstance(switcher, QWidget)

    slot_mock = MagicMock()
    switcher.profile_changed.connect(slot_mock)

    switcher._on_clicked("turbo")
    assert switcher.current_profile() == "turbo"
    slot_mock.assert_called_with("turbo")


def test_search_bar_widget(qapp):
    """Verify SearchBar emits search_changed on text update."""
    search = SearchBar(placeholder="Filter...")
    assert isinstance(search, QWidget)

    slot_mock = MagicMock()
    search.search_changed.connect(slot_mock)

    search.setText("diagnostics")
    slot_mock.assert_called_with("diagnostics")


def test_severity_badge_widget(qapp):
    """Verify SeverityBadge sets severity styling correctly."""
    badge = SeverityBadge(level="warning", text="High Priority")
    assert isinstance(badge, QWidget)
    assert "High Priority" in badge.text()

    badge.set_severity("critical", "Emergency")
    assert "Emergency" in badge.text()


def test_toast_notification_widget(qapp):
    """Verify ToastNotification instantiates headlessly."""
    toast = ToastNotification()
    assert isinstance(toast, QWidget)
    toast.show_message("Alert", "Memory usage high", level="warning")
    assert toast._title_label.text() == "Alert"


def test_access_gate_dialog(qapp):
    """Verify AccessGateDialog instantiates without raising exceptions."""
    dlg = AccessGateDialog()
    assert isinstance(dlg, QWidget)
    assert hasattr(dlg, "pin_edit")
    assert hasattr(dlg, "request_btn")


def test_telegram_config_dialog(qapp):
    """Verify TelegramConfigDialog instantiates without raising exceptions."""
    dlg = TelegramConfigDialog()
    assert isinstance(dlg, QWidget)
    assert hasattr(dlg, "token_edit")
    assert hasattr(dlg, "chat_edit")


def test_resting_triage_dialog(qapp):
    """Verify RestingTriageDialog instantiates without raising exceptions."""
    dlg = RestingTriageDialog()
    assert isinstance(dlg, QWidget)


# =========================================================================
# PyQt6 Signals & Theme Change Event Handling Tests
# =========================================================================

def test_settings_page_theme_changed_signal(qapp):
    """Verify SettingsPage theme_changed signal emits selected theme name."""
    page = SettingsPage()
    slot_mock = MagicMock()
    page.theme_changed.connect(slot_mock)

    # Toggle to different index so currentIndexChanged fires
    current_idx = page.theme_combo.currentIndex()
    new_idx = 0 if current_idx == 1 else 1
    page.theme_combo.setCurrentIndex(new_idx)
    slot_mock.assert_called()
    emitted_theme = slot_mock.call_args[0][0]
    assert isinstance(emitted_theme, str)
    assert len(emitted_theme) > 0


def test_theme_application_resilience(qapp):
    """Verify applying themes and styles does not crash pages or widgets."""
    from app.theme import get_stylesheet

    for theme_name in ("workstation", "obsidian", "light"):
        qss = get_stylesheet(theme_name)
        assert isinstance(qss, str)
        assert len(qss) > 0

        # Apply to headless QApplication instance
        qapp.setStyleSheet(qss)

        # Instantiating page under active theme
        page = DashboardPage()
        assert page is not None
