import subprocess
import time
import shutil
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

CREATE_NO_WINDOW = 0x08000000

# Pre-configured hidden STARTUPINFO for Windows
_startupinfo = subprocess.STARTUPINFO()
_startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
_startupinfo.wShowWindow = 0  # SW_HIDE

# Cache to avoid invoking nvidia-smi every single 1000ms tick
_cached_gpu_info: List[Dict[str, Any]] = []
_last_gpu_query_time = 0.0

# Patch GPUtil if imported so no unshielded Popen can ever be invoked
try:
    import GPUtil
    if hasattr(GPUtil, "Popen"):
        _orig_gputil_popen = GPUtil.Popen

        def _silent_gputil_popen(*args, **kwargs):
            kwargs["creationflags"] = CREATE_NO_WINDOW
            kwargs["startupinfo"] = _startupinfo
            return _orig_gputil_popen(*args, **kwargs)

        GPUtil.Popen = _silent_gputil_popen
except Exception:
    pass


def get_gpu_stats() -> List[Dict[str, Any]]:
    """
    Retrieve GPU telemetry completely silently with zero console windows.
    Queries nvidia-smi with CREATE_NO_WINDOW + SW_HIDE flags.
    Caches for 5.0 seconds to minimize CPU cycles.
    """
    global _cached_gpu_info, _last_gpu_query_time

    now = time.time()
    if _cached_gpu_info and (now - _last_gpu_query_time < 5.0):
        return _cached_gpu_info

    gpus = []

    # Method 1: Query nvidia-smi with explicit window suppression flags
    nvidia_smi = shutil.which("nvidia-smi") or "nvidia-smi"
    try:
        cmd = [
            nvidia_smi,
            "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
            "--format=csv,noheader,nounits"
        ]
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=CREATE_NO_WINDOW,
            startupinfo=_startupinfo
        )
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    try:
                        name = parts[0]
                        load = float(parts[1]) if parts[1] != "[Not Supported]" else 0.0
                        mem_used = float(parts[2]) if parts[2] != "[Not Supported]" else 0.0
                        mem_total = float(parts[3]) if parts[3] != "[Not Supported]" else 0.0
                        temp = float(parts[4]) if parts[4] != "[Not Supported]" else 0.0

                        gpus.append({
                            "name": name,
                            "load": round(load, 1),
                            "memory_used": round(mem_used, 1),
                            "memory_total": round(mem_total, 1),
                            "temperature": round(temp, 1)
                        })
                    except (ValueError, IndexError):
                        continue
    except Exception as e:
        logger.debug(f"Silent nvidia-smi query: {e}")

    # Method 2: If no dedicated NVIDIA found, query via WMI Win32_VideoController
    if not gpus:
        try:
            import wmi
            c = wmi.WMI()
            for v in c.Win32_VideoController():
                name = getattr(v, "Name", "")
                if name:
                    ram_mb = 0.0
                    raw_ram = getattr(v, "AdapterRAM", 0)
                    if raw_ram and raw_ram > 0:
                        ram_mb = round(raw_ram / (1024 * 1024), 0)

                    gpus.append({
                        "name": name,
                        "load": 0.0,
                        "memory_used": 0.0,
                        "memory_total": ram_mb,
                        "temperature": 0.0
                    })
        except Exception:
            pass

    _cached_gpu_info = gpus
    # If WMI was used or no GPUs found, cache longer to prevent COM overhead
    _last_gpu_query_time = now if ("NVIDIA" in str(gpus)) else (now + 10.0)
    return gpus
