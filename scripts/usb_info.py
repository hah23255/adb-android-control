#!/usr/bin/env python3
"""Backwards-compatibility shim — canonical module is now
:mod:`adb_android_control.usb`. CLI preserved.

This shim handles the ``termux-usb -e`` callback case where TERMUX_USB_FD
is set in the environment. Will be removed in v2.0.
"""

from __future__ import annotations

import os
import sys
import warnings

from adb_android_control.usb import identify_via_fd

warnings.warn(
    "scripts.usb_info is deprecated; import from adb_android_control.usb "
    "instead. Will be removed in v2.0.",
    DeprecationWarning,
    stacklevel=2,
)


def main() -> None:
    """CLI entry: read the descriptor from $TERMUX_USB_FD or argv[1]."""
    fd = int(os.environ.get("TERMUX_USB_FD", sys.argv[1] if len(sys.argv) > 1 else 0))
    info = identify_via_fd(fd)
    if info is None:
        print("Could not read USB descriptor.")  # noqa: T201
        return
    print(f"Vendor ID:  0x{info.vid:04x}")  # noqa: T201
    print(f"Product ID: 0x{info.pid:04x}")  # noqa: T201
    print(f"Device:     {info.device_name}")  # noqa: T201


__all__ = ["main"]


if __name__ == "__main__":
    main()
