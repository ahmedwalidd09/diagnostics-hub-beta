# Test Infrastructure & Strategy — Diagnostics Hub

## 1. Architecture Overview

Diagnostics Hub employs an automated, headless test architecture driven by `pytest` (v9.1.1), targeting native Win32 performance APIs, cryptographic licensing access gates, multi-tier process termination, and PyQt6 graphical user interface modules.

### Core Principles
- **Headless Execution**: All UI tests run entirely offscreen using `QT_QPA_PLATFORM=offscreen` and a session-scoped `QApplication` fixture. Tests can execute in headless CI/CD environments without an attached display.
- **Isolated State**: The `isolated_appdata` fixture redirects all persistent configuration, licensing, and token storage away from the user's real `%APPDATA%\DiagnosticsHub` directory to a transient `tmp_path` sandbox.
- **Thread Safety**: Long-running background `QThread` workers (`ProcessListWorker`, `RamMonitorWorker`, `NetworkMonitorWorker`) are safely neutralized during instantiation tests via the `mock_page_workers` fixture to prevent test suite deadlocks.
- **Network Isolation**: Telegram Bot API HTTP communications via `urllib.request.urlopen` are mocked with deterministic JSON context managers, requiring zero external internet access.
- **Platform Resilience**: Win32 `psapi.GetPerformanceInfo` and `taskkill` interactions are verified both live on Windows and through mocked ctypes/subprocess boundaries to validate fallback behaviors.

---

## 2. Test Suite Inventory

| Test File | Target Modules | Coverage & Verification Scope |
|---|---|---|
| `tests/conftest.py` | Global test harness | Session-scoped offscreen `qapp`, `isolated_appdata` filesystem monkeypatching, and `mock_page_workers` thread neutralization. |
| `tests/test_kernel_apis.py` | `app/utils/ram_api.py` | Live Win32 `GetPerformanceInfo` structure retrieval, non-paged pool memory leak threshold calculation (`> 800 MB`), boundary testing, and ctypes WinDLL exception fallback to zeroed metrics. |
| `tests/test_access_gate.py` | `app/utils/access_gate.py` | Machine GUID fingerprinting, HMAC SHA-256 license signature verification (missing, corrupted, forged, valid), credential storage, Telegram parameter flexibility (single/zero argument invocations), and mocked request/approval workflows. |
| `tests/test_process_utils.py` | `app/utils/process_utils.py` | Multi-tier process termination logic (`kill_process_with_fallback`), Tier 1 `psutil` termination, recursive tree killing, Tier 2 `taskkill /F /PID [/T]` command-line fallback, PID type casting, and invalid PID handling. |
| `tests/test_gui_instantiation.py` | `app/modules/*`, `app/widgets/*` | Headless offscreen instantiation of all 9 primary application pages and 9 custom widgets/dialogs, PyQt6 signal propagation (`theme_changed`, `profile_changed`, `search_changed`), and multi-theme application resilience (`workstation`, `obsidian`, `light`). |

---

## 3. How to Run the Test Suite

### Run All Tests
```powershell
python -m pytest tests/ -v
```

### Run by Specific Subsystem
```powershell
# Kernel Memory & PSAPI APIs
python -m pytest tests/test_kernel_apis.py -v

# Cryptographic Access Gate & Telegram Verification
python -m pytest tests/test_access_gate.py -v

# Multi-Tier Process Termination
python -m pytest tests/test_process_utils.py -v

# GUI Pages & Custom Widgets Instantiation
python -m pytest tests/test_gui_instantiation.py -v
```

### Run with Short Summary
```powershell
python -m pytest tests/ -q
```

---

## 4. Fixture Contracts

### `qapp` (Scope: `session`)
Initializes `QApplication(["--platform", "offscreen"])` if `QApplication.instance()` is not present. Guarantees a single GUI application instance across the entire test session.

### `isolated_appdata` (Scope: `function`, `autouse=True`)
Dynamically creates a clean temporary directory and monkeypatches:
- `app.constants.APPDATA_DIR`
- `app.utils.access_gate.APPDATA_DIR`
- `app.utils.access_gate.WHITELIST_FILE`
- `app.utils.access_gate.TELEGRAM_CONFIG_FILE`

Guarantees tests neither inspect nor mutate real user activation licenses or bot credentials in `%APPDATA%`.

### `mock_page_workers` (Scope: `function`, `autouse=True`)
Monkeypatches `_start_worker` on `ProcessManagerPage`, `RamCleanerPage`, and `NetworkMonitorPage` with a no-op handler (`lambda self: None`), preventing background `QThread` event loops from spawning during UI construction tests.

---

## 5. Invalidation Conditions & Safeguards

The test suite will fail if:
1. `QT_QPA_PLATFORM` is improperly configured or offscreen support is missing when creating QWidgets.
2. Background QThreads are started without proper mock interception or termination cleanup, hanging test runner teardown.
3. Telegram access gate functions raise `TypeError` when called with only `node_id` or no arguments.
4. Process termination utilities raise unhandled exceptions on invalid PID types or failed termination attempts.
5. Win32 structure sizes or types mismatch in `PERFORMANCE_INFORMATION`.
