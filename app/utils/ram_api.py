import ctypes
from ctypes import wintypes
import psutil
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Windows API Constants
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_SET_QUOTA = 0x0100
PROCESS_ALL_ACCESS = 0x1F0FFF
SYSTEM_MEMORY_LIST_INFORMATION = 80
MEMORY_PURGE_STANDBY_LIST = 4


def empty_all_working_sets() -> int:
    """
    Trims the working set (unnecessary RAM pages) of all accessible processes.
    Returns the count of successfully trimmed processes.
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)

    trimmed_count = 0
    # Desired access flags
    access_rights = PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA

    for proc in psutil.process_iter(["pid"]):
        pid = proc.info["pid"]
        if pid <= 4:  # Skip System Idle and System process
            continue
        try:
            handle = kernel32.OpenProcess(access_rights, False, pid)
            if not handle:
                # Try PROCESS_ALL_ACCESS if running elevated
                handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)

            if handle:
                try:
                    if psapi.EmptyWorkingSet(handle):
                        trimmed_count += 1
                finally:
                    kernel32.CloseHandle(handle)
        except Exception:
            continue

    return trimmed_count


def purge_standby_list() -> bool:
    """
    Purges the Windows file system standby cache list via NtSetSystemInformation.
    Requires administrator privileges.
    """
    try:
        ntdll = ctypes.WinDLL("ntdll")
        command = ctypes.c_ulong(MEMORY_PURGE_STANDBY_LIST)
        status = ntdll.NtSetSystemInformation(
            SYSTEM_MEMORY_LIST_INFORMATION,
            ctypes.byref(command),
            ctypes.sizeof(command)
        )
        return status == 0
    except Exception as e:
        logger.debug(f"Failed to purge standby list: {e}")
        return False


def clean_ram() -> Dict[str, Any]:
    """
    Execute full memory optimization pipeline:
    1. Records initial memory.
    2. Trims working sets across all processes.
    3. Purges standby memory list if privileged.
    4. Records final memory and returns delta metrics.
    """
    before_mem = psutil.virtual_memory()
    before_available_mb = before_mem.available / (1024 * 1024)

    trimmed_procs = empty_all_working_sets()
    standby_purged = purge_standby_list()

    after_mem = psutil.virtual_memory()
    after_available_mb = after_mem.available / (1024 * 1024)
    freed_mb = max(0.0, after_available_mb - before_available_mb)

    return {
        "before_available_mb": round(before_available_mb, 1),
        "after_available_mb": round(after_available_mb, 1),
        "freed_mb": round(freed_mb, 1),
        "freed_gb": round(freed_mb / 1024.0, 2),
        "trimmed_processes": trimmed_procs,
        "standby_purged": standby_purged
    }
