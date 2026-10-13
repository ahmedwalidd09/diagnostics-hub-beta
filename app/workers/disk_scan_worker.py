import os
import glob
import time
import ctypes
from ctypes import wintypes
from pathlib import Path
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from app.utils.system_info import is_admin

logger = logging.getLogger(__name__)


def query_recycle_bin() -> tuple[int, int]:
    """Query Recycle Bin size and item count via shell32.SHQueryRecycleBinW."""
    try:
        class SHQUERYRBINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("i64Size", ctypes.c_int64),
                ("i64NumItems", ctypes.c_int64),
            ]

        rb_info = SHQUERYRBINFO()
        rb_info.cbSize = ctypes.sizeof(SHQUERYRBINFO)

        shell32 = ctypes.windll.shell32
        res = shell32.SHQueryRecycleBinW(None, ctypes.byref(rb_info))
        if res == 0:
            return rb_info.i64Size, rb_info.i64NumItems
    except Exception as e:
        logger.debug(f"Failed to query Recycle Bin: {e}")
    return 0, 0


class DiskScanWorker(QThread):
    """
    Scans 8 junk/cache categories for reclaimable disk space.
    Reports item count, size, and admin privilege requirements.
    """
    progress_signal = pyqtSignal(int, str)
    category_scanned_signal = pyqtSignal(dict)
    scan_complete_signal = pyqtSignal(list, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stopped = False

    def stop(self):
        self._stopped = True

    def _scan_files_older_than(self, folder_path: str, min_age_seconds: int = 3600) -> tuple[int, int, list]:
        """Scan directory files older than min_age_seconds without following symlinks."""
        file_count = 0
        total_size = 0
        file_list = []
        now = time.time()

        if not os.path.exists(folder_path):
            return 0, 0, []

        try:
            for root, _, files in os.walk(folder_path, followlinks=False):
                if self._stopped:
                    break
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        st = os.stat(fp, follow_symlinks=False)
                        if (now - st.st_mtime) >= min_age_seconds:
                            file_count += 1
                            total_size += st.st_size
                            file_list.append(fp)
                    except Exception:
                        continue
        except Exception:
            pass

        return file_count, total_size, file_list

    def run(self):
        categories = []
        admin = is_admin()
        local_appdata = os.environ.get("LOCALAPPDATA", "")

        # 1. Windows Temp Files (Older than 1 hour)
        self.progress_signal.emit(10, "Scanning Windows & User Temp files...")
        user_temp = os.environ.get("TEMP", "")
        win_temp = r"C:\Windows\Temp"
        c1, s1, fl1 = self._scan_files_older_than(user_temp, 3600)
        c2, s2, fl2 = self._scan_files_older_than(win_temp, 3600)
        cat_temp = {
            "id": "temp_files",
            "name": "Windows & User Temp Files",
            "icon": "📁",
            "count": c1 + c2,
            "bytes": s1 + s2,
            "requires_admin": False,
            "description": "Temporary workspace files older than 1 hour left behind by closed applications.",
            "paths": fl1 + fl2
        }
        categories.append(cat_temp)
        self.category_scanned_signal.emit(cat_temp)

        # 2. Browser Caches (Chrome, Edge, Firefox)
        if not self._stopped:
            self.progress_signal.emit(25, "Scanning Web Browser caches...")
            browser_paths = [
                os.path.join(local_appdata, r"Google\Chrome\User Data\Default\Cache\Cache_Data"),
                os.path.join(local_appdata, r"Microsoft\Edge\User Data\Default\Cache\Cache_Data"),
            ]
            # Firefox profiles
            ff_profiles = glob.glob(os.path.join(local_appdata, r"Mozilla\Firefox\Profiles\*\cache2\entries"))
            browser_paths.extend(ff_profiles)

            b_count, b_size, b_files = 0, 0, []
            for bp in browser_paths:
                c, s, fl = self._scan_files_older_than(bp, 0)
                b_count += c
                b_size += s
                b_files.extend(fl)

            cat_browser = {
                "id": "browser_cache",
                "name": "Web Browser Caches",
                "icon": "🌐",
                "count": b_count,
                "bytes": b_size,
                "requires_admin": False,
                "description": "Offline images and cached web scripts from Chrome, Edge, and Firefox.",
                "paths": b_files
            }
            categories.append(cat_browser)
            self.category_scanned_signal.emit(cat_browser)

        # 3. Windows Update Cache
        if not self._stopped:
            self.progress_signal.emit(40, "Scanning Windows Update staging cache...")
            upd_path = r"C:\Windows\SoftwareDistribution\Download"
            u_count, u_size, u_files = self._scan_files_older_than(upd_path, 0)
            cat_upd = {
                "id": "windows_update",
                "name": "Windows Update Cache",
                "icon": "🔄",
                "count": u_count,
                "bytes": u_size,
                "requires_admin": True,
                "description": "Previously installed Windows Update installation packages that are no longer needed.",
                "paths": u_files
            }
            categories.append(cat_upd)
            self.category_scanned_signal.emit(cat_upd)

        # 4. Recycle Bin
        if not self._stopped:
            self.progress_signal.emit(55, "Querying Recycle Bin...")
            rb_size, rb_items = query_recycle_bin()
            cat_rb = {
                "id": "recycle_bin",
                "name": "Recycle Bin",
                "icon": "🗑️",
                "count": max(0, rb_items),
                "bytes": max(0, rb_size),
                "requires_admin": False,
                "description": "Deleted files stored in the Windows Recycle Bin waiting to be purged.",
                "paths": ["__RECYCLE_BIN__"]
            }
            categories.append(cat_rb)
            self.category_scanned_signal.emit(cat_rb)

        # 5. Thumbnail Cache
        if not self._stopped:
            self.progress_signal.emit(65, "Scanning Explorer Thumbnail database...")
            thumb_dir = os.path.join(local_appdata, r"Microsoft\Windows\Explorer")
            th_count, th_size, th_files = 0, 0, []
            for tf in glob.glob(os.path.join(thumb_dir, "thumbcache_*.db")):
                try:
                    st = os.stat(tf)
                    th_count += 1
                    th_size += st.st_size
                    th_files.append(tf)
                except Exception:
                    pass
            cat_thumb = {
                "id": "thumbnail_cache",
                "name": "Windows Thumbnail Cache",
                "icon": "🖼️",
                "count": th_count,
                "bytes": th_size,
                "requires_admin": False,
                "description": "Preview thumbnail databases for File Explorer.",
                "paths": th_files
            }
            categories.append(cat_thumb)
            self.category_scanned_signal.emit(cat_thumb)

        # 6. Windows Log Files
        if not self._stopped:
            self.progress_signal.emit(75, "Searching Windows Log files...")
            log_dirs = [r"C:\Windows\Logs", r"C:\Windows\Panther"]
            l_count, l_size, l_files = 0, 0, []
            for ld in log_dirs:
                c, s, fl = self._scan_files_older_than(ld, 0)
                l_count += c
                l_size += s
                l_files.extend(fl)
            cat_logs = {
                "id": "windows_logs",
                "name": "System & Setup Log Files",
                "icon": "📜",
                "count": l_count,
                "bytes": l_size,
                "requires_admin": True,
                "description": "Historical diagnostic event logs and Windows setup traces.",
                "paths": l_files
            }
            categories.append(cat_logs)
            self.category_scanned_signal.emit(cat_logs)

        # 7. Old Windows Installations (Windows.old)
        if not self._stopped:
            self.progress_signal.emit(85, "Checking Windows.old backup directory...")
            win_old = r"C:\Windows.old"
            wo_count, wo_size, wo_files = 0, 0, []
            if os.path.exists(win_old):
                wo_count, wo_size, wo_files = self._scan_files_older_than(win_old, 0)
            cat_old = {
                "id": "windows_old",
                "name": "Previous Windows Installation (Windows.old)",
                "icon": "💾",
                "count": wo_count,
                "bytes": wo_size,
                "requires_admin": True,
                "description": "Backup from previous Windows version. Caution: Deleting prevents rolling back.",
                "paths": wo_files
            }
            categories.append(cat_old)
            self.category_scanned_signal.emit(cat_old)

        # 8. Memory Crash Dumps
        if not self._stopped:
            self.progress_signal.emit(95, "Checking System Crash Dumps...")
            dump_dirs = [r"C:\Windows\Minidump", os.path.join(local_appdata, "CrashDumps")]
            d_count, d_size, d_files = 0, 0, []
            for dd in dump_dirs:
                c, s, fl = self._scan_files_older_than(dd, 0)
                d_count += c
                d_size += s
                d_files.extend(fl)
            cat_dumps = {
                "id": "crash_dumps",
                "name": "Memory Crash Dumps",
                "icon": "💥",
                "count": d_count,
                "bytes": d_size,
                "requires_admin": True,
                "description": "BSOD minidumps and crash debug memory snapshots.",
                "paths": d_files
            }
            categories.append(cat_dumps)
            self.category_scanned_signal.emit(cat_dumps)

        total_bytes = sum(c["bytes"] for c in categories)
        total_files = sum(c["count"] for c in categories)
        summary = {
            "total_bytes": total_bytes,
            "total_gb": round(total_bytes / (1024 ** 3), 2),
            "total_files": total_files
        }

        self.progress_signal.emit(100, f"Found {summary['total_gb']} GB reclaimable space across {total_files} files.")
        self.scan_complete_signal.emit(categories, summary)
