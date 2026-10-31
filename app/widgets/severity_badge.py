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
            elif lvl in ("warning", "medium", "moderate", "suspicious"):
                text = "Warning" if lvl == "warning" else level.capitalize()
            else:
                text = "Critical" if lvl == "critical" else level.capitalize()

        if lvl in ("healthy", "good", "low", "clean", "passed"):
            bg = "rgba(16, 185, 129, 0.12)"
            color = "#10b981"
            border = "rgba(16, 185, 129, 0.3)"
            icon = "✓"
        elif lvl in ("warning", "medium", "moderate", "suspicious"):
            bg = "rgba(245, 158, 11, 0.12)"
            color = "#f59e0b"
            border = "rgba(245, 158, 11, 0.3)"
            icon = "!"
        elif lvl in ("info", "blue"):
            bg = "rgba(59, 130, 246, 0.12)"
            color = "#3b82f6"
            border = "rgba(59, 130, 246, 0.3)"
            icon = "ℹ"
        else:  # critical, high, malicious
            bg = "rgba(239, 68, 68, 0.12)"
            color = "#ef4444"
            border = "rgba(239, 68, 68, 0.3)"
            icon = "✕"

        self.setText(f"{icon}  {text}")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {color};
                border: 1px solid {border};
                border-radius: 10px;
                padding: 2px 10px;
                font-weight: 600;
                font-size: 11px;
            }}
        """)
