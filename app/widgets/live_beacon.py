import math
import time
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush


class LiveBeaconWidget(QWidget):
    """
    Sleek pulsing cyber LED telemetry beacon.
    Renders an animated glowing pulse dot with real-time status.
    """

    def __init__(self, text: str = "LIVE TELEMETRY", parent=None):
        super().__init__(parent)
        self._text = text
        self._phase = 0.0
        self.setFixedHeight(28)
        self.setMinimumWidth(150)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(50)  # 20 FPS smooth breathing pulse

    def _on_tick(self):
        if not self.isVisible():
            return
        self._phase = (self._phase + 0.08) % (2 * math.pi)
        self.update()

    def set_text(self, text: str):
        self._text = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        h = self.height()
        cy = h / 2.0
        cx = 14.0

        # Breathing glow factor (0.4 to 1.0)
        pulse = 0.6 + 0.4 * math.sin(self._phase)

        # 1. Outer Neon Glow Halo
        glow_radius = 8.0 + 3.0 * pulse
        glow_alpha = int(45 + 55 * pulse)
        glow_color = QColor(0, 168, 255, glow_alpha)
        painter.setBrush(QBrush(glow_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(cx - glow_radius), int(cy - glow_radius), int(glow_radius * 2), int(glow_radius * 2))

        # 2. Inner Bright LED Core
        core_color = QColor(0, 210, 255)
        painter.setBrush(QBrush(core_color))
        painter.drawEllipse(int(cx - 4), int(cy - 4), 8, 8)

        # 3. Micro White Highlight
        painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
        painter.drawEllipse(int(cx - 1.5), int(cy - 1.5), 3, 3)

        # 4. Status Text (Cyber Cyan / White)
        painter.setPen(QColor(0, 210, 255))
        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        painter.setFont(font)
        painter.drawText(28, int(cy + 4), self._text)

        painter.end()
