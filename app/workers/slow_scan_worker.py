import os
import time
import json
import psutil
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from app.utils.wmi_utils import get_cpu_temperature, get_disk_media_types
from app.utils.threat_signatures import threat_db
from app.utils.registry_utils import (
    get_registry_startup_entries,
    get_startup_folder_entries,
    get_task_scheduler_entries
)
from app.constants import STARTUP_RECOMMENDATIONS_PATH
from app.database import db

logger = logging.getLogger(__name__)


class SlowScanWorker(QThread):
    """
    Executes a comprehensive 8-category deep diagnostic scan sequentially.
    Emits progressive category updates and final weighted health score.
    """
    progress_signal = pyqtSignal(int, str)
    category_done_signal = pyqtSignal(str, dict)
    scan_complete_signal = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        try:
            self.progress_signal.emit(5, "Analyzing CPU Pressure...")
            cat_results = {}
            recommendations = []

            # -----------------------------------------------------------------
            # 1. CPU Pressure (Weight: 20%)
            # -----------------------------------------------------------------
            if self._stopped:
                return
            avg_cpu = psutil.cpu_percent(interval=2)  # 2-sec avg
            heavy_procs = []
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                try:
                    c_pct = p.info['cpu_percent'] or 0.0
                    if c_pct > 5.0:
                        heavy_procs.append((p.info['name'], p.info['pid'], c_pct))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            heavy_procs.sort(key=lambda x: x[2], reverse=True)

            if avg_cpu < 30:
                cpu_score = 100
                cpu_status = "Excellent"
                cpu_finding = f"System CPU utilization is low at {avg_cpu:.1f}%. No bottlenecks detected."
            elif avg_cpu < 60:
                cpu_score = 70
                cpu_status = "Moderate"
                cpu_finding = f"CPU utilization is moderate at {avg_cpu:.1f}%."
            elif avg_cpu < 85:
                cpu_score = 40
                cpu_status = "High"
                cpu_finding = f"High CPU utilization at {avg_cpu:.1f}%."
            else:
                cpu_score = 10
                cpu_status = "Critical"
                cpu_finding = f"Severe CPU saturation at {avg_cpu:.1f}%!"

            if heavy_procs:
                top_p = heavy_procs[0]
                cpu_finding += f" Top consumer: <b>{top_p[0]} (PID {top_p[1]})</b> using <b>{top_p[2]:.1f}% CPU</b>."
                if cpu_score < 70:
                    recommendations.append(f"Consider closing high-CPU application: {top_p[0]} (using {top_p[2]:.1f}% CPU).")

            cat_results["CPU Pressure"] = {
                "score": cpu_score,
                "weight": 0.20,
                "status": cpu_status,
                "findings": cpu_finding
            }
            self.category_done_signal.emit("CPU Pressure", cat_results["CPU Pressure"])

            # -----------------------------------------------------------------
            # 2. Memory Pressure (Weight: 25%)
            # -----------------------------------------------------------------
            if self._stopped:
                return
            self.progress_signal.emit(20, "Inspecting Memory Pressure & Swap...")
            vmem = psutil.virtual_memory()
            try:
                swap = psutil.swap_memory()
            except Exception:
                class DummySwap:
                    percent = 0.0
                    used = 0
                    total = 0
                swap = DummySwap()
            mem_pct = vmem.percent
            top_mem_procs = []
            for p in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    rss = p.info['memory_info'].rss if p.info['memory_info'] else 0
                    if rss > 100 * 1024 * 1024:  # > 100 MB
                        top_mem_procs.append((p.info['name'], rss / (1024 * 1024)))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            top_mem_procs.sort(key=lambda x: x[1], reverse=True)

            if mem_pct < 50:
                mem_score = 100
                mem_status = "Optimal"
            elif mem_pct < 70:
                mem_score = 75
                mem_status = "Good"
            elif mem_pct < 85:
                mem_score = 45
                mem_status = "High"
            else:
                mem_score = 10
                mem_status = "Critical"

            if swap.percent > 50:
                mem_score = max(5, mem_score - 20)

            top_summary = ", ".join([f"{name} ({mb:.0f} MB)" for name, mb in top_mem_procs[:3]]) or "None"
            mem_finding = f"RAM is <b>{mem_pct}% full</b> ({vmem.used / (1024**3):.1f} GB / {vmem.total / (1024**3):.1f} GB). Top consumers: {top_summary}."
            if swap.percent > 50:
                mem_finding += f" System is actively swapping ({swap.percent}% swap used), causing significant disk bottlenecks."
                recommendations.append("RAM is exhausted and swapping to disk. Close large applications or optimize memory using the RAM Cleaner.")
            elif mem_score < 50:
                recommendations.append("Free up RAM by closing heavy background browser tabs or desktop applications.")

            cat_results["Memory Pressure"] = {
                "score": mem_score,
                "weight": 0.25,
                "status": mem_status,
                "findings": mem_finding
            }
            self.category_done_signal.emit("Memory Pressure", cat_results["Memory Pressure"])

            # -----------------------------------------------------------------
            # 3. Disk Health & Speed (Weight: 15%)
            # -----------------------------------------------------------------
            if self._stopped:
                return
            self.progress_signal.emit(35, "Testing Disk Health, Latency & Speed...")
            os_drive = os.environ.get("SystemDrive", "C:") + "\\"
            usage = psutil.disk_usage(os_drive)
            free_gb = usage.free / (1024 ** 3)

            media_types = get_disk_media_types()
            is_hdd = any(t == "HDD" for t in media_types.values())

            # Latency estimation
            io_latency_ms = 0.0
            try:
                disk_io = psutil.disk_io_counters()
                if disk_io and disk_io.read_count > 0:
                    io_latency_ms = round(disk_io.read_time / disk_io.read_count, 1)
            except Exception:
                pass

            if is_hdd:
                disk_score = 10 if free_gb < 10 else 35
                disk_status = "Slow (HDD)"
                disk_finding = "You are using a mechanical hard drive (HDD) as system storage. Mechanical HDDs are the #1 cause of Windows slowness."
                recommendations.append("Upgrade your OS drive to a Solid State Drive (SSD) for an instant 5-10x performance boost.")
            else:
                if free_gb > 50:
                    disk_score = 100
                    disk_status = "Fast (SSD)"
                    disk_finding = f"SSD detected with plenty of free headroom ({free_gb:.1f} GB available on {os_drive})."
                elif free_gb > 15:
                    disk_score = 75
                    disk_status = "Adequate"
                    disk_finding = f"SSD detected. {free_gb:.1f} GB free space remaining."
                else:
                    disk_score = 45
                    disk_status = "Low Space"
                    disk_finding = f"Critically low disk space on {os_drive} ({free_gb:.1f} GB free). Windows needs at least 15 GB for paging and cache."
                    recommendations.append(f"Free up at least 15 GB on {os_drive} using the Disk Cleanup module.")

            cat_results["Disk Health & Speed"] = {
                "score": disk_score,
                "weight": 0.15,
                "status": disk_status,
                "findings": disk_finding
            }
            self.category_done_signal.emit("Disk Health & Speed", cat_results["Disk Health & Speed"])

            # -----------------------------------------------------------------
            # 4. Startup Bloat (Weight: 15%)
            # -----------------------------------------------------------------
            if self._stopped:
                return
            self.progress_signal.emit(50, "Scanning Startup Programs & Boot Services...")
            reg_entries = get_registry_startup_entries()
            folder_entries = get_startup_folder_entries()
            task_entries = get_task_scheduler_entries()
            total_startup = len(reg_entries) + len(folder_entries) + len(task_entries)

            # Recommendations check
            known_recs = []
            try:
                if os.path.exists(STARTUP_RECOMMENDATIONS_PATH):
                    with open(STARTUP_RECOMMENDATIONS_PATH, "r", encoding="utf-8") as f:
                        rec_db = json.load(f)
                        rec_map = {item["name"].lower(): item for item in rec_db}
                        for entry in reg_entries + folder_entries + task_entries:
                            name_clean = entry["name"].lower()
                            if name_clean in rec_map and not rec_map[name_clean].get("essential", False):
                                known_recs.append(entry["name"])
            except Exception:
                pass

            if total_startup <= 5:
                startup_score = 100
                startup_status = "Lean"
            elif total_startup <= 10:
                startup_score = 75
                startup_status = "Moderate"
            elif total_startup <= 20:
                startup_score = 45
                startup_status = "Bloated"
            else:
                startup_score = 15
                startup_status = "Heavy"

            startup_finding = f"Found <b>{total_startup} applications</b> launching automatically at Windows startup."
            if known_recs:
                startup_finding += f" Recommended to disable: {', '.join(known_recs[:4])}."
                recommendations.append(f"Disable non-essential startup programs ({', '.join(known_recs[:3])}) in Startup Manager to reduce boot time by 30-60s.")

            cat_results["Startup Bloat"] = {
                "score": startup_score,
                "weight": 0.15,
                "status": startup_status,
                "findings": startup_finding
            }
            self.category_done_signal.emit("Startup Bloat", cat_results["Startup Bloat"])

            # -----------------------------------------------------------------
            # 5. Background Services (Weight: 5%)
            # -----------------------------------------------------------------
            if self._stopped:
                return
            self.progress_signal.emit(65, "Counting Background Windows Services...")
            running_services = 0
            try:
                for svc in psutil.win_service_iter():
                    if svc.status() == "running":
                        running_services += 1
            except Exception:
                running_services = 110  # Reasonable default estimate

            if running_services < 100:
                svc_score = 100
                svc_status = "Clean"
            elif running_services <= 150:
                svc_score = 70
                svc_status = "Normal"
            else:
                svc_score = 40
                svc_status = "High"

            cat_results["Background Services"] = {
                "score": svc_score,
                "weight": 0.05,
                "status": svc_status,
                "findings": f"Detected <b>{running_services} active system services</b> running in the background."
            }
            self.category_done_signal.emit("Background Services", cat_results["Background Services"])

            # -----------------------------------------------------------------
            # 6. Thermal Throttling (Weight: 5%)
            # -----------------------------------------------------------------
            if self._stopped:
                return
            self.progress_signal.emit(75, "Checking CPU Thermals & Throttling...")
            cpu_temp = get_cpu_temperature()
            if cpu_temp is not None:
                if cpu_temp < 65:
                    thermal_score = 100
                    thermal_status = "Cool"
                    thermal_finding = f"CPU operating temperature is cool at <b>{cpu_temp}°C</b>."
                elif cpu_temp < 80:
                    thermal_score = 70
                    thermal_status = "Warm"
                    thermal_finding = f"CPU temperature is warm at <b>{cpu_temp}°C</b>."
                elif cpu_temp < 90:
                    thermal_score = 30
                    thermal_status = "Hot"
                    thermal_finding = f"CPU temperature is elevated at <b>{cpu_temp}°C</b>. Thermal throttling may occur under load."
                    recommendations.append("Inspect CPU cooling fans and clean dust vents to avoid thermal throttling.")
                else:
                    thermal_score = 5
                    thermal_status = "Critical Throttling"
                    thermal_finding = f"CPU is actively thermal throttling at <b>{cpu_temp}°C</b>! Clock speeds are heavily reduced."
                    recommendations.append(f"URGENT: CPU temperature is {cpu_temp}°C. Clean radiator/heatsink and check thermal paste immediately.")
            else:
                thermal_score = 100
                thermal_status = "Normal"
                thermal_finding = "Hardware temperature sensors not reporting via WMI (cooling assumed nominal)."

            cat_results["Thermal Throttling"] = {
                "score": thermal_score,
                "weight": 0.05,
                "status": thermal_status,
                "findings": thermal_finding
            }
            self.category_done_signal.emit("Thermal Throttling", cat_results["Thermal Throttling"])

            # -----------------------------------------------------------------
            # 7. Malware & Suspicious Activity (Weight: 10%)
            # -----------------------------------------------------------------
            if self._stopped:
                return
            self.progress_signal.emit(85, "Scanning for Suspicious Processes & Impostors...")
            suspicious_count = 0
            suspicious_details = []
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    pname = proc.info['name'] or ""
                    pexe = proc.info['exe'] or ""
                    if threat_db.is_known_threat_name(pname):
                        suspicious_count += 1
                        suspicious_details.append(f"Known threat match: {pname}")
                    elif threat_db.is_system_duplicate_impostor(pname, pexe):
                        suspicious_count += 1
                        suspicious_details.append(f"Fake system binary outside System32: {pname} ({pexe})")
                    elif threat_db.is_suspicious_path(pexe):
                        suspicious_count += 1
                        suspicious_details.append(f"Process running from temp directory: {pname}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if suspicious_count == 0:
                mal_score = 100
                mal_status = "Clean"
                mal_finding = "No suspicious processes, fake system impostors, or temp binary executions detected."
            elif suspicious_count <= 2:
                mal_score = 60
                mal_status = "Suspicious"
                mal_finding = f"Flagged <b>{suspicious_count} potentially suspicious process(es)</b>: {'; '.join(suspicious_details)}."
                recommendations.append("Investigate flagged processes in the Virus Scanner module.")
            else:
                mal_score = 20
                mal_status = "High Risk"
                mal_finding = f"Found <b>{suspicious_count} high-risk processes</b> running from abnormal locations."
                recommendations.append("Run a full threat scan and terminate unauthorized background processes immediately.")

            cat_results["Malware/Suspicious"] = {
                "score": mal_score,
                "weight": 0.10,
                "status": mal_status,
                "findings": mal_finding
            }
            self.category_done_signal.emit("Malware/Suspicious", cat_results["Malware/Suspicious"])

            # -----------------------------------------------------------------
            # 8. Junk Files (Weight: 5%)
            # -----------------------------------------------------------------
            if self._stopped:
                return
            self.progress_signal.emit(95, "Estimating Reclaimable Junk Cache...")
            junk_bytes = 0
            temp_dirs = [os.environ.get("TEMP", ""), r"C:\Windows\Temp"]
            for tdir in temp_dirs:
                if os.path.exists(tdir):
                    try:
                        for entry in os.scandir(tdir):
                            try:
                                if entry.is_file(follow_symlinks=False):
                                    junk_bytes += entry.stat().st_size
                            except Exception:
                                pass
                    except Exception:
                        pass

            junk_gb = junk_bytes / (1024 ** 3)
            if junk_gb < 1.0:
                junk_score = 100
                junk_status = "Clean"
            elif junk_gb < 5.0:
                junk_score = 70
                junk_status = "Moderate"
            elif junk_gb < 15.0:
                junk_score = 40
                junk_status = "Cluttered"
            else:
                junk_score = 15
                junk_status = "Severely Cluttered"

            cat_results["Junk Files"] = {
                "score": junk_score,
                "weight": 0.05,
                "status": junk_status,
                "findings": f"Detected approximately <b>{junk_gb:.2f} GB</b> of temp files and reclaimable cache."
            }
            if junk_score < 70:
                recommendations.append(f"Reclaim {junk_gb:.1f} GB of storage space using the Disk Cleanup tool.")
            self.category_done_signal.emit("Junk Files", cat_results["Junk Files"])

            # -----------------------------------------------------------------
            # Overall Score Calculation
            # -----------------------------------------------------------------
            overall_score = int(round(sum(c["score"] * c["weight"] for c in cat_results.values())))
            overall_score = max(0, min(100, overall_score))

            if overall_score >= 85:
                overall_status = "Your PC is healthy"
            elif overall_score >= 60:
                overall_status = "Your PC has some issues affecting performance"
            elif overall_score >= 30:
                overall_status = "Your PC has significant performance problems"
            else:
                overall_status = "Your PC needs urgent attention"

            final_payload = {
                "score": overall_score,
                "status": overall_status,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "categories": cat_results,
                "recommendations": recommendations
            }

            # Persist to database
            db.save_scan_result(
                score=overall_score,
                status=overall_status,
                category_scores={k: v["score"] for k, v in cat_results.items()},
                findings={k: v["findings"] for k, v in cat_results.items()},
                recommendations=recommendations
            )

            self.progress_signal.emit(100, "Diagnostic Scan Completed!")
            self.scan_complete_signal.emit(final_payload)

        except Exception as e:
            logger.error(f"Error during SlowScanWorker execution: {e}")
            self.progress_signal.emit(100, f"Error: {e}")
