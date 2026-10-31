"""Theme and QSS styles for Diagnostics Hub - Slate & Zinc Professional Workstation Edition."""

DARK_THEME_QSS = """
QMainWindow, QWidget#MainContent {
    background-color: #0f1117;
    color: #f1f5f9;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
}

/* Sidebar Styling */
QFrame#Sidebar {
    background-color: #12151e;
    border-right: 1px solid #262a38;
}

QListWidget#SidebarList {
    background-color: transparent;
    border: none;
    outline: none;
    padding-top: 8px;
}

QListWidget#SidebarList::item {
    color: #94a3b8;
    padding: 9px 14px;
    margin: 2px 8px;
    border-radius: 6px;
    font-weight: 500;
    font-size: 13px;
    border: 1px solid transparent;
}

QListWidget#SidebarList::item:hover {
    background-color: #1e222e;
    color: #f1f5f9;
    border: 1px solid #262a38;
}

QListWidget#SidebarList::item:selected {
    background-color: #1e293b;
    color: #ffffff;
    font-weight: 600;
    border-left: 3px solid #3b82f6;
    border-top: 1px solid #262a38;
    border-bottom: 1px solid #262a38;
    border-right: 1px solid #262a38;
}

/* Cards & Frames */
QFrame.Card, QFrame#CardFrame {
    background-color: #161922;
    border: 1px solid #262a38;
    border-radius: 8px;
    padding: 14px;
}

/* Typography */
QLabel {
    color: #f1f5f9;
}

QLabel#CardTitle {
    font-size: 13px;
    font-weight: 600;
    color: #f1f5f9;
}

QLabel#SubText {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#HugeMetric {
    font-size: 26px;
    font-weight: 600;
    color: #ffffff;
}

/* Buttons */
QPushButton {
    background-color: #1e222e;
    color: #f1f5f9;
    border: 1px solid #262a38;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #262a38;
    color: #ffffff;
    border-color: #3b82f6;
}

QPushButton:pressed {
    background-color: #161922;
    border-color: #2563eb;
}

QPushButton:disabled {
    background-color: #12151e;
    color: #475569;
    border-color: #1e222e;
}

/* Primary Action Button (Blue) */
QPushButton#PrimaryButton, QPushButton#ActionBlue {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    border-radius: 6px;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover, QPushButton#ActionBlue:hover {
    background-color: #1d4ed8;
    border-color: #60a5fa;
}

/* Destructive Action Button (Red) */
QPushButton#DestructiveButton, QPushButton#ActionRed {
    background-color: #b91c1c;
    color: #ffffff;
    border: 1px solid #ef4444;
    border-radius: 6px;
    font-weight: 600;
}

QPushButton#DestructiveButton:hover, QPushButton#ActionRed:hover {
    background-color: #991b1b;
    border-color: #f87171;
}

/* Secondary Button */
QPushButton#SecondaryButton {
    background-color: #161922;
    color: #94a3b8;
    border: 1px solid #262a38;
}

QPushButton#SecondaryButton:hover {
    background-color: #1e222e;
    border-color: #3b82f6;
    color: #ffffff;
}

/* Inputs */
QLineEdit {
    background-color: #12151e;
    color: #f1f5f9;
    border: 1px solid #262a38;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}

QLineEdit:focus {
    border: 1px solid #3b82f6;
    background-color: #161922;
}

/* Tables */
QTableWidget {
    background-color: #12151e;
    gridline-color: #1e222e;
    border: 1px solid #262a38;
    border-radius: 6px;
    color: #f1f5f9;
    selection-background-color: #1e293b;
    selection-color: #ffffff;
}

QTableWidget::item {
    padding: 6px 10px;
    border-bottom: 1px solid #1a1e2b;
}

QTableWidget::item:selected {
    background-color: #1e293b;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #161922;
    color: #94a3b8;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid #262a38;
    font-weight: 600;
    font-size: 12px;
}

/* Progress Bars */
QProgressBar {
    background-color: #1e222e;
    border: 1px solid #262a38;
    border-radius: 4px;
    text-align: center;
    color: #f1f5f9;
    font-size: 11px;
    font-weight: 600;
    height: 14px;
}

QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 3px;
}

/* Checkboxes */
QCheckBox {
    color: #f1f5f9;
    spacing: 8px;
    font-size: 13px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    background-color: #12151e;
    border: 1px solid #262a38;
    border-radius: 4px;
}

QCheckBox::indicator:checked {
    background-color: #3b82f6;
    border-color: #3b82f6;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #1e222e;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #3b82f6;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 1px solid #3b82f6;
    width: 14px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #3b82f6;
}

/* Scrollbars */
QScrollBar:vertical {
    background: #0f1117;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #262a38;
    min-height: 25px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #3b82f6;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #0f1117;
    height: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #262a38;
    min-width: 25px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #3b82f6;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #262a38;
    background-color: #161922;
    border-radius: 6px;
}

QTabBar::tab {
    background-color: #12151e;
    color: #94a3b8;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
    font-weight: 500;
}

QTabBar::tab:hover {
    color: #f1f5f9;
    background-color: #1e222e;
}

QTabBar::tab:selected {
    background-color: #161922;
    color: #ffffff;
    border: 1px solid #262a38;
    border-bottom: none;
    font-weight: 600;
}

/* Modals & Dialogs */
QDialog {
    background-color: #0f1117;
    color: #f1f5f9;
}

QFrame#AdminBanner {
    background-color: #1e293b;
    border-bottom: 1px solid #334155;
    padding: 6px 12px;
}
"""

LIGHT_THEME_QSS = DARK_THEME_QSS  # Workstation operates with dark canvas default


def get_stylesheet(theme_name: str = "dark") -> str:
    """Return the QSS string for workstation slate/zinc theme."""
    return DARK_THEME_QSS
