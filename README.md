# Windows Diagnostics Hub (Beta)

A native Windows hardware monitor, process controller, and kernel memory management workstation built with Python 3.11+ and PyQt6.

Operates with minimal CPU overhead, zero UI stutter, and direct Win32 API integration.

---

## Architecture & Subsystems

1. **Telemetry Dashboard**  
   Continuous 1-second sampling of CPU utilization, core clock frequencies, core temperatures, RAM, pagefile, disk I/O throughput, GPU metrics, network throughput, and battery status.

2. **System Diagnostic Analyzer**  
   Evaluates 8 performance pillars: CPU load, memory pressure, disk I/O saturation, boot applications, background services, thermals, binary impersonators, and disk cache. Outputs a 0–100 health index with direct remediation options.

3. **Process Controller**  
   Multi-column task manager with numeric sorting, real-time disk read/write bandwidth, Authenticode publisher verification, process tree termination, and process suspension/resumption.

4. **Malware & Threat Auditor**  
   Heuristic scanner flagging execution from temporary directories, randomized executable paths, and system binary spoofing (`csrss.exe`/`lsass.exe` outside `System32`). Includes SHA-256 signature auditing and VirusTotal v3 API verification.

5. **Memory Manager**  
   Executes working-set trimming (`EmptyWorkingSet`) and standby cache flushing via `NtSetSystemInformation`. Runs a 5-minute rolling detector for monotonic memory leaks.

6. **Startup & Task Scheduler Manager**  
   Inspects and toggles startup entries across `HKCU`/`HKLM` Run keys, Startup directories, and Task Scheduler logon jobs. Preserves an undo transaction log in SQLite.

7. **Storage Purge**  
   Scans and purges 8 cleanable targets: Windows Temp, browser caches (Chrome, Edge, Firefox), Windows Update download cache, Recycle Bin, Explorer thumbnail cache, error logs, `Windows.old`, and crash dumps.

8. **Network & Socket Monitor**  
   Real-time bandwidth graph via PyQtGraph, active socket table with protocol inspection, outbound connection alerts, and a Windows DNS cache inspector/flusher.

---

## Requirements

- Windows 10 or Windows 11 (x64)
- Python 3.11+

## Setup & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Launch application
python main.py
```

## Standalone Binary Build

```bash
pyinstaller build.spec
```
Binary outputs to `dist/DiagnosticsHub.exe`.
