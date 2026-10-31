import math
from PyQt6.QtCore import Qt, QRectF, pyqtProperty, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QPen, QColor, QFont
from PyQt6.QtWidgets import QWidget
from app.constants import (
    COLOR_GAUGE_HEALTHY,
    COLOR_GAUGE_WARNING,
    COLOR_GAUGE_CRITICAL
)


class GaugeWidget(QWidget):
    """
    Clean, minimal circular progress gauge for workstation diagnostics.
    Provides smooth animated transitions with understated status coloring.
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

        self.setMinimumSize(120, 120)

        self._anim = QPropertyAnimation(self, b"display_value")
        self._anim.setDuration(350)
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
            if val >= 80:
                return QColor(COLOR_GAUGE_HEALTHY)
            elif val >= 50:
                return QColor(COLOR_GAUGE_WARNING)
            else:
                return QColor(COLOR_GAUGE_CRITICAL)
        else:
            if val < 70:
                return QColor(COLOR_GAUGE_HEALTHY)
            elif val < 85:
                return QColor(COLOR_GAUGE_WARNING)
            else:
                return QColor(COLOR_GAUGE_CRITICAL)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        size = min(width, height)

        margin = 12
        gauge_rect = QRectF(
            (width - size) / 2 + margin,
            (height - size) / 2 + margin,
            size - 2 * margin,
            size - 2 * margin
        )

        # 1. Background Track
        track_pen = QPen(QColor("#1e222e"), 7)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)

        start_angle = 225 * 16
        span_angle = -270 * 16
        painter.drawArc(gauge_rect, start_angle, span_angle)

        # 2. Progress Arc
        ratio = (self._display_value - self._min_value) / (self._max_value - self._min_value or 1.0)
        value_span = int(ratio * span_angle)

        if abs(value_span) > 0:
            active_color = self._get_active_color()
            active_pen = QPen(active_color, 7)
            active_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(active_pen)
            painter.drawArc(gauge_rect, start_angle, value_span)

        # 3. Center Value Text
        painter.setPen(QColor("#f1f5f9"))
        font_val = QFont("Segoe UI", int(size * 0.17), QFont.Weight.DemiBold)
        painter.setFont(font_val)

        val_str = f"{int(round(self._display_value))}{self._unit}"
        text_rect = QRectF(gauge_rect.x(), gauge_rect.y() + gauge_rect.height() * 0.18,
                           gauge_rect.width(), gauge_rect.height() * 0.40)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, val_str)

        # 4. Title Text Below
        if self._title:
            painter.setPen(QColor("#94a3b8"))
            font_title = QFont("Segoe UI", max(8, int(size * 0.08)), QFont.Weight.Medium)
            painter.setFont(font_title)
            title_rect = QRectF(gauge_rect.x(), gauge_rect.y() + gauge_rect.height() * 0.58,
                                gauge_rect.width(), gauge_rect.height() * 0.25)
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self._title)

        painter.end()
