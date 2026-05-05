#!/usr/bin/env python3
"""Backwards-compatibility shim — canonical module is now
:mod:`adb_android_control.usb`. CLI preserved.

Will be removed in v2.0.
"""

from __future__ import annotations

import sys
import warnings

from adb_android_control.usb import (
    USB_KNOWN_DEVICES,
    USB_VENDORS,
    USBDeviceInfo,
    identify_via_fd,
    identify_via_ioctl,
    parse_device_descriptor,
)

warnings.warn(
    "scripts.usb_identify is deprecated; import from "
    "adb_android_control.usb instead. Will be removed in v2.0.",
    DeprecationWarning,
    stacklevel=2,
)


def main() -> None:
    """CLI entry: identify USB device on the file descriptor passed as argv[1]."""
    fd = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    info = identify_via_ioctl(fd)
    if info is None:
        print("Could not identify device (ioctl failed).")
        return
    print(f"VID:PID = {info.vid_pid}")
    print(f"Vendor  = {info.vendor_name}")
    print(f"Device  = {info.device_name}")


__all__ = [
    "USB_KNOWN_DEVICES",
    "USB_VENDORS",
    "USBDeviceInfo",
    "identify_via_fd",
    "identify_via_ioctl",
    "main",
    "parse_device_descriptor",
]


if __name__ == "__main__":
    main()
