# Migration Guide

> *Upgrading from v1.0.x → v1.1.0 (and onward to v2.0).*

## v1.0.x → v1.0.1 (security release — history rewritten)

### Why force-push

`v1.0.0` shipped `device.env` to a public repo with real personally-
identifying information. The fix is `git filter-repo` to remove the
file and redact 7 token classes from every blob in history. **All
commit SHAs prior to `v1.0.1` are gone.**

### If you have a fork

```bash
# Back up any commits you'd added on top of upstream
git checkout main
git log --oneline upstream/main..HEAD > /tmp/my-commits.txt

# Reset to the new upstream
git fetch upstream
git reset --hard upstream/main
git push origin main --force

# Cherry-pick your commits back if needed (re-base on new history)
git cherry-pick <each commit from /tmp/my-commits.txt>
```

### If you have a local clone

```bash
cd adb-android-control
git fetch
git reset --hard origin/main
```

### If you have an open PR

The PR base is gone. Either:

1. **Re-create from the new main** (cleanest):
   ```bash
   git checkout -b my-feature-v2 origin/main
   git cherry-pick <your commits>
   git push origin my-feature-v2
   gh pr create
   ```

2. **Or rebase aggressively** (may have many conflicts):
   ```bash
   git rebase --onto origin/main <old-base-sha> <my-feature>
   git push origin my-feature --force-with-lease
   ```

## v1.0.x → v1.1.0 (package restructure)

The functional code moved from `scripts/*.py` into a proper Python
package at `adb_android_control/`. The old `scripts/*.py` are now
**deprecation shims** that re-export from the new location.

### What still works (no change needed)

```python
from scripts.adb_controller import ADBController        # ⚠️ DeprecationWarning
from scripts.adb_monitor    import LogcatMonitor        # ⚠️ DeprecationWarning
from scripts.adb_automation import ADBAutomation, AppTester  # ⚠️
```

These still import correctly but emit `DeprecationWarning`. They will
be **removed entirely in v2.0**.

### What's new (recommended)

```python
from adb_android_control import (
    ADBController, ADBError, DeviceOfflineError, DeviceInfo,
)
from adb_android_control.monitor import (
    LogcatMonitor, PerformanceMonitor, CrashMonitor,
)
from adb_android_control.automation import (
    ADBAutomation, AppTester, DeviceManager, ScreenRecorder,
)
from adb_android_control.radio import RadioScanner
from adb_android_control.connection_monitor import ConnectionMonitor
from adb_android_control.port_scan import PortScanner
from adb_android_control.usb import parse_device_descriptor, USBDeviceInfo
```

### Breaking changes in `1.1.0`

These are intentional improvements; old call sites will break with
clear errors.

| Old (v1.0.x) | New (v1.1.0) |
|---|---|
| `ADBError("...")` | Still works. Now base of typed hierarchy. New subclasses: `ADBNotFoundError`, `DeviceOfflineError`, `ADBTimeoutError`, `ADBPermissionError`. |
| `_execute_step` returned `bool \| str` | `execute_step` (no leading underscore) returns typed `StepOutcome` |
| `WiFiInfo.rssi: int` (dB unspecified) | `WiFiInfo.rssi_dbm: int` |
| `WiFiInfo.frequency: int` | `WiFiInfo.frequency_mhz: int` |
| `WiFiInfo.link_speed: int` | `WiFiInfo.link_speed_mbps: int` |
| `WiFiInfo.tx_speed`, `rx_speed` | `tx_speed_mbps`, `rx_speed_mbps` |
| `BluetoothInfo.connected_devices: list[Dict]` | `tuple[dict[str, str], ...]` (immutable; frozen dataclass) |
| `connection_monitor` events as `tuple[str, str]` | `Change(kind: ChangeType, detail: str)` typed dataclass |
| `time` field type implicit | All timestamps now timezone-aware UTC `datetime` |
| `subprocess.run(..., shell=True)` (in `radio_scan.py`) | argv-list only (security hardening) |

### Type-checking impact

If you use mypy: the new package ships a `py.typed` marker and is
fully typed. You may see new errors against your call sites that
previously passed silently. These are real type bugs the old code
hid — fix them.

### CLI change

The new `adb-control` console-script (after `pip install .[dev]`)
unifies what was previously a shell-script + several `python -m
scripts.*` invocations:

```bash
adb-control devices              # list
adb-control info                 # device snapshot
adb-control monitor logcat       # was: python -m scripts.adb_monitor logcat
adb-control workflow my.json     # was: python -m scripts.adb_automation
adb-control health               # was: python -m scripts.adb_automation (DeviceManager demo)
adb-control radio                # was: python -m scripts.radio_scan
adb-control connection check     # was: python -m scripts.connection_monitor check
adb-control scan-port 10.0.0.1   # was: python -m scripts.adb_port_scan 10.0.0.1
```

The old commands still work via the deprecation shims.

## v1.1.x → v2.0 (planned)

Preview of breaking changes coming in v2.0 (per the public roadmap):

- **`scripts/*.py` REMOVED entirely.** Migrate imports to
  `adb_android_control.*` before v2.0.
- **`ADBController.shell` may grow stricter input validation** for
  the package-name / property-key parameters (currently advisory
  per `SECURITY.md`).
- **CLI** may grow richer subcommand structure under `adb-control
  monitor` and `adb-control radio`.

We will publish a `v2.0.0-rc1` release with at least 30 days advance
notice before final v2.0.

## Help

If you hit a migration issue not covered here, please open a public
issue (NOT a security advisory) at
<https://github.com/hah23255/adb-android-control/issues>.
