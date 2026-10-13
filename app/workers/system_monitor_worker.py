import time
import psutil
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from app.utils.system_info import get_cpu_brand, get_uptime_str, get_static_system_info
from app.utils.wmi_utils import get_cpu_temperature
from app.utils.gpu_utils import get_gpu_stats
from app.utils.ram_api import clean_ram
from app.settings_manager import settings

logger = logging.getLogger(__name__)


class SystemMonitorWorker(QThread):
    """
    Continuous 1-second background telemetry polling thread.
    Emits data_signal with comprehensive metrics every tick.
    Throttles heavy disk partition and temperature WMI polling to eliminate CPU drag.
    """
    data_signal = pyqtSignal(dict)
    auto_clean_signal = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._static_info = get_static_system_info()
        try:
            self._last_disk_io = psutil.disk_io_counters()
        except Exception:
            self._last_disk_io = None

        try:
            self._last_net_io = psutil.net_io_counters()
        except Exception:
            self._last_net_io = None

        self._last_poll_time = time.time()
        self._last_auto_clean_time = 0.0

        # Caching for heavy disk partition and temperature metrics
        self._cached_partitions = []
        self._last_partition_poll_time = 0.0
        self._cached_cpu_temp = None
        self._last_temp_poll_time = 0.0

    def stop(self):
        self._running = False
        self.wait(3000)

    def run(self):
        # Initialize COM once for this thread's lifetime
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass

        # Warm up CPU percent counter
        try:
            psutil.cpu_percent(percpu=True)
        except Exception:
            pass

        try:
            while self._running:
                try:
                    curr_time = time.time()
                    time_delta = max(0.5, curr_time - self._last_poll_time)

                    # CPU Metrics
                    try:
                        cpu_total = psutil.cpu_percent(interval=None)
                        per_core = psutil.cpu_percent(percpu=True)
                    except Exception:
                        cpu_total = 0.0
                        per_core = [0.0]

                    try:
                        cpu_freq = psutil.cpu_freq()
                    except Exception:
                        cpu_freq = None

                    # CPU Temperature: throttled to 10 seconds
                    if (curr_time - self._last_temp_poll_time >= 10.0) or (self._cached_cpu_temp is None):
                        self._cached_cpu_temp = get_cpu_temperature()
                        self._last_temp_poll_time = curr_time
                    cpu_temp = self._cached_cpu_temp

                    # Memory Metrics
                    vmem = psutil.virtual_memory()
                    try:
                        swap = psutil.swap_memory()
                    except Exception:
                        class DummySwap:
                            percent = 0.0
                            used = 0
                            total = 0
                        swap = DummySwap()

                    # Disk I/O Deltas: real-time delta every second (<0.1ms overhead)
                    disk_read_mbs = 0.0
                    disk_write_mbs = 0.0
                    try:
                        curr_disk_io = psutil.disk_io_counters()
                        if curr_disk_io and self._last_disk_io:
                            disk_read_mbs = max(0.0, (curr_disk_io.read_bytes - self._last_disk_io.read_bytes) / time_delta / (1024 * 1024))
                            disk_write_mbs = max(0.0, (curr_disk_io.write_bytes - self._last_disk_io.write_bytes) / time_delta / (1024 * 1024))
                        self._last_disk_io = curr_disk_io
                    except Exception:
                        pass

                    # Partitions: throttled to every 12 seconds to prevent mechanical HDD spin-up stalls
                    if (curr_time - self._last_partition_poll_time >= 12.0) or not self._cached_partitions:
                        partitions_data = []
                        for part in psutil.disk_partitions(all=False):
                            if "cdrom" in part.opts or part.fstype == "":
                                continue
                            try:
                                usage = psutil.disk_usage(part.mountpoint)
                                partitions_data.append({
                                    "device": part.device,
                                    "mountpoint": part.mountpoint,
                                    "fstype": part.fstype,
                                    "total_gb": round(usage.total / (1024 ** 3), 1),
                                    "used_gb": round(usage.used / (1024 ** 3), 1),
                                    "free_gb": round(usage.free / (1024 ** 3), 1),
                                    "percent": usage.percent
                                })
                            except (PermissionError, OSError):
                                continue
                        self._cached_partitions = partitions_data
                        self._last_partition_poll_time = curr_time
                    else:
                        partitions_data = self._cached_partitions

                    # Network I/O Deltas: real-time delta every second
                    net_down_kbs = 0.0
                    net_up_kbs = 0.0
                    curr_net_io = None
                    try:
                        curr_net_io = psutil.net_io_counters()
                        if curr_net_io and self._last_net_io:
                            net_down_kbs = max(0.0, (curr_net_io.bytes_recv - self._last_net_io.bytes_recv) / time_delta / 1024.0)
                            net_up_kbs = max(0.0, (curr_net_io.bytes_sent - self._last_net_io.bytes_sent) / time_delta / 1024.0)
                        self._last_net_io = curr_net_io
                    except Exception:
                        pass

                    # GPU Metrics (Cached internally for 8 seconds)
                    gpu_list = get_gpu_stats()

                    # Battery Metrics
                    battery = psutil.sensors_battery()
                    battery_data = None
                    if battery:
                        battery_data = {
                            "percent": battery.percent,
                            "power_plugged": battery.power_plugged,
                            "secsleft": battery.secsleft
                        }

                    # Auto RAM Clean Check
                    if settings.get("ram_autoclean_enabled", False):
                        thresh = float(settings.get("ram_autoclean_threshold", 85.0))
                        if vmem.percent >= thresh and (curr_time - self._last_auto_clean_time >= 300):
                            self._last_auto_clean_time = curr_time
                            result = clean_ram()
                            self.auto_clean_signal.emit(result)

                    # Package Payload
                    payload = {
                        "timestamp": curr_time,
                        "cpu": {
                            "percent": cpu_total,
                            "per_core": per_core,
                            "temp": cpu_temp,
                            "model": self._static_info["cpu_brand"],
                            "freq_current": round(cpu_freq.current, 0) if cpu_freq else 0,
                            "freq_max": round(cpu_freq.max, 0) if cpu_freq else 0
                        },
                        "ram": {
                            "percent": vmem.percent,
                            "used_gb": round(vmem.used / (1024 ** 3), 1),
                            "total_gb": round(vmem.total / (1024 ** 3), 1),
                            "available_gb": round(vmem.available / (1024 ** 3), 1),
                            "swap_percent": swap.percent,
                            "swap_used_gb": round(swap.used / (1024 ** 3), 1),
                            "swap_total_gb": round(swap.total / (1024 ** 3), 1)
                        },
                        "disk": {
                            "partitions": partitions_data,
                            "read_mbs": round(disk_read_mbs, 2),
                            "write_mbs": round(disk_write_mbs, 2)
                        },
                        "gpu": gpu_list,
                        "network": {
                            "down_kbs": round(net_down_kbs, 1),
                            "up_kbs": round(net_up_kbs, 1),
                            "total_recv_mb": round((curr_net_io.bytes_recv if curr_net_io else 0) / (1024 ** 2), 1),
                            "total_sent_mb": round((curr_net_io.bytes_sent if curr_net_io else 0) / (1024 ** 2), 1)
                        },
                        "battery": battery_data,
                        "system": {
                            "os": self._static_info["os"],
                            "hostname": self._static_info["hostname"],
                            "username": self._static_info["username"],
                            "uptime": get_uptime_str(),
                            "is_admin": self._static_info["is_admin"]
                        }
                    }

                    self.data_signal.emit(payload)
                    self._last_poll_time = curr_time

                except Exception as e:
                    logger.error(f"Error in SystemMonitorWorker loop: {e}")

                for _ in range(10):
                    if not self._running:
                        break
                    time.sleep(0.1)

        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass
