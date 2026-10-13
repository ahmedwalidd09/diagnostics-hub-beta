from PyQt6.QtWidgets import QLineEdit, QToolButton
from PyQt6.QtCore import Qt, pyqtSignal


class SearchBar(QLineEdit):
    """Filterable search bar with clear button and stylized appearance."""
    search_changed = pyqtSignal(str)

    def __init__(self, placeholder: str = "Search processes, services, or files...", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.textChanged.connect(self._on_text_changed)
        self.setStyleSheet("""
            QLineEdit {
                background-color: #0d1117;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #58a6ff;
            }
        """)

    def _on_text_changed(self, text: str):
        self.search_changed.emit(text.strip())
