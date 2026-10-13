from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint


class ToastNotification(QWidget):
    """Slide-in and fade-out toast notification widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.SubWindow | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(14, 12, 14, 12)
        self._layout.setSpacing(12)

        self._icon_label = QLabel(self)
        self._icon_label.setStyleSheet("font-size: 20px;")
        self._layout.addWidget(self._icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self._title_label = QLabel(self)
        self._title_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #ffffff;")
        text_layout.addWidget(self._title_label)

        self._message_label = QLabel(self)
        self._message_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        self._message_label.setWordWrap(True)
        text_layout.addWidget(self._message_label)

        self._layout.addLayout(text_layout)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)

        self._anim = None
        self.hide()

    def show_message(self, title: str, message: str, level: str = "info", duration_ms: int = 4000):
        icons = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌"
        }
        border_colors = {
            "info": "#1f6feb",
            "success": "#238636",
            "warning": "#d29922",
            "error": "#da3633"
        }

        self._icon_label.setText(icons.get(level.lower(), "ℹ️"))
        self._title_label.setText(title)
        self._message_label.setText(message)

        border = border_colors.get(level.lower(), "#30363d")
        self.setStyleSheet(f"""
            ToastNotification {{
                background-color: #161b22;
                border: 1px solid {border};
                border-radius: 8px;
            }}
        """)
        self.adjustSize()
        self.setFixedWidth(max(280, min(380, self.sizeHint().width())))

        parent = self.parentWidget()
        if parent:
            target_x = parent.width() - self.width() - 20
            target_y = 20
            start_x = parent.width()
            self.move(start_x, target_y)
            self._opacity_effect.setOpacity(1.0)
            self.show()
            self.raise_()

            # Slide-in animation
            self._pos_anim = QPropertyAnimation(self, b"pos")
            self._pos_anim.setDuration(300)
            self._pos_anim.setStartValue(QPoint(start_x, target_y))
            self._pos_anim.setEndValue(QPoint(target_x, target_y))
            self._pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._pos_anim.start()
        else:
            self._opacity_effect.setOpacity(1.0)
            self.show()

        self._timer.start(duration_ms)

    def _fade_out(self):
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(400)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.hide)
        self._anim.start()
