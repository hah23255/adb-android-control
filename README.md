# ADB Android Control Skill

Comprehensive Android device control via ADB (Android Debug Bridge) for Claude Code.

## Features

- **App Management**: Install, uninstall, list packages, clear data
- **File Operations**: Push/pull files, browse filesystem
- **Screen Control**: Screenshots, screen recording
- **Input Simulation**: Taps, swipes, text input, key events
- **Shell Access**: Run commands on device
- **Debugging**: Logcat, dumpsys, system info
- **Automation**: Python scripts for complex workflows
- **Auto-Connect**: Persistent wireless ADB with auto-reconnect
- **Port Scanning**: Automatic port detection when connection changes
- **Connection Monitor**: Real-time monitoring with notifications
- **Radio Scanner**: WiFi/Bluetooth status, signal strength, MIMO
- **USB Detection**: Identify USB devices via OTG

## Prerequisites

- ADB installed (comes with Termux `pkg install android-tools`)
- Android device with Developer Options enabled
- USB debugging or Wireless debugging enabled

## Installation

```bash
# Install the skill
claude /plugin marketplace add ~/.claude/skills/adb-android-control
```

## Device Connection

### Wireless ADB (Recommended)

1. Enable Wireless Debugging on Android device:
   - Settings > Developer Options > Wireless Debugging

2. Pair (first time only):
   ```bash
   adb pair <ip>:<pairing_port> <pairing_code>
   ```

3. Connect:
   ```bash
   adb connect <ip>:<port>
   ```

### Verify Connection

```bash
adb devices
# Should show: <device-ip>:<port>    device
```

## Quick Start

### Auto-Connect Setup (Recommended)

```bash
# One-time setup
cd ~/.claude/skills/adb-android-control/termux
./setup.sh MYDEVICE 192.168.1.100:5555

# Control commands (available after setup)
adb-control status   # Show connection status
adb-control start    # Start all services
adb-control scan     # Find new port if changed
adb-control log      # View connection logs
```

### Basic ADB Commands

```bash
# Check device info
adb shell getprop ro.product.model

# Take screenshot
adb exec-out screencap -p > screen.png

# Install app
adb install app.apk

# Tap at coordinates
adb shell input tap 500 1000

# Input text
adb shell input text "Hello"
```

### Radio & Network Status

```bash
# WiFi/Bluetooth status with signal strength
python3 scripts/radio_scan.py

# Scan for nearby WiFi networks
adb shell cmd wifi list-scan-results

# Check Bluetooth devices
adb shell dumpsys bluetooth_manager | grep "Bonded devices" -A20
```

## Python Scripts

Located in `scripts/`:

### adb_controller.py

Main controller with clean API:

```python
from adb_controller import ADBController

adb = ADBController()

# Device info
info = adb.get_device_info()
print(f"Model: {info.model}")

# Screenshot
adb.screenshot('capture.png')

# Input
adb.tap(500, 1000)
adb.input_text("Hello World")
```

### adb_automation.py

Workflow automation:

```python
from adb_automation import AppTester, DeviceManager

# App testing
tester = AppTester()
tester.install_and_launch('app.apk', 'com.example.app')

# Device health check
mgr = DeviceManager()
health = mgr.health_check()
```

### adb_monitor.py

Real-time monitoring:

```bash
# Logcat streaming
python3 scripts/adb_monitor.py logcat -l E

# Performance monitoring
python3 scripts/adb_monitor.py perf -i 5

# Crash detection
python3 scripts/adb_monitor.py crash
```

## References

- `references/keycodes.md` - Complete key event codes
- `references/troubleshooting.md` - Common issues and solutions

## Usage Examples

### App Management

```bash
# List third-party apps
adb shell pm list packages -3

# Uninstall app
adb uninstall com.example.app

# Clear app data
adb shell pm clear com.example.app
```

### Screen Operations

```bash
# Screenshot
adb exec-out screencap -p > screenshot.png

# Record screen (30 seconds)
adb shell screenrecord --time-limit 30 /sdcard/video.mp4
adb pull /sdcard/video.mp4 ./
```

### Input Simulation

```bash
# Tap
adb shell input tap 500 1000

# Swipe up
adb shell input swipe 500 1500 500 500 300

# Type text
adb shell input text "HelloWorld"

# Press home
adb shell input keyevent 3
```

### System Info

```bash
# Battery level
adb shell dumpsys battery | grep level

# Memory info
adb shell dumpsys meminfo

# Current activity
adb shell dumpsys activity activities | grep mResumedActivity
```

## Current Device

Connected: `<device-ip>:<port>`

## Troubleshooting

See `references/troubleshooting.md` for common issues.

Quick fixes:

```bash
# Restart ADB
adb kill-server && adb start-server

# Reconnect
adb disconnect && adb connect <device-ip>:<port>
```

## License

MIT
