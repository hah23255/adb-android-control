# Changelog

All notable changes to adb-android-control will be documented here.

## [1.0.0] - 2025-12-25

### Added

**Core Functionality:**
- Complete ADB command reference in SKILL.md
- App management (install, uninstall, list, clear data, force stop)
- File operations (push, pull, ls, mkdir, rm)
- Screen control (screenshot, screen recording)
- Input simulation (tap, swipe, text, key events)
- Shell access and command execution
- Logcat viewing and filtering
- Device info retrieval (battery, memory, storage, props)
- System settings manipulation

**Python Scripts:**
- `adb_controller.py`: Main controller with clean API (800+ lines)
- `adb_automation.py`: Workflow automation and app testing (400+ lines)
- `adb_monitor.py`: Real-time monitoring for logs, performance, crashes (500+ lines)

**Reference Documentation:**
- Complete key event codes reference (100+ keycodes)
- Troubleshooting guide for common issues
- Automation workflow examples

**Automation Features:**
- AppTester class for automated app testing
- DeviceManager for health checks and cleanup
- PerformanceMonitor for real-time metrics
- LogcatMonitor for log streaming
- CrashMonitor for crash detection

### Wireless ADB Support

- Full wireless debugging support
- Pairing and connection management
- Auto-reconnect capabilities

### Known Limitations

- Some operations require root access
- Screen recording limited to 180 seconds (Android limitation)
- Input text cannot include certain special characters

### Planned for v2.0

- UI element detection and interaction
- OCR-based text recognition
- Multi-device support
- Workflow recording and playback
