from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QButtonGroup
from PyQt6.QtCore import pyqtSignal


class ProfileSwitcherWidget(QWidget):
    """
    Workstation Performance Profile Switcher (Balanced, Performance, Eco).
    Provides instant mode selection with understated visual states.
    """
    profile_changed = pyqtSignal(str)

    PROFILES = [
        ("balanced", "Balanced", "#3b82f6"),
        ("turbo", "Performance", "#ef4444"),
        ("stealth", "Eco Efficiency", "#10b981")
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_profile = "balanced"
        self._buttons = {}
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)

        self.setStyleSheet("""
            QWidget {
                background-color: #12151e;
                border: 1px solid #262a38;
                border-radius: 6px;
            }
        """)

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        for mode, label, accent_color in self.PROFILES:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setObjectName(f"ProfileBtn_{mode}")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: #94a3b8;
                    border: none;
                    border-radius: 4px;
                    padding: 2px 10px;
                    font-size: 11px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    color: #ffffff;
                    background-color: #1e222e;
                }}
                QPushButton:checked {{
                    color: #ffffff;
                    background-color: #1e293b;
                    border: 1px solid {accent_color};
                    font-weight: 600;
                }}
            """)
            btn.clicked.connect(lambda checked, m=mode: self._on_clicked(m))
            self.btn_group.addButton(btn)
            layout.addWidget(btn)
            self._buttons[mode] = btn

        self._buttons["balanced"].setChecked(True)

    def _on_clicked(self, mode: str):
        if self._current_profile != mode:
            self._current_profile = mode
            self.profile_changed.emit(mode)

    def current_profile(self) -> str:
        return self._current_profile
