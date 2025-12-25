#!/data/data/com.termux/files/usr/bin/python3
"""
Radio Scanner - WiFi and Bluetooth status and scanning for Android/Termux
Uses both Termux API and ADB for comprehensive radio information.
"""

import subprocess
import json
import re
import sys
from dataclasses import dataclass
from typing import Optional, List, Dict

@dataclass
class WiFiInfo:
    ssid: str
    bssid: str
    rssi: int  # dBm
    frequency: int  # MHz
    link_speed: int  # Mbps
    tx_speed: int
    rx_speed: int
    standard: str  # 11ac, 11ax, etc
    channel: int
    band: str  # 2.4GHz, 5GHz, 6GHz
    ip: str
    mac: str
    security: str

@dataclass
class BluetoothInfo:
    enabled: bool
    name: str
    address: str
    state: str
    connected_devices: List[Dict]

def run_cmd(cmd: str, timeout: int = 10) -> str:
    """Run shell command and return output."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True,
                                text=True, timeout=timeout)
        return result.stdout + result.stderr
    except:
        return ""

def freq_to_channel(freq: int) -> int:
    """Convert frequency to WiFi channel number."""
    if 2412 <= freq <= 2484:
        if freq == 2484:
            return 14
        return (freq - 2412) // 5 + 1
    elif 5170 <= freq <= 5825:
        return (freq - 5170) // 5 + 34
    elif 5955 <= freq <= 7115:  # 6GHz
        return (freq - 5955) // 5 + 1
    return 0

def freq_to_band(freq: int) -> str:
    """Convert frequency to band name."""
    if 2400 <= freq <= 2500:
        return "2.4GHz"
    elif 5150 <= freq <= 5850:
        return "5GHz"
    elif 5925 <= freq <= 7125:
        return "6GHz"
    return "Unknown"

def get_wifi_termux() -> Optional[Dict]:
    """Get WiFi info via Termux API."""
    output = run_cmd("termux-wifi-connectioninfo 2>/dev/null")
    try:
        return json.loads(output)
    except:
        return None

def get_wifi_adb() -> Optional[WiFiInfo]:
    """Get detailed WiFi info via ADB dumpsys."""
    output = run_cmd("adb shell dumpsys wifi 2>/dev/null | grep -E 'mWifiInfo|score=' | head -5")

    if not output:
        return None

    # Parse mWifiInfo line
    match = re.search(r'SSID: "([^"]*)".*BSSID: ([0-9a-f:]+).*RSSI: (-?\d+).*'
                      r'Link speed: (\d+).*Tx Link speed: (\d+).*Rx Link speed: (\d+).*'
                      r'Frequency: (\d+).*Wi-Fi standard: (\w+)', output, re.IGNORECASE)

    if match:
        freq = int(match.group(7))
        return WiFiInfo(
            ssid=match.group(1),
            bssid=match.group(2),
            rssi=int(match.group(3)),
            link_speed=int(match.group(4)),
            tx_speed=int(match.group(5)),
            rx_speed=int(match.group(6)),
            frequency=freq,
            standard=match.group(8),
            channel=freq_to_channel(freq),
            band=freq_to_band(freq),
            ip="",
            mac="",
            security=""
        )
    return None

def get_wifi_scan_adb() -> List[Dict]:
    """Get nearby WiFi networks via ADB."""
    output = run_cmd("adb shell cmd wifi list-scan-results 2>/dev/null", timeout=15)
    networks = []

    for line in output.split('\n'):
        # Parse scan result lines
        match = re.search(r'([0-9a-f:]{17})\s+(\d+)\s+(-?\d+)\s+\[([^\]]*)\]\s+(.*)', line, re.I)
        if match:
            freq = int(match.group(2))
            networks.append({
                'bssid': match.group(1),
                'frequency': freq,
                'rssi': int(match.group(3)),
                'security': match.group(4),
                'ssid': match.group(5).strip(),
                'channel': freq_to_channel(freq),
                'band': freq_to_band(freq)
            })

    return sorted(networks, key=lambda x: x['rssi'], reverse=True)

def get_bluetooth_adb() -> Optional[BluetoothInfo]:
    """Get Bluetooth info via ADB."""
    output = run_cmd("adb shell dumpsys bluetooth_manager 2>/dev/null | head -50")

    enabled = "enabled: true" in output
    state_match = re.search(r'state: (\w+)', output)
    name_match = re.search(r"name: (.+)", output)
    addr_match = re.search(r'address: ([0-9A-Fa-f:X]+)', output)

    return BluetoothInfo(
        enabled=enabled,
        state=state_match.group(1) if state_match else "UNKNOWN",
        name=name_match.group(1).strip() if name_match else "Unknown",
        address=addr_match.group(1) if addr_match else "Unknown",
        connected_devices=[]
    )

def get_bluetooth_devices_adb() -> List[Dict]:
    """Get connected Bluetooth devices."""
    output = run_cmd("adb shell dumpsys bluetooth_manager 2>/dev/null | grep -A2 'Connected devices'")
    devices = []
    # Parse connected devices
    for match in re.finditer(r'([0-9A-Fa-f:]{17})\s*(\S+)?', output):
        devices.append({
            'address': match.group(1),
            'name': match.group(2) or 'Unknown'
        })
    return devices

def get_wifi_link_stats() -> Dict:
    """Get detailed WiFi link layer stats."""
    output = run_cmd("adb shell dumpsys wifi 2>/dev/null | grep -E 'tx=|rx=|bcn=' | head -5")
    stats = {}

    # Parse tx/rx stats
    match = re.search(r'tx=([0-9.]+),\s*([0-9.]+),\s*([0-9.]+)\s+rx=([0-9.]+)', output)
    if match:
        stats['tx_good'] = float(match.group(1))
        stats['tx_retry'] = float(match.group(2))
        stats['tx_bad'] = float(match.group(3))
        stats['rx_good'] = float(match.group(4))

    return stats

def rssi_to_quality(rssi: int) -> str:
    """Convert RSSI to signal quality description."""
    if rssi >= -50:
        return "Excellent"
    elif rssi >= -60:
        return "Good"
    elif rssi >= -70:
        return "Fair"
    elif rssi >= -80:
        return "Weak"
    else:
        return "Poor"

def print_wifi_status():
    """Print current WiFi status."""
    print("=" * 60)
    print("📶 WiFi Status")
    print("=" * 60)

    # Try Termux API first
    termux_wifi = get_wifi_termux()
    adb_wifi = get_wifi_adb()

    if adb_wifi:
        print(f"  SSID:        {adb_wifi.ssid}")
        print(f"  BSSID:       {adb_wifi.bssid}")
        print(f"  Signal:      {adb_wifi.rssi} dBm ({rssi_to_quality(adb_wifi.rssi)})")
        print(f"  Frequency:   {adb_wifi.frequency} MHz (Channel {adb_wifi.channel})")
        print(f"  Band:        {adb_wifi.band}")
        print(f"  Standard:    802.{adb_wifi.standard}")
        print(f"  Link Speed:  {adb_wifi.link_speed} Mbps")
        print(f"  TX Speed:    {adb_wifi.tx_speed} Mbps")
        print(f"  RX Speed:    {adb_wifi.rx_speed} Mbps")
    elif termux_wifi:
        rssi = termux_wifi.get('rssi', 0)
        freq = termux_wifi.get('frequency_mhz', 0)
        print(f"  SSID:        {termux_wifi.get('ssid', 'Unknown')}")
        print(f"  BSSID:       {termux_wifi.get('bssid', 'Unknown')}")
        print(f"  Signal:      {rssi} dBm ({rssi_to_quality(rssi)})")
        print(f"  Frequency:   {freq} MHz (Channel {freq_to_channel(freq)})")
        print(f"  Band:        {freq_to_band(freq)}")
        print(f"  Link Speed:  {termux_wifi.get('link_speed_mbps', 0)} Mbps")
        print(f"  IP:          {termux_wifi.get('ip', 'Unknown')}")
    else:
        print("  WiFi info not available")

    # Link stats
    stats = get_wifi_link_stats()
    if stats:
        print(f"\n  TX Stats:    Good: {stats.get('tx_good', 0)}, Retry: {stats.get('tx_retry', 0)}, Bad: {stats.get('tx_bad', 0)}")
        print(f"  RX Stats:    Good: {stats.get('rx_good', 0)}")
    print()

def print_wifi_scan():
    """Print nearby WiFi networks."""
    print("=" * 60)
    print("📡 Nearby WiFi Networks")
    print("=" * 60)

    networks = get_wifi_scan_adb()
    if networks:
        print(f"{'SSID':<25} {'RSSI':>6} {'Ch':>4} {'Band':<7} {'Security':<15}")
        print("-" * 60)
        for net in networks[:15]:  # Top 15
            ssid = net['ssid'][:24] if net['ssid'] else "(hidden)"
            print(f"{ssid:<25} {net['rssi']:>4}dB {net['channel']:>4} {net['band']:<7} {net['security'][:14]:<15}")
    else:
        print("  Scan not available (may need location permission)")
    print()

def print_bluetooth_status():
    """Print Bluetooth status."""
    print("=" * 60)
    print("🔵 Bluetooth Status")
    print("=" * 60)

    bt = get_bluetooth_adb()
    if bt:
        print(f"  State:       {bt.state}")
        print(f"  Enabled:     {bt.enabled}")
        print(f"  Name:        {bt.name}")
        print(f"  Address:     {bt.address}")

        devices = get_bluetooth_devices_adb()
        if devices:
            print(f"\n  Connected Devices:")
            for dev in devices:
                print(f"    - {dev['address']} ({dev['name']})")
    else:
        print("  Bluetooth info not available")
    print()

def print_radio_capabilities():
    """Print device radio capabilities."""
    print("=" * 60)
    print("📻 Radio Capabilities")
    print("=" * 60)

    output = run_cmd("adb shell dumpsys wifi 2>/dev/null | grep -i 'SupportedFeatures\\|MIMO\\|antenna\\|band' | head -10")

    # Parse features
    if "WIFI_FEATURE" in output:
        features = re.findall(r'WIFI_FEATURE_(\w+)', output)
        print(f"  WiFi Features: {len(features)} supported")
        key_features = ['P2P', 'TDLS', 'D2D_RTT', 'LOW_LATENCY', 'DUAL_BAND_SIMULTANEOUS']
        for f in key_features:
            status = "✓" if f in features else "✗"
            print(f"    {status} {f.replace('_', ' ').title()}")

    # Check MIMO support (implied by high speeds)
    if "866" in output or "1200" in output or "2400" in output:
        print(f"\n  MIMO:        Supported (Multi-stream capable)")

    # Supported channels
    ch_output = run_cmd("adb shell dumpsys wifi 2>/dev/null | grep -i 'SupportedChannelList'")
    if "24g" in ch_output.lower():
        ch_24 = re.search(r'SupportedChannelListIn24g\[([^\]]+)\]', ch_output)
        if ch_24:
            print(f"  2.4GHz Ch:   {ch_24.group(1)}")
    if "5g" in ch_output.lower():
        ch_5 = re.search(r'SupportedChannelListIn5g\[([^\]]+)\]', ch_output)
        if ch_5:
            print(f"  5GHz Ch:     {ch_5.group(1)}")
    if "6g" in ch_output.lower():
        ch_6 = re.search(r'SupportedChannelListIn6g\[([^\]]+)\]', ch_output)
        if ch_6:
            channels = ch_6.group(1)
            print(f"  6GHz Ch:     {channels[:50]}..." if len(channels) > 50 else f"  6GHz Ch:     {channels}")
    print()

def main():
    args = sys.argv[1:] if len(sys.argv) > 1 else ['all']

    if 'wifi' in args or 'all' in args:
        print_wifi_status()

    if 'scan' in args or 'all' in args:
        print_wifi_scan()

    if 'bluetooth' in args or 'bt' in args or 'all' in args:
        print_bluetooth_status()

    if 'caps' in args or 'all' in args:
        print_radio_capabilities()

if __name__ == "__main__":
    main()
