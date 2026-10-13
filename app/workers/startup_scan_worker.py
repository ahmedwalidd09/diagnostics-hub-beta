import os
import json
import psutil
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from app.utils.registry_utils import (
    get_registry_startup_entries,
    get_startup_folder_entries,
    get_task_scheduler_entries
)
from app.constants import STARTUP_RECOMMENDATIONS_PATH

logger = logging.getLogger(__name__)


class StartupScanWorker(QThread):
    """
    Scans Windows startup points across Registry, Startup folders,
    Task Scheduler, and Automatic Services.
    """
    progress_signal = pyqtSignal(int, str)
    scan_complete_signal = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rec_map = {}
        self._load_recommendations()

    def _load_recommendations(self):
        try:
            if os.path.exists(STARTUP_RECOMMENDATIONS_PATH):
                with open(STARTUP_RECOMMENDATIONS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._rec_map = {item["name"].lower(): item for item in data}
        except Exception as e:
            logger.error(f"Failed to load startup recommendations: {e}")

    def _apply_recommendation(self, entry: dict):
        clean_name = entry["name"].lower()
        if clean_name in self._rec_map:
            rec = self._rec_map[clean_name]
            entry["essential"] = rec.get("essential", False)
            entry["impact"] = rec.get("impact", entry.get("impact", "Medium"))
            entry["recommendation"] = rec.get("recommendation", "")
            if entry["essential"]:
                entry["badge_level"] = "healthy"
                entry["badge_text"] = "Keep"
            else:
                entry["badge_level"] = "critical"
                entry["badge_text"] = "Safe to Disable"
        else:
            entry["essential"] = False
            entry["recommendation"] = "User installed or unknown application."
            entry["badge_level"] = "warning"
            entry["badge_text"] = "Optional"

    def run(self):
        entries = []
        try:
            # 1. Registry
            self.progress_signal.emit(20, "Reading Registry startup keys...")
            reg = get_registry_startup_entries()
            for r in reg:
                self._apply_recommendation(r)
            entries.extend(reg)

            # 2. Startup Folders
            self.progress_signal.emit(50, "Scanning Startup folders...")
            folder = get_startup_folder_entries()
            for f in folder:
                self._apply_recommendation(f)
            entries.extend(folder)

            # 3. Scheduled Tasks
            self.progress_signal.emit(75, "Querying Logon Scheduled Tasks...")
            tasks = get_task_scheduler_entries()
            for t in tasks:
                self._apply_recommendation(t)
            entries.extend(tasks)

            # 4. Automatic Services (Read-only overview)
            self.progress_signal.emit(90, "Enumerating Automatic Windows Services...")
            try:
                for svc in psutil.win_service_iter():
                    info = svc.as_dict()
                    if info.get("start_type") == "automatic":
                        s_name = info.get("name", "")
                        d_name = info.get("display_name", s_name)
                        status_str = info.get("status", "stopped")
                        entry = {
                            "name": d_name,
                            "raw_name": s_name,
                            "command": info.get("binpath", ""),
                            "source": "Windows Service",
                            "enabled": (status_str == "running"),
                            "impact": "Medium",
                            "path": info.get("binpath", ""),
                            "essential": True,
                            "recommendation": f"Windows System Service ({s_name}). Status: {status_str}.",
                            "badge_level": "healthy",
                            "badge_text": "Keep (Service)"
                        }
                        entries.append(entry)
            except Exception as e:
                logger.debug(f"Service scan exception: {e}")

            self.progress_signal.emit(100, f"Found {len(entries)} startup items.")
            self.scan_complete_signal.emit(entries)

        except Exception as e:
            logger.error(f"Error in StartupScanWorker: {e}")
            self.progress_signal.emit(100, f"Error: {e}")
            self.scan_complete_signal.emit(entries)
