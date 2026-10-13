import os
import time
import shutil
import ctypes
import logging
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

# Recycle bin flags: no confirmation, no progress UI, no sound
SHERB_NOCONFIRMATION = 0x00000001
SHERB_NOPROGRESSUI = 0x00000002
SHERB_NOSOUND = 0x00000004


class DiskCleanWorker(QThread):
    """
    Safely executes deletion of user-selected junk file categories.
    Implements hardcoded safeguards against accidental system file removal.
    """
    progress_signal = pyqtSignal(int, str)
    clean_complete_signal = pyqtSignal(dict)

    def __init__(self, selected_categories: list, parent=None):
        super().__init__(parent)
        self.selected_categories = selected_categories
        self._stopped = False

    def stop(self):
        self._stopped = True

    def _is_safe_to_delete(self, file_path: str, category_id: str) -> bool:
        """Enforce strict deletion safety rules."""
        if not file_path or not os.path.exists(file_path):
            return False

        # Never follow symlinks
        if os.path.islink(file_path):
            return False

        norm_path = os.path.abspath(file_path).lower()

        # Never delete critical system binaries from Windows/System32
        if r"\windows\system32" in norm_path or r"\windows\syswow64" in norm_path:
            return False

        # If in temp files, must be older than 1 hour
        if category_id == "temp_files":
            try:
                st = os.stat(file_path, follow_symlinks=False)
                if (time.time() - st.st_mtime) < 3600:
                    return False
            except Exception:
                return False

        # Do not delete executable files inside Windows root
        if norm_path.startswith(r"c:\windows") and norm_path.endswith((".exe", ".sys", ".dll")):
            # Unless inside SoftwareDistribution\Download or Logs
            if r"\softwaredistribution\download" not in norm_path and r"\windows\logs" not in norm_path:
                return False

        return True

    def run(self):
        cleaned_bytes = 0
        cleaned_categories_count = 0
        skipped_count = 0
        total_cats = len(self.selected_categories)

        for cat_idx, cat in enumerate(self.selected_categories):
            if self._stopped:
                break

            cat_id = cat.get("id")
            cat_name = cat.get("name")
            paths = cat.get("paths", [])

            self.progress_signal.emit(
                int((cat_idx / max(1, total_cats)) * 100),
                f"Cleaning {cat_name}..."
            )

            if cat_id == "recycle_bin":
                # Empty Recycle Bin via Shell API
                try:
                    flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
                    res = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
                    if res == 0:
                        cleaned_bytes += cat.get("bytes", 0)
                except Exception as e:
                    logger.debug(f"Failed to empty recycle bin: {e}")
                cleaned_categories_count += 1
                continue

            file_count = len(paths)
            cat_cleaned_bytes = 0

            for f_idx, file_path in enumerate(paths):
                if self._stopped:
                    break

                if not self._is_safe_to_delete(file_path, cat_id):
                    skipped_count += 1
                    continue

                try:
                    f_size = os.path.getsize(file_path)
                    os.remove(file_path)
                    cat_cleaned_bytes += f_size
                    cleaned_bytes += f_size
                except (PermissionError, OSError):
                    skipped_count += 1

                if f_idx % 20 == 0:
                    self.progress_signal.emit(
                        int((cat_idx / max(1, total_cats)) * 100),
                        f"Cleaning {cat_name}... ({f_idx + 1}/{file_count})"
                    )

            cleaned_categories_count += 1

        summary = {
            "cleaned_bytes": cleaned_bytes,
            "cleaned_gb": round(cleaned_bytes / (1024 ** 3), 2),
            "cleaned_mb": round(cleaned_bytes / (1024 ** 2), 1),
            "categories_cleaned": cleaned_categories_count,
            "skipped_count": skipped_count
        }

        self.progress_signal.emit(100, f"Cleaned {summary['cleaned_gb']} GB. ({skipped_count} files in-use skipped).")
        self.clean_complete_signal.emit(summary)
