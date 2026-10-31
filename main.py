import sys
import os
import subprocess

# Suppress console windows for all subprocess calls (GPUtil nvidia-smi, schtasks, etc.)
if sys.platform == "win32":
    _orig_popen = subprocess.Popen
    CREATE_NO_WINDOW = 0x08000000

    def _silent_popen(*args, **kwargs):
        if "creationflags" not in kwargs:
            kwargs["creationflags"] = CREATE_NO_WINDOW
        else:
            kwargs["creationflags"] |= CREATE_NO_WINDOW

        if "startupinfo" not in kwargs or kwargs["startupinfo"] is None:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE
            kwargs["startupinfo"] = si
        else:
            kwargs["startupinfo"].dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs["startupinfo"].wShowWindow = 0

        return _orig_popen(*args, **kwargs)

    subprocess.Popen = _silent_popen

import logging
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon, QLinearGradient, QPen
from PyQt6.QtCore import Qt, QTimer

from app.constants import APP_NAME, APP_VERSION
from app.theme import get_stylesheet
from app.settings_manager import settings
from app.main_window import MainWindow

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("DiagnosticsHub")


def create_splash_pixmap() -> QPixmap:
    """Render a clean, professional workstation splash screen graphic."""
    pix = QPixmap(500, 260)
    pix.fill(QColor("#0f1117"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Outer border
    painter.setPen(QColor("#262a38"))
    painter.drawRect(0, 0, 499, 259)

    # Accent Top Header Bar
    painter.fillRect(0, 0, 500, 3, QColor("#3b82f6"))

    # Icon Circle Badge
    painter.setBrush(QColor("#161922"))
    painter.setPen(QPen(QColor("#262a38"), 1.5))
    painter.drawEllipse(32, 42, 58, 58)

    # Icon symbol
    painter.setPen(QColor("#3b82f6"))
    painter.setFont(QFont("Segoe UI", 24, QFont.Weight.DemiBold))
    painter.drawText(32, 42, 58, 58, Qt.AlignmentFlag.AlignCenter, "⚙")

    # App Title & Subtitle
    painter.setPen(QColor("#f1f5f9"))
    painter.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
    painter.drawText(106, 66, APP_NAME)

    painter.setPen(QColor("#94a3b8"))
    painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
    painter.drawText(106, 88, f"Workstation Telemetry & Control Subsystem • v{APP_VERSION}")

    # Loading status text
    painter.setPen(QColor("#94a3b8"))
    painter.setFont(QFont("Segoe UI", 10))
    painter.drawText(32, 175, "Initializing kernel diagnostics and hardware monitors...")

    # Clean Progress Bar Line
    painter.setPen(QPen(QColor("#1e222e"), 3))
    painter.drawLine(32, 195, 468, 195)

    painter.setPen(QPen(QColor("#3b82f6"), 3))
    painter.drawLine(32, 195, 320, 195)

    # Footer note
    painter.setPen(QColor("#64748b"))
    painter.setFont(QFont("Segoe UI", 9))
    painter.drawText(32, 230, "Native PyQt6 • Low-overhead threading architecture")

    painter.end()
    return pix


def main():
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Google.DiagnosticsHub.App.1.0")
        from app.utils.system_info import enable_debug_privilege
        enable_debug_privilege()
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "assets", "icons", "app_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Apply initial theme stylesheet
    current_theme = settings.get("theme", "dark")
    app.setStyleSheet(get_stylesheet(current_theme))

    # Show Splash Screen
    splash_pix = create_splash_pixmap()
    splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
    splash.show()
    app.processEvents()

    # Access Gate Verification (Telegram Bot & One-Time Machine Whitelist)
    from app.utils.access_gate import is_machine_whitelisted
    from app.widgets.access_modal import AccessGateDialog

    if not is_machine_whitelisted():
        splash.hide()
        gate = AccessGateDialog()
        if not gate.exec():
            # Exit if access was not authorized
            os._exit(0)
        splash.show()
        app.processEvents()

    # Instantiate Main Window
    window = MainWindow()

    # Smooth transition from splash to main window
    def show_main():
        splash.finish(window)
        window.show()

    QTimer.singleShot(600, show_main)

    ret = app.exec()
    os._exit(ret)


if __name__ == "__main__":
    main()
