# ADB Best Practices & Guidelines

Guidelines for safe, efficient, and professional ADB usage.

## Table of Contents

1. [Security Guidelines](#security-guidelines)
2. [Performance Guidelines](#performance-guidelines)
3. [Scripting Guidelines](#scripting-guidelines)
4. [Testing Guidelines](#testing-guidelines)
5. [Debugging Guidelines](#debugging-guidelines)
6. [Maintenance Guidelines](#maintenance-guidelines)

---

## Security Guidelines

### G-SEC-01: Minimize Debug Mode Exposure

**Rule:** Disable USB/Wireless debugging when not actively using ADB.

```bash
# After development session
adb disconnect

# Remind user to disable debugging
echo "Remember to disable USB debugging in Developer Options"
```

**Rationale:** ADB provides full device access. Leaving it enabled exposes your device to potential attacks.

---

### G-SEC-02: Use Trusted Networks Only

**Rule:** Only use wireless ADB on private, trusted networks.

**Bad:**
- Public WiFi (coffee shops, airports)
- Shared office networks
- Hotel WiFi

**Good:**
- Home network
- Private development network
- VPN-protected network

---

### G-SEC-03: Verify Device Identity

**Rule:** Always verify the device fingerprint when authorizing.

```
Allow USB debugging?

The computer's RSA key fingerprint is:
XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX

☐ Always allow from this computer
```

Only check "Always allow" for your own trusted computers.

---

### G-SEC-04: Secure Credential Handling

**Rule:** Never hardcode or expose credentials in ADB scripts.

**Bad:**
```bash
adb shell input text "mypassword123"  # Exposed in history
```

**Good:**
```bash
# Read from secure input
read -s -p "Password: " PASSWORD
adb shell input text "$PASSWORD"
unset PASSWORD
```

---

### G-SEC-05: Audit Installed Apps

**Rule:** Regularly audit apps installed via ADB.

```bash
# List apps installed via ADB (third-party)
adb shell pm list packages -3

# Check for unknown packages
adb shell pm list packages -3 | sort > installed_apps.txt
diff installed_apps.txt known_apps.txt
```

---

### G-SEC-06: Revoke Authorizations Periodically

**Rule:** Revoke USB debugging authorizations monthly.

```
Settings > Developer Options > Revoke USB debugging authorizations
```

This clears all trusted computers, requiring re-authorization.

---

## Performance Guidelines

### G-PERF-01: Use exec-out for Binary Data

**Rule:** Use `exec-out` instead of `shell` for screenshots and binary data.

**Bad:**
```bash
adb shell screencap -p /sdcard/s.png
adb pull /sdcard/s.png ./
adb shell rm /sdcard/s.png
```

**Good:**
```bash
adb exec-out screencap -p > screenshot.png
```

**Rationale:** `exec-out` streams data directly without shell processing, faster and avoids file creation on device.

---

### G-PERF-02: Batch Operations

**Rule:** Combine multiple operations into single commands when possible.

**Bad:**
```bash
adb shell mkdir /sdcard/test
adb shell touch /sdcard/test/file1
adb shell touch /sdcard/test/file2
```

**Good:**
```bash
adb shell "mkdir -p /sdcard/test && touch /sdcard/test/file{1,2}"
```

---

### G-PERF-03: Use Compression for Large Transfers

**Rule:** Compress files before transferring.

```bash
# Compress on device
adb shell "cd /sdcard && tar czf backup.tar.gz DCIM/"

# Transfer compressed
adb pull /sdcard/backup.tar.gz ./

# Cleanup
adb shell rm /sdcard/backup.tar.gz
```

---

### G-PERF-04: Filter Logcat Output

**Rule:** Always filter logcat to reduce data volume.

**Bad:**
```bash
adb logcat  # Overwhelming output
```

**Good:**
```bash
# By level
adb logcat "*:E"

# By tag
adb logcat -s "MyApp:*"

# By PID
adb logcat --pid=$(adb shell pidof -s com.myapp)

# Limited lines
adb logcat -d | tail -100
```

---

### G-PERF-05: Reuse Connections

**Rule:** Keep ADB connection alive during development sessions.

```bash
# Keep screen on while debugging
adb shell svc power stayon usb

# Verify connection periodically
watch -n 60 "adb devices"
```

---

## Scripting Guidelines

### G-SCRIPT-01: Always Check Device Connection

**Rule:** Verify device is connected before operations.

```bash
#!/bin/bash

# Check device connection
if ! adb devices | grep -q "device$"; then
    echo "Error: No device connected"
    exit 1
fi

# Proceed with operations
adb shell echo "Device ready"
```

---

### G-SCRIPT-02: Use Error Handling

**Rule:** Handle errors gracefully in scripts.

```bash
#!/bin/bash
set -e  # Exit on error

# Function with error handling
install_apk() {
    local apk="$1"

    if [ ! -f "$apk" ]; then
        echo "Error: APK not found: $apk"
        return 1
    fi

    if ! adb install -r "$apk" 2>&1 | grep -q "Success"; then
        echo "Error: Installation failed"
        return 1
    fi

    echo "Installed successfully"
}

install_apk "app.apk" || exit 1
```

---

### G-SCRIPT-03: Support Multiple Devices

**Rule:** Handle multiple connected devices explicitly.

```bash
#!/bin/bash

# Get target device
DEVICE="${1:-}"

if [ -z "$DEVICE" ]; then
    DEVICES=$(adb devices | grep device$ | cut -f1)
    COUNT=$(echo "$DEVICES" | wc -w)

    if [ "$COUNT" -eq 0 ]; then
        echo "No devices connected"
        exit 1
    elif [ "$COUNT" -gt 1 ]; then
        echo "Multiple devices. Specify target:"
        echo "$DEVICES"
        exit 1
    fi

    DEVICE="$DEVICES"
fi

# Use specific device
adb -s "$DEVICE" shell echo "Using device: $DEVICE"
```

---

### G-SCRIPT-04: Add Timeouts

**Rule:** Set appropriate timeouts for operations.

```bash
#!/bin/bash

# Timeout wrapper
timeout_cmd() {
    local timeout="$1"
    shift
    timeout "$timeout" "$@" || {
        echo "Command timed out after ${timeout}s"
        return 1
    }
}

# Usage
timeout_cmd 30 adb shell "long_running_command"
```

---

### G-SCRIPT-05: Log Operations

**Rule:** Log important operations for debugging.

```bash
#!/bin/bash

LOGFILE="adb_operations.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOGFILE"
}

log "Starting operation"
adb install app.apk && log "Install successful" || log "Install failed"
log "Operation complete"
```

---

## Testing Guidelines

### G-TEST-01: Fresh State Testing

**Rule:** Start tests from a known clean state.

```bash
# Test setup
setup_test() {
    local package="$1"

    adb shell am force-stop "$package"
    adb shell pm clear "$package"
    sleep 1
}

# Usage
setup_test "com.myapp"
adb shell monkey -p com.myapp -c android.intent.category.LAUNCHER 1
```

---

### G-TEST-02: Capture Evidence

**Rule:** Always capture screenshots/recordings for test evidence.

```bash
#!/bin/bash

TEST_NAME="login_test"
EVIDENCE_DIR="./evidence/$TEST_NAME_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$EVIDENCE_DIR"

# Capture before
adb exec-out screencap -p > "$EVIDENCE_DIR/before.png"

# Run test
run_test

# Capture after
adb exec-out screencap -p > "$EVIDENCE_DIR/after.png"

# Capture logs
adb logcat -d > "$EVIDENCE_DIR/logcat.txt"
```

---

### G-TEST-03: Use Consistent Coordinates

**Rule:** Calculate coordinates relative to screen size.

```bash
#!/bin/bash

# Get screen dimensions
SIZE=$(adb shell wm size | grep -oE '[0-9]+x[0-9]+')
WIDTH=$(echo $SIZE | cut -dx -f1)
HEIGHT=$(echo $SIZE | cut -dx -f2)

# Calculate relative positions
CENTER_X=$((WIDTH / 2))
CENTER_Y=$((HEIGHT / 2))
TOP_Y=$((HEIGHT / 4))
BOTTOM_Y=$((HEIGHT * 3 / 4))

# Use relative coordinates
adb shell input tap $CENTER_X $CENTER_Y
```

---

### G-TEST-04: Add Delays Appropriately

**Rule:** Use appropriate delays between actions.

```bash
# After launching app
sleep 3

# After tap
sleep 0.5

# After text input
sleep 0.3

# After screen transition
sleep 1

# After network operation
sleep 2
```

---

## Debugging Guidelines

### G-DEBUG-01: Isolate Problems

**Rule:** Test one thing at a time.

```bash
# Step 1: Test connection
adb devices

# Step 2: Test basic command
adb shell echo "test"

# Step 3: Test specific operation
adb shell pm list packages
```

---

### G-DEBUG-02: Check Logs First

**Rule:** Always check logcat when something fails.

```bash
# Clear log
adb logcat -c

# Reproduce issue

# Check errors
adb logcat -d "*:E" | tail -50
```

---

### G-DEBUG-03: Use Verbose Mode

**Rule:** Enable verbose output for troubleshooting.

```bash
# Verbose ADB
ADB_TRACE=all adb devices

# Verbose install
adb install -r -v app.apk
```

---

### G-DEBUG-04: Document Issues

**Rule:** Create reproducible issue reports.

```bash
#!/bin/bash

REPORT="issue_report_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$REPORT"

# Device info
adb shell getprop > "$REPORT/props.txt"

# Screenshot
adb exec-out screencap -p > "$REPORT/screen.png"

# Logs
adb logcat -d > "$REPORT/logcat.txt"
adb bugreport > "$REPORT/bugreport.zip"

# Package dump
adb shell dumpsys package com.myapp > "$REPORT/package.txt"

echo "Report saved to $REPORT/"
```

---

## Maintenance Guidelines

### G-MAINT-01: Update ADB Regularly

**Rule:** Keep ADB/platform-tools updated.

```bash
# Check version
adb version

# Update (Termux)
pkg update && pkg upgrade android-tools
```

---

### G-MAINT-02: Clean Up Regularly

**Rule:** Remove temporary files from device.

```bash
# Weekly cleanup
adb shell rm -rf /sdcard/tmp/*
adb shell rm -rf /data/local/tmp/*
adb shell rm -rf /sdcard/*.png  # Old screenshots
```

---

### G-MAINT-03: Backup Scripts

**Rule:** Version control your ADB scripts.

```bash
# Initialize repo
git init adb-scripts
cd adb-scripts

# Add scripts
git add *.sh
git commit -m "Add ADB automation scripts"
```

---

### G-MAINT-04: Document Custom Workflows

**Rule:** Document all custom automation.

```markdown
# Script: deploy_app.sh

## Purpose
Deploy and test application on connected device.

## Usage
./deploy_app.sh <apk_path>

## Prerequisites
- Device connected via ADB
- APK file exists

## Steps
1. Uninstall existing app
2. Install new APK
3. Launch app
4. Capture screenshot
```

---

## Quick Reference

| Category | Rule | Key Point |
|----------|------|-----------|
| Security | G-SEC-01 | Disable debugging when not in use |
| Security | G-SEC-02 | Trusted networks only |
| Performance | G-PERF-01 | Use exec-out for binary data |
| Performance | G-PERF-02 | Batch operations |
| Scripting | G-SCRIPT-01 | Check connection first |
| Scripting | G-SCRIPT-02 | Handle errors |
| Testing | G-TEST-01 | Start from clean state |
| Testing | G-TEST-02 | Capture evidence |
| Debugging | G-DEBUG-01 | Isolate problems |
| Debugging | G-DEBUG-02 | Check logs first |
