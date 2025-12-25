#!/usr/bin/env python3
"""
ADB Controller - Main interface for Android device control.
Provides clean API for all ADB operations with error handling.
"""

import subprocess
import time
import re
import logging
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ADBError(Exception):
    """ADB operation failed."""
    pass


class DeviceState(Enum):
    """Device connection states."""
    DEVICE = "device"
    OFFLINE = "offline"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"


@dataclass
class DeviceInfo:
    """Device information container."""
    serial: str
    model: str
    android_version: str
    sdk_version: int
    screen_size: Tuple[int, int]
    battery_level: int
    state: DeviceState


class ADBController:
    """Main ADB controller class."""

    def __init__(self, device_serial: Optional[str] = None):
        """
        Initialize ADB controller.

        Args:
            device_serial: Target device serial (None for first available)
        """
        self.device_serial = device_serial
        self._verify_adb()

    def _verify_adb(self) -> None:
        """Verify ADB is available."""
        try:
            result = subprocess.run(['adb', 'version'], capture_output=True, text=True)
            if result.returncode != 0:
                raise ADBError("ADB not available")
        except FileNotFoundError:
            raise ADBError("ADB not installed or not in PATH")

    def _run(self, cmd: List[str], timeout: int = 30) -> str:
        """
        Run ADB command.

        Args:
            cmd: Command parts
            timeout: Timeout in seconds

        Returns:
            Command output

        Raises:
            ADBError: If command fails
        """
        full_cmd = ['adb']
        if self.device_serial:
            full_cmd.extend(['-s', self.device_serial])
        full_cmd.extend(cmd)

        logger.debug(f"Running: {' '.join(full_cmd)}")

        try:
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode != 0 and result.stderr:
                raise ADBError(f"Command failed: {result.stderr.strip()}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise ADBError(f"Command timed out after {timeout}s")

    def _shell(self, cmd: str, timeout: int = 30) -> str:
        """Run shell command on device."""
        return self._run(['shell', cmd], timeout)

    # === Device Management ===

    def devices(self) -> List[Dict[str, str]]:
        """List connected devices."""
        output = self._run(['devices', '-l'])
        devices = []
        for line in output.split('\n')[1:]:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2:
                device = {
                    'serial': parts[0],
                    'state': parts[1]
                }
                for part in parts[2:]:
                    if ':' in part:
                        key, val = part.split(':', 1)
                        device[key] = val
                devices.append(device)
        return devices

    def connect(self, host: str, port: int = 5555) -> bool:
        """Connect to device wirelessly."""
        try:
            result = self._run(['connect', f'{host}:{port}'])
            return 'connected' in result.lower()
        except ADBError:
            return False

    def disconnect(self, host: Optional[str] = None) -> bool:
        """Disconnect from device."""
        try:
            if host:
                self._run(['disconnect', host])
            else:
                self._run(['disconnect'])
            return True
        except ADBError:
            return False

    def get_device_info(self) -> DeviceInfo:
        """Get comprehensive device information."""
        model = self._shell('getprop ro.product.model')
        android_ver = self._shell('getprop ro.build.version.release')
        sdk = int(self._shell('getprop ro.build.version.sdk'))

        size_output = self._shell('wm size')
        match = re.search(r'(\d+)x(\d+)', size_output)
        screen = (int(match.group(1)), int(match.group(2))) if match else (0, 0)

        battery_output = self._shell('dumpsys battery | grep level')
        battery_match = re.search(r'level:\s*(\d+)', battery_output)
        battery = int(battery_match.group(1)) if battery_match else 0

        return DeviceInfo(
            serial=self.device_serial or 'unknown',
            model=model,
            android_version=android_ver,
            sdk_version=sdk,
            screen_size=screen,
            battery_level=battery,
            state=DeviceState.DEVICE
        )

    # === App Management ===

    def list_packages(self, third_party_only: bool = False) -> List[str]:
        """List installed packages."""
        cmd = 'pm list packages'
        if third_party_only:
            cmd += ' -3'
        output = self._shell(cmd)
        return [line.replace('package:', '') for line in output.split('\n') if line]

    def install_apk(self, apk_path: str, replace: bool = True,
                    grant_permissions: bool = False) -> bool:
        """Install APK."""
        cmd = ['install']
        if replace:
            cmd.append('-r')
        if grant_permissions:
            cmd.append('-g')
        cmd.append(apk_path)

        try:
            result = self._run(cmd, timeout=120)
            return 'success' in result.lower()
        except ADBError as e:
            logger.error(f"Install failed: {e}")
            return False

    def uninstall(self, package: str, keep_data: bool = False) -> bool:
        """Uninstall app."""
        cmd = ['uninstall']
        if keep_data:
            cmd.append('-k')
        cmd.append(package)

        try:
            result = self._run(cmd)
            return 'success' in result.lower()
        except ADBError:
            return False

    def clear_data(self, package: str) -> bool:
        """Clear app data."""
        try:
            result = self._shell(f'pm clear {package}')
            return 'success' in result.lower()
        except ADBError:
            return False

    def force_stop(self, package: str) -> None:
        """Force stop app."""
        self._shell(f'am force-stop {package}')

    def start_activity(self, package: str, activity: str) -> None:
        """Start activity."""
        self._shell(f'am start -n {package}/{activity}')

    def start_app(self, package: str) -> None:
        """Start app (launch main activity)."""
        self._shell(f'monkey -p {package} -c android.intent.category.LAUNCHER 1')

    def get_current_activity(self) -> str:
        """Get current foreground activity."""
        output = self._shell('dumpsys activity activities | grep mResumedActivity')
        return output

    # === File Operations ===

    def push(self, local_path: str, remote_path: str) -> bool:
        """Push file to device."""
        try:
            self._run(['push', local_path, remote_path], timeout=300)
            return True
        except ADBError as e:
            logger.error(f"Push failed: {e}")
            return False

    def pull(self, remote_path: str, local_path: str) -> bool:
        """Pull file from device."""
        try:
            self._run(['pull', remote_path, local_path], timeout=300)
            return True
        except ADBError as e:
            logger.error(f"Pull failed: {e}")
            return False

    def ls(self, path: str = '/sdcard') -> List[str]:
        """List directory contents."""
        output = self._shell(f'ls -la {path}')
        return output.split('\n')

    def mkdir(self, path: str) -> None:
        """Create directory."""
        self._shell(f'mkdir -p {path}')

    def rm(self, path: str, recursive: bool = False) -> None:
        """Remove file or directory."""
        cmd = 'rm -rf' if recursive else 'rm'
        self._shell(f'{cmd} {path}')

    # === Screen Operations ===

    def screenshot(self, local_path: str = 'screenshot.png') -> bool:
        """Take screenshot and save locally."""
        try:
            result = subprocess.run(
                ['adb'] + (['-s', self.device_serial] if self.device_serial else []) +
                ['exec-out', 'screencap', '-p'],
                capture_output=True,
                timeout=30
            )
            if result.returncode == 0:
                Path(local_path).write_bytes(result.stdout)
                return True
            return False
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return False

    def screen_record(self, remote_path: str = '/sdcard/recording.mp4',
                      time_limit: int = 30, bit_rate: int = 4000000) -> None:
        """Start screen recording (non-blocking)."""
        cmd = f'screenrecord --time-limit {time_limit} --bit-rate {bit_rate} {remote_path}'
        subprocess.Popen(
            ['adb'] + (['-s', self.device_serial] if self.device_serial else []) +
            ['shell', cmd]
        )

    def get_screen_size(self) -> Tuple[int, int]:
        """Get screen resolution."""
        output = self._shell('wm size')
        match = re.search(r'(\d+)x(\d+)', output)
        if match:
            return int(match.group(1)), int(match.group(2))
        return 0, 0

    # === Input Simulation ===

    def tap(self, x: int, y: int) -> None:
        """Tap at coordinates."""
        self._shell(f'input tap {x} {y}')

    def swipe(self, x1: int, y1: int, x2: int, y2: int,
              duration_ms: int = 300) -> None:
        """Swipe gesture."""
        self._shell(f'input swipe {x1} {y1} {x2} {y2} {duration_ms}')

    def long_press(self, x: int, y: int, duration_ms: int = 1000) -> None:
        """Long press at coordinates."""
        self._shell(f'input swipe {x} {y} {x} {y} {duration_ms}')

    def input_text(self, text: str) -> None:
        """Input text (spaces replaced with %s)."""
        escaped = text.replace(' ', '%s').replace("'", "\\'")
        self._shell(f"input text '{escaped}'")

    def key_event(self, keycode: int) -> None:
        """Send key event by code."""
        self._shell(f'input keyevent {keycode}')

    def press_home(self) -> None:
        """Press home button."""
        self.key_event(3)

    def press_back(self) -> None:
        """Press back button."""
        self.key_event(4)

    def press_menu(self) -> None:
        """Press menu button."""
        self.key_event(82)

    def press_enter(self) -> None:
        """Press enter key."""
        self.key_event(66)

    def press_power(self) -> None:
        """Press power button."""
        self.key_event(26)

    def wake_up(self) -> None:
        """Wake up device."""
        self.key_event(224)  # KEYCODE_WAKEUP

    def scroll_up(self, steps: int = 1) -> None:
        """Scroll up (swipe down)."""
        w, h = self.get_screen_size()
        for _ in range(steps):
            self.swipe(w // 2, h // 4, w // 2, h * 3 // 4, 200)

    def scroll_down(self, steps: int = 1) -> None:
        """Scroll down (swipe up)."""
        w, h = self.get_screen_size()
        for _ in range(steps):
            self.swipe(w // 2, h * 3 // 4, w // 2, h // 4, 200)

    # === System Info ===

    def get_battery_level(self) -> int:
        """Get battery level percentage."""
        output = self._shell('dumpsys battery | grep level')
        match = re.search(r'level:\s*(\d+)', output)
        return int(match.group(1)) if match else 0

    def get_property(self, prop: str) -> str:
        """Get system property."""
        return self._shell(f'getprop {prop}')

    def set_setting(self, namespace: str, key: str, value: str) -> None:
        """Set system setting."""
        self._shell(f'settings put {namespace} {key} {value}')

    def get_setting(self, namespace: str, key: str) -> str:
        """Get system setting."""
        return self._shell(f'settings get {namespace} {key}')

    # === Logcat ===

    def logcat(self, lines: int = 100, filter_tag: Optional[str] = None) -> str:
        """Get logcat output."""
        cmd = 'logcat -d'
        if filter_tag:
            cmd += f' -s "{filter_tag}:*"'
        cmd += f' | tail -n {lines}'
        return self._shell(cmd)

    def clear_logcat(self) -> None:
        """Clear logcat buffer."""
        self._shell('logcat -c')

    # === Power ===

    def reboot(self, mode: Optional[str] = None) -> None:
        """Reboot device."""
        cmd = ['reboot']
        if mode:
            cmd.append(mode)
        self._run(cmd)

    def set_stay_awake(self, enabled: bool) -> None:
        """Set stay awake while charging."""
        value = 'usb' if enabled else 'false'
        self._shell(f'svc power stayon {value}')


def main():
    """Demo usage."""
    adb = ADBController()

    print("=== ADB Controller Demo ===\n")

    # List devices
    devices = adb.devices()
    print(f"Connected devices: {len(devices)}")
    for d in devices:
        print(f"  {d['serial']} - {d['state']}")

    if not devices:
        print("No devices connected!")
        return

    # Device info
    print("\nDevice Info:")
    info = adb.get_device_info()
    print(f"  Model: {info.model}")
    print(f"  Android: {info.android_version}")
    print(f"  Screen: {info.screen_size[0]}x{info.screen_size[1]}")
    print(f"  Battery: {info.battery_level}%")

    # List packages
    print("\nThird-party apps:")
    packages = adb.list_packages(third_party_only=True)[:5]
    for pkg in packages:
        print(f"  {pkg}")

    print("\n=== Demo Complete ===")


if __name__ == '__main__':
    main()
