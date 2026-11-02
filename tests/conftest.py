import os
import sys
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure Qt offscreen platform is set for headless environments
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """
    Session-scoped fixture providing a headless QApplication instance.
    Uses --platform offscreen to run without requiring an interactive display.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    yield app


@pytest.fixture(autouse=True)
def isolated_appdata(tmp_path, monkeypatch):
    """
    Fixture providing an isolated temporary APPDATA directory.
    Monkeypatches app.constants.APPDATA_DIR, app.utils.access_gate.APPDATA_DIR,
    WHITELIST_FILE, and TELEGRAM_CONFIG_FILE so tests never read or write the
    real user's license in %APPDATA%.
    """
    appdata_mock = tmp_path / "DiagnosticsHub"
    appdata_mock.mkdir(parents=True, exist_ok=True)
    whitelist_mock = appdata_mock / "whitelist.lic"
    telegram_mock = appdata_mock / "telegram_config.json"

    import app.constants
    import app.utils.access_gate

    monkeypatch.setattr(app.constants, "APPDATA_DIR", appdata_mock)
    monkeypatch.setattr(app.utils.access_gate, "APPDATA_DIR", appdata_mock)
    monkeypatch.setattr(app.utils.access_gate, "WHITELIST_FILE", whitelist_mock)
    monkeypatch.setattr(app.utils.access_gate, "TELEGRAM_CONFIG_FILE", telegram_mock)

    yield appdata_mock


@pytest.fixture(autouse=True)
def mock_page_workers(monkeypatch):
    """
    Fixture monkeypatching _start_worker on ProcessManagerPage, RamCleanerPage,
    and NetworkMonitorPage so background QThreads do not hang pytest execution.
    """
    try:
        from app.modules.process_manager import ProcessManagerPage
        monkeypatch.setattr(ProcessManagerPage, "_start_worker", lambda self: None)
    except Exception:
        pass

    try:
        from app.modules.ram_cleaner import RamCleanerPage
        monkeypatch.setattr(RamCleanerPage, "_start_worker", lambda self: None)
    except Exception:
        pass

    try:
        from app.modules.network_monitor import NetworkMonitorPage
        monkeypatch.setattr(NetworkMonitorPage, "_start_worker", lambda self: None)
    except Exception:
        pass

    yield
