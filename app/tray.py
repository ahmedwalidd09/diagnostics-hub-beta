from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import pyqtSignal, QObject
from app.constants import APP_NAME


def create_tray_pixmap() -> QPixmap:
    """Generate a sleek cyber colored hub icon pixmap for system tray."""
    pix = QPixmap(32, 32)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Outer cyber crimson ring
    painter.setBrush(QColor("#07080c"))
    painter.setPen(QColor("#ff2a51"))
    painter.drawEllipse(2, 2, 28, 28)
    # Inner electric blue core
    painter.setBrush(QColor("#00a8ff"))
    painter.setPen(QColor("#00d2ff"))
    painter.drawEllipse(10, 10, 12, 12)
    painter.end()
    return pix


class SystemTray(QObject):
    """System Tray manager handling icon, context actions, and balloon notifications."""
    open_hub_requested = pyqtSignal()
    quick_ram_clean_requested = pyqtSignal()
    quick_scan_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon = QIcon(create_tray_pixmap())
        self.tray_icon = QSystemTrayIcon(self.icon, parent)
        self.tray_icon.setToolTip(APP_NAME)

        self._menu = QMenu()
        self._menu.setStyleSheet("""
            QMenu {
                background-color: #07080c;
                color: #f0f6fc;
                border: 1px solid #1a2130;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #00a8ff;
                color: #ffffff;
            }
        """)

        act_open = self._menu.addAction("🖥️ Open Hub")
        act_open.triggered.connect(self.open_hub_requested.emit)

        act_ram = self._menu.addAction("🧹 Quick RAM Clean")
        act_ram.triggered.connect(self.quick_ram_clean_requested.emit)

        act_scan = self._menu.addAction("🔍 Quick Threat Scan")
        act_scan.triggered.connect(self.quick_scan_requested.emit)

        self._menu.addSeparator()

        act_exit = self._menu.addAction("❌ Exit Application")
        act_exit.triggered.connect(self.exit_requested.emit)

        self.tray_icon.setContextMenu(self._menu)
        self.tray_icon.activated.connect(self._on_activated)

    def show(self):
        self.tray_icon.show()

    def hide(self):
        self.tray_icon.hide()

    def show_notification(self, title: str, message: str, icon=QSystemTrayIcon.MessageIcon.Information):
        """Display desktop notification from tray icon."""
        if self.tray_icon.isVisible():
            self.tray_icon.showMessage(title, message, icon, 4000)

    def _on_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.open_hub_requested.emit()
