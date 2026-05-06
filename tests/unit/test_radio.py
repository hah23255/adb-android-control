"""Unit tests for :mod:`adb_android_control.radio`.

Doctrine: AAA (Law 3), pure-function tests where possible (Law 9), no
real subprocess (Law 6 via injected mock controller), no real network.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from adb_android_control.controller import ADBController, ADBError
from adb_android_control.radio import (
    BluetoothInfo,
    RadioScanner,
    WiFiInfo,
    freq_to_band,
    freq_to_channel,
    parse_bluetooth_devices,
    parse_bluetooth_info,
    parse_link_stats,
    parse_scan_results,
    parse_wifi_info,
    rssi_to_quality,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Pure conversion helpers
# ---------------------------------------------------------------------------


class TestFrequencyToChannel:
    @pytest.mark.parametrize(
        ("freq", "expected_channel"),
        [
            # 2.4 GHz
            (2412, 1),
            (2437, 6),
            (2462, 11),
            (2472, 13),
            (2484, 14),  # special-case channel 14
            # 5 GHz
            (5180, 36),
            (5200, 40),
            (5825, 165),
            # 6 GHz
            (5955, 1),
            (5975, 5),
            (7115, 233),
            # Out of range → 0
            (1, 0),
            (10000, 0),
            (5900, 0),  # gap between 5GHz and 6GHz
        ],
    )
    def test_frequency_to_channel_mapping(self, freq: int, expected_channel: int) -> None:
        # Arrange + Act + Assert
        assert freq_to_channel(freq) == expected_channel

    # ------------------------------------------------------------------
    # Issue #4 — off-grid frequencies must return 0, not a fictional
    # channel number. Hand-written cases complement the alignment-
    # invariant Hypothesis properties.
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("freq", [2473, 2474, 2477, 2480, 2483])
    def test_24ghz_gap_band_returns_zero(self, freq: int) -> None:
        # The 12 MHz gap between channel 13 (2472) and channel 14 (2484)
        # has no channel; the buggy implementation mapped these to 13/14/15.
        assert freq_to_channel(freq) == 0

    @pytest.mark.parametrize("freq", [2413, 2414, 2415, 2416, 2418, 2438])
    def test_24ghz_off_grid_returns_zero(self, freq: int) -> None:
        # Sub-5-MHz offsets inside the 2.4 GHz band must not be mapped.
        assert freq_to_channel(freq) == 0

    @pytest.mark.parametrize("freq", [5171, 5172, 5181, 5189, 5821, 5824])
    def test_5ghz_off_grid_returns_zero(self, freq: int) -> None:
        # 5 GHz frequencies not aligned to the 5 MHz channel grid (i.e.
        # ``(freq - 5000) % 5 != 0``). Buggy implementation fabricated
        # channels 34, 37, 164. Note: 5175 IS aligned (channel 35), so
        # it is intentionally excluded here.
        assert freq_to_channel(freq) == 0

    @pytest.mark.parametrize("freq", [5956, 5957, 5974, 7114])
    def test_6ghz_off_grid_returns_zero(self, freq: int) -> None:
        # 6 GHz off-grid frequencies must return 0.
        assert freq_to_channel(freq) == 0

    @pytest.mark.parametrize("freq", [2411, 2485, 5169, 5826, 5954, 7116])
    def test_band_boundary_just_outside_returns_zero(self, freq: int) -> None:
        # One MHz outside any band's outer envelope must return 0.
        assert freq_to_channel(freq) == 0


class TestFrequencyToBand:
    @pytest.mark.parametrize(
        ("freq", "expected_band"),
        [
            (2400, "2.4GHz"),
            (2462, "2.4GHz"),
            (2500, "2.4GHz"),
            (5150, "5GHz"),
            (5500, "5GHz"),
            (5850, "5GHz"),
            (5925, "6GHz"),
            (6500, "6GHz"),
            (7125, "6GHz"),
            (1, "Unknown"),
            (8000, "Unknown"),
        ],
    )
    def test_frequency_to_band_mapping(self, freq: int, expected_band: str) -> None:
        assert freq_to_band(freq) == expected_band


class TestRssiToQuality:
    @pytest.mark.parametrize(
        ("rssi", "expected_quality"),
        [
            (-30, "Excellent"),
            (-50, "Excellent"),
            (-51, "Good"),
            (-60, "Good"),
            (-65, "Fair"),
            (-70, "Fair"),
            (-75, "Weak"),
            (-80, "Weak"),
            (-90, "Poor"),
            (-100, "Poor"),
        ],
    )
    def test_rssi_quality_mapping(self, rssi: int, expected_quality: str) -> None:
        # Arrange + Act + Assert
        assert rssi_to_quality(rssi) == expected_quality


# ---------------------------------------------------------------------------
# parse_wifi_info
# ---------------------------------------------------------------------------


class TestParseWifiInfo:
    def test_parses_well_formed_dumpsys_output(self) -> None:
        # Arrange — a synthetic dumpsys-style line (no real device data)
        dumpsys = (
            'mWifiInfo SSID: "TestNet", BSSID: aa:bb:cc:dd:ee:ff, '
            "RSSI: -55, Link speed: 866, Tx Link speed: 866, Rx Link speed: 866, "
            "Frequency: 5500, Wi-Fi standard: 11ac"
        )

        # Act
        info = parse_wifi_info(dumpsys)

        # Assert
        assert info is not None
        assert info.ssid == "TestNet"
        assert info.bssid == "aa:bb:cc:dd:ee:ff"
        assert info.rssi_dbm == -55
        assert info.link_speed_mbps == 866
        assert info.frequency_mhz == 5500
        assert info.standard == "11ac"
        assert info.channel == 100  # (5500 - 5170) // 5 + 34 = 100
        assert info.band == "5GHz"

    @pytest.mark.parametrize(
        "garbage",
        [
            "",
            "totally unrelated text",
            'SSID: "Net" but missing other fields',
        ],
    )
    def test_returns_none_for_unparseable_input(self, garbage: str) -> None:
        # Arrange + Act + Assert
        assert parse_wifi_info(garbage) is None


# ---------------------------------------------------------------------------
# parse_scan_results
# ---------------------------------------------------------------------------


class TestParseScanResults:
    def test_parses_multiple_networks_sorted_by_rssi(self) -> None:
        # Arrange
        scan = (
            "aa:bb:cc:dd:ee:01 2412 -70 [WPA2-PSK-CCMP] WeakNet\n"
            "aa:bb:cc:dd:ee:02 5180 -45 [WPA3-SAE] StrongNet\n"
            "aa:bb:cc:dd:ee:03 2462 -60 [WPA2-PSK-CCMP] MidNet\n"
        )

        # Act
        networks = parse_scan_results(scan)

        # Assert — sorted strongest-first
        assert [n["ssid"] for n in networks] == ["StrongNet", "MidNet", "WeakNet"]
        assert networks[0]["rssi_dbm"] == -45
        assert networks[0]["band"] == "5GHz"
        assert networks[2]["band"] == "2.4GHz"

    def test_skips_garbage_lines(self) -> None:
        # Arrange
        scan = (
            "header line not a result\n"
            "aa:bb:cc:dd:ee:02 5180 -45 [WPA3-SAE] OnlyValid\n"
            "more junk\n"
            "\n"
        )

        # Act
        networks = parse_scan_results(scan)

        # Assert
        assert len(networks) == 1
        assert networks[0]["ssid"] == "OnlyValid"

    def test_empty_input_returns_empty_list(self) -> None:
        assert parse_scan_results("") == []


# ---------------------------------------------------------------------------
# parse_bluetooth_info / devices
# ---------------------------------------------------------------------------


class TestParseBluetoothInfo:
    def test_extracts_state_name_address_when_enabled(self) -> None:
        # Arrange
        out = (
            "Bluetooth Manager:\n"
            "  enabled: true\n"
            "  state: ON\n"
            "  name: TestDevice\n"
            "  address: AA:BB:CC:DD:EE:FF\n"
        )

        # Act
        info = parse_bluetooth_info(out)

        # Assert
        assert info.enabled is True
        assert info.state == "ON"
        assert info.name == "TestDevice"
        assert info.address == "AA:BB:CC:DD:EE:FF"

    def test_disabled_when_no_enabled_marker(self) -> None:
        # Arrange
        out = "  state: OFF\n"

        # Act
        info = parse_bluetooth_info(out)

        # Assert
        assert info.enabled is False
        assert info.state == "OFF"
        assert info.name == "Unknown"
        assert info.address == "Unknown"

    def test_address_with_redaction_x_pattern_passes_through(self) -> None:
        """Some adb builds redact MAC bytes as X. Our parser preserves the visible part."""
        # Arrange
        out = "address: XX:XX:XX:XX:B6:6C\n"

        # Act
        info = parse_bluetooth_info(out)

        # Assert
        assert info.address == "XX:XX:XX:XX:B6:6C"


class TestParseBluetoothDevices:
    def test_extracts_address_name_pairs(self) -> None:
        # Arrange
        out = (
            "Connected devices:\n  AA:11:22:33:44:55  Headphones\n  BB:11:22:33:44:55  CarStereo\n"
        )

        # Act
        devices = parse_bluetooth_devices(out)

        # Assert
        addresses = [d["address"] for d in devices]
        assert "AA:11:22:33:44:55" in addresses
        assert "BB:11:22:33:44:55" in addresses


# ---------------------------------------------------------------------------
# parse_link_stats
# ---------------------------------------------------------------------------


class TestParseLinkStats:
    def test_extracts_four_stat_fields(self) -> None:
        # Arrange
        out = "tx=1234.5, 12.3, 0.5 rx=9999.9 bcn=42"

        # Act
        stats = parse_link_stats(out)

        # Assert
        assert stats == {
            "tx_good": 1234.5,
            "tx_retry": 12.3,
            "tx_bad": 0.5,
            "rx_good": 9999.9,
        }

    def test_unparseable_returns_empty(self) -> None:
        assert parse_link_stats("nothing relevant") == {}


# ---------------------------------------------------------------------------
# RadioScanner — DI'd controller
# ---------------------------------------------------------------------------


def _mock_controller() -> ADBController:
    mock = MagicMock(spec_set=ADBController)
    mock.device_serial = None
    return mock


class TestRadioScannerErrorPaths:
    """internal lesson (adaptive fault tolerance).

    Adaptive Fault Tolerance: each probe degrades to a sensible default.
    """

    def test_get_wifi_returns_none_when_shell_fails(self) -> None:
        # Arrange
        adb = _mock_controller()
        adb.shell.side_effect = ADBError("device offline")
        scanner = RadioScanner(adb=adb)

        # Act
        result = scanner.get_wifi()

        # Assert
        assert result is None

    def test_scan_wifi_returns_empty_list_on_error(self) -> None:
        # Arrange
        adb = _mock_controller()
        adb.shell.side_effect = ADBError("permission denied")
        scanner = RadioScanner(adb=adb)

        # Act
        result = scanner.scan_wifi()

        # Assert
        assert result == []

    def test_get_bluetooth_returns_none_on_error(self) -> None:
        # Arrange
        adb = _mock_controller()
        adb.shell.side_effect = ADBError("offline")
        scanner = RadioScanner(adb=adb)

        # Act + Assert
        assert scanner.get_bluetooth() is None

    def test_get_link_stats_returns_empty_dict_on_error(self) -> None:
        # Arrange
        adb = _mock_controller()
        adb.shell.side_effect = ADBError("oops")
        scanner = RadioScanner(adb=adb)

        # Act + Assert
        assert scanner.get_link_stats() == {}


class TestRadioScannerHappyPath:
    def test_get_wifi_parses_dumpsys_into_wifi_info(self) -> None:
        # Arrange
        adb = _mock_controller()
        adb.shell.return_value = (
            'mWifiInfo SSID: "Home", BSSID: 11:22:33:44:55:66, RSSI: -52, '
            "Link speed: 433, Tx Link speed: 433, Rx Link speed: 433, "
            "Frequency: 5180, Wi-Fi standard: 11ax"
        )
        scanner = RadioScanner(adb=adb)

        # Act
        info = scanner.get_wifi()

        # Assert
        assert isinstance(info, WiFiInfo)
        assert info.ssid == "Home"
        assert info.frequency_mhz == 5180
        assert info.band == "5GHz"

    def test_get_capabilities_extracts_features_and_channels(self) -> None:
        # Arrange
        adb = _mock_controller()

        def shell_router(cmd: str, **_: object) -> str:
            if "SupportedFeatures" in cmd or "MIMO" in cmd:
                return "WIFI_FEATURE_P2P WIFI_FEATURE_TDLS speed: 866"
            if "SupportedChannelList" in cmd:
                return (
                    "SupportedChannelListIn24g[1,2,3,4,5,6,7,8,9,10,11] "
                    "SupportedChannelListIn5g[36,40,44,48] "
                    "SupportedChannelListIn6g[1,5,9,13]"
                )
            return ""

        adb.shell.side_effect = shell_router
        scanner = RadioScanner(adb=adb)

        # Act
        caps = scanner.get_capabilities()

        # Assert
        assert "P2P" in caps["features"]
        assert "TDLS" in caps["features"]
        assert caps["mimo_likely"] is True
        assert caps["channels_24ghz"] == "1,2,3,4,5,6,7,8,9,10,11"
        assert caps["channels_5ghz"] == "36,40,44,48"
        assert caps["channels_6ghz"] == "1,5,9,13"


# ---------------------------------------------------------------------------
# Termux fallback
# ---------------------------------------------------------------------------


class TestTermuxFallback:
    def test_returns_none_when_termux_binary_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        import subprocess as sp

        def _missing(*_a: object, **_k: object) -> object:
            raise FileNotFoundError("termux-wifi-connectioninfo not on PATH")

        monkeypatch.setattr(sp, "run", _missing)

        # Act + Assert
        assert RadioScanner.get_wifi_via_termux() is None

    def test_returns_none_when_output_is_not_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        import subprocess as sp

        class _FakeResult:
            returncode = 0
            stdout = "not json at all"
            stderr = ""

        def _ok(*_a: object, **_k: object) -> _FakeResult:
            return _FakeResult()

        monkeypatch.setattr(sp, "run", _ok)

        # Act + Assert
        assert RadioScanner.get_wifi_via_termux() is None

    def test_returns_dict_for_valid_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        import subprocess as sp

        class _FakeResult:
            returncode = 0
            stdout = '{"ssid": "TestNet", "rssi": -50, "frequency_mhz": 5180}'
            stderr = ""

        def _ok(*_a: object, **_k: object) -> _FakeResult:
            return _FakeResult()

        monkeypatch.setattr(sp, "run", _ok)

        # Act
        data = RadioScanner.get_wifi_via_termux()

        # Assert
        assert data == {"ssid": "TestNet", "rssi": -50, "frequency_mhz": 5180}


# ---------------------------------------------------------------------------
# Value object frozen contract
# ---------------------------------------------------------------------------


class TestValueObjects:
    def test_wifi_info_is_frozen(self) -> None:
        # Arrange
        info = WiFiInfo(
            ssid="X",
            bssid="00:11:22:33:44:55",
            rssi_dbm=-50,
            frequency_mhz=5180,
            link_speed_mbps=433,
            tx_speed_mbps=433,
            rx_speed_mbps=433,
            standard="11ac",
            channel=36,
            band="5GHz",
        )

        # Act + Assert
        with pytest.raises(Exception):  # noqa: B017
            info.ssid = "Y"  # type: ignore[misc]

    def test_bluetooth_info_is_frozen(self) -> None:
        # Arrange
        bt = BluetoothInfo(enabled=True, name="X", address="A", state="ON")

        # Act + Assert
        with pytest.raises(Exception):  # noqa: B017
            bt.enabled = False  # type: ignore[misc]
