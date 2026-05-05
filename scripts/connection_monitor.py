#!/usr/bin/env python3
"""Backwards-compatibility shim — canonical module is now
:mod:`adb_android_control.connection_monitor`. CLI entry preserved.

Will be removed in v2.0.
"""

from __future__ import annotations

import sys
import warnings

from adb_android_control.connection_monitor import (
    Change,
    ChangeType,
    ConnectionMonitor,
    ConnectionState,
    detect_changes,
    fetch_adb_status,
    fetch_wifi_info,
    parse_adb_devices,
)

warnings.warn(
    "scripts.connection_monitor is deprecated; import from "
    "adb_android_control.connection_monitor instead. Will be removed in v2.0.",
    DeprecationWarning,
    stacklevel=2,
)


def status(monitor: ConnectionMonitor) -> None:
    """Print current connection-monitor status."""
    state = monitor.get_current_state()
    print("=" * 50)
    print("Connection Monitor Status")
    print("=" * 50)
    print(f"  ADB Connected: {state.connected}")
    if state.connected:
        print(f"  Address:       {state.ip}:{state.port}")
    print(f"  WiFi SSID:     {state.ssid}")
    print(f"  Signal:        {state.rssi_dbm} dBm")
    print(f"  Frequency:     {state.frequency_mhz} MHz")
    print()
    if monitor.last_state is not None:
        print(f"  Last Check:    {monitor.last_state.timestamp}")
        print(f"  Last Port:     {monitor.last_state.port}")


def main() -> None:
    """CLI entry — supports status / check / run subcommands."""
    monitor = ConnectionMonitor()
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "status":
            status(monitor)
        elif cmd == "check":
            changes = monitor.check()
            if changes:
                for c in changes:
                    print(f"{c.kind.value}: {c.detail}")
            else:
                print("No changes")
        elif cmd == "run":
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            monitor.run(interval_s=interval)
    else:
        status(monitor)
        changes = monitor.check()
        if changes:
            print("Changes detected:")
            for c in changes:
                print(f"  {c.kind.value}: {c.detail}")


__all__ = [
    "Change",
    "ChangeType",
    "ConnectionMonitor",
    "ConnectionState",
    "detect_changes",
    "fetch_adb_status",
    "fetch_wifi_info",
    "main",
    "parse_adb_devices",
    "status",
]


if __name__ == "__main__":
    main()
