"""CLI print helpers used by the ``adb-control`` console script.

These helpers intentionally live inside the package so the console script
works after ``pip install`` even though ``scripts/`` is not packaged.
Standalone scripts under ``scripts/`` re-export these names for backwards
compatibility.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from adb_android_control.radio import (
    RadioScanner,
    freq_to_band,
    freq_to_channel,
    rssi_to_quality,
)

if TYPE_CHECKING:
    from adb_android_control.connection_monitor import ConnectionMonitor
    from adb_android_control.monitor import LogEntry, PerformanceSnapshot


def _line(text: str = "") -> None:
    """Write a single line of CLI output to stdout.

    Used instead of ``print`` so this module needs no print-lint suppression
    while producing identical terminal output.
    """
    sys.stdout.write(f"{text}\n")


# ---------------------------------------------------------------------------
# Monitor helpers
# ---------------------------------------------------------------------------

_LEVEL_COLORS: dict[str, str] = {
    "VERBOSE": "\033[37m",
    "DEBUG": "\033[34m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "FATAL": "\033[35m",
}
_RESET = "\033[0m"


def print_log_entry(entry: LogEntry) -> None:
    """ANSI-coloured pretty-print of a :class:`LogEntry`."""
    color = _LEVEL_COLORS.get(entry.level, "")
    _line(f"{color}[{entry.timestamp}] {entry.level[0]} {entry.tag}: {entry.message}{_RESET}")


def print_snapshot(snapshot: PerformanceSnapshot) -> None:
    """Compact pretty-print of a :class:`PerformanceSnapshot`."""
    _line(f"\n--- {snapshot.timestamp.strftime('%H:%M:%S')} ---")
    _line(f"Battery: {snapshot.battery_level}%")
    _line(f"CPU: {snapshot.cpu_usage:.1f}%")
    _line(f"Memory: {snapshot.memory_used_mb}/{snapshot.memory_total_mb} MB")
    _line(f"Disk: {snapshot.disk_used_percent:.1f}%")
    _line(f"Processes: {snapshot.running_processes}")


# ---------------------------------------------------------------------------
# Radio helpers
# ---------------------------------------------------------------------------

_HR = "=" * 60


def print_wifi_status(scanner: RadioScanner | None = None) -> None:
    """Print current Wi-Fi connection info."""
    scanner = scanner or RadioScanner()
    _line(_HR)
    _line("📶 WiFi Status")
    _line(_HR)

    adb_wifi = scanner.get_wifi()
    termux_wifi = scanner.get_wifi_via_termux() if adb_wifi is None else None

    if adb_wifi is not None:
        _line(f"  SSID:        {adb_wifi.ssid}")
        _line(f"  BSSID:       {adb_wifi.bssid}")
        _line(f"  Signal:      {adb_wifi.rssi_dbm} dBm ({rssi_to_quality(adb_wifi.rssi_dbm)})")
        _line(f"  Frequency:   {adb_wifi.frequency_mhz} MHz (Channel {adb_wifi.channel})")
        _line(f"  Band:        {adb_wifi.band}")
        _line(f"  Standard:    802.{adb_wifi.standard}")
        _line(f"  Link Speed:  {adb_wifi.link_speed_mbps} Mbps")
        _line(f"  TX Speed:    {adb_wifi.tx_speed_mbps} Mbps")
        _line(f"  RX Speed:    {adb_wifi.rx_speed_mbps} Mbps")
    elif termux_wifi is not None:
        rssi = termux_wifi.get("rssi", 0)
        freq = termux_wifi.get("frequency_mhz", 0)
        _line(f"  SSID:        {termux_wifi.get('ssid', 'Unknown')}")
        _line(f"  BSSID:       {termux_wifi.get('bssid', 'Unknown')}")
        _line(f"  Signal:      {rssi} dBm ({rssi_to_quality(rssi)})")
        _line(f"  Frequency:   {freq} MHz (Channel {freq_to_channel(freq)})")
        _line(f"  Band:        {freq_to_band(freq)}")
        _line(f"  Link Speed:  {termux_wifi.get('link_speed_mbps', 0)} Mbps")
        _line(f"  IP:          {termux_wifi.get('ip', 'Unknown')}")
    else:
        _line("  WiFi info not available")

    stats = scanner.get_link_stats()
    if stats:
        _line(
            f"\n  TX Stats:    Good: {stats.get('tx_good', 0)}, "
            f"Retry: {stats.get('tx_retry', 0)}, Bad: {stats.get('tx_bad', 0)}"
        )
        _line(f"  RX Stats:    Good: {stats.get('rx_good', 0)}")
    _line()


def print_wifi_scan(scanner: RadioScanner | None = None) -> None:
    """Print nearby Wi-Fi networks."""
    scanner = scanner or RadioScanner()
    _line(_HR)
    _line("📡 Nearby WiFi Networks")
    _line(_HR)

    networks = scanner.scan_wifi()
    if networks:
        _line(f"{'SSID':<25} {'RSSI':>6} {'Ch':>4} {'Band':<7} {'Security':<15}")
        _line("-" * 60)
        for net in networks[:15]:
            ssid = net["ssid"][:24] if net["ssid"] else "(hidden)"
            _line(
                f"{ssid:<25} {net['rssi_dbm']:>4}dB {net['channel']:>4} "
                f"{net['band']:<7} {net['security'][:14]:<15}"
            )
    else:
        _line("  Scan not available (may need location permission)")
    _line()


def print_bluetooth_status(scanner: RadioScanner | None = None) -> None:
    """Print Bluetooth adapter state."""
    scanner = scanner or RadioScanner()
    _line(_HR)
    _line("🔵 Bluetooth Status")
    _line(_HR)

    bt = scanner.get_bluetooth()
    if bt is not None:
        _line(f"  State:       {bt.state}")
        _line(f"  Enabled:     {bt.enabled}")
        _line(f"  Name:        {bt.name}")
        _line(f"  Address:     {bt.address}")
        devices = scanner.get_bluetooth_devices()
        if devices:
            _line("\n  Connected Devices:")
            for dev in devices:
                _line(f"    - {dev['address']} ({dev['name']})")
    else:
        _line("  Bluetooth info not available")
    _line()


def print_radio_capabilities(scanner: RadioScanner | None = None) -> None:
    """Print device radio capabilities (features, MIMO, channel lists)."""
    scanner = scanner or RadioScanner()
    _line(_HR)
    _line("📻 Radio Capabilities")
    _line(_HR)

    caps = scanner.get_capabilities()
    features = caps.get("features", [])
    if features:
        _line(f"  WiFi Features: {len(features)} supported")
        key_features = [
            "P2P",
            "TDLS",
            "D2D_RTT",
            "LOW_LATENCY",
            "DUAL_BAND_SIMULTANEOUS",
        ]
        for f in key_features:
            status = "✓" if f in features else "✗"
            _line(f"    {status} {f.replace('_', ' ').title()}")
    if caps.get("mimo_likely"):
        _line("\n  MIMO:        Supported (Multi-stream capable)")
    if caps.get("channels_24ghz"):
        _line(f"  2.4GHz Ch:   {caps['channels_24ghz']}")
    if caps.get("channels_5ghz"):
        _line(f"  5GHz Ch:     {caps['channels_5ghz']}")
    if caps.get("channels_6ghz"):
        chans = caps["channels_6ghz"]
        if len(chans) > 50:
            _line(f"  6GHz Ch:     {chans[:50]}...")
        else:
            _line(f"  6GHz Ch:     {chans}")
    _line()


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


def status(monitor: ConnectionMonitor) -> None:
    """Print current connection-monitor status."""
    state = monitor.get_current_state()
    _line("=" * 50)
    _line("Connection Monitor Status")
    _line("=" * 50)
    _line(f"  ADB Connected: {state.connected}")
    if state.connected:
        _line(f"  Address:       {state.ip}:{state.port}")
    _line(f"  WiFi SSID:     {state.ssid}")
    _line(f"  Signal:        {state.rssi_dbm} dBm")
    _line(f"  Frequency:     {state.frequency_mhz} MHz")
    _line()
    if monitor.last_state is not None:
        _line(f"  Last Check:    {monitor.last_state.timestamp}")
        _line(f"  Last Port:     {monitor.last_state.port}")


__all__ = [
    "print_bluetooth_status",
    "print_log_entry",
    "print_radio_capabilities",
    "print_snapshot",
    "print_wifi_scan",
    "print_wifi_status",
    "status",
]
