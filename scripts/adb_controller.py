#!/usr/bin/env python3
"""Backwards-compatibility shim — the canonical module is now
:mod:`adb_android_control.controller`.

The old :mod:`scripts.adb_controller` symbols are re-exported below.
This file will be removed in v2.0; please migrate imports.
"""

from __future__ import annotations

import warnings

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

warnings.warn(
    "scripts.adb_controller is deprecated; import from adb_android_control instead. "
    "This shim will be removed in v2.0.",
    DeprecationWarning,
    stacklevel=2,
)


def main() -> None:
    """Demo runner — prints connected devices and basic info."""
    adb = ADBController()
    print("=== ADB Controller Demo ===\n")
    devices = adb.devices()
    print(f"Connected devices: {len(devices)}")
    for d in devices:
        print(f"  {d['serial']} - {d['state']}")
    if not devices:
        print("No devices connected!")
        return
    info = adb.get_device_info()
    print("\nDevice Info:")
    print(f"  Model: {info.model}")
    print(f"  Android: {info.android_version}")
    print(f"  Screen: {info.screen_size[0]}x{info.screen_size[1]}")
    print(f"  Battery: {info.battery_level}%")
    print("\nThird-party apps:")
    for pkg in adb.list_packages(third_party_only=True)[:5]:
        print(f"  {pkg}")
    print("\n=== Demo Complete ===")


__all__ = [
    "ADBController",
    "ADBError",
    "ADBNotFoundError",
    "ADBPermissionError",
    "ADBTimeoutError",
    "DeviceInfo",
    "DeviceOfflineError",
    "DeviceState",
    "main",
]


if __name__ == "__main__":
    main()
