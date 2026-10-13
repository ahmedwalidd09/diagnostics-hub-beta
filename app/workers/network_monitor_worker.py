import time
import subprocess
import psutil
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from app.utils.threat_signatures import threat_db

logger = logging.getLogger(__name__)

STANDARD_WEB_PORTS = {80, 443, 53, 8080, 8443, 993, 995, 587, 465, 22, 123}
COMMON_BROWSERS = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe", "svchost.exe"}

CREATE_NO_WINDOW = 0x08000000
_startupinfo = subprocess.STARTUPINFO()
_startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
_startupinfo.wShowWindow = 0  # SW_HIDE


def parse_dns_cache() -> list[dict]:
    """Parse output from `ipconfig /displaydns` into structured entries."""
    entries = []
    try:
        proc = subprocess.run(
            ["ipconfig", "/displaydns"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=8,
            creationflags=CREATE_NO_WINDOW,
            startupinfo=_startupinfo
        )
        if proc.returncode == 0:
            lines = proc.stdout.splitlines()
            current_entry = {}
            for line in lines:
                line = line.strip()
                if "Record Name" in line:
                    if "record_name" in current_entry:
                        entries.append(current_entry)
                    current_entry = {"record_name": line.split(":")[-1].strip()}
                elif "Record Type" in line and current_entry:
                    current_entry["record_type"] = line.split(":")[-1].strip()
                elif "Time To Live" in line and current_entry:
                    current_entry["ttl"] = line.split(":")[-1].strip()
                elif ("A (IPv4) Record" in line or "AAAA (IPv6) Record" in line or "Data" in line) and current_entry:
                    current_entry["data"] = line.split(":")[-1].strip()

            if "record_name" in current_entry:
                entries.append(current_entry)
    except Exception as e:
        logger.debug(f"Failed to parse DNS cache: {e}")
    return entries


def flush_dns_cache() -> bool:
    """Flush Windows DNS Resolver Cache via `ipconfig /flushdns`."""
    try:
        res = subprocess.run(
            ["ipconfig", "/flushdns"],
            capture_output=True,
            timeout=5,
            creationflags=CREATE_NO_WINDOW,
            startupinfo=_startupinfo
        )
        return res.returncode == 0
    except Exception as e:
        logger.error(f"Failed to flush DNS cache: {e}")
        return False


class NetworkMonitorWorker(QThread):
    """
    Tracks real-time network throughput and active sockets.
    Optimized:
    - Bandwidth polling remains 1s for graph responsiveness (<0.1ms cost)
    - Socket connection audit only runs when Network tab is visible, throttled to every 4 seconds
    - Capped at max 120 active connections to eliminate UI table churn
    - Retains process name cache with gentle eviction instead of full clear
    """
    bandwidth_signal = pyqtSignal(float, float)  # (down_kbs, up_kbs)
    connections_data_signal = pyqtSignal(list, list, list)  # (connections, suspicious, process_summary)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._active = False  # Detailed socket tracking paused until page is active
        try:
            self._last_net_io = psutil.net_io_counters()
        except Exception:
            self._last_net_io = None
        self._last_time = time.time()
        self._proc_cache = {}  # pid -> name

    def set_active(self, active: bool):
        self._active = active

    def stop(self):
        self._running = False
        self.wait(3000)

    def run(self):
        tick = 0
        while self._running:
            try:
                curr_time = time.time()
                dt = max(0.5, curr_time - self._last_time)

                # Bandwidth delta (every 1s, <0.1ms overhead)
                down_kbs = 0.0
                up_kbs = 0.0
                try:
                    curr_io = psutil.net_io_counters()
                    if curr_io and self._last_net_io:
                        down_kbs = max(0.0, (curr_io.bytes_recv - self._last_net_io.bytes_recv) / dt / 1024.0)
                        up_kbs = max(0.0, (curr_io.bytes_sent - self._last_net_io.bytes_sent) / dt / 1024.0)
                    self._last_net_io = curr_io
                except Exception:
                    pass
                self._last_time = curr_time

                self.bandwidth_signal.emit(round(down_kbs, 1), round(up_kbs, 1))

                # Connection audit: only when page is active, throttled to every 4 ticks (4s)
                tick += 1
                if self._active and (tick % 4 == 0):
                    raw_conns = psutil.net_connections(kind='inet')
                    all_conns = []
                    suspicious_conns = []
                    pid_conn_counts = {}

                    # Sort raw connections: ESTABLISHED and LISTEN first
                    sorted_raw = sorted(
                        raw_conns,
                        key=lambda c: 0 if c.status == "ESTABLISHED" else (1 if c.status == "LISTEN" else 2)
                    )

                    for c in sorted_raw[:120]:  # Cap to top 120 entries
                        if not self._running or not self._active:
                            break
                        pid = c.pid or 0
                        status = c.status or "UNKNOWN"
                        proto = "TCP" if c.type == 1 else "UDP"

                        # Resolve process name with cache
                        pname = self._proc_cache.get(pid)
                        if not pname:
                            try:
                                if pid > 0:
                                    p = psutil.Process(pid)
                                    pname = p.name()
                                    self._proc_cache[pid] = pname
                                else:
                                    pname = "System"
                            except Exception:
                                pname = "Unknown"

                        pid_conn_counts[pid] = pid_conn_counts.get(pid, 0) + 1

                        local_addr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "-:-"
                        remote_addr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "-:-"
                        r_port = c.raddr.port if c.raddr else 0
                        r_ip = c.raddr.ip if c.raddr else ""

                        is_suspicious = False
                        flag_reason = ""

                        if status == "ESTABLISHED" and r_ip:
                            if threat_db.is_suspicious_ip(r_ip):
                                is_suspicious = True
                                flag_reason = f"Known Malicious IP: {r_ip}"
                            elif threat_db.is_known_threat_name(pname):
                                is_suspicious = True
                                flag_reason = f"Threat process communicating: {pname}"
                            elif r_port not in STANDARD_WEB_PORTS and pname.lower() not in COMMON_BROWSERS and pid > 4:
                                is_suspicious = True
                                flag_reason = f"Non-standard outbound port {r_port}"

                        conn_dict = {
                            "process": pname,
                            "pid": pid,
                            "protocol": proto,
                            "local_address": local_addr,
                            "remote_address": remote_addr,
                            "remote_ip": r_ip,
                            "remote_port": r_port,
                            "status": status,
                            "is_suspicious": is_suspicious,
                            "reason": flag_reason
                        }

                        all_conns.append(conn_dict)
                        if is_suspicious:
                            suspicious_conns.append(conn_dict)

                    # Build per-process connection summary
                    proc_summary = []
                    for p_id, count in sorted(pid_conn_counts.items(), key=lambda x: x[1], reverse=True)[:25]:
                        proc_summary.append({
                            "name": self._proc_cache.get(p_id, "Unknown"),
                            "pid": p_id,
                            "connections": count
                        })

                    # Maintain cache bound gently (evict oldest without clearing all)
                    if len(self._proc_cache) > 400:
                        keys = list(self._proc_cache.keys())[:200]
                        for k in keys:
                            self._proc_cache.pop(k, None)

                    self.connections_data_signal.emit(all_conns, suspicious_conns, proc_summary)

            except Exception as e:
                logger.error(f"Error in NetworkMonitorWorker: {e}")

            for _ in range(10):
                if not self._running:
                    break
                time.sleep(0.1)
