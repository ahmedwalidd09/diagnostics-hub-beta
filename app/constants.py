import os
import sys
from pathlib import Path

APP_NAME = "Windows Diagnostics Hub"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Windows Diagnostics Hub Team"

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

# UI Theme Colors (Cyber Stealth: Obsidian Black, Neon Red & Electric Blue)
COLOR_BG_PRIMARY = "#07080c"
COLOR_BG_CARD = "#0d1017"
COLOR_BG_SIDEBAR = "#040508"
COLOR_SIDEBAR_ACTIVE = "#00a8ff"
COLOR_TEXT_PRIMARY = "#f0f6fc"
COLOR_TEXT_SECONDARY = "#828d9e"
COLOR_ACCENT_BLUE = "#00a8ff"
COLOR_ACCENT_RED = "#ff2a51"
COLOR_ACCENT_GREEN = "#00e676"
COLOR_BORDER = "#1a2130"
COLOR_BORDER_GLOW = "#00a8ff"

# Gauge and Health Status Colors (Cyber HUD)
COLOR_GAUGE_HEALTHY = "#00a8ff"     # Neon Electric Blue for normal load
COLOR_GAUGE_WARNING = "#ff9f1a"     # Cyber Amber for elevated load
COLOR_GAUGE_CRITICAL = "#ff2a51"    # Cyber Crimson Red for critical load
COLOR_INFO_BLUE = "#00d2ff"         # Cyber Cyan

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
