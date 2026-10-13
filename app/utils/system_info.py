import os
import sys
import platform
import ctypes
import psutil
from datetime import datetime
from typing import Dict, Any

try:
    import cpuinfo
except ImportError:
    cpuinfo = None


def is_admin() -> bool:
    """Check if the current process has administrator privileges on Windows."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def enable_debug_privilege() -> bool:
    """Enable SeDebugPrivilege in current process token if running elevated."""
    try:
        advapi32 = ctypes.windll.advapi32
        kernel32 = ctypes.windll.kernel32
        TOKEN_ADJUST_PRIVILEGES = 0x0020
        TOKEN_QUERY = 0x0008
        SE_PRIVILEGE_ENABLED = 0x00000002

        class LUID(ctypes.Structure):
            _fields_ = [("LowPart", ctypes.c_ulong), ("HighPart", ctypes.c_long)]

        class LUID_AND_ATTRIBUTES(ctypes.Structure):
            _fields_ = [("Luid", LUID), ("Attributes", ctypes.c_ulong)]

        class TOKEN_PRIVILEGES(ctypes.Structure):
            _fields_ = [("PrivilegeCount", ctypes.c_ulong), ("Privileges", LUID_AND_ATTRIBUTES * 1)]

        h_token = ctypes.wintypes.HANDLE()
        if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(h_token)):
            return False

        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, "SeDebugPrivilege", ctypes.byref(luid)):
            kernel32.CloseHandle(h_token)
            return False

        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED

        advapi32.AdjustTokenPrivileges(h_token, False, ctypes.byref(tp), 0, None, None)
        kernel32.CloseHandle(h_token)
        return True
    except Exception:
        return False


def restart_as_admin() -> bool:
    """Relaunch the current application with UAC elevation prompt."""
    try:
        script = os.path.abspath(sys.argv[0])
        params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        if getattr(sys, "frozen", False):
            # PyInstaller executable
            executable = sys.executable
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
        else:
            # Python script
            executable = sys.executable
            full_params = f'"{script}" {params}'.strip()
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, full_params, None, 1)

        if ret > 32:
            sys.exit(0)
            return True
        return False
    except Exception as e:
        print(f"Failed to elevate permissions: {e}")
        return False


def get_cpu_brand() -> str:
    """Retrieve full CPU brand string safely."""
    try:
        if cpuinfo:
            info = cpuinfo.get_cpu_info()
            if "brand_raw" in info and info["brand_raw"]:
                return info["brand_raw"]
    except Exception:
        pass
    return platform.processor() or "Unknown CPU"


def get_uptime_str() -> str:
    """Calculate and format system uptime as 'X days, Y hours, Z minutes'."""
    try:
        boot_timestamp = psutil.boot_time()
        uptime_seconds = int(datetime.now().timestamp() - boot_timestamp)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0 or days > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        return ", ".join(parts)
    except Exception:
        return "Unknown"


def get_static_system_info() -> Dict[str, Any]:
    """Collect static system specifications for display."""
    total_ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    return {
        "os": platform.platform(),
        "hostname": platform.node(),
        "username": os.getlogin() if hasattr(os, "getlogin") else os.environ.get("USERNAME", "User"),
        "cpu_brand": get_cpu_brand(),
        "physical_cores": psutil.cpu_count(logical=False) or 1,
        "logical_cores": psutil.cpu_count(logical=True) or 1,
        "total_ram_gb": total_ram_gb,
        "is_admin": is_admin()
    }
