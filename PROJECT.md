# Project: Diagnostics Hub Production Fixes & Test Suite

## Architecture
Diagnostics Hub is a Windows desktop system diagnostic, optimization, and security application built with PyQt6, utilizing native Win32 APIs, ctypes, psutil, and WMI for hardware/kernel telemetry and process management.

### Module Boundaries & Data Flow
- **Access Control & Licensing**: `app/utils/access_gate.py` controls machine licensing and Telegram verification modal requests.
- **Packaging**: `build.spec` defines PyInstaller standalone build configuration, bundling code and assets.
- **Process Management**: `app/utils/process_utils.py` provides shared two-tier process termination (`psutil` -> `taskkill`), utilized by `app/modules/process_manager.py` and `app/modules/ram_cleaner.py`.
- **UI Styling & Theming**: `app/constants.py` defines design tokens (`COLOR_ACCENT_BLUE`, `COLOR_TEXT_PRIMARY`, etc.) consumed across UI modules and tray icon.
- **Kernel APIs**: `app/utils/ram_api.py` uses Win32 `psapi.GetPerformanceInfo` ctypes bindings for kernel memory metrics.
- **Test Infrastructure**: `tests/` contains automated pytest test suites covering access gate, kernel APIs, process utilities, and headless GUI instantiation.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Telegram Verification Parameter Handling | Update `send_telegram_access_request` and `check_telegram_approval` to support optional `node_id`, defaulting credentials via `get_telegram_credentials()` | M1 | ORIGINAL_REQUEST Â§ R1 |
| 2 | Application Assets in Build Spec | Update `build.spec` datas to include `('app/assets', 'app/assets')` for standalone PyInstaller bundling | M1 | ORIGINAL_REQUEST Â§ R2 |
| 3 | Process Termination Logic Consolidation | Extract duplicate process kill logic from `process_manager.py` and `ram_cleaner.py` into `kill_process_with_fallback` in `app/utils/process_utils.py` | M1 | ORIGINAL_REQUEST Â§ R5 |
| 4 | UI Styling Token Standardization | Replace hardcoded neon colors (`#00d2ff`, `#00a8ff`, `#ff2a51`) in `disk_cleanup.py`, `startup_manager.py`, and `tray.py` with tokens from `app.constants` | M1 | ORIGINAL_REQUEST Â§ R4 |
| 5 | Automated Test Suite | Create `tests/` covering `get_kernel_performance_info()`, `is_machine_whitelisted()`, process utils, access gate, and headless GUI instantiation | M2 | ORIGINAL_REQUEST Â§ R3 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Implementation Track (R1, R2, R4, R5) | `app/utils/access_gate.py`, `build.spec`, `app/utils/process_utils.py`, `app/modules/process_manager.py`, `app/modules/ram_cleaner.py`, `app/modules/disk_cleanup.py`, `app/modules/startup_manager.py`, `app/tray.py` | none | DONE |
| 2 | M2: E2E Testing Track (R3) | `tests/conftest.py`, `tests/test_kernel_apis.py`, `tests/test_access_gate.py`, `tests/test_process_utils.py`, `tests/test_gui_instantiation.py`, `TEST_INFRA.md`, `TEST_READY.md` | none | DONE |
| 3 | M3: Final Acceptance & Hardening | Full E2E test pass, 2 Reviewers, 2 Challengers, Forensic Auditor verification | M1, M2 | DONE |

## Interface Contracts

### M1: Telegram Access Gate Contract (`app/utils/access_gate.py`)
```python
def send_telegram_access_request(
    node_id: str = "",
    bot_token: str = "",
    chat_id: str = ""
) -> tuple[bool, str]: ...

def check_telegram_approval(
    node_id: str = "",
    bot_token: str = "",
    chat_id: str = "",
    entered_pin: str = ""
) -> tuple[bool, str]: ...
```
- If `node_id` is empty, fallback to `get_short_node_id()`.
- If `bot_token` or `chat_id` is empty, fallback to `get_telegram_credentials()`.
- `check_telegram_approval` returns `(True, target_pin)` when approved so `access_modal.py` pin verification succeeds.

### M1: Process Utility Contract (`app/utils/process_utils.py`)
```python
def kill_process_with_fallback(
    pid: int | str,
    tree: bool = False
) -> bool: ...
```
- Converts `pid` to integer.
- Tier 1: Uses `psutil.Process(pid)`. If `tree=True`, enumerates `p.children(recursive=True)` and kills children, then kills `p`.
- Tier 2: If `psutil` fails or cannot kill, invokes `taskkill /F /PID <pid> [/T]`.
- Returns `True` if either tier successfully killed the process, `False` otherwise.
- Pure utility function: no Qt imports, no UI message boxes.

### M1: UI Styling Contract (`app.constants`)
- Target files: `app/modules/disk_cleanup.py`, `app/modules/startup_manager.py`, `app/tray.py`.
- Neon replacements:
  - `#00d2ff` -> `COLOR_ACCENT_BLUE` (`#3b82f6`)
  - `#00a8ff` -> `COLOR_ACCENT_BLUE` (`#3b82f6`)
  - `#ff2a51` -> `COLOR_TEXT_PRIMARY` (`#f1f5f9`) or `COLOR_ACCENT_BLUE`
- Zero occurrences of `#00d2ff`, `#00a8ff`, or `#ff2a51` in those 3 files. Also sanitized `app/modules/virus_scanner.py` for repository cleanliness.

### M1: Standalone Build Spec Contract (`build.spec`)
- `datas` includes `('app/assets', 'app/assets')` and `('data', 'data')`.
- All paths verified to exist in repository.

### M2: Test Suite Contract (`tests/`)
- Test runner: `pytest` (v9.1.1).
- `tests/conftest.py`:
  - `qapp`: session fixture with `QT_QPA_PLATFORM=offscreen` and `QApplication(["--platform", "offscreen"])`.
  - `isolated_appdata`: temporary directory fixture patching `APPDATA_DIR`, `WHITELIST_FILE`, and `TELEGRAM_CONFIG_FILE`.
  - `mock_page_workers`: fixture monkeypatching `_start_worker` on `ProcessManagerPage`, `RamCleanerPage`, `NetworkMonitorPage`.
- Test files:
  - `tests/test_kernel_apis.py`: verifies `get_kernel_performance_info()` live and mock failure fallback.
  - `tests/test_access_gate.py`: verifies `is_machine_whitelisted()` and Telegram request/approval with mocked urllib requests.
  - `tests/test_process_utils.py`: verifies `kill_process_with_fallback()`.
  - `tests/test_gui_instantiation.py`: verifies offscreen instantiation and signal handling for all 9 application pages and widgets.

## Code Layout
- `app/utils/access_gate.py`: Exclusively owned by M1 Worker
- `build.spec`: Exclusively owned by M1 Worker
- `app/utils/process_utils.py`: Exclusively owned by M1 Worker
- `app/modules/process_manager.py`: Exclusively owned by M1 Worker
- `app/modules/ram_cleaner.py`: Exclusively owned by M1 Worker
- `app/modules/disk_cleanup.py`: Exclusively owned by M1 Worker
- `app/modules/startup_manager.py`: Exclusively owned by M1 Worker
- `app/tray.py`: Exclusively owned by M1 Worker
- `tests/*`: Exclusively owned by M2 Test Writer
- `TEST_INFRA.md`, `TEST_READY.md`: Exclusively owned by M2 Test Writer
