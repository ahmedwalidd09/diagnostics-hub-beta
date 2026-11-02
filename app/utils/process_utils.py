import subprocess
from typing import Union
import psutil


def kill_process_with_fallback(pid: Union[int, str], tree: bool = False) -> bool:
    """
    Terminate a process using a robust two-tier strategy:
    Tier 1: psutil.Process(pid). If tree=True, recursively kills child processes first, then parent.
    Tier 2: If psutil fails or process not killed, fallback to Windows 'taskkill /F /PID {pid}' (plus /T if tree=True).

    Returns True if the process was successfully terminated by either tier, False otherwise.
    """
    try:
        pid_int = int(pid)
    except (ValueError, TypeError):
        return False

    killed = False

    # Tier 1: psutil termination
    try:
        p = psutil.Process(pid_int)
        if tree:
            for child in p.children(recursive=True):
                try:
                    child.kill()
                except Exception:
                    pass
        p.kill()
        killed = True
    except Exception:
        pass

    # Tier 2: taskkill command-line fallback
    if not killed:
        try:
            cmd = f"taskkill /F /PID {pid_int}" + (" /T" if tree else "")
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                killed = True
        except Exception:
            pass

    return killed
