#!/usr/bin/env python3
"""Backwards-compatibility shim — canonical module is now
:mod:`adb_android_control.port_scan`. CLI preserved.

Will be removed in v2.0.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

from adb_android_control.port_scan import (
    PortScanner,
    check_port,
    read_last_port,
    rewrite_devices_config,
    save_last_port,
    try_adb_connect,
    update_devices_file,
)

warnings.warn(
    "scripts.adb_port_scan is deprecated; import from "
    "adb_android_control.port_scan instead. Will be removed in v2.0.",
    DeprecationWarning,
    stacklevel=2,
)


def main() -> None:
    """CLI entry: scan a port range, update ``~/.adb_devices`` if found."""
    ip = sys.argv[1] if len(sys.argv) > 1 else "<DEVICE_IP_HOME>"
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 30000
    end = int(sys.argv[3]) if len(sys.argv) > 3 else 45000

    print(f"Scanning {ip} ports {start}-{end}...")
    scanner = PortScanner()
    port = scanner.find_adb_port(ip, start=start, end=end)

    if port:
        print(f"\n✓ ADB found at {ip}:{port}")
        update_devices_file(
            Path.home() / ".adb_devices", name="ZFOLD7", ip=ip, port=port
        )
        save_last_port(Path.home() / ".adb_last_port", port)
        print(f"Config updated. Use: adb -s {ip}:{port} shell")
    else:
        print("\n✗ No ADB port found.")
        print("Ensure Wireless Debugging is enabled on device.")


__all__ = [
    "PortScanner",
    "check_port",
    "main",
    "read_last_port",
    "rewrite_devices_config",
    "save_last_port",
    "try_adb_connect",
    "update_devices_file",
]


if __name__ == "__main__":
    main()
