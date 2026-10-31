from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush


class LiveBeaconWidget(QWidget):
    """
    Static, zero-CPU telemetry status indicator.
    Replaces animated pulse timers with a clean, low-overhead status pill.
    """

    def __init__(self, text: str = "Telemetry Active • 1000ms", parent=None):
        super().__init__(parent)
        self._text = text
        self.setFixedHeight(26)
        self.setMinimumWidth(160)

    def set_text(self, text: str):
        self._text = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        h = self.height()
        cy = h / 2.0
        cx = 10.0

        # Draw steady status dot
        core_color = QColor("#10b981")  # Clean emerald green
        painter.setBrush(QBrush(core_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(cx - 3.5), int(cy - 3.5), 7, 7)

        # Draw status label
        painter.setPen(QColor("#94a3b8"))
        font = QFont("Segoe UI", 9, QFont.Weight.Medium)
        painter.setFont(font)
        painter.drawText(int(cx + 10), int(cy + 4), self._text)

        painter.end()
