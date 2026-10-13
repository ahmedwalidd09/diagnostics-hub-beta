import time
import psutil
import logging
from collections import deque
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class RamMonitorWorker(QThread):
    """
    Dedicated background worker for RAM telemetry, top memory consumers,
    and 5-minute memory leak detection.
    Completely isolates all process iterations from the GUI thread.
    """
    ram_data_signal = pyqtSignal(dict, list, list)  # (overview, top_consumers, leaking_procs)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._active = False
        self._history_30s = {}     # pid -> (rss_mb, timestamp)
        self._leak_buffers = {}    # pid -> deque of (timestamp, rss_mb)

    def set_active(self, active: bool):
        """Throttle polling when the RAM Cleaner tab is not visible."""
        self._active = active

    def stop(self):
        self._running = False
        self.wait(3000)

    def run(self):
        while self._running:
            if not self._active:
                for _ in range(10):
                    if not self._running or self._active:
                        break
                    time.sleep(0.1)
                continue

            try:
                now = time.time()

                # 1. Virtual memory & Swap
                vmem = psutil.virtual_memory()
                try:
                    swap = psutil.swap_memory()
                except Exception:
                    class DummySwap:
                        percent = 0.0
                        used = 0
                        total = 0
                    swap = DummySwap()

                total_ram_mb = max(1.0, vmem.total / (1024 * 1024))

                overview = {
                    "percent": vmem.percent,
                    "used_gb": round(vmem.used / (1024 ** 3), 1),
                    "total_gb": round(vmem.total / (1024 ** 3), 1),
                    "available_gb": round(vmem.available / (1024 ** 3), 1),
                    "swap_used_gb": round(swap.used / (1024 ** 3), 1),
                    "swap_total_gb": round(swap.total / (1024 ** 3), 1),
                    "swap_percent": swap.percent
                }

                # 2. Iterate processes for top consumers and memory leaks
                procs = []
                for p in psutil.process_iter(['pid', 'name', 'memory_info']):
                    if not self._running:
                        break
                    try:
                        info = p.info
                        pid = info['pid']
                        name = info['name'] or f"PID {pid}"
                        mem_info = info.get('memory_info')
                        rss = mem_info.rss if mem_info else 0
                        rss_mb = round(rss / (1024 * 1024), 1)

                        # Trend Arrow calculation (compared to 30s ago)
                        trend_arrow = "→"
                        if pid in self._history_30s:
                            old_rss, old_time = self._history_30s[pid]
                            if (now - old_time) >= 20:
                                diff = rss_mb - old_rss
                                if diff > 10:
                                    trend_arrow = "↑"
                                elif diff < -10:
                                    trend_arrow = "↓"
                                self._history_30s[pid] = (rss_mb, now)
                        else:
                            self._history_30s[pid] = (rss_mb, now)

                        # Memory leak rolling buffer tracking (last 10 readings over 5 mins)
                        if pid not in self._leak_buffers:
                            self._leak_buffers[pid] = deque(maxlen=10)
                        self._leak_buffers[pid].append((now, rss_mb))

                        procs.append({
                            "name": name,
                            "pid": pid,
                            "ram_mb": rss_mb,
                            "pct": (rss_mb / total_ram_mb) * 100.0,
                            "trend": trend_arrow
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                # Clean up terminated PIDs from history and leak buffers
                active_pids = {p["pid"] for p in procs}
                self._history_30s = {pid: v for pid, v in self._history_30s.items() if pid in active_pids}
                self._leak_buffers = {pid: v for pid, v in self._leak_buffers.items() if pid in active_pids}

                # Sort top 15 consumers
                procs.sort(key=lambda x: x["ram_mb"], reverse=True)
                top15 = procs[:15]

                # Check for suspected memory leaks
                # Condition: Monotonic growth >50% over window, current > 200MB
                leaking_procs = []
                for p in procs:
                    pid = p["pid"]
                    buf = self._leak_buffers.get(pid)
                    if buf and len(buf) >= 6:
                        first_t, first_rss = buf[0]
                        last_t, last_rss = buf[-1]
                        dt_mins = max(1.0, (last_t - first_t) / 60.0)
                        if last_rss > 200.0 and first_rss > 20.0:
                            growth_ratio = (last_rss - first_rss) / first_rss
                            if growth_ratio >= 0.50:
                                rate = round((last_rss - first_rss) / dt_mins, 1)
                                leaking_procs.append({
                                    "name": p["name"],
                                    "pid": pid,
                                    "current_mb": last_rss,
                                    "old_mb": first_rss,
                                    "growth_rate": rate
                                })

                leaking_procs.sort(key=lambda x: x["growth_rate"], reverse=True)

                self.ram_data_signal.emit(overview, top15, leaking_procs)

            except Exception as e:
                logger.error(f"Error in RamMonitorWorker: {e}")

            # Sleep: 3s when active, 10s when inactive/background
            sleep_ticks = 30 if self._active else 100
            for _ in range(sleep_ticks):
                if not self._running:
                    break
                time.sleep(0.1)
