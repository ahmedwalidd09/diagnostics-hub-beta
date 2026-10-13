import json
import logging
from pathlib import Path
from typing import Any, Dict
from app.constants import SETTINGS_PATH, DEFAULT_RAM_CLEAN_THRESHOLD

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS: Dict[str, Any] = {
    "theme": "dark",
    "virustotal_api_key": "",
    "ram_autoclean_enabled": False,
    "ram_autoclean_threshold": DEFAULT_RAM_CLEAN_THRESHOLD,
    "startup_with_windows": False,
    "notify_cpu_alert": True,
    "notify_ram_alert": True,
    "notify_threat_detected": True,
    "notify_scan_complete": True,
    "minimize_to_tray": True
}


class SettingsManager:
    """Manages application settings persisted in JSON."""

    def __init__(self, file_path: Path = SETTINGS_PATH):
        self.file_path = Path(file_path)
        self.settings: Dict[str, Any] = DEFAULT_SETTINGS.copy()
        self.load()

    def load(self) -> None:
        """Load settings from JSON file, falling back to defaults."""
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # Merge with default settings to preserve missing keys
                        merged = DEFAULT_SETTINGS.copy()
                        merged.update(data)
                        self.settings = merged
                        return
            except Exception as e:
                logger.error(f"Error reading settings from {self.file_path}: {e}")
        self.settings = DEFAULT_SETTINGS.copy()
        self.save()

    def save(self) -> None:
        """Save settings dictionary to JSON file."""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving settings to {self.file_path}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a setting value."""
        return self.settings.get(key, default if default is not None else DEFAULT_SETTINGS.get(key))

    def set(self, key: str, value: Any) -> None:
        """Update a setting value and persist to disk."""
        self.settings[key] = value
        self.save()

    def update(self, new_settings: Dict[str, Any]) -> None:
        """Bulk update settings and persist."""
        self.settings.update(new_settings)
        self.save()


# Singleton settings instance
settings = SettingsManager()
