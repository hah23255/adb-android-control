#!/usr/bin/env python3
"""Backwards-compatibility shim — canonical module is now
:mod:`adb_android_control.automation`. Will be removed in v2.0.
"""

from __future__ import annotations

import json
import warnings

from adb_android_control.automation import (
    ADBAutomation,
    AppTester,
    AutomationResult,
    AutomationStep,
    DeviceManager,
    InstallAndLaunchResult,
    ScreenRecorder,
    StepOutcome,
)

warnings.warn(
    "scripts.adb_automation is deprecated; import from "
    "adb_android_control.automation instead. Will be removed in v2.0.",
    DeprecationWarning,
    stacklevel=2,
)


def main() -> None:
    """Demo entrypoint — prints a device health check as JSON."""
    print("=== ADB Automation Demo ===\n")
    mgr = DeviceManager()
    print(json.dumps(mgr.health_check(), indent=2))
    print("\n=== Demo Complete ===")


__all__ = [
    "ADBAutomation",
    "AppTester",
    "AutomationResult",
    "AutomationStep",
    "DeviceManager",
    "InstallAndLaunchResult",
    "ScreenRecorder",
    "StepOutcome",
    "main",
]


if __name__ == "__main__":
    main()
