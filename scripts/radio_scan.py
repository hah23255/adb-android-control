#!/usr/bin/env python3
"""Backwards-compatibility shim — canonical module is now
:mod:`adb_android_control.radio`. CLI print helpers preserved here.

Will be removed in v2.0.
"""

from __future__ import annotations

import sys
import warnings

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

warnings.warn(
    "scripts.radio_scan is deprecated; import from adb_android_control.radio "
    "instead. Will be removed in v2.0.",
    DeprecationWarning,
    stacklevel=2,
)


# ---------------------------------------------------------------------------
# CLI print helpers (kept here so the package stays I/O-free)
# ---------------------------------------------------------------------------


_HR = "=" * 60


def print_wifi_status(scanner: RadioScanner | None = None) -> None:
    """Print current Wi-Fi connection info."""
    scanner = scanner or RadioScanner()
    print(_HR)
    print("📶 WiFi Status")
    print(_HR)

    adb_wifi = scanner.get_wifi()
    termux_wifi = scanner.get_wifi_via_termux() if adb_wifi is None else None

    if adb_wifi is not None:
        print(f"  SSID:        {adb_wifi.ssid}")
        print(f"  BSSID:       {adb_wifi.bssid}")
        print(f"  Signal:      {adb_wifi.rssi_dbm} dBm ({rssi_to_quality(adb_wifi.rssi_dbm)})")
        print(f"  Frequency:   {adb_wifi.frequency_mhz} MHz (Channel {adb_wifi.channel})")
        print(f"  Band:        {adb_wifi.band}")
        print(f"  Standard:    802.{adb_wifi.standard}")
        print(f"  Link Speed:  {adb_wifi.link_speed_mbps} Mbps")
        print(f"  TX Speed:    {adb_wifi.tx_speed_mbps} Mbps")
        print(f"  RX Speed:    {adb_wifi.rx_speed_mbps} Mbps")
    elif termux_wifi is not None:
        rssi = termux_wifi.get("rssi", 0)
        freq = termux_wifi.get("frequency_mhz", 0)
        print(f"  SSID:        {termux_wifi.get('ssid', 'Unknown')}")
        print(f"  BSSID:       {termux_wifi.get('bssid', 'Unknown')}")
        print(f"  Signal:      {rssi} dBm ({rssi_to_quality(rssi)})")
        print(f"  Frequency:   {freq} MHz (Channel {freq_to_channel(freq)})")
        print(f"  Band:        {freq_to_band(freq)}")
        print(f"  Link Speed:  {termux_wifi.get('link_speed_mbps', 0)} Mbps")
        print(f"  IP:          {termux_wifi.get('ip', 'Unknown')}")
    else:
        print("  WiFi info not available")

    stats = scanner.get_link_stats()
    if stats:
        print(
            f"\n  TX Stats:    Good: {stats.get('tx_good', 0)}, "
            f"Retry: {stats.get('tx_retry', 0)}, Bad: {stats.get('tx_bad', 0)}"
        )
        print(f"  RX Stats:    Good: {stats.get('rx_good', 0)}")
    print()


def print_wifi_scan(scanner: RadioScanner | None = None) -> None:
    """Print nearby Wi-Fi networks."""
    scanner = scanner or RadioScanner()
    print(_HR)
    print("📡 Nearby WiFi Networks")
    print(_HR)

    networks = scanner.scan_wifi()
    if networks:
        print(f"{'SSID':<25} {'RSSI':>6} {'Ch':>4} {'Band':<7} {'Security':<15}")
        print("-" * 60)
        for net in networks[:15]:
            ssid = net["ssid"][:24] if net["ssid"] else "(hidden)"
            print(
                f"{ssid:<25} {net['rssi_dbm']:>4}dB {net['channel']:>4} "
                f"{net['band']:<7} {net['security'][:14]:<15}"
            )
    else:
        print("  Scan not available (may need location permission)")
    print()


def print_bluetooth_status(scanner: RadioScanner | None = None) -> None:
    """Print Bluetooth adapter state."""
    scanner = scanner or RadioScanner()
    print(_HR)
    print("🔵 Bluetooth Status")
    print(_HR)

    bt = scanner.get_bluetooth()
    if bt is not None:
        print(f"  State:       {bt.state}")
        print(f"  Enabled:     {bt.enabled}")
        print(f"  Name:        {bt.name}")
        print(f"  Address:     {bt.address}")
        devices = scanner.get_bluetooth_devices()
        if devices:
            print("\n  Connected Devices:")
            for dev in devices:
                print(f"    - {dev['address']} ({dev['name']})")
    else:
        print("  Bluetooth info not available")
    print()


def print_radio_capabilities(scanner: RadioScanner | None = None) -> None:
    """Print device radio capabilities (features, MIMO, channel lists)."""
    scanner = scanner or RadioScanner()
    print(_HR)
    print("📻 Radio Capabilities")
    print(_HR)

    caps = scanner.get_capabilities()
    features = caps.get("features", [])
    if features:
        print(f"  WiFi Features: {len(features)} supported")
        key_features = [
            "P2P",
            "TDLS",
            "D2D_RTT",
            "LOW_LATENCY",
            "DUAL_BAND_SIMULTANEOUS",
        ]
        for f in key_features:
            status = "✓" if f in features else "✗"
            print(f"    {status} {f.replace('_', ' ').title()}")
    if caps.get("mimo_likely"):
        print("\n  MIMO:        Supported (Multi-stream capable)")
    if caps.get("channels_24ghz"):
        print(f"  2.4GHz Ch:   {caps['channels_24ghz']}")
    if caps.get("channels_5ghz"):
        print(f"  5GHz Ch:     {caps['channels_5ghz']}")
    if caps.get("channels_6ghz"):
        chans = caps["channels_6ghz"]
        if len(chans) > 50:
            print(f"  6GHz Ch:     {chans[:50]}...")
        else:
            print(f"  6GHz Ch:     {chans}")
    print()


def main() -> None:
    """Pick subcommands from sys.argv[1:] (default: 'all')."""
    args = sys.argv[1:] if len(sys.argv) > 1 else ["all"]
    scanner = RadioScanner()

    if "wifi" in args or "all" in args:
        print_wifi_status(scanner)
    if "scan" in args or "all" in args:
        print_wifi_scan(scanner)
    if "bluetooth" in args or "bt" in args or "all" in args:
        print_bluetooth_status(scanner)
    if "caps" in args or "all" in args:
        print_radio_capabilities(scanner)


__all__ = [
    "BluetoothInfo",
    "RadioScanner",
    "WiFiInfo",
    "freq_to_band",
    "freq_to_channel",
    "main",
    "parse_bluetooth_devices",
    "parse_bluetooth_info",
    "parse_link_stats",
    "parse_scan_results",
    "parse_wifi_info",
    "print_bluetooth_status",
    "print_radio_capabilities",
    "print_wifi_scan",
    "print_wifi_status",
    "rssi_to_quality",
]


if __name__ == "__main__":
    main()
