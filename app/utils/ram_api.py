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
MEMORY_FLUSH_MODIFIED_LIST = 2
MEMORY_PURGE_MODIFIED_LIST = 3
MEMORY_PURGE_STANDBY_LIST = 4


class PERFORMANCE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("CommitTotal", ctypes.c_size_t),
        ("CommitLimit", ctypes.c_size_t),
        ("CommitPeak", ctypes.c_size_t),
        ("PhysicalTotal", ctypes.c_size_t),
        ("PhysicalAvailable", ctypes.c_size_t),
        ("SystemCache", ctypes.c_size_t),
        ("KernelTotal", ctypes.c_size_t),
        ("KernelPaged", ctypes.c_size_t),
        ("KernelNonpaged", ctypes.c_size_t),
        ("PageSize", ctypes.c_size_t),
        ("HandleCount", wintypes.DWORD),
        ("ProcessCount", wintypes.DWORD),
        ("ThreadCount", wintypes.DWORD),
    ]


def get_kernel_performance_info() -> Dict[str, Any]:
    """
    Extracts deep kernel memory metrics via Win32 GetPerformanceInfo.
    Reveals Paged/Non-Paged pool allocations (crucial for diagnosing driver memory leaks)
    and System Cache size.
    """
    try:
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        perf_info = PERFORMANCE_INFORMATION()
        perf_info.cb = ctypes.sizeof(PERFORMANCE_INFORMATION)

        if psapi.GetPerformanceInfo(ctypes.byref(perf_info), perf_info.cb):
            page_size = perf_info.PageSize or 4096
            kernel_paged_mb = round((perf_info.KernelPaged * page_size) / (1024 * 1024), 1)
            kernel_nonpaged_mb = round((perf_info.KernelNonpaged * page_size) / (1024 * 1024), 1)
            system_cache_mb = round((perf_info.SystemCache * page_size) / (1024 * 1024), 1)
            commit_total_gb = round((perf_info.CommitTotal * page_size) / (1024 ** 3), 2)
            commit_limit_gb = round((perf_info.CommitLimit * page_size) / (1024 ** 3), 2)
            commit_pct = round((perf_info.CommitTotal / (perf_info.CommitLimit or 1)) * 100.0, 1)

            # A non-paged pool exceeding 800 MB is almost always a leaking driver
            # (e.g. network packet filter or GPU driver leak).
            nonpaged_leak_warning = kernel_nonpaged_mb > 800.0

            return {
                "kernel_paged_mb": kernel_paged_mb,
                "kernel_nonpaged_mb": kernel_nonpaged_mb,
                "system_cache_mb": system_cache_mb,
                "commit_total_gb": commit_total_gb,
                "commit_limit_gb": commit_limit_gb,
                "commit_percent": commit_pct,
                "nonpaged_warning": nonpaged_leak_warning,
                "handles": perf_info.HandleCount,
                "threads": perf_info.ThreadCount,
                "processes": perf_info.ProcessCount
            }
    except Exception as e:
        logger.debug(f"Failed to query GetPerformanceInfo: {e}")

    # Fallback to zeroed stats
    return {
        "kernel_paged_mb": 0.0,
        "kernel_nonpaged_mb": 0.0,
        "system_cache_mb": 0.0,
        "commit_total_gb": 0.0,
        "commit_limit_gb": 0.0,
        "commit_percent": 0.0,
        "nonpaged_warning": False,
        "handles": 0,
        "threads": 0,
        "processes": 0
    }


def empty_all_working_sets() -> int:
    """
    Trims the working set (unnecessary RAM pages) of all accessible processes.
    Returns the count of successfully trimmed processes.
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)

    trimmed_count = 0
    access_rights = PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA

    for proc in psutil.process_iter(["pid"]):
        pid = proc.info["pid"]
        if pid <= 4:
            continue
        try:
            handle = kernel32.OpenProcess(access_rights, False, pid)
            if not handle:
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


def purge_modified_list() -> bool:
    """
    Flushes and purges the Windows modified page list to disk, releasing frame allocations.
    Requires administrator privileges.
    """
    try:
        ntdll = ctypes.WinDLL("ntdll")
        command = ctypes.c_ulong(MEMORY_PURGE_MODIFIED_LIST)
        status = ntdll.NtSetSystemInformation(
            SYSTEM_MEMORY_LIST_INFORMATION,
            ctypes.byref(command),
            ctypes.sizeof(command)
        )
        return status == 0
    except Exception as e:
        logger.debug(f"Failed to purge modified list: {e}")
        return False


def clean_ram() -> Dict[str, Any]:
    """
    Standard memory optimization pipeline:
    1. Records initial memory.
    2. Trims working sets across all user processes.
    3. Purges standby memory list if elevated.
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


def deep_clean_ram() -> Dict[str, Any]:
    """
    Full multi-stage memory optimization pipeline:
    Stage 1: Working set compression across user-space processes.
    Stage 2: Standby memory list purge.
    Stage 3: Modified page list purge.
    """
    before_mem = psutil.virtual_memory()
    before_available_mb = before_mem.available / (1024 * 1024)

    trimmed_procs = empty_all_working_sets()
    standby_purged = purge_standby_list()
    modified_purged = purge_modified_list()

    after_mem = psutil.virtual_memory()
    after_available_mb = after_mem.available / (1024 * 1024)
    freed_mb = max(0.0, after_available_mb - before_available_mb)

    return {
        "before_available_mb": round(before_available_mb, 1),
        "after_available_mb": round(after_available_mb, 1),
        "freed_mb": round(freed_mb, 1),
        "freed_gb": round(freed_mb / 1024.0, 2),
        "trimmed_processes": trimmed_procs,
        "standby_purged": standby_purged,
        "modified_purged": modified_purged
    }
