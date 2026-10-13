from collections import deque
from typing import Sequence, Optional
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath, QLinearGradient


class SparklineWidget(QWidget):
    """
    Mini inline cyber history visualization.
    Features subtle gridlines, glowing neon lines (Electric Blue / Crimson),
    and soft ambient area gradients.
    """

    def __init__(
        self,
        max_points: int = 60,
        min_val: float = 0.0,
        max_val: float = 100.0,
        line_color: str = "#00a8ff",
        fill_alpha: int = 50,
        parent=None
    ):
        super().__init__(parent)
        self.max_points = max_points
        self.min_val = min_val
        self.max_val = max_val
        self.line_color = QColor(line_color)
        self.fill_alpha = fill_alpha
        self.history = deque(maxlen=max_points)
        self.setMinimumHeight(45)

    def add_point(self, value: float):
        self.history.append(float(value))
        self.update()

    def set_data(self, values: Sequence[float]):
        self.history = deque(values, maxlen=self.max_points)
        self.update()

    def set_line_color(self, color_str: str):
        self.line_color = QColor(color_str)
        self.update()

    def clear(self):
        self.history.clear()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        n = len(self.history)

        # 1. Subtle Cyber Gridlines (25%, 50%, 75%)
        grid_pen = QPen(QColor(22, 28, 42, 120), 1, Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)
        painter.drawLine(0, int(h * 0.25), w, int(h * 0.25))
        painter.drawLine(0, int(h * 0.50), w, int(h * 0.50))
        painter.drawLine(0, int(h * 0.75), w, int(h * 0.75))

        if n < 2:
            painter.end()
            return

        pts = []
        for i, val in enumerate(self.history):
            clamped = max(self.min_val, min(self.max_val, val))
            norm = (clamped - self.min_val) / (self.max_val - self.min_val or 1.0)
            x = (i / (self.max_points - 1)) * w
            y = h - (norm * (h - 6)) - 3
            pts.append(QPointF(x, y))

        # 2. Gradient Fill Area Under Curve
        fill_path = QPainterPath()
        fill_path.moveTo(pts[0].x(), h)
        for pt in pts:
            fill_path.lineTo(pt)
        fill_path.lineTo(pts[-1].x(), h)
        fill_path.closeSubpath()

        gradient = QLinearGradient(0, 0, 0, h)
        c_top = QColor(self.line_color)
        c_top.setAlpha(self.fill_alpha)
        c_bottom = QColor(self.line_color)
        c_bottom.setAlpha(0)
        gradient.setColorAt(0, c_top)
        gradient.setColorAt(1, c_bottom)
        painter.fillPath(fill_path, gradient)

        # 3. Outer Neon Glow Line
        glow_pen = QPen(QColor(self.line_color.red(), self.line_color.green(), self.line_color.blue(), 60), 4)
        glow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line_path = QPainterPath()
        line_path.moveTo(pts[0])
        for pt in pts[1:]:
            line_path.lineTo(pt)
        painter.strokePath(line_path, glow_pen)

        # 4. Core Crisp Cyber Line
        core_pen = QPen(self.line_color, 2)
        core_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.strokePath(line_path, core_pen)

        # 5. Glowing Latest Indicator Dot
        if pts:
            last_pt = pts[-1]
            # Outer glow
            painter.setBrush(QColor(self.line_color.red(), self.line_color.green(), self.line_color.blue(), 100))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(last_pt, 6, 6)
            # Inner white center
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(last_pt, 2.5, 2.5)

        painter.end()
