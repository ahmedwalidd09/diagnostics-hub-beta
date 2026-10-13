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
    """Render a sleek Cyber Stealth splash screen graphic (Black, Red, Blue)."""
    pix = QPixmap(500, 270)
    pix.fill(QColor("#07080c"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Outer border
    painter.setPen(QColor("#1a2130"))
    painter.drawRect(0, 0, 499, 269)

    # Accent Top Header Bar (Crimson to Electric Blue)
    grad = QLinearGradient(0, 0, 500, 0)
    grad.setColorAt(0.0, QColor("#ff2a51"))
    grad.setColorAt(0.5, QColor("#00d2ff"))
    grad.setColorAt(1.0, QColor("#00a8ff"))
    painter.fillRect(0, 0, 500, 4, grad)

    # Icon Hexagon/Circle Badge
    painter.setBrush(QColor("#0d1017"))
    painter.setPen(QPen(QColor("#00a8ff"), 2))
    painter.drawEllipse(32, 45, 62, 62)

    # Icon symbol
    painter.setPen(QColor("#00d2ff"))
    painter.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
    painter.drawText(32, 45, 62, 62, Qt.AlignmentFlag.AlignCenter, "⚡")

    # App Title & Cyber Subtitle
    painter.setPen(QColor("#ffffff"))
    painter.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
    painter.drawText(112, 70, APP_NAME.upper())

    painter.setPen(QColor("#ff2a51"))
    painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
    painter.drawText(112, 92, "CYBER STEALTH // x64 ARCHITECTURE")

    painter.setPen(QColor("#828d9e"))
    painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Normal))
    painter.drawText(112, 110, f"v{APP_VERSION} • Real-Time Diagnostics & Optimization Subsystem")

    # Loading status text
    painter.setPen(QColor("#00d2ff"))
    painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
    painter.drawText(32, 195, "Initializing kernel monitors and hardware telemetry...")

    # Cyber Progress Bar Line
    painter.setPen(QPen(QColor("#1a2130"), 3))
    painter.drawLine(32, 215, 468, 215)

    bar_grad = QLinearGradient(32, 0, 340, 0)
    bar_grad.setColorAt(0.0, QColor("#ff2a51"))
    bar_grad.setColorAt(1.0, QColor("#00a8ff"))
    painter.setPen(QPen(bar_grad, 3))
    painter.drawLine(32, 215, 340, 215)

    # Footer note
    painter.setPen(QColor("#828d9e"))
    painter.setFont(QFont("Segoe UI", 9))
    painter.drawText(32, 240, "Engineered with PyQt6 & Python 3.11+ • 60 FPS Native Pipeline")

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
