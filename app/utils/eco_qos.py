"""
Windows EcoQoS (Efficiency Mode) and Process Priority Utilities.
Leverages Win32 SetProcessInformation with ProcessPowerThrottling to
drastically reduce CPU and memory priority of idle background applications.
"""

import ctypes
from ctypes import wintypes
import logging

logger = logging.getLogger(__name__)

# Windows Constants
PROCESS_SET_INFORMATION = 0x0200
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_POWER_THROTTLING_CURRENT_VERSION = 1
PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1
PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION = 0x4
ProcessPowerThrottling = 4  # PROCESS_INFORMATION_CLASS enum


class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
    _fields_ = [
        ("Version", wintypes.DWORD),
        ("ControlMask", wintypes.DWORD),
        ("StateMask", wintypes.DWORD),
    ]


def set_process_eco_qos(pid: int, enable: bool = True) -> bool:
    """
    Enables or disables Windows Efficiency Mode (EcoQoS) on a process by PID.
    Under EcoQoS, Windows schedules threads on efficiency cores and throttles clock speeds.
    """
    if pid <= 4:
        return False

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    h_proc = kernel32.OpenProcess(PROCESS_SET_INFORMATION, False, pid)
    if not h_proc:
        return False

    try:
        state = PROCESS_POWER_THROTTLING_STATE()
        state.Version = PROCESS_POWER_THROTTLING_CURRENT_VERSION
        state.ControlMask = PROCESS_POWER_THROTTLING_EXECUTION_SPEED | PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION
        state.StateMask = (PROCESS_POWER_THROTTLING_EXECUTION_SPEED | PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION) if enable else 0

        success = kernel32.SetProcessInformation(
            h_proc,
            ProcessPowerThrottling,
            ctypes.byref(state),
            ctypes.sizeof(state)
        )
        return bool(success)
    except Exception as e:
        logger.debug(f"Failed to set EcoQoS for PID {pid}: {e}")
        return False
    finally:
        kernel32.CloseHandle(h_proc)


def trim_process_working_set(pid: int) -> bool:
    """
    Trims the working set of a single process, releasing its physical RAM pages.
    """
    if pid <= 4:
        return False

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)

    access = 0x0400 | 0x0100  # PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA
    h_proc = kernel32.OpenProcess(access, False, pid)
    if not h_proc:
        return False

    try:
        return bool(psapi.EmptyWorkingSet(h_proc))
    except Exception:
        return False
    finally:
        kernel32.CloseHandle(h_proc)
