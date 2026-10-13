from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt


class SeverityBadge(QLabel):
    """Status pill badge displaying colored indicators (Healthy, Warning, Critical, etc.)."""

    def __init__(self, level: str = "healthy", text: str = "", parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_severity(level, text)

    def set_severity(self, level: str, text: str = ""):
        lvl = level.lower()
        if not text:
            if lvl in ("healthy", "good", "low", "clean", "passed"):
                text = "Healthy" if lvl == "healthy" else level.capitalize()
            elif lvl in ("warning", "medium", "moderate"):
                text = "Warning" if lvl == "warning" else level.capitalize()
            else:
                text = "Critical" if lvl == "critical" else level.capitalize()

        if lvl in ("healthy", "good", "low", "clean", "passed"):
            bg = "rgba(0, 210, 255, 0.12)"
            color = "#00d2ff"
            border = "rgba(0, 210, 255, 0.35)"
            icon = "⚡"
        elif lvl in ("warning", "medium", "moderate", "suspicious"):
            bg = "rgba(255, 159, 26, 0.12)"
            color = "#ff9f1a"
            border = "rgba(255, 159, 26, 0.4)"
            icon = "⚠️"
        elif lvl in ("info", "blue"):
            bg = "rgba(0, 168, 255, 0.15)"
            color = "#00a8ff"
            border = "rgba(0, 168, 255, 0.4)"
            icon = "🔷"
        else:  # critical, high, malicious
            bg = "rgba(255, 42, 81, 0.15)"
            color = "#ff2a51"
            border = "rgba(255, 42, 81, 0.45)"
            icon = "🛑"

        self.setText(f"{icon}  {text}")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {color};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 3px 12px;
                font-weight: 700;
                font-size: 11px;
                letter-spacing: 0.3px;
            }}
        """)
