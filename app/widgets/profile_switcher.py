from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QButtonGroup
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor


class ProfileSwitcherWidget(QWidget):
    """
    Cyber Performance Profile Switcher (Turbo, Balanced, Stealth).
    Provides instant power/performance mode selection with sleek visual states.
    """
    profile_changed = pyqtSignal(str)

    PROFILES = [
        ("balanced", "⚡ Balanced", "#00a8ff"),
        ("turbo", "🚀 Turbo Boost", "#ff2a51"),
        ("stealth", "🍃 Stealth Eco", "#38bdf8")
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_profile = "balanced"
        self._buttons = {}
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.setStyleSheet("""
            QWidget {
                background-color: #07090e;
                border: 1px solid #1a2130;
                border-radius: 8px;
            }
        """)

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        for mode, label, color in self.PROFILES:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.setObjectName(f"ProfileBtn_{mode}")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: #798394;
                    border: none;
                    border-radius: 5px;
                    padding: 4px 12px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    color: #ffffff;
                    background: rgba(255, 255, 255, 0.05);
                }}
                QPushButton:checked {{
                    color: #ffffff;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {color}, stop:1 rgba(0, 0, 0, 0.6));
                    border: 1px solid {color};
                    font-weight: 700;
                }}
            """)
            btn.clicked.connect(lambda checked, m=mode: self._on_clicked(m))
            self.btn_group.addButton(btn)
            layout.addWidget(btn)
            self._buttons[mode] = btn

        # Select balanced by default
        self._buttons["balanced"].setChecked(True)

    def _on_clicked(self, mode: str):
        if self._current_profile != mode:
            self._current_profile = mode
            self.profile_changed.emit(mode)

    def current_profile(self) -> str:
        return self._current_profile

    def set_profile(self, mode: str):
        if mode in self._buttons:
            self._buttons[mode].setChecked(True)
            self._current_profile = mode
