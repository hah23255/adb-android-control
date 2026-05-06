"""Wi-Fi and Bluetooth radio scanning via ADB ``dumpsys`` and Termux API.

Doctrine note
-------------
Pure helpers (``freq_to_channel``, ``freq_to_band``, ``rssi_to_quality``)
are module-level functions — directly unit-testable without any I/O
(Doctrine Law 9: one concept per test).

The :class:`RadioScanner` class composes against the public
:meth:`ADBController.shell` API (Law 2) and accepts an injected
controller for test isolation (Law 5).

The Termux API path (``termux-wifi-connectioninfo``) uses ``subprocess.run``
directly because it is *not* an ADB call — it talks to the Termux app
over a local UNIX socket. ``shell=True`` is avoided everywhere; argv
form only.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any

from adb_android_control.controller import ADBController

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure helpers (no I/O, fully testable in isolation)
# ---------------------------------------------------------------------------


def freq_to_channel(freq_mhz: int) -> int:
    """Convert Wi-Fi frequency (MHz) to IEEE 802.11 channel number.

    Returns ``0`` if the frequency is not on the canonical channel-center
    grid for any supported band.

    The function validates *alignment* to the per-band 5 MHz grid in
    addition to the per-band frequency range. Off-grid inputs (gap-band
    frequencies, sub-MHz offsets) return ``0`` rather than a fictional
    channel number — see issue #4.

    Channel plans:

    - 2.4 GHz: channels 1-13 at ``2412 + 5 * (n - 1)`` MHz; channel 14
      alone at 2484 MHz. Frequencies 2473-2483 are the 12 MHz gap and
      have no channel.
    - 5 GHz: ``channel = (freq - 5000) / 5``; valid centers fall in
      ``[5170, 5825]`` (channels 34-165).
    - 6 GHz: channels 1, 5, 9, ..., 233 at ``5955 + 5 * (n - 1)`` MHz.
    """
    # 2.4 GHz: channels 1-13 at 2412+5*(n-1) MHz; channel 14 alone at 2484.
    if 2412 <= freq_mhz <= 2472 and (freq_mhz - 2412) % 5 == 0:
        return (freq_mhz - 2412) // 5 + 1
    if freq_mhz == 2484:
        return 14
    # 5 GHz: channel = (freq - 5000) / 5; valid in [5170, 5825].
    if 5170 <= freq_mhz <= 5825 and (freq_mhz - 5000) % 5 == 0:
        return (freq_mhz - 5000) // 5
    # 6 GHz: channels 1, 5, 9, ..., 233 at 5955+5*(n-1) MHz.
    if 5955 <= freq_mhz <= 7115 and (freq_mhz - 5955) % 5 == 0:
        return (freq_mhz - 5955) // 5 + 1
    return 0


def freq_to_band(freq_mhz: int) -> str:
    """Convert Wi-Fi frequency (MHz) to band name.

    Permissive by design: any frequency inside a band's overall envelope
    returns the band string, even if it is not on the canonical
    channel-center grid. Band classification is a coarser concept than
    channel number — see :func:`freq_to_channel` for the strict mapping.
    """
    if 2400 <= freq_mhz <= 2500:
        return "2.4GHz"
    if 5150 <= freq_mhz <= 5850:
        return "5GHz"
    if 5925 <= freq_mhz <= 7125:
        return "6GHz"
    return "Unknown"


def rssi_to_quality(rssi_dbm: int) -> str:
    """Convert RSSI in dBm to a qualitative description."""
    if rssi_dbm >= -50:
        return "Excellent"
    if rssi_dbm >= -60:
        return "Good"
    if rssi_dbm >= -70:
        return "Fair"
    if rssi_dbm >= -80:
        return "Weak"
    return "Poor"


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WiFiInfo:
    """Snapshot of the device's current Wi-Fi connection."""

    ssid: str
    bssid: str
    rssi_dbm: int
    frequency_mhz: int
    link_speed_mbps: int
    tx_speed_mbps: int
    rx_speed_mbps: int
    standard: str  # "11ac", "11ax", etc
    channel: int
    band: str
    ip: str = ""
    mac: str = ""
    security: str = ""


@dataclass(frozen=True)
class BluetoothInfo:
    """Bluetooth adapter status and connected devices."""

    enabled: bool
    name: str
    address: str
    state: str
    connected_devices: tuple[dict[str, str], ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Parser regexes (compiled once)
# ---------------------------------------------------------------------------


_WIFI_INFO_RE = re.compile(
    r"SSID:\s*\"([^\"]*)\".*?BSSID:\s*([0-9a-f:]+).*?RSSI:\s*(-?\d+).*?"
    r"Link speed:\s*(\d+).*?Tx Link speed:\s*(\d+).*?Rx Link speed:\s*(\d+).*?"
    r"Frequency:\s*(\d+).*?Wi-Fi standard:\s*(\w+)",
    re.IGNORECASE | re.DOTALL,
)
_SCAN_RESULT_RE = re.compile(
    r"([0-9a-f:]{17})\s+(\d+)\s+(-?\d+)\s+\[([^\]]*)\]\s+(.*)",
    re.IGNORECASE,
)
_BT_STATE_RE = re.compile(r"state:\s*(\w+)")
_BT_NAME_RE = re.compile(r"name:\s*(.+)")
_BT_ADDR_RE = re.compile(r"address:\s*([0-9A-Fa-f:X]+)")
_BT_DEVICE_RE = re.compile(r"([0-9A-Fa-f:]{17})\s*(\S+)?")
_LINK_STATS_RE = re.compile(r"tx=([0-9.]+),\s*([0-9.]+),\s*([0-9.]+)\s+rx=([0-9.]+)")


# ---------------------------------------------------------------------------
# Parsers (pure-ish — string in, structured out)
# ---------------------------------------------------------------------------


def parse_wifi_info(dumpsys_output: str) -> WiFiInfo | None:
    """Parse the `mWifiInfo` line of ``dumpsys wifi`` into :class:`WiFiInfo`."""
    if not dumpsys_output:
        return None
    match = _WIFI_INFO_RE.search(dumpsys_output)
    if match is None:
        return None
    freq = int(match.group(7))
    return WiFiInfo(
        ssid=match.group(1),
        bssid=match.group(2),
        rssi_dbm=int(match.group(3)),
        link_speed_mbps=int(match.group(4)),
        tx_speed_mbps=int(match.group(5)),
        rx_speed_mbps=int(match.group(6)),
        frequency_mhz=freq,
        standard=match.group(8),
        channel=freq_to_channel(freq),
        band=freq_to_band(freq),
    )


def parse_scan_results(scan_output: str) -> list[dict[str, Any]]:
    """Parse output of ``cmd wifi list-scan-results`` into network dicts.

    Sorted by RSSI descending (strongest first).
    """
    networks: list[dict[str, Any]] = []
    for line in scan_output.split("\n"):
        match = _SCAN_RESULT_RE.search(line)
        if match is None:
            continue
        freq = int(match.group(2))
        networks.append(
            {
                "bssid": match.group(1),
                "frequency_mhz": freq,
                "rssi_dbm": int(match.group(3)),
                "security": match.group(4),
                "ssid": match.group(5).strip(),
                "channel": freq_to_channel(freq),
                "band": freq_to_band(freq),
            }
        )
    return sorted(networks, key=lambda n: n["rssi_dbm"], reverse=True)


def parse_bluetooth_info(dumpsys_output: str) -> BluetoothInfo:
    """Parse `dumpsys bluetooth_manager` head into :class:`BluetoothInfo`."""
    enabled = "enabled: true" in dumpsys_output
    state_match = _BT_STATE_RE.search(dumpsys_output)
    name_match = _BT_NAME_RE.search(dumpsys_output)
    addr_match = _BT_ADDR_RE.search(dumpsys_output)
    return BluetoothInfo(
        enabled=enabled,
        state=state_match.group(1) if state_match else "UNKNOWN",
        name=name_match.group(1).strip() if name_match else "Unknown",
        address=addr_match.group(1) if addr_match else "Unknown",
    )


def parse_bluetooth_devices(dumpsys_output: str) -> list[dict[str, str]]:
    """Parse the `Connected devices` block into address/name records."""
    return [
        {"address": match.group(1), "name": match.group(2) or "Unknown"}
        for match in _BT_DEVICE_RE.finditer(dumpsys_output)
    ]


def parse_link_stats(stats_output: str) -> dict[str, float]:
    """Parse `tx=A,B,C rx=D` line from `dumpsys wifi` into a stats dict."""
    match = _LINK_STATS_RE.search(stats_output)
    if match is None:
        return {}
    return {
        "tx_good": float(match.group(1)),
        "tx_retry": float(match.group(2)),
        "tx_bad": float(match.group(3)),
        "rx_good": float(match.group(4)),
    }


# ---------------------------------------------------------------------------
# Scanner — the I/O-touching surface
# ---------------------------------------------------------------------------


class RadioScanner:
    """Aggregate Wi-Fi/Bluetooth/radio probes via ADB and Termux API.

    Pass an existing :class:`ADBController` via ``adb=`` for test injection;
    otherwise one is constructed eagerly.
    """

    def __init__(
        self,
        device_serial: str | None = None,
        *,
        adb: ADBController | None = None,
    ) -> None:
        self.adb: ADBController = adb if adb is not None else ADBController(device_serial)

    # -- Wi-Fi (host-side Termux API) ---------------------------------------

    @staticmethod
    def get_wifi_via_termux() -> dict[str, Any] | None:
        """Call ``termux-wifi-connectioninfo`` and parse its JSON. ``None`` on failure."""
        try:
            result = subprocess.run(
                ["termux-wifi-connectioninfo"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0 or not result.stdout.strip():
            return None
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    # -- Wi-Fi (ADB) --------------------------------------------------------

    def get_wifi(self) -> WiFiInfo | None:
        """Read the current Wi-Fi connection via ADB ``dumpsys wifi``."""
        try:
            output = self.adb.shell("dumpsys wifi | grep -E 'mWifiInfo|score=' | head -5")
        except Exception as exc:  # noqa: BLE001 — internal lesson (adaptive fault tolerance)
            logger.debug("get_wifi failed: %s", exc)
            return None
        return parse_wifi_info(output)

    def scan_wifi(self) -> list[dict[str, Any]]:
        """Run a Wi-Fi scan and return networks (sorted by RSSI desc)."""
        try:
            output = self.adb.shell("cmd wifi list-scan-results", timeout=15)
        except Exception as exc:  # noqa: BLE001
            logger.debug("scan_wifi failed: %s", exc)
            return []
        return parse_scan_results(output)

    def get_link_stats(self) -> dict[str, float]:
        """Pull tx/rx link-layer statistics from ``dumpsys wifi``."""
        try:
            output = self.adb.shell("dumpsys wifi | grep -E 'tx=|rx=|bcn=' | head -5")
        except Exception as exc:  # noqa: BLE001
            logger.debug("get_link_stats failed: %s", exc)
            return {}
        return parse_link_stats(output)

    # -- Bluetooth -----------------------------------------------------------

    def get_bluetooth(self) -> BluetoothInfo | None:
        """Read Bluetooth adapter state via ``dumpsys bluetooth_manager``."""
        try:
            output = self.adb.shell("dumpsys bluetooth_manager | head -50")
        except Exception as exc:  # noqa: BLE001
            logger.debug("get_bluetooth failed: %s", exc)
            return None
        return parse_bluetooth_info(output)

    def get_bluetooth_devices(self) -> list[dict[str, str]]:
        """Pull connected Bluetooth devices via ``dumpsys bluetooth_manager``."""
        try:
            output = self.adb.shell("dumpsys bluetooth_manager | grep -A2 'Connected devices'")
        except Exception as exc:  # noqa: BLE001
            logger.debug("get_bluetooth_devices failed: %s", exc)
            return []
        return parse_bluetooth_devices(output)

    # -- Radio capabilities -------------------------------------------------

    def get_capabilities(self) -> dict[str, Any]:
        """Aggregate features, MIMO support, and supported channel lists."""
        try:
            features_output = self.adb.shell(
                "dumpsys wifi | grep -i 'SupportedFeatures\\|MIMO\\|antenna\\|band' | head -10"
            )
        except Exception:  # noqa: BLE001
            features_output = ""

        try:
            channels_output = self.adb.shell("dumpsys wifi | grep -i 'SupportedChannelList'")
        except Exception:  # noqa: BLE001
            channels_output = ""

        features = re.findall(r"WIFI_FEATURE_(\w+)", features_output)
        result: dict[str, Any] = {
            "features": features,
            "mimo_likely": any(marker in features_output for marker in ("866", "1200", "2400")),
            "channels_24ghz": "",
            "channels_5ghz": "",
            "channels_6ghz": "",
        }
        ch_24 = re.search(r"SupportedChannelListIn24g\[([^\]]+)\]", channels_output)
        if ch_24:
            result["channels_24ghz"] = ch_24.group(1)
        ch_5 = re.search(r"SupportedChannelListIn5g\[([^\]]+)\]", channels_output)
        if ch_5:
            result["channels_5ghz"] = ch_5.group(1)
        ch_6 = re.search(r"SupportedChannelListIn6g\[([^\]]+)\]", channels_output)
        if ch_6:
            result["channels_6ghz"] = ch_6.group(1)
        return result
