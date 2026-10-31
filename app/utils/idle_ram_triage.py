"""
Resting Memory Triage Advisor.
Audits the Windows system specifically for causes of high RAM usage while idle:
- Kernel Non-Paged Pool & Paged Pool leaks (driver leaks)
- Standby List and Modified Page accumulation
- Background browser processes running with zero active windows
- Electron app memory hoarding
- Windows SysMain / Search Indexer pressure
"""

import os
import psutil
from typing import Dict, List, Any
from app.utils.ram_api import get_kernel_performance_info, purge_standby_list, purge_modified_list
from app.utils.eco_qos import set_process_eco_qos, trim_process_working_set


def analyze_resting_memory() -> Dict[str, Any]:
    """
    Performs an automated diagnostic scan of idle memory pressure.
    Returns categorized findings and actionable remediation targets.
    """
    findings = []
    remediations = []
    potential_freed_mb = 0.0

    # 1. Kernel Pool & Cache Analysis
    kernel = get_kernel_performance_info()
    npp_mb = kernel.get("kernel_nonpaged_mb", 0.0)
    paged_mb = kernel.get("kernel_paged_mb", 0.0)
    sys_cache_mb = kernel.get("system_cache_mb", 0.0)

    if npp_mb > 800.0:
        findings.append({
            "severity": "critical",
            "title": f"High Non-Paged Pool Allocation ({npp_mb:.0f} MB)",
            "description": "Kernel Non-Paged Pool exceeds 800 MB. This is a classic symptom of a leaking third-party driver (such as a network filter or display driver). Non-paged pool memory cannot be paged to disk."
        })
    elif npp_mb > 500.0:
        findings.append({
            "severity": "warning",
            "title": f"Elevated Non-Paged Pool ({npp_mb:.0f} MB)",
            "description": "Kernel Non-Paged Pool is higher than typical idle levels (200-400 MB)."
        })

    if sys_cache_mb > 1500.0:
        findings.append({
            "severity": "warning",
            "title": f"Large Standby System Cache ({sys_cache_mb:.0f} MB)",
            "description": "Windows file cache is retaining extensive standby memory pages that have not been reclaimed."
        })
        remediations.append("purge_standby")
        potential_freed_mb += sys_cache_mb * 0.7

    # 2. Background Browser & Electron Process Audit
    browser_names = {"chrome.exe", "msedge.exe", "brave.exe", "firefox.exe"}
    electron_names = {"discord.exe", "slack.exe", "teams.exe", "spotify.exe", "code.exe"}

    browser_ram = 0.0
    browser_pids = []
    electron_ram = 0.0
    electron_pids = []

    for p in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            name = (p.info['name'] or '').lower()
            mem = p.info.get('memory_info')
            if not mem:
                continue
            mb = mem.rss / (1024 * 1024)

            if name in browser_names:
                browser_ram += mb
                browser_pids.append(p.info['pid'])
            elif name in electron_names:
                electron_ram += mb
                electron_pids.append(p.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if browser_ram > 600.0:
        findings.append({
            "severity": "warning",
            "title": f"Background Browser Memory Footprint ({browser_ram:.0f} MB across {len(browser_pids)} processes)",
            "description": "Browsers often keep dozens of background helper tasks active even when resting."
        })
        remediations.append("trim_browsers")
        potential_freed_mb += browser_ram * 0.5

    if electron_ram > 500.0:
        findings.append({
            "severity": "info",
            "title": f"Electron Background Applications ({electron_ram:.0f} MB across {len(electron_pids)} processes)",
            "description": "Chat and productivity apps (Slack, Discord, Teams) retain active Chromium working sets."
        })
        remediations.append("eco_electron")
        potential_freed_mb += electron_ram * 0.4

    # Memory overview
    vmem = psutil.virtual_memory()

    return {
        "current_ram_percent": vmem.percent,
        "used_gb": round(vmem.used / (1024 ** 3), 1),
        "total_gb": round(vmem.total / (1024 ** 3), 1),
        "kernel_nonpaged_mb": npp_mb,
        "kernel_paged_mb": paged_mb,
        "system_cache_mb": sys_cache_mb,
        "findings": findings,
        "remediations": remediations,
        "potential_freed_mb": round(potential_freed_mb, 1),
        "browser_pids": browser_pids,
        "electron_pids": electron_pids
    }


def execute_resting_triage_fix() -> Dict[str, Any]:
    """
    Executes an intelligent triage flush specifically targeted at resting RAM bloat:
    1. Standby list cache purge
    2. Modified page flush
    3. Trims and applies EcoQoS to background browser & electron helpers
    """
    analysis = analyze_resting_memory()
    before_avail = psutil.virtual_memory().available / (1024 * 1024)

    # 1. Purge Standby and Modified Lists
    purge_standby_list()
    purge_modified_list()

    # 2. Trim & apply EcoQoS to background helpers
    trimmed = 0
    all_target_pids = analysis.get("browser_pids", []) + analysis.get("electron_pids", [])
    for pid in all_target_pids:
        try:
            if trim_process_working_set(pid):
                trimmed += 1
            set_process_eco_qos(pid, True)
        except Exception:
            continue

    after_avail = psutil.virtual_memory().available / (1024 * 1024)
    freed = max(0.0, after_avail - before_avail)

    return {
        "freed_mb": round(freed, 1),
        "trimmed_count": trimmed,
        "new_ram_percent": psutil.virtual_memory().percent
    }
