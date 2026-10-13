import os
import time
import psutil
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from app.utils.threat_signatures import threat_db
from app.utils.virustotal_api import VirusTotalClient
from app.settings_manager import settings

logger = logging.getLogger(__name__)

STANDARD_WEB_PORTS = {80, 443, 53, 8080, 8443, 993, 995, 587, 465, 22, 123}
COMMON_BROWSERS = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe"}


class VirusScanWorker(QThread):
    """
    Multi-mode security scanner executing quick heuristic process scans,
    file/folder hash checks with VirusTotal, or network threat audits.
    """
    progress_signal = pyqtSignal(int, str)
    threat_found_signal = pyqtSignal(dict)
    scan_complete_signal = pyqtSignal(list, dict)

    def __init__(self, scan_type: str = "quick", target_path: str = "", parent=None):
        super().__init__(parent)
        self.scan_type = scan_type
        self.target_path = target_path
        self._stopped = False
        self.vt_client = VirusTotalClient(settings.get("virustotal_api_key", ""))

    def stop(self):
        self._stopped = True

    def run(self):
        results = []
        threats_count = 0
        scanned_count = 0

        try:
            if self.scan_type == "quick":
                # Quick Scan of Running Processes
                all_procs = list(psutil.process_iter(['pid', 'name', 'exe']))
                total = len(all_procs)

                for i, proc in enumerate(all_procs):
                    if self._stopped:
                        break

                    try:
                        pname = proc.info['name'] or ""
                        pexe = proc.info['exe'] or ""
                        pid = proc.info['pid']
                        scanned_count += 1

                        self.progress_signal.emit(
                            int((i / max(1, total)) * 100),
                            f"Checking process {pname} (PID {pid})..."
                        )

                        threat_entry = None

                        # Check 1: Known Threat Name
                        if threat_db.is_known_threat_name(pname):
                            threat_entry = {
                                "name": pname,
                                "pid": pid,
                                "path": pexe,
                                "threat_type": "Known Malware Signature",
                                "severity": "Critical",
                                "action": "Kill Process & Quarantine"
                            }
                        # Check 2: Fake Duplicate System Binary
                        elif threat_db.is_system_duplicate_impostor(pname, pexe):
                            threat_entry = {
                                "name": pname,
                                "pid": pid,
                                "path": pexe,
                                "threat_type": "System Impostor Binary",
                                "severity": "High",
                                "action": "Inspect & Terminate"
                            }
                        # Check 3: Suspicious Path Execution
                        elif threat_db.is_suspicious_path(pexe):
                            threat_entry = {
                                "name": pname,
                                "pid": pid,
                                "path": pexe,
                                "threat_type": "Suspicious Temp Location",
                                "severity": "Medium",
                                "action": "Investigate File"
                            }
                        # Check 4: Unsigned Binary from non-standard path
                        elif pexe and not pexe.lower().startswith(r"c:\windows") and not pexe.lower().startswith(r"c:\program files"):
                            if not threat_db.verify_digital_signature(pexe):
                                threat_entry = {
                                    "name": pname,
                                    "pid": pid,
                                    "path": pexe,
                                    "threat_type": "Unsigned Executable",
                                    "severity": "Low",
                                    "action": "Verify Origin"
                                }

                        if threat_entry:
                            threats_count += 1
                            results.append(threat_entry)
                            self.threat_found_signal.emit(threat_entry)

                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

            elif self.scan_type == "file":
                # File or Folder Hash Scan
                files_to_scan = []
                if os.path.isfile(self.target_path):
                    files_to_scan.append(self.target_path)
                elif os.path.isdir(self.target_path):
                    for root, _, files in os.walk(self.target_path):
                        if self._stopped:
                            break
                        for f in files:
                            # Focus on executables, scripts, and archives
                            if f.lower().endswith(('.exe', '.dll', '.sys', '.bat', '.ps1', '.vbs', '.js', '.scr')):
                                files_to_scan.append(os.path.join(root, f))

                total_files = len(files_to_scan)
                has_vt = bool(self.vt_client.api_key)

                for i, file_path in enumerate(files_to_scan):
                    if self._stopped:
                        break

                    scanned_count += 1
                    file_name = os.path.basename(file_path)
                    progress_pct = int((i / max(1, total_files)) * 100)
                    self.progress_signal.emit(progress_pct, f"Hashing {file_name}...")

                    sha256 = threat_db.calculate_file_sha256(file_path)
                    if not sha256:
                        continue

                    threat_entry = None
                    known_sig = threat_db.is_known_threat_hash(sha256)
                    if known_sig:
                        threat_entry = {
                            "name": file_name,
                            "pid": "-",
                            "path": file_path,
                            "threat_type": f"Database Match: {known_sig}",
                            "severity": "Critical",
                            "action": "Delete File"
                        }
                    elif has_vt:
                        self.progress_signal.emit(progress_pct, f"Querying VirusTotal: {file_name}...")
                        vt_data = self.vt_client.check_file_hash(sha256)
                        if vt_data and vt_data.get("malicious", 0) > 0:
                            mal = vt_data["malicious"]
                            sev = "Critical" if mal > 5 else "High"
                            threat_entry = {
                                "name": file_name,
                                "pid": "-",
                                "path": file_path,
                                "threat_type": f"VirusTotal ({mal} engines detected)",
                                "severity": sev,
                                "action": "Quarantine"
                            }

                    if threat_entry:
                        threats_count += 1
                        results.append(threat_entry)
                        self.threat_found_signal.emit(threat_entry)

            elif self.scan_type == "network":
                # Active Network Connections Threat Check
                self.progress_signal.emit(10, "Enumerating active network connections...")
                connections = psutil.net_connections(kind='inet')
                total_conns = len(connections)

                for i, conn in enumerate(connections):
                    if self._stopped:
                        break

                    scanned_count += 1
                    if conn.status != "ESTABLISHED" or not conn.raddr:
                        continue

                    remote_ip = conn.raddr.ip
                    remote_port = conn.raddr.port
                    pid = conn.pid or 0

                    try:
                        p = psutil.Process(pid) if pid > 0 else None
                        pname = p.name() if p else "System"
                    except Exception:
                        pname = "Unknown"

                    threat_entry = None
                    if threat_db.is_suspicious_ip(remote_ip):
                        threat_entry = {
                            "name": pname,
                            "pid": pid,
                            "path": f"{remote_ip}:{remote_port}",
                            "threat_type": f"Known Malicious IP: {remote_ip}",
                            "severity": "Critical",
                            "action": "Block Connection & Isolate"
                        }
                    elif remote_port not in STANDARD_WEB_PORTS and pname.lower() not in COMMON_BROWSERS and pid > 4:
                        threat_entry = {
                            "name": pname,
                            "pid": pid,
                            "path": f"{remote_ip}:{remote_port}",
                            "threat_type": f"Unusual Port Outbound ({remote_port})",
                            "severity": "Medium",
                            "action": "Verify Connection"
                        }

                    if threat_entry:
                        threats_count += 1
                        results.append(threat_entry)
                        self.threat_found_signal.emit(threat_entry)

            summary = {
                "scanned_count": scanned_count,
                "threats_count": threats_count,
                "clean_count": max(0, scanned_count - threats_count)
            }

            self.progress_signal.emit(100, f"Scan completed. Found {threats_count} potential threat(s).")
            self.scan_complete_signal.emit(results, summary)

        except Exception as e:
            logger.error(f"Error in VirusScanWorker: {e}")
            self.progress_signal.emit(100, f"Error: {e}")
            self.scan_complete_signal.emit(results, {
                "scanned_count": scanned_count,
                "threats_count": threats_count,
                "clean_count": max(0, scanned_count - threats_count)
            })
