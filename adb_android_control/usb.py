"""USB device identification — read the standard 18-byte device descriptor.

Doctrine note
-------------
- ``parse_device_descriptor`` is a pure function: bytes in, structured
  result out. Heavily-parametrised property-fuzzable in Phase 3.
- ``USB_VENDORS`` and ``USB_KNOWN_DEVICES`` are module-level constants
  documenting the public lookup tables (Law 2: tables are data contracts).
- The Linux ioctl path lives in :func:`identify_via_ioctl`. It's
  Linux-only and not unit-tested here — covered by integration when a
  real USB device is attached.
"""

from __future__ import annotations

import ctypes
import fcntl
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------


USB_VENDORS: dict[int, str] = {
    0x04E8: "Samsung",
    0x05AC: "Apple",
    0x0483: "STMicroelectronics",
    0x067B: "Prolific",
    0x0781: "SanDisk",
    0x0BB4: "HTC",
    0x0BDA: "Realtek",
    0x0FCE: "Sony",
    0x1004: "LG",
    0x10C4: "Silicon Labs",
    0x12D1: "Huawei",
    0x18D1: "Google",
    0x19D2: "ZTE",
    0x1A40: "Terminus Hub",
    0x1A86: "QinHeng (CH340)",
    0x1D6B: "Linux Foundation",
    0x1F3A: "Allwinner",
    0x2109: "VIA Hub",
    0x22B8: "Motorola",
    0x2717: "Xiaomi",
    0x2A70: "OnePlus",
    0x2E8A: "Raspberry Pi",
    0x8087: "Intel",
}

USB_KNOWN_DEVICES: dict[tuple[int, int], str] = {
    (0x04E8, 0x6860): "Samsung Galaxy (MTP)",
    (0x04E8, 0x6861): "Samsung Galaxy (PTP)",
    (0x04E8, 0x6862): "Samsung Galaxy (RNDIS)",
    (0x18D1, 0x4EE1): "Google Pixel (MTP)",
    (0x18D1, 0x4EE2): "Google Pixel (PTP)",
    (0x22B8, 0x2E82): "Motorola (MTP)",
    (0x2717, 0xFF40): "Xiaomi (MTP)",
    (0x2A70, 0x9024): "OnePlus (MTP)",
}


# ---------------------------------------------------------------------------
# Pure parser
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class USBDeviceInfo:
    """Identification extracted from a USB device descriptor."""

    vid: int
    pid: int
    vendor_name: str
    device_name: str

    @property
    def vid_pid(self) -> str:
        """Canonical ``"vvvv:pppp"`` lowercased hex form."""
        return f"{self.vid:04x}:{self.pid:04x}"


def parse_device_descriptor(data: bytes) -> USBDeviceInfo | None:
    """Parse the standard 18-byte USB device descriptor.

    Returns ``None`` if ``data`` is shorter than 12 bytes (the minimum
    needed to read VID at offset 8-9 and PID at offset 10-11). Validates
    nothing about the prefix bytes — that's the caller's concern.

    Reference: USB 2.0 Specification §9.6.1.
    """
    if len(data) < 12:
        return None
    vid = data[8] | (data[9] << 8)
    pid = data[10] | (data[11] << 8)
    return USBDeviceInfo(
        vid=vid,
        pid=pid,
        vendor_name=USB_VENDORS.get(vid, "Unknown"),
        device_name=USB_KNOWN_DEVICES.get((vid, pid), f"Unknown (0x{vid:04x}:0x{pid:04x})"),
    )


# ---------------------------------------------------------------------------
# I/O paths (file-fd and ioctl) — thin wrappers around the parser
# ---------------------------------------------------------------------------


def identify_via_fd(fd: int) -> USBDeviceInfo | None:
    """Read 18 bytes from ``fd`` and parse them as a USB device descriptor.

    This is the path used by ``termux-usb -e`` callbacks: the Termux app
    opens the device, calls back with a file descriptor, and we just
    ``os.read`` the descriptor bytes.
    """
    try:
        data = os.read(fd, 18)
    except OSError as exc:
        logger.error("os.read on fd %d failed: %s", fd, exc)
        return None
    return parse_device_descriptor(data)


# USBDEVFS ioctl constant — Linux-specific.
# Source: linux/usb/usbdevice_fs.h
_USBDEVFS_CONTROL = 0xC0185500


class _CtrlTransfer(ctypes.Structure):
    """Mirrors `struct usbdevfs_ctrltransfer` from <linux/usb/usbdevice_fs.h>."""

    _fields_ = (
        ("bRequestType", ctypes.c_uint8),
        ("bRequest", ctypes.c_uint8),
        ("wValue", ctypes.c_uint16),
        ("wIndex", ctypes.c_uint16),
        ("wLength", ctypes.c_uint16),
        ("timeout", ctypes.c_uint32),
        ("data", ctypes.c_void_p),
    )


def identify_via_ioctl(fd: int) -> USBDeviceInfo | None:
    """Issue a USBDEVFS_CONTROL ioctl to retrieve the device descriptor.

    Linux-only. Returns ``None`` on any error. NOT unit-tested here —
    integration coverage requires a real attached USB device.
    """
    try:
        data = ctypes.create_string_buffer(18)
        ctrl = _CtrlTransfer()
        ctrl.bRequestType = 0x80  # USB_DIR_IN | USB_TYPE_STANDARD | USB_RECIP_DEVICE
        ctrl.bRequest = 0x06  # USB_REQ_GET_DESCRIPTOR
        ctrl.wValue = 0x0100  # USB_DT_DEVICE << 8
        ctrl.wIndex = 0
        ctrl.wLength = 18
        ctrl.timeout = 1000
        ctrl.data = ctypes.cast(data, ctypes.c_void_p)

        ret = fcntl.ioctl(fd, _USBDEVFS_CONTROL, ctrl)
    except OSError as exc:
        logger.error("USBDEVFS_CONTROL ioctl on fd %d failed: %s", fd, exc)
        return None

    if ret < 0:
        logger.error("USBDEVFS_CONTROL ioctl returned %d", ret)
        return None
    return parse_device_descriptor(bytes(data))
