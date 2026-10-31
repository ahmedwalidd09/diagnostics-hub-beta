import os
import sys
from pathlib import Path

APP_NAME = "Windows Diagnostics Hub"
APP_VERSION = "1.1.0"
APP_AUTHOR = "Diagnostics Hub Engineering"

# App Data directory
APPDATA_DIR = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "DiagnosticsHub"
APPDATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = APPDATA_DIR / "data.db"
SETTINGS_PATH = APPDATA_DIR / "settings.json"

# Base directory
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "app" / "assets"
KNOWN_THREATS_PATH = DATA_DIR / "known_threats.json"
STARTUP_RECOMMENDATIONS_PATH = DATA_DIR / "startup_recommendations.json"

# UI Theme Colors (Clean Slate / Zinc Professional Design System)
COLOR_BG_PRIMARY = "#0f1117"        # Root application canvas
COLOR_BG_CARD = "#161922"           # Container cards and panels
COLOR_BG_SIDEBAR = "#12151e"        # Navigation sidebar
COLOR_SIDEBAR_ACTIVE = "#3b82f6"    # Active sidebar accent
COLOR_TEXT_PRIMARY = "#f1f5f9"      # Primary headings and active values
COLOR_TEXT_SECONDARY = "#94a3b8"    # Subtitles, descriptive labels
COLOR_TEXT_MUTED = "#64748b"        # Units, timestamps, inactive text
COLOR_ACCENT_BLUE = "#3b82f6"       # Primary action blue
COLOR_ACCENT_RED = "#ef4444"        # Destructive action red
COLOR_ACCENT_GREEN = "#10b981"      # Success green
COLOR_BORDER = "#262a38"            # 1px structural border
COLOR_BORDER_GLOW = "#3b82f6"       # Focus border

# Health Status & Gauge Colors (Understated, functional)
COLOR_GAUGE_HEALTHY = "#3b82f6"     # Normal load
COLOR_GAUGE_WARNING = "#f59e0b"     # Elevated load
COLOR_GAUGE_CRITICAL = "#ef4444"    # Critical load
COLOR_INFO_BLUE = "#60a5fa"         # Informational blue

# Default Thresholds
DEFAULT_RAM_CLEAN_THRESHOLD = 85.0
DEFAULT_CPU_ALERT_THRESHOLD = 90.0
DEFAULT_RAM_ALERT_THRESHOLD = 85.0
DISK_WARNING_PERCENT = 70.0
DISK_CRITICAL_PERCENT = 90.0
TEMP_WARNING_CELSIUS = 80.0
TEMP_CRITICAL_CELSIUS = 85.0

# VirusTotal API endpoints
VT_API_BASE = "https://www.virustotal.com/api/v3"
