import logging
from PyQt6.QtCore import QThread, pyqtSignal
from app.utils.ram_api import clean_ram
from app.database import db

logger = logging.getLogger(__name__)


class RamCleanWorker(QThread):
    """
    Background worker that invokes Windows memory optimization APIs
    without freezing the main application GUI.
    """
    cleaning_finished_signal = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            result = clean_ram()
            # Record baseline in SQLite
            db.record_memory_baseline(
                total_mb=result.get("before_available_mb", 0) + result.get("freed_mb", 0),
                used_mb=result.get("before_available_mb", 0),
                free_mb=result.get("after_available_mb", 0)
            )
            self.cleaning_finished_signal.emit(result)
        except Exception as e:
            logger.error(f"Error during RAM cleaning: {e}")
            self.cleaning_finished_signal.emit({
                "before_available_mb": 0.0,
                "after_available_mb": 0.0,
                "freed_mb": 0.0,
                "freed_gb": 0.0,
                "trimmed_processes": 0,
                "standby_purged": False,
                "error": str(e)
            })
