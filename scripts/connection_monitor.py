#!/data/data/com.termux/files/usr/bin/python3
"""
Connection Monitor - Watches ADB connection and WiFi changes
Detects port changes, network switches, and connection drops
"""

import subprocess
import time
import json
import os
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class ConnectionState:
    timestamp: str
    connected: bool
    ip: str
    port: int
    ssid: str
    rssi: int
    frequency: int

class ConnectionMonitor:
    def __init__(self):
        self.config_file = Path.home() / ".adb_devices"
        self.log_file = Path.home() / ".adb_monitor.log"
        self.state_file = Path.home() / ".adb_state.json"
        self.last_state: Optional[ConnectionState] = None
        self.load_state()

    def log(self, msg: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} {msg}"
        print(line)
        with open(self.log_file, "a") as f:
            f.write(line + "\n")

    def notify(self, title: str, msg: str):
        """Send notification via Termux API"""
        try:
            subprocess.run([
                "termux-notification",
                "-t", title,
                "-c", msg,
                "--priority", "high"
            ], timeout=5)
        except:
            pass

    def run_cmd(self, cmd: str, timeout: int = 5) -> str:
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True,
                                    text=True, timeout=timeout)
            return result.stdout.strip()
        except:
            return ""

    def get_wifi_info(self) -> Dict:
        """Get current WiFi connection info"""
        output = self.run_cmd("termux-wifi-connectioninfo 2>/dev/null")
        try:
            return json.loads(output)
        except:
            return {}

    def get_adb_status(self) -> tuple:
        """Get ADB connection status - returns (connected, ip, port)"""
        output = self.run_cmd("adb devices 2>/dev/null")
        for line in output.split('\n'):
            if '\tdevice' in line:
                addr = line.split('\t')[0]
                if ':' in addr:
                    ip, port = addr.rsplit(':', 1)
                    return True, ip, int(port)
        return False, "", 0

    def get_current_state(self) -> ConnectionState:
        wifi = self.get_wifi_info()
        connected, ip, port = self.get_adb_status()

        return ConnectionState(
            timestamp=datetime.now().isoformat(),
            connected=connected,
            ip=ip,
            port=port,
            ssid=wifi.get('ssid', 'Unknown'),
            rssi=wifi.get('rssi', 0),
            frequency=wifi.get('frequency_mhz', 0)
        )

    def save_state(self, state: ConnectionState):
        with open(self.state_file, 'w') as f:
            json.dump({
                'timestamp': state.timestamp,
                'connected': state.connected,
                'ip': state.ip,
                'port': state.port,
                'ssid': state.ssid,
                'rssi': state.rssi,
                'frequency': state.frequency
            }, f)

    def load_state(self):
        try:
            with open(self.state_file) as f:
                data = json.load(f)
                self.last_state = ConnectionState(**data)
        except:
            self.last_state = None

    def detect_changes(self, current: ConnectionState) -> list:
        """Detect what changed between states"""
        changes = []

        if not self.last_state:
            if current.connected:
                changes.append(("CONNECTED", f"{current.ip}:{current.port}"))
            return changes

        last = self.last_state

        # Connection state change
        if last.connected and not current.connected:
            changes.append(("DISCONNECTED", f"Lost connection to {last.ip}:{last.port}"))

        elif not last.connected and current.connected:
            changes.append(("CONNECTED", f"{current.ip}:{current.port}"))

        # Port changed (while connected)
        elif current.connected and last.port != current.port:
            changes.append(("PORT_CHANGED", f"{last.port} → {current.port}"))

        # IP changed (network switch)
        elif current.connected and last.ip != current.ip:
            changes.append(("NETWORK_CHANGED", f"{last.ip} → {current.ip}"))

        # SSID changed
        if last.ssid != current.ssid and current.ssid != 'Unknown':
            changes.append(("WIFI_CHANGED", f"{last.ssid} → {current.ssid}"))

        # Signal strength significant change (>10 dB)
        if abs(last.rssi - current.rssi) > 10:
            changes.append(("SIGNAL_CHANGED", f"{last.rssi}dB → {current.rssi}dB"))

        return changes

    def update_config(self, ip: str, port: int):
        """Update ~/.adb_devices with new port"""
        if not self.config_file.exists():
            return

        content = self.config_file.read_text()
        lines = []
        for line in content.split('\n'):
            if '=' in line and not line.startswith('#'):
                name, addr = line.split('=', 1)
                if ip in addr:
                    lines.append(f"{name}={ip}:{port}")
                    continue
            lines.append(line)

        self.config_file.write_text('\n'.join(lines))

    def check(self) -> list:
        """Single check - returns list of changes"""
        current = self.get_current_state()
        changes = self.detect_changes(current)

        for change_type, detail in changes:
            self.log(f"[{change_type}] {detail}")

            # Auto-update config on port change
            if change_type == "PORT_CHANGED" and current.connected:
                self.update_config(current.ip, current.port)
                self.log(f"[CONFIG_UPDATED] {current.ip}:{current.port}")

            # Notify on important changes
            if change_type in ("DISCONNECTED", "PORT_CHANGED", "NETWORK_CHANGED"):
                self.notify("ADB Monitor", f"{change_type}: {detail}")

        self.last_state = current
        self.save_state(current)

        return changes

    def run(self, interval: int = 10):
        """Continuous monitoring loop"""
        self.log("[MONITOR_START] Connection monitor started")
        self.notify("ADB Monitor", "Monitoring started")

        while True:
            try:
                self.check()
                time.sleep(interval)
            except KeyboardInterrupt:
                self.log("[MONITOR_STOP] Stopped by user")
                break
            except Exception as e:
                self.log(f"[ERROR] {e}")
                time.sleep(interval)

    def status(self):
        """Print current status"""
        state = self.get_current_state()
        print("=" * 50)
        print("Connection Monitor Status")
        print("=" * 50)
        print(f"  ADB Connected: {state.connected}")
        if state.connected:
            print(f"  Address:       {state.ip}:{state.port}")
        print(f"  WiFi SSID:     {state.ssid}")
        print(f"  Signal:        {state.rssi} dBm")
        print(f"  Frequency:     {state.frequency} MHz")
        print()

        if self.last_state:
            print(f"  Last Check:    {self.last_state.timestamp}")
            print(f"  Last Port:     {self.last_state.port}")

if __name__ == "__main__":
    import sys

    monitor = ConnectionMonitor()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "status":
            monitor.status()
        elif cmd == "check":
            changes = monitor.check()
            if changes:
                for c, d in changes:
                    print(f"{c}: {d}")
            else:
                print("No changes")
        elif cmd == "run":
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            monitor.run(interval)
    else:
        # Default: single check and status
        monitor.status()
        changes = monitor.check()
        if changes:
            print("Changes detected:")
            for c, d in changes:
                print(f"  {c}: {d}")
