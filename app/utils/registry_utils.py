import os
import sys
import winreg
import csv
import io
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

RUN_KEYS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU_Run"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU_RunOnce"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM_Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKLM_RunOnce"),
]


CREATE_NO_WINDOW = 0x08000000
_startupinfo = subprocess.STARTUPINFO()
_startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
_startupinfo.wShowWindow = 0  # SW_HIDE


def resolve_lnk_target(lnk_path: str) -> str:
    """Resolve Windows shortcut (.lnk) destination path."""
    try:
        import pythoncom
        pythoncom.CoInitialize()
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(lnk_path)
        target = str(shortcut.TargetPath)
        if target:
            return target
    except Exception:
        pass

    try:
        cmd = f'(New-Object -ComObject WScript.Shell).CreateShortcut("{lnk_path}").TargetPath'
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=CREATE_NO_WINDOW,
            startupinfo=_startupinfo
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return lnk_path


def estimate_exe_impact(exe_path: str) -> str:
    """Estimate impact based on file size if path exists."""
    clean_path = exe_path.strip().strip('"').split(" -")[0].split(" /")[0]
    if os.path.exists(clean_path):
        try:
            size_mb = os.path.getsize(clean_path) / (1024 * 1024)
            if size_mb > 50:
                return "High"
            elif size_mb > 10:
                return "Medium"
            return "Low"
        except Exception:
            pass
    return "Medium"


def get_registry_startup_entries() -> List[Dict[str, Any]]:
    """Enumerate startup applications in HKCU and HKLM Run/RunOnce registry keys."""
    entries = []
    for root_hkey, subkey_path, source_name in RUN_KEYS:
        is_user = (root_hkey == winreg.HKEY_CURRENT_USER)
        try:
            with winreg.OpenKey(root_hkey, subkey_path, 0, winreg.KEY_READ) as key:
                count = winreg.QueryInfoKey(key)[1]
                for i in range(count):
                    try:
                        name, command, _ = winreg.EnumValue(key, i)
                        is_disabled = name.startswith("DISABLED_")
                        display_name = name[9:] if is_disabled else name
                        entries.append({
                            "name": display_name,
                            "raw_name": name,
                            "command": command,
                            "source": "Registry",
                            "registry_root": "HKCU" if is_user else "HKLM",
                            "registry_key": subkey_path,
                            "enabled": not is_disabled,
                            "impact": estimate_exe_impact(command),
                            "path": command
                        })
                    except OSError:
                        continue
        except OSError:
            # Key might not exist or access denied
            continue
    return entries


def toggle_registry_entry(entry: Dict[str, Any], enable: bool) -> bool:
    """Toggle a registry startup item between enabled and disabled by renaming."""
    root_hkey = winreg.HKEY_CURRENT_USER if entry.get("registry_root") == "HKCU" else winreg.HKEY_LOCAL_MACHINE
    subkey_path = entry.get("registry_key", r"Software\Microsoft\Windows\CurrentVersion\Run")
    raw_name = entry.get("raw_name", entry.get("name"))
    command = entry.get("command", "")

    try:
        with winreg.OpenKey(root_hkey, subkey_path, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                target_name = entry["name"]
                winreg.SetValueEx(key, target_name, 0, winreg.REG_SZ, command)
                if raw_name != target_name:
                    try:
                        winreg.DeleteValue(key, raw_name)
                    except OSError:
                        pass
            else:
                target_name = f"DISABLED_{entry['name']}"
                winreg.SetValueEx(key, target_name, 0, winreg.REG_SZ, command)
                if raw_name != target_name:
                    try:
                        winreg.DeleteValue(key, raw_name)
                    except OSError:
                        pass
        return True
    except Exception as e:
        logger.error(f"Failed to toggle registry entry {entry.get('name')}: {e}")
        return False


def get_startup_folder_entries() -> List[Dict[str, Any]]:
    """Enumerate shortcuts in per-user and all-users Startup folders."""
    entries = []
    user_startup = Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup"
    common_startup = Path(os.environ.get("PROGRAMDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup"

    folders = [
        (user_startup, "User Startup Folder"),
        (common_startup, "System Startup Folder")
    ]

    for folder, src_label in folders:
        if not folder.exists():
            continue

        # Check active items
        for item in folder.glob("*.lnk"):
            target = resolve_lnk_target(str(item))
            entries.append({
                "name": item.stem,
                "raw_name": item.name,
                "command": target,
                "source": "Startup Folder",
                "folder_path": str(folder),
                "file_path": str(item),
                "enabled": True,
                "impact": estimate_exe_impact(target),
                "path": target
            })

        # Check disabled items inside Disabled/ folder
        disabled_dir = folder / "Disabled"
        if disabled_dir.exists():
            for item in disabled_dir.glob("*.lnk"):
                target = resolve_lnk_target(str(item))
                entries.append({
                    "name": item.stem,
                    "raw_name": item.name,
                    "command": target,
                    "source": "Startup Folder",
                    "folder_path": str(folder),
                    "file_path": str(item),
                    "enabled": False,
                    "impact": estimate_exe_impact(target),
                    "path": target
                })

    return entries


def toggle_startup_folder_entry(entry: Dict[str, Any], enable: bool) -> bool:
    """Toggle a startup folder shortcut by moving into/out of Disabled/ subfolder."""
    try:
        file_path = Path(entry["file_path"])
        folder_path = Path(entry["folder_path"])
        disabled_dir = folder_path / "Disabled"
        disabled_dir.mkdir(exist_ok=True)

        if enable:
            target_path = folder_path / file_path.name
            if file_path.exists() and file_path != target_path:
                file_path.rename(target_path)
        else:
            target_path = disabled_dir / file_path.name
            if file_path.exists() and file_path != target_path:
                file_path.rename(target_path)
        return True
    except Exception as e:
        logger.error(f"Failed to toggle startup folder entry: {e}")
        return False


def get_task_scheduler_entries() -> List[Dict[str, Any]]:
    """Enumerate logon scheduled tasks via schtasks."""
    entries = []
    try:
        proc = subprocess.run(
            ["schtasks", "/query", "/fo", "CSV", "/v"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=10,
            creationflags=CREATE_NO_WINDOW,
            startupinfo=_startupinfo
        )
        if proc.returncode == 0:
            reader = csv.reader(io.StringIO(proc.stdout))
            headers = next(reader, None)
            if headers:
                col_taskname = next((i for i, h in enumerate(headers) if "taskname" in h.lower()), 0)
                col_status = next((i for i, h in enumerate(headers) if "status" in h.lower()), -1)
                col_trigger = next((i for i, h in enumerate(headers) if "trigger" in h.lower()), -1)
                col_task_to_run = next((i for i, h in enumerate(headers) if "task to run" in h.lower() or "action" in h.lower()), -1)

                for row in reader:
                    if len(row) <= max(col_taskname, col_status, col_trigger):
                        continue
                    trigger = row[col_trigger] if col_trigger != -1 else ""
                    if "logon" in trigger.lower():
                        task_name = row[col_taskname]
                        status = row[col_status] if col_status != -1 else "Ready"
                        cmd = row[col_task_to_run] if col_task_to_run != -1 and col_task_to_run < len(row) else ""
                        is_enabled = "disabled" not in status.lower()
                        short_name = task_name.split("\\")[-1] or task_name

                        entries.append({
                            "name": short_name,
                            "raw_name": task_name,
                            "command": cmd,
                            "source": "Scheduled Task",
                            "enabled": is_enabled,
                            "impact": estimate_exe_impact(cmd),
                            "path": cmd
                        })
    except Exception as e:
        logger.debug(f"Failed to query scheduled tasks: {e}")
    return entries


def toggle_task_scheduler_entry(task_name: str, enable: bool) -> bool:
    """Enable or disable scheduled task via schtasks CLI."""
    flag = "/enable" if enable else "/disable"
    try:
        res = subprocess.run(
            ["schtasks", "/change", "/tn", task_name, flag],
            capture_output=True,
            timeout=5,
            creationflags=CREATE_NO_WINDOW,
            startupinfo=_startupinfo
        )
        return res.returncode == 0
    except Exception as e:
        logger.error(f"Failed to toggle task {task_name}: {e}")
        return False


def disable_windows_widgets() -> dict:
    """
    Permanently disable Windows 11 Widgets:
    1. Terminate running WidgetService / Widgets processes.
    2. Set HKLM / HKCU Group Policy: AllowNewsAndInterests = 0.
    3. Hide taskbar widget button: TaskbarDa = 0.
    4. Remove WebExperience and WidgetsPlatformRuntime Appx packages.
    """
    results = {"killed": False, "policy_applied": False, "packages_removed": False}
    # 1. Kill processes
    try:
        subprocess.run(
            "taskkill /F /IM WidgetService.exe /IM Widgets.exe",
            shell=True,
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
            startupinfo=_startupinfo
        )
        results["killed"] = True
    except Exception:
        pass

    # 2. Registry Policies
    try:
        # HKCU Policies
        for subkey in [r"Software\Policies\Microsoft\Dsh", r"Software\Policies\Microsoft\Windows\Windows Feeds"]:
            try:
                k = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(k, "AllowNewsAndInterests", 0, winreg.REG_DWORD, 0)
                winreg.SetValueEx(k, "EnableFeeds", 0, winreg.REG_DWORD, 0)
                winreg.CloseKey(k)
            except Exception:
                pass

        # HKLM Policies (if running elevated)
        for subkey in [r"SOFTWARE\Policies\Microsoft\Dsh", r"SOFTWARE\Policies\Microsoft\Windows\Windows Feeds"]:
            try:
                k = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, subkey, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(k, "AllowNewsAndInterests", 0, winreg.REG_DWORD, 0)
                winreg.SetValueEx(k, "EnableFeeds", 0, winreg.REG_DWORD, 0)
                winreg.CloseKey(k)
                results["policy_applied"] = True
            except Exception:
                pass

        # Explorer taskbar toggle
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(k, "TaskbarDa", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(k)
        except Exception:
            pass

    except Exception:
        pass

    # 3. Appx removal
    try:
        cmd = 'Get-AppxPackage *WebExperience*, *WidgetsPlatformRuntime* | Remove-AppxPackage -ErrorAction SilentlyContinue'
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            shell=True,
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
            startupinfo=_startupinfo
        )
        results["packages_removed"] = True
    except Exception:
        pass

    return results
