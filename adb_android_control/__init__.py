"""Android device control via ADB."""
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

__version__ = "2.0.3"
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

# Public submodules.
from adb_android_control import (  # noqa: F401
    automation,
    connection_monitor,
    monitor,
    port_scan,
    radio,
    usb,
)
