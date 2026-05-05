"""adb-android-control — Comprehensive Android device control via ADB.

Public API entrypoint. Most users want :class:`ADBController` from
``adb_android_control.controller``.

Doctrine: Master Tester Doctrine — see ``docs/TESTING_DOCTRINE.md``.
"""

from __future__ import annotations

from adb_android_control.controller import (
    ADBController,
    ADBError,
    ADBNotFoundError,
    ADBPermissionError,
    ADBTimeoutError,
    DeviceInfo,
    DeviceOfflineError,
    DeviceState,
)

__version__ = "2.0.0"
__all__ = [
    "ADBController",
    "ADBError",
    "ADBNotFoundError",
    "ADBPermissionError",
    "ADBTimeoutError",
    "DeviceInfo",
    "DeviceOfflineError",
    "DeviceState",
    "__version__",
]

# Submodules — importable via `from adb_android_control import <name>`
from adb_android_control import (  # noqa: F401
    automation,
    connection_monitor,
    monitor,
    port_scan,
    radio,
    usb,
)
