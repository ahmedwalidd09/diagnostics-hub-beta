import math
from PyQt6.QtCore import Qt, QRectF, pyqtProperty, QPropertyAnimation, QEasingCurve, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QConicalGradient
from PyQt6.QtWidgets import QWidget
from app.constants import (
    COLOR_GAUGE_HEALTHY,
    COLOR_GAUGE_WARNING,
    COLOR_GAUGE_CRITICAL,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY
)


class GaugeWidget(QWidget):
    """
    Cyber HUD Circular Progress Gauge with radial tech ticks,
    electric sweep arcs, dynamic cyber neon coloring (Electric Blue to Crimson Red),
    and smooth hardware-accelerated animations.
    """

    def __init__(
        self,
        title: str = "",
        unit: str = "%",
        min_value: float = 0.0,
        max_value: float = 100.0,
        invert_colors: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self._title = title
        self._unit = unit
        self._min_value = float(min_value)
        self._max_value = float(max_value)
        self._invert_colors = invert_colors
        self._value = self._min_value
        self._display_value = self._min_value

        self.setMinimumSize(130, 130)

        # Animation setup for smooth transitions
        self._anim = QPropertyAnimation(self, b"display_value")
        self._anim.setDuration(400)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    @pyqtProperty(float)
    def display_value(self) -> float:
        return self._display_value

    @display_value.setter
    def display_value(self, val: float):
        self._display_value = max(self._min_value, min(self._max_value, float(val)))
        self.update()

    def set_value(self, val: float, animated: bool = True):
        target = max(self._min_value, min(self._max_value, float(val)))
        self._value = target
        if not self.isVisible():
            self._anim.stop()
            self._display_value = target
            return

        if abs(target - self._display_value) < 0.3:
            self._display_value = target
            self.update()
            return

        if animated:
            self._anim.stop()
            self._anim.setStartValue(self._display_value)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self.display_value = target

    def value(self) -> float:
        return self._value

    def set_title(self, title: str):
        self._title = title
        self.update()

    def _get_active_color(self) -> QColor:
        val = self._display_value
        if self._invert_colors:
            # Higher is better (e.g., PC Health Score)
            if val >= 80:
                return QColor(COLOR_GAUGE_HEALTHY)  # #00a8ff
            elif val >= 50:
                return QColor(COLOR_GAUGE_WARNING)  # #ff9f1a
            else:
                return QColor(COLOR_GAUGE_CRITICAL) # #ff2a51
        else:
            # Lower is better (e.g., Resource Usage)
            if val < 70:
                return QColor(COLOR_GAUGE_HEALTHY)  # Electric Blue #00a8ff
            elif val < 85:
                return QColor(COLOR_GAUGE_WARNING)  # Cyber Amber #ff9f1a
            else:
                return QColor(COLOR_GAUGE_CRITICAL) # Neon Crimson Red #ff2a51

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        size = min(width, height)
        cx = width / 2.0
        cy = height / 2.0

        margin = 14
        gauge_rect = QRectF(
            (width - size) / 2 + margin,
            (height - size) / 2 + margin,
            size - 2 * margin,
            size - 2 * margin
        )

        # 1. Draw Outer Cyber Tick Marks (HUD Ticks)
        tick_pen = QPen(QColor(30, 40, 60, 180), 1.5)
        painter.setPen(tick_pen)
        radius = (size - 2 * margin) / 2.0 + 4
        # 14 ticks spanning the 270 degree arc (225 down to -45 degrees)
        for i in range(15):
            angle_deg = 225 - (i / 14.0) * 270
            angle_rad = math.radians(angle_deg)
            x1 = cx + (radius - 2) * math.cos(angle_rad)
            y1 = cy - (radius - 2) * math.sin(angle_rad)
            x2 = cx + (radius + 2) * math.cos(angle_rad)
            y2 = cy - (radius + 2) * math.sin(angle_rad)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # 2. Draw Background Obsidian Track
        track_pen = QPen(QColor(18, 24, 38), 9)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)

        start_angle = 225 * 16
        span_angle = -270 * 16
        painter.drawArc(gauge_rect, start_angle, span_angle)

        # 3. Draw Active Glow & Progress Arc
        ratio = (self._display_value - self._min_value) / (self._max_value - self._min_value or 1.0)
        value_span = int(ratio * span_angle)

        if abs(value_span) > 0:
            active_color = self._get_active_color()

            # Outer subtle glow arc
            glow_color = QColor(active_color)
            glow_color.setAlpha(40)
            glow_pen = QPen(glow_color, 14)
            glow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(glow_pen)
            painter.drawArc(gauge_rect, start_angle, value_span)

            # Core sharp progress arc
            active_pen = QPen(active_color, 9)
            active_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(active_pen)
            painter.drawArc(gauge_rect, start_angle, value_span)

        # 4. Draw Center Value Text
        painter.setPen(QColor("#ffffff"))
        font_val = QFont("Segoe UI", int(size * 0.17), QFont.Weight.Bold)
        painter.setFont(font_val)

        val_str = f"{int(round(self._display_value))}{self._unit}"
        text_rect = QRectF(gauge_rect.x(), gauge_rect.y() + gauge_rect.height() * 0.16,
                           gauge_rect.width(), gauge_rect.height() * 0.42)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, val_str)

        # 5. Draw Cyber Title Text below
        if self._title:
            painter.setPen(QColor(0, 210, 255))
            font_title = QFont("Segoe UI", max(8, int(size * 0.08)), QFont.Weight.DemiBold)
            font_title.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
            painter.setFont(font_title)
            title_rect = QRectF(gauge_rect.x(), gauge_rect.y() + gauge_rect.height() * 0.58,
                                gauge_rect.width(), gauge_rect.height() * 0.25)
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self._title.upper())

        painter.end()
