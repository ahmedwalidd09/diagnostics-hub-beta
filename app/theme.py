"""Theme and QSS styles for Diagnostics Hub - Cyber Stealth Edition (Black, Red & Blue)."""

DARK_THEME_QSS = """
QMainWindow, QWidget#MainContent {
    background-color: #07080c;
    color: #f0f6fc;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
}

/* Sidebar Styling */
QFrame#Sidebar {
    background-color: #040508;
    border-right: 1px solid #141824;
}

QListWidget#SidebarList {
    background-color: transparent;
    border: none;
    outline: none;
    padding-top: 8px;
}

QListWidget#SidebarList::item {
    color: #828d9e;
    padding: 10px 16px;
    margin: 3px 8px;
    border-radius: 6px;
    font-weight: 500;
    font-size: 13px;
    border: 1px solid transparent;
}

QListWidget#SidebarList::item:hover {
    background-color: rgba(0, 168, 255, 0.08);
    color: #f0f6fc;
    border: 1px solid rgba(0, 168, 255, 0.2);
}

QListWidget#SidebarList::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 168, 255, 0.25), stop:1 rgba(0, 168, 255, 0.03));
    color: #ffffff;
    font-weight: 700;
    border-left: 3px solid #00a8ff;
    border-top: 1px solid rgba(0, 168, 255, 0.3);
    border-bottom: 1px solid rgba(0, 168, 255, 0.3);
    border-right: 1px solid rgba(0, 168, 255, 0.1);
}

/* Cards & Frames - Cyber Obsidian HUD */
QFrame.Card, QFrame#CardFrame {
    background-color: #0d1017;
    border: 1px solid #1a2130;
    border-top: 2px solid qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff2a51, stop:0.4 #1a2130, stop:1 #00a8ff);
    border-radius: 8px;
    padding: 14px;
}

/* Typography */
QLabel {
    color: #f0f6fc;
}

QLabel#CardTitle {
    font-size: 13px;
    font-weight: 700;
    color: #00d2ff;
    letter-spacing: 0.5px;
}

QLabel#SubText {
    color: #798394;
    font-size: 12px;
}

QLabel#HugeMetric {
    font-size: 26px;
    font-weight: bold;
    color: #ffffff;
}

/* Buttons - Cyberpunk Styling */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #161b26, stop:1 #0f131c);
    color: #d1d9e6;
    border: 1px solid #222b3d;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1e2536, stop:1 #141924);
    color: #ffffff;
    border-color: #00a8ff;
}

QPushButton:pressed {
    background-color: #0a0d14;
    border-color: #0070f3;
}

QPushButton:disabled {
    background-color: #0a0d14;
    color: #424a59;
    border-color: #161b26;
}

/* Primary Action Button (Electric Blue) */
QPushButton#PrimaryButton, QPushButton#ActionBlue {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0052cc, stop:1 #00a8ff);
    color: #ffffff;
    border: 1px solid #38bdf8;
    font-weight: 700;
}

QPushButton#PrimaryButton:hover, QPushButton#ActionBlue:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0066ff, stop:1 #00d2ff);
    border-color: #7dd3fc;
}

/* Destructive Action Button (Neon Crimson Red) */
QPushButton#DestructiveButton, QPushButton#ActionRed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b30024, stop:1 #ff2a51);
    color: #ffffff;
    border: 1px solid #ff4757;
    font-weight: 700;
}

QPushButton#DestructiveButton:hover, QPushButton#ActionRed:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d90429, stop:1 #ff5277);
    border-color: #ff6b81;
}

/* Secondary Button (Titanium Grey with Blue Edge) */
QPushButton#SecondaryButton {
    background-color: #121622;
    color: #d1d9e6;
    border: 1px solid #222b3d;
}

QPushButton#SecondaryButton:hover {
    border-color: #00a8ff;
    color: #ffffff;
}

/* Inputs */
QLineEdit {
    background-color: #07090e;
    color: #f0f6fc;
    border: 1px solid #1e2638;
    border-radius: 6px;
    padding: 6px 12px;
    selection-background-color: #00a8ff;
}

QLineEdit:focus {
    border: 1px solid #00a8ff;
    background-color: #090c13;
}

QComboBox {
    background-color: #121622;
    color: #f0f6fc;
    border: 1px solid #1e2638;
    border-radius: 6px;
    padding: 6px 12px;
}

QComboBox::drop-down {
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #0d1017;
    color: #f0f6fc;
    border: 1px solid #1e2638;
    selection-background-color: #00a8ff;
}

/* Checkboxes */
QCheckBox {
    color: #f0f6fc;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #252f44;
    border-radius: 4px;
    background-color: #07090e;
}

QCheckBox::indicator:hover {
    border-color: #00a8ff;
}

QCheckBox::indicator:checked {
    background-color: #00a8ff;
    border-color: #38bdf8;
}

/* Tables & Lists */
QTableView, QTableWidget {
    background-color: #090c12;
    border: 1px solid #1a2130;
    border-radius: 6px;
    gridline-color: #141824;
    color: #f0f6fc;
    selection-background-color: rgba(0, 168, 255, 0.28);
    selection-color: #ffffff;
    outline: none;
}

QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #121622, stop:1 #0c0e16);
    color: #00d2ff;
    padding: 8px;
    font-weight: 700;
    border: none;
    border-bottom: 2px solid #00a8ff;
    border-right: 1px solid #1a2130;
}

QTableCornerButton::section {
    background-color: #0c0e16;
    border: none;
}

/* Progress Bars */
QProgressBar {
    background-color: #121622;
    border: 1px solid #1e2638;
    border-radius: 4px;
    text-align: center;
    color: #ffffff;
    font-weight: 700;
    font-size: 11px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0052cc, stop:1 #00a8ff);
    border-radius: 3px;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #141824;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0052cc, stop:1 #00a8ff);
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00d2ff, stop:1 #0070f3);
    border: 2px solid #ffffff;
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #ff2a51;
    border-color: #ffffff;
}

/* Scrollbars */
QScrollBar:vertical {
    background: #07080c;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #1e2638;
    min-height: 25px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #00a8ff;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #07080c;
    height: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #1e2638;
    min-width: 25px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #00a8ff;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #1a2130;
    background-color: #0d1017;
    border-radius: 6px;
}

QTabBar::tab {
    background-color: #07080c;
    color: #828d9e;
    padding: 8px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background-color: #0d1017;
    color: #00d2ff;
    border: 1px solid #1a2130;
    border-bottom: none;
    font-weight: 700;
}

QTabBar::tab:hover {
    color: #ffffff;
}

/* Tooltips */
QToolTip {
    background-color: #0d1017;
    color: #00d2ff;
    border: 1px solid #00a8ff;
    padding: 5px 8px;
    border-radius: 4px;
    font-weight: 500;
}

/* Admin Banner */
QFrame#AdminBanner {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(255, 42, 81, 0.2), stop:1 rgba(0, 168, 255, 0.05));
    border: 1px solid #ff2a51;
    border-radius: 6px;
    padding: 8px 12px;
}
"""

LIGHT_THEME_QSS = """
QMainWindow, QWidget#MainContent {
    background-color: #f6f8fa;
    color: #1f2328;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
}

/* Sidebar Styling */
QFrame#Sidebar {
    background-color: #ffffff;
    border-right: 1px solid #d0d7de;
}

QListWidget#SidebarList {
    background-color: transparent;
    border: none;
    outline: none;
    padding-top: 8px;
}

QListWidget#SidebarList::item {
    color: #59636e;
    padding: 10px 16px;
    margin: 3px 8px;
    border-radius: 6px;
    font-weight: 500;
    font-size: 13px;
}

QListWidget#SidebarList::item:hover {
    background-color: rgba(0, 0, 0, 0.05);
    color: #1f2328;
}

QListWidget#SidebarList::item:selected {
    background-color: #0969da;
    color: #ffffff;
    font-weight: 600;
}

/* Cards & Frames */
QFrame.Card, QFrame#CardFrame {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 8px;
    padding: 14px;
}

/* Typography */
QLabel {
    color: #1f2328;
}

QLabel#CardTitle {
    font-size: 14px;
    font-weight: 600;
    color: #1f2328;
}

QLabel#SubText {
    color: #59636e;
    font-size: 12px;
}

QLabel#HugeMetric {
    font-size: 26px;
    font-weight: bold;
    color: #1f2328;
}

/* Buttons */
QPushButton {
    background-color: #f6f8fa;
    color: #24292f;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #f3f4f6;
    border-color: #8c959f;
}

QPushButton:pressed {
    background-color: #ebecf0;
}

QPushButton#PrimaryButton, QPushButton#ActionGreen {
    background-color: #1f883d;
    color: #ffffff;
    border: 1px solid #1a7f37;
    font-weight: 600;
}

QPushButton#DestructiveButton, QPushButton#ActionRed {
    background-color: #cf222e;
    color: #ffffff;
    border: 1px solid #b62324;
    font-weight: 600;
}

/* Inputs */
QLineEdit {
    background-color: #ffffff;
    color: #1f2328;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #0969da;
}

QTableView, QTableWidget {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    gridline-color: #eaeef2;
    color: #1f2328;
    selection-background-color: #0969da;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #f6f8fa;
    color: #59636e;
    padding: 8px;
    font-weight: 600;
    border: none;
    border-bottom: 1px solid #d0d7de;
}

QProgressBar {
    background-color: #eaeef2;
    border: 1px solid #d0d7de;
    border-radius: 4px;
    text-align: center;
    color: #1f2328;
    font-weight: 600;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: #1f883d;
    border-radius: 3px;
}

QScrollBar:vertical {
    background: #f6f8fa;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #d0d7de;
    min-height: 25px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #8c959f;
}

QTabWidget::pane {
    border: 1px solid #d0d7de;
    background-color: #ffffff;
    border-radius: 6px;
}

QTabBar::tab {
    background-color: #f6f8fa;
    color: #59636e;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #1f2328;
    border: 1px solid #d0d7de;
    border-bottom: none;
    font-weight: 600;
}

QFrame#AdminBanner {
    background-color: #fff8c5;
    border: 1px solid #d4a72c;
    border-radius: 6px;
    padding: 8px 12px;
}
"""


def get_stylesheet(theme_name: str = "dark") -> str:
    """Return the QSS string for dark (cyber stealth) or light theme."""
    if str(theme_name).lower() == "light":
        return LIGHT_THEME_QSS
    return DARK_THEME_QSS
