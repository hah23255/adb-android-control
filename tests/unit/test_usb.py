"""Unit tests for :mod:`adb_android_control.usb`.

Doctrine: AAA (Law 3); ``parse_device_descriptor`` is the canonical
property-fuzzing target for Phase 3. Here we cover hand-crafted
descriptor bytes and lookup-table contracts.
"""

from __future__ import annotations

import os

import pytest

from adb_android_control.usb import (
    USB_KNOWN_DEVICES,
    USB_VENDORS,
    USBDeviceInfo,
    identify_via_fd,
    parse_device_descriptor,
)

pytestmark = pytest.mark.unit


def _make_descriptor(vid: int, pid: int) -> bytes:
    """Construct an 18-byte USB device descriptor with given VID/PID."""
    buf = bytearray(18)
    buf[0] = 18           # bLength
    buf[1] = 0x01         # bDescriptorType (DEVICE)
    buf[8] = vid & 0xFF
    buf[9] = (vid >> 8) & 0xFF
    buf[10] = pid & 0xFF
    buf[11] = (pid >> 8) & 0xFF
    return bytes(buf)


# ---------------------------------------------------------------------------
# parse_device_descriptor — pure
# ---------------------------------------------------------------------------


class TestParseDeviceDescriptor:
    def test_extracts_vid_pid_from_known_samsung_device(self) -> None:
        # Arrange
        data = _make_descriptor(0x04E8, 0x6860)

        # Act
        info = parse_device_descriptor(data)

        # Assert
        assert info is not None
        assert info.vid == 0x04E8
        assert info.pid == 0x6860
        assert info.vendor_name == "Samsung"
        assert info.device_name == "Samsung Galaxy (MTP)"

    def test_extracts_vid_pid_from_known_pixel_device(self) -> None:
        # Arrange
        data = _make_descriptor(0x18D1, 0x4EE1)

        # Act
        info = parse_device_descriptor(data)

        # Assert
        assert info is not None
        assert info.vid == 0x18D1
        assert info.pid == 0x4EE1
        assert info.vendor_name == "Google"
        assert info.device_name == "Google Pixel (MTP)"

    def test_unknown_vid_returns_unknown_vendor(self) -> None:
        # Arrange — a VID not in the table
        data = _make_descriptor(0xFFFF, 0x1234)

        # Act
        info = parse_device_descriptor(data)

        # Assert
        assert info is not None
        assert info.vendor_name == "Unknown"

    def test_known_vendor_with_unknown_pid_falls_back_to_hex(self) -> None:
        # Arrange — Samsung VID, unrecognized PID
        data = _make_descriptor(0x04E8, 0xDEAD)

        # Act
        info = parse_device_descriptor(data)

        # Assert
        assert info is not None
        assert info.vendor_name == "Samsung"
        assert "0x04e8:0xdead" in info.device_name

    @pytest.mark.parametrize("size", [0, 1, 7, 11])
    def test_returns_none_when_descriptor_too_short(self, size: int) -> None:
        # Arrange
        data = b"\x00" * size

        # Act + Assert — graceful degradation, no crash
        assert parse_device_descriptor(data) is None

    def test_extracts_at_minimum_12_bytes(self) -> None:
        """Just enough bytes to read VID (8-9) and PID (10-11)."""
        # Arrange
        data = bytearray(12)
        data[8:12] = bytes([0xE8, 0x04, 0x60, 0x68])

        # Act
        info = parse_device_descriptor(bytes(data))

        # Assert
        assert info is not None
        assert info.vid == 0x04E8
        assert info.pid == 0x6860

    def test_full_18_byte_descriptor_works(self) -> None:
        # Arrange
        data = _make_descriptor(0x2A70, 0x9024)

        # Act
        info = parse_device_descriptor(data)

        # Assert
        assert info is not None
        assert info.device_name == "OnePlus (MTP)"


# ---------------------------------------------------------------------------
# USBDeviceInfo helpers
# ---------------------------------------------------------------------------


class TestUSBDeviceInfo:
    def test_vid_pid_format_is_lowercase_hex_with_colon(self) -> None:
        # Arrange + Act
        info = USBDeviceInfo(
            vid=0x04E8,
            pid=0x6860,
            vendor_name="Samsung",
            device_name="X",
        )

        # Assert
        assert info.vid_pid == "04e8:6860"

    def test_vid_pid_pads_short_values(self) -> None:
        # Arrange + Act
        info = USBDeviceInfo(vid=0x1, pid=0xA, vendor_name="X", device_name="Y")

        # Assert
        assert info.vid_pid == "0001:000a"

    def test_is_frozen(self) -> None:
        # Arrange
        info = USBDeviceInfo(vid=1, pid=2, vendor_name="A", device_name="B")

        # Act + Assert
        with pytest.raises(Exception):  # noqa: B017
            info.vid = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Lookup-table contract tests (Doctrine Law 2: tables are public API)
# ---------------------------------------------------------------------------


class TestLookupTables:
    def test_all_known_devices_have_known_vendor(self) -> None:
        """Every (vid, pid) in USB_KNOWN_DEVICES must map back to a known vendor."""
        # Arrange + Act + Assert
        for vid, _pid in USB_KNOWN_DEVICES:
            assert vid in USB_VENDORS, (
                f"VID 0x{vid:04x} listed in USB_KNOWN_DEVICES but missing "
                f"from USB_VENDORS — table inconsistency"
            )

    def test_vendor_table_uses_lowercase_hex_keys(self) -> None:
        """Defensive: ensure the table keys are within USB VID range (0x0000-0xFFFF)."""
        # Arrange + Act + Assert
        for vid in USB_VENDORS:
            assert 0 <= vid <= 0xFFFF, f"VID {vid:#x} out of valid USB range"

    def test_vendor_table_has_no_empty_names(self) -> None:
        # Arrange + Act + Assert
        for vid, name in USB_VENDORS.items():
            assert name.strip(), f"VID 0x{vid:04x} has empty/whitespace name"


# ---------------------------------------------------------------------------
# identify_via_fd — file-descriptor I/O path
# ---------------------------------------------------------------------------


class TestIdentifyViaFd:
    def test_reads_and_parses_descriptor(self) -> None:
        # Arrange — use a real OS pipe so os.read works without mocking
        r, w = os.pipe()
        try:
            os.write(w, _make_descriptor(0x18D1, 0x4EE1))

            # Act
            info = identify_via_fd(r)

            # Assert
            assert info is not None
            assert info.vendor_name == "Google"
            assert info.device_name == "Google Pixel (MTP)"
        finally:
            os.close(r)
            os.close(w)

    def test_returns_none_on_oserror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange — bad fd will OSError
        def _raise(*_a: object, **_k: object) -> bytes:
            raise OSError("bad fd")

        monkeypatch.setattr(os, "read", _raise)

        # Act + Assert — internal lesson (adaptive fault tolerance) graceful degradation
        assert identify_via_fd(99999) is None
