# ADB Use Cases

Practical use cases and workflows for ADB Android Control.

## Table of Contents

1. [App Development & Testing](#app-development--testing)
2. [Device Management](#device-management)
3. [Automation & Scripting](#automation--scripting)
4. [Data Extraction & Backup](#data-extraction--backup)
5. [Performance Analysis](#performance-analysis)
6. [Accessibility & Input](#accessibility--input)
7. [System Administration](#system-administration)
8. [Security Testing](#security-testing)

---

## App Development & Testing

### UC-1: Install and Test APK

**Scenario**: Deploy debug APK to device for testing.

```bash
# Install with all permissions granted
adb install -r -g ./app-debug.apk

# Launch app
adb shell monkey -p com.myapp -c android.intent.category.LAUNCHER 1

# View app logs
adb logcat --pid=$(adb shell pidof -s com.myapp) | grep -E "INFO|WARN|ERROR"
```

### UC-2: Clear App State for Fresh Test

**Scenario**: Reset app to initial state between test runs.

```bash
# Force stop app
adb shell am force-stop com.myapp

# Clear all data
adb shell pm clear com.myapp

# Relaunch
adb shell monkey -p com.myapp -c android.intent.category.LAUNCHER 1
```

### UC-3: Capture Bug Reproduction

**Scenario**: Record screen while reproducing a bug.

```bash
# Start recording
adb shell screenrecord --time-limit 60 /sdcard/bug_repro.mp4 &

# ... reproduce bug ...

# Pull video
adb pull /sdcard/bug_repro.mp4 ./

# Capture logcat
adb logcat -d > bug_logs.txt

# Take final screenshot
adb exec-out screencap -p > bug_final.png
```

### UC-4: Multi-Device Testing

**Scenario**: Run same test on multiple devices.

```bash
#!/bin/bash
# test_all_devices.sh

APK="./app.apk"
PACKAGE="com.myapp"

for device in $(adb devices | grep device$ | cut -f1); do
    echo "Testing on: $device"

    adb -s $device install -r $APK
    adb -s $device shell monkey -p $PACKAGE -c android.intent.category.LAUNCHER 1
    sleep 5
    adb -s $device exec-out screencap -p > "screenshot_${device}.png"
done
```

---

## Device Management

### UC-5: Device Health Check

**Scenario**: Daily device health monitoring.

```bash
#!/bin/bash
# health_check.sh

echo "=== Device Health Report ==="
echo "Date: $(date)"
echo ""

echo "Device:"
echo "  Model: $(adb shell getprop ro.product.model)"
echo "  Android: $(adb shell getprop ro.build.version.release)"

echo ""
echo "Battery:"
adb shell dumpsys battery | grep -E "level|status|temperature"

echo ""
echo "Storage:"
adb shell df -h /data /sdcard 2>/dev/null | tail -2

echo ""
echo "Memory:"
adb shell cat /proc/meminfo | head -3

echo ""
echo "Running Apps: $(adb shell ps -A | wc -l)"
```

### UC-6: Batch App Removal

**Scenario**: Remove bloatware or unwanted apps.

```bash
#!/bin/bash
# remove_bloatware.sh

APPS_TO_REMOVE=(
    "com.facebook.appmanager"
    "com.facebook.system"
    "com.samsung.android.game.gamehome"
)

for app in "${APPS_TO_REMOVE[@]}"; do
    echo "Removing: $app"
    adb shell pm uninstall -k --user 0 $app 2>/dev/null || echo "  Not found"
done
```

### UC-7: Device Cleanup

**Scenario**: Free up storage space.

```bash
# Clear package cache
adb shell pm trim-caches 999999999999

# Clear thumbnail cache
adb shell rm -rf /sdcard/DCIM/.thumbnails/*

# Clear download folder
adb shell rm -rf /sdcard/Download/*

# Clear app caches (for specific app)
adb shell pm clear com.example.app

# Check freed space
adb shell df -h /data
```

---

## Automation & Scripting

### UC-8: Automated Login Flow

**Scenario**: Automate login for repeated testing.

```bash
#!/bin/bash
# auto_login.sh

PACKAGE="com.myapp"
USERNAME="testuser"
PASSWORD="testpass123"

# Launch app
adb shell monkey -p $PACKAGE -c android.intent.category.LAUNCHER 1
sleep 3

# Tap username field (adjust coordinates for your app)
adb shell input tap 540 600
sleep 0.5

# Enter username
adb shell input text "$USERNAME"
sleep 0.3

# Tap password field
adb shell input tap 540 750
sleep 0.5

# Enter password
adb shell input text "$PASSWORD"
sleep 0.3

# Tap login button
adb shell input tap 540 900

echo "Login attempted"
```

### UC-9: Scroll and Capture Content

**Scenario**: Capture long scrolling content (terms, lists).

```bash
#!/bin/bash
# scroll_capture.sh

OUTPUT_DIR="./captures"
mkdir -p "$OUTPUT_DIR"

for i in {1..10}; do
    echo "Capturing page $i..."
    adb exec-out screencap -p > "$OUTPUT_DIR/page_$i.png"

    # Scroll down
    adb shell input swipe 540 1500 540 500 300
    sleep 1
done

echo "Captured 10 pages to $OUTPUT_DIR"
```

### UC-10: Automated UI Test Sequence

**Scenario**: Run through app navigation flow.

```python
#!/usr/bin/env python3
# ui_test.py

import subprocess
import time

def adb(cmd):
    subprocess.run(['adb', 'shell'] + cmd.split(), check=True)

def tap(x, y):
    adb(f'input tap {x} {y}')
    time.sleep(0.5)

def swipe_up():
    adb('input swipe 540 1500 540 500 300')
    time.sleep(0.5)

def screenshot(name):
    subprocess.run(['adb', 'exec-out', 'screencap', '-p'],
                   stdout=open(f'{name}.png', 'wb'))

# Test flow
print("Starting UI test...")

# Step 1: Tap menu button
tap(100, 150)
screenshot('step1_menu')

# Step 2: Scroll down
swipe_up()
screenshot('step2_scrolled')

# Step 3: Tap settings
tap(540, 800)
screenshot('step3_settings')

print("Test complete!")
```

---

## Data Extraction & Backup

### UC-11: Extract All Photos

**Scenario**: Backup all photos from device.

```bash
#!/bin/bash
# backup_photos.sh

BACKUP_DIR="./phone_photos_$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

echo "Pulling photos from DCIM/Camera..."
adb pull /sdcard/DCIM/Camera/ "$BACKUP_DIR/Camera/"

echo "Pulling photos from Pictures..."
adb pull /sdcard/Pictures/ "$BACKUP_DIR/Pictures/"

echo "Pulling screenshots..."
adb pull /sdcard/Screenshots/ "$BACKUP_DIR/Screenshots/"

echo "Backup complete: $BACKUP_DIR"
du -sh "$BACKUP_DIR"
```

### UC-12: Extract App APKs

**Scenario**: Backup installed apps as APK files.

```bash
#!/bin/bash
# extract_apks.sh

OUTPUT_DIR="./extracted_apks"
mkdir -p "$OUTPUT_DIR"

# Get third-party packages
for pkg in $(adb shell pm list packages -3 | cut -d: -f2); do
    pkg=$(echo $pkg | tr -d '\r')
    echo "Extracting: $pkg"

    # Get APK path
    apk_path=$(adb shell pm path $pkg | cut -d: -f2 | tr -d '\r')

    # Pull APK
    adb pull "$apk_path" "$OUTPUT_DIR/${pkg}.apk" 2>/dev/null
done

echo "Extracted $(ls -1 $OUTPUT_DIR | wc -l) APKs"
```

### UC-13: Database Extraction (Debug Builds)

**Scenario**: Extract SQLite database from debug app.

```bash
#!/bin/bash
# extract_db.sh

PACKAGE="com.myapp.debug"
DB_NAME="app_database.db"

# Run as app user
adb shell run-as $PACKAGE cat databases/$DB_NAME > ./$DB_NAME

# Verify
sqlite3 ./$DB_NAME "SELECT name FROM sqlite_master WHERE type='table';"
```

---

## Performance Analysis

### UC-14: Memory Usage Monitoring

**Scenario**: Track app memory usage over time.

```bash
#!/bin/bash
# monitor_memory.sh

PACKAGE="com.myapp"
INTERVAL=5
DURATION=60

echo "timestamp,pss_kb,private_dirty_kb" > memory_log.csv

end=$((SECONDS + DURATION))
while [ $SECONDS -lt $end ]; do
    mem=$(adb shell dumpsys meminfo $PACKAGE | grep "TOTAL" | head -1)
    pss=$(echo $mem | awk '{print $2}')
    private=$(echo $mem | awk '{print $3}')

    echo "$(date +%H:%M:%S),$pss,$private" >> memory_log.csv
    sleep $INTERVAL
done

echo "Memory log saved to memory_log.csv"
```

### UC-15: Frame Rate Analysis

**Scenario**: Check for UI jank during scrolling.

```bash
# Enable GPU profiling
adb shell setprop debug.hwui.profile true
adb shell setprop debug.hwui.profile.maxframes 120

# Capture frame data
adb shell dumpsys gfxinfo com.myapp > gfxinfo.txt

# Look for janky frames (>16ms)
grep -E "^\s+[0-9]+" gfxinfo.txt | awk '$1 > 16 {print "Janky frame: " $1 "ms"}'
```

### UC-16: Network Traffic Analysis

**Scenario**: Monitor app network usage.

```bash
# Get app UID
UID=$(adb shell dumpsys package com.myapp | grep userId= | cut -d= -f2)

# Get network stats
adb shell cat /proc/net/xt_qtaguid/stats | grep $UID

# Real-time monitoring
watch -n 1 "adb shell cat /proc/net/xt_qtaguid/stats | grep $UID"
```

---

## Accessibility & Input

### UC-17: Remote Device Control

**Scenario**: Control device without touching it.

```bash
# Navigation
adb shell input keyevent KEYCODE_HOME      # Home
adb shell input keyevent KEYCODE_BACK      # Back
adb shell input keyevent KEYCODE_APP_SWITCH # Recent apps

# Volume
adb shell input keyevent KEYCODE_VOLUME_UP
adb shell input keyevent KEYCODE_VOLUME_DOWN
adb shell input keyevent KEYCODE_VOLUME_MUTE

# Media
adb shell input keyevent KEYCODE_MEDIA_PLAY_PAUSE
adb shell input keyevent KEYCODE_MEDIA_NEXT
adb shell input keyevent KEYCODE_MEDIA_PREVIOUS
```

### UC-18: Text Input Automation

**Scenario**: Fill forms automatically.

```bash
#!/bin/bash
# fill_form.sh

# Focus on first field (tap)
adb shell input tap 540 400

# Enter name
adb shell input text "John%sDoe"
adb shell input keyevent KEYCODE_TAB

# Enter email
adb shell input text "john.doe@email.com"
adb shell input keyevent KEYCODE_TAB

# Enter phone
adb shell input text "5551234567"

# Submit
adb shell input keyevent KEYCODE_ENTER
```

### UC-19: Accessibility Testing

**Scenario**: Test app with different font sizes.

```bash
# Set large font
adb shell settings put system font_scale 1.5

# Test app
adb exec-out screencap -p > large_font.png

# Reset font
adb shell settings put system font_scale 1.0
```

---

## System Administration

### UC-20: Batch Settings Configuration

**Scenario**: Configure device for development.

```bash
#!/bin/bash
# dev_setup.sh

echo "Configuring device for development..."

# Disable animations (faster UI testing)
adb shell settings put global window_animation_scale 0
adb shell settings put global transition_animation_scale 0
adb shell settings put global animator_duration_scale 0

# Keep screen on while charging
adb shell svc power stayon usb

# Set screen timeout to 30 minutes
adb shell settings put system screen_off_timeout 1800000

# Enable GPU profiling
adb shell setprop debug.hwui.profile true

echo "Development configuration complete"
```

### UC-21: Network Configuration

**Scenario**: Toggle network settings for testing.

```bash
# Airplane mode ON
adb shell settings put global airplane_mode_on 1
adb shell am broadcast -a android.intent.action.AIRPLANE_MODE

# Airplane mode OFF
adb shell settings put global airplane_mode_on 0
adb shell am broadcast -a android.intent.action.AIRPLANE_MODE

# WiFi only
adb shell svc wifi enable
adb shell svc data disable

# Mobile data only
adb shell svc wifi disable
adb shell svc data enable
```

---

## Security Testing

### UC-22: Permission Audit

**Scenario**: Audit app permissions.

```bash
#!/bin/bash
# audit_permissions.sh

PACKAGE="com.target.app"

echo "=== Permission Audit: $PACKAGE ==="
echo ""

echo "Requested Permissions:"
adb shell dumpsys package $PACKAGE | grep "android.permission" | sort -u

echo ""
echo "Granted Runtime Permissions:"
adb shell dumpsys package $PACKAGE | grep "granted=true" | grep "permission"

echo ""
echo "Dangerous Permissions:"
adb shell dumpsys package $PACKAGE | grep -E "CAMERA|LOCATION|CONTACTS|MICROPHONE|STORAGE|SMS|CALL"
```

### UC-23: App Data Inspection

**Scenario**: Inspect app's stored data (debug builds).

```bash
#!/bin/bash
# inspect_app_data.sh

PACKAGE="com.myapp.debug"

echo "=== Shared Preferences ==="
adb shell run-as $PACKAGE cat shared_prefs/*.xml 2>/dev/null

echo ""
echo "=== Database Files ==="
adb shell run-as $PACKAGE ls -la databases/ 2>/dev/null

echo ""
echo "=== Cache Contents ==="
adb shell run-as $PACKAGE ls -la cache/ 2>/dev/null
```

---

## Quick Reference

| Use Case | Key Command |
|----------|-------------|
| Install APK | `adb install -r app.apk` |
| Clear data | `adb shell pm clear pkg` |
| Screenshot | `adb exec-out screencap -p > s.png` |
| Record screen | `adb shell screenrecord /sdcard/v.mp4` |
| Tap screen | `adb shell input tap X Y` |
| Enter text | `adb shell input text "text"` |
| View logs | `adb logcat -d` |
| Device info | `adb shell getprop ro.product.model` |
| List apps | `adb shell pm list packages -3` |
| Pull file | `adb pull /sdcard/file ./` |
