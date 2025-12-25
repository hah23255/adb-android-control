# ADB Tutorials & Educational Resources

Learn ADB from beginner to advanced with hands-on tutorials.

## Table of Contents

1. [Beginner Tutorials](#beginner-tutorials)
2. [Intermediate Tutorials](#intermediate-tutorials)
3. [Advanced Tutorials](#advanced-tutorials)
4. [Quick Exercises](#quick-exercises)
5. [External Resources](#external-resources)

---

## Beginner Tutorials

### Tutorial 1: Your First ADB Commands

**Objective:** Learn basic ADB commands and device interaction.

**Prerequisites:**
- ADB installed
- Device connected (see [SETUP.md](SETUP.md))

**Duration:** 15 minutes

#### Step 1: Verify Connection

```bash
# Check ADB is installed
adb version
# Expected: Android Debug Bridge version X.X.X

# List connected devices
adb devices
# Expected: Shows your device with "device" status
```

#### Step 2: Get Device Information

```bash
# Get device model
adb shell getprop ro.product.model
# Example output: Pixel 6

# Get Android version
adb shell getprop ro.build.version.release
# Example output: 13

# Get screen size
adb shell wm size
# Example output: Physical size: 1080x2400
```

#### Step 3: Take Your First Screenshot

```bash
# Capture screenshot
adb exec-out screencap -p > my_first_screenshot.png

# Verify file was created
ls -la my_first_screenshot.png
```

#### Step 4: Explore the Device

```bash
# List files in sdcard
adb shell ls /sdcard/

# Check storage space
adb shell df -h /sdcard

# See running processes
adb shell ps -A | head -20
```

**Congratulations!** You've completed your first ADB session.

---

### Tutorial 2: File Transfer Basics

**Objective:** Learn to transfer files between computer and device.

**Duration:** 10 minutes

#### Step 1: Push Files to Device

```bash
# Create a test file
echo "Hello from ADB!" > test.txt

# Push to device
adb push test.txt /sdcard/

# Verify on device
adb shell cat /sdcard/test.txt
# Expected: Hello from ADB!
```

#### Step 2: Pull Files from Device

```bash
# Pull a file
adb pull /sdcard/test.txt ./pulled_test.txt

# Verify locally
cat pulled_test.txt
```

#### Step 3: Create Directory and Transfer Folder

```bash
# Create local folder with files
mkdir my_folder
echo "File 1" > my_folder/file1.txt
echo "File 2" > my_folder/file2.txt

# Push entire folder
adb push my_folder /sdcard/

# Verify
adb shell ls /sdcard/my_folder/
```

#### Step 4: Clean Up

```bash
# Remove from device
adb shell rm -rf /sdcard/my_folder
adb shell rm /sdcard/test.txt

# Remove locally
rm -rf my_folder test.txt pulled_test.txt
```

---

### Tutorial 3: App Management Basics

**Objective:** Learn to manage apps via ADB.

**Duration:** 15 minutes

#### Step 1: List Installed Apps

```bash
# List all packages
adb shell pm list packages

# List third-party apps only
adb shell pm list packages -3

# Search for specific app
adb shell pm list packages | grep -i "chrome"
```

#### Step 2: Get App Information

```bash
# Choose an app (example: Chrome)
PACKAGE="com.android.chrome"

# Get APK location
adb shell pm path $PACKAGE

# Get app info
adb shell dumpsys package $PACKAGE | head -50
```

#### Step 3: App Control

```bash
# Force stop app
adb shell am force-stop com.android.chrome

# Clear app data (use with caution!)
# adb shell pm clear com.android.chrome

# Launch app
adb shell monkey -p com.android.chrome -c android.intent.category.LAUNCHER 1
```

#### Step 4: Install/Uninstall (Practice)

```bash
# Download a test APK (example: F-Droid)
# Or use any APK you have

# Install
adb install -r app.apk

# Uninstall (keeping data)
adb uninstall -k com.example.app

# Full uninstall
adb uninstall com.example.app
```

---

## Intermediate Tutorials

### Tutorial 4: Input Automation

**Objective:** Learn to simulate user input.

**Duration:** 20 minutes

#### Step 1: Understand Screen Coordinates

```bash
# Get screen size
adb shell wm size
# Example: 1080x2400

# Coordinates start from top-left (0,0)
# X increases to the right
# Y increases downward
```

#### Step 2: Tap Simulation

```bash
# Tap center of screen
adb shell input tap 540 1200

# Tap top-left area
adb shell input tap 100 100

# Tap bottom-right area
adb shell input tap 980 2300
```

#### Step 3: Swipe Gestures

```bash
# Swipe up (scroll down)
adb shell input swipe 540 1800 540 600 300

# Swipe down (scroll up)
adb shell input swipe 540 600 540 1800 300

# Swipe left
adb shell input swipe 900 1200 180 1200 200

# Swipe right
adb shell input swipe 180 1200 900 1200 200

# Long press (swipe with same start/end)
adb shell input swipe 540 1200 540 1200 1000
```

#### Step 4: Text Input

```bash
# Simple text (no spaces)
adb shell input text "HelloWorld"

# Text with spaces (use %s)
adb shell input text "Hello%sWorld"

# Special characters need encoding
adb shell input text "test123"
```

#### Step 5: Key Events

```bash
# Navigation
adb shell input keyevent KEYCODE_HOME
adb shell input keyevent KEYCODE_BACK
adb shell input keyevent KEYCODE_MENU

# Text editing
adb shell input keyevent KEYCODE_DEL      # Backspace
adb shell input keyevent KEYCODE_ENTER    # Enter

# Volume
adb shell input keyevent KEYCODE_VOLUME_UP
adb shell input keyevent KEYCODE_VOLUME_DOWN
```

#### Practice Exercise

Create a script that:
1. Opens Settings
2. Scrolls down
3. Takes a screenshot

```bash
#!/bin/bash
# exercise_input.sh

# Open Settings
adb shell am start -a android.settings.SETTINGS
sleep 2

# Scroll down
adb shell input swipe 540 1500 540 500 300
sleep 1

# Screenshot
adb exec-out screencap -p > settings_scrolled.png

echo "Done! Check settings_scrolled.png"
```

---

### Tutorial 5: Logcat Mastery

**Objective:** Learn to effectively use logcat for debugging.

**Duration:** 25 minutes

#### Step 1: Basic Logcat

```bash
# View live logs (Ctrl+C to stop)
adb logcat

# Dump current logs and exit
adb logcat -d

# Clear log buffer
adb logcat -c
```

#### Step 2: Filtering by Priority

```bash
# Priority levels: V(erbose), D(ebug), I(nfo), W(arning), E(rror), F(atal)

# Errors only
adb logcat "*:E"

# Warnings and above
adb logcat "*:W"

# Info and above
adb logcat "*:I"
```

#### Step 3: Filtering by Tag

```bash
# Single tag
adb logcat -s "ActivityManager:I"

# Multiple tags
adb logcat -s "ActivityManager:I" "WindowManager:E"

# Silence others, show specific
adb logcat "*:S" "MyApp:V"
```

#### Step 4: Filtering by App

```bash
# Get app PID
PID=$(adb shell pidof -s com.android.chrome)
echo "Chrome PID: $PID"

# Filter by PID
adb logcat --pid=$PID
```

#### Step 5: Output Formatting

```bash
# With timestamps
adb logcat -v time

# With thread info
adb logcat -v threadtime

# Brief format
adb logcat -v brief

# Save to file
adb logcat -d -v threadtime > app_logs.txt
```

#### Step 6: Practical Debugging

```bash
#!/bin/bash
# debug_app.sh

PACKAGE="com.myapp"

# Clear old logs
adb logcat -c

# Launch app
adb shell monkey -p $PACKAGE -c android.intent.category.LAUNCHER 1

# Wait for app to start
sleep 3

# Capture logs
PID=$(adb shell pidof -s $PACKAGE)
adb logcat --pid=$PID -d > "${PACKAGE}_debug.log"

# Show errors
echo "=== Errors Found ==="
grep -E "E/|Exception|Error" "${PACKAGE}_debug.log"
```

---

### Tutorial 6: Screen Recording

**Objective:** Learn to capture device screen.

**Duration:** 15 minutes

#### Step 1: Basic Recording

```bash
# Start recording (max 3 minutes)
adb shell screenrecord /sdcard/video.mp4
# Press Ctrl+C to stop

# Or set time limit
adb shell screenrecord --time-limit 10 /sdcard/video.mp4

# Pull video
adb pull /sdcard/video.mp4 ./
```

#### Step 2: Recording Options

```bash
# Lower resolution (smaller file)
adb shell screenrecord --size 720x1280 /sdcard/video.mp4

# Lower bitrate (smaller file, lower quality)
adb shell screenrecord --bit-rate 2000000 /sdcard/video.mp4

# Combined
adb shell screenrecord --size 720x1280 --bit-rate 2000000 --time-limit 30 /sdcard/video.mp4
```

#### Step 3: Recording Automation

```bash
#!/bin/bash
# record_test.sh

OUTPUT="test_$(date +%Y%m%d_%H%M%S).mp4"

echo "Starting recording: $OUTPUT"
echo "Press Ctrl+C to stop..."

# Start recording in background
adb shell screenrecord --time-limit 180 /sdcard/recording.mp4 &
RECORD_PID=$!

# Wait for user to stop
trap "kill $RECORD_PID 2>/dev/null" INT

wait $RECORD_PID

# Pull and cleanup
sleep 1
adb pull /sdcard/recording.mp4 "./$OUTPUT"
adb shell rm /sdcard/recording.mp4

echo "Saved: $OUTPUT"
```

---

## Advanced Tutorials

### Tutorial 7: UI Automation Framework

**Objective:** Build a reusable UI automation framework.

**Duration:** 45 minutes

#### Framework Structure

```bash
mkdir -p automation/{lib,tests,reports}
```

#### Core Library: lib/adb_utils.sh

```bash
#!/bin/bash
# lib/adb_utils.sh

# Configuration
DEVICE_SERIAL="${ADB_DEVICE:-}"
SCREENSHOT_DIR="./reports/screenshots"
LOG_FILE="./reports/automation.log"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Device wrapper
adb_cmd() {
    if [ -n "$DEVICE_SERIAL" ]; then
        adb -s "$DEVICE_SERIAL" "$@"
    else
        adb "$@"
    fi
}

# Check connection
check_device() {
    if ! adb_cmd devices | grep -q "device$"; then
        log "ERROR: No device connected"
        return 1
    fi
    log "Device connected"
    return 0
}

# Get screen dimensions
get_screen_size() {
    local size=$(adb_cmd shell wm size | grep -oE '[0-9]+x[0-9]+')
    SCREEN_WIDTH=$(echo $size | cut -dx -f1)
    SCREEN_HEIGHT=$(echo $size | cut -dx -f2)
    log "Screen: ${SCREEN_WIDTH}x${SCREEN_HEIGHT}"
}

# Tap with percentage coordinates
tap_percent() {
    local x_pct=$1
    local y_pct=$2
    local x=$((SCREEN_WIDTH * x_pct / 100))
    local y=$((SCREEN_HEIGHT * y_pct / 100))
    log "Tap: ($x, $y) [${x_pct}%, ${y_pct}%]"
    adb_cmd shell input tap $x $y
    sleep 0.5
}

# Swipe
swipe_up() {
    local mid_x=$((SCREEN_WIDTH / 2))
    adb_cmd shell input swipe $mid_x $((SCREEN_HEIGHT * 75 / 100)) $mid_x $((SCREEN_HEIGHT * 25 / 100)) 300
    sleep 0.5
}

swipe_down() {
    local mid_x=$((SCREEN_WIDTH / 2))
    adb_cmd shell input swipe $mid_x $((SCREEN_HEIGHT * 25 / 100)) $mid_x $((SCREEN_HEIGHT * 75 / 100)) 300
    sleep 0.5
}

# Screenshot
screenshot() {
    local name="${1:-screenshot}"
    local file="$SCREENSHOT_DIR/${name}_$(date +%H%M%S).png"
    mkdir -p "$SCREENSHOT_DIR"
    adb_cmd exec-out screencap -p > "$file"
    log "Screenshot: $file"
    echo "$file"
}

# Wait for app
wait_for_app() {
    local package=$1
    local timeout=${2:-10}
    local count=0

    while [ $count -lt $timeout ]; do
        if adb_cmd shell pidof -s "$package" > /dev/null 2>&1; then
            log "App running: $package"
            return 0
        fi
        sleep 1
        ((count++))
    done

    log "ERROR: App not started: $package"
    return 1
}

# Launch app
launch_app() {
    local package=$1
    adb_cmd shell monkey -p "$package" -c android.intent.category.LAUNCHER 1 > /dev/null 2>&1
    log "Launched: $package"
    sleep 2
}

# Initialize
init() {
    mkdir -p ./reports
    check_device || exit 1
    get_screen_size
}
```

#### Example Test: tests/test_settings.sh

```bash
#!/bin/bash
# tests/test_settings.sh

source ./lib/adb_utils.sh

TEST_NAME="Settings Navigation"

log "=== TEST: $TEST_NAME ==="

# Initialize
init

# Step 1: Open Settings
log "Step 1: Open Settings"
adb_cmd shell am start -a android.settings.SETTINGS
sleep 2
screenshot "settings_home"

# Step 2: Scroll down
log "Step 2: Scroll down"
swipe_up
sleep 1
screenshot "settings_scrolled"

# Step 3: Go back
log "Step 3: Navigate back"
adb_cmd shell input keyevent KEYCODE_HOME
sleep 1
screenshot "home_screen"

log "=== TEST COMPLETE ==="
```

---

### Tutorial 8: Performance Monitoring

**Objective:** Monitor app performance metrics.

**Duration:** 30 minutes

See `scripts/adb_monitor.py` for the complete implementation.

#### Quick Performance Check

```bash
#!/bin/bash
# perf_check.sh

PACKAGE=$1

if [ -z "$PACKAGE" ]; then
    echo "Usage: $0 <package_name>"
    exit 1
fi

echo "=== Performance Check: $PACKAGE ==="

# Memory
echo ""
echo "Memory Usage:"
adb shell dumpsys meminfo $PACKAGE | grep -E "TOTAL|Native|Dalvik"

# CPU
echo ""
echo "CPU Usage:"
adb shell top -n 1 -b | grep $PACKAGE | head -5

# Battery impact
echo ""
echo "Battery Stats:"
adb shell dumpsys batterystats --charged $PACKAGE | head -20

# Frame stats
echo ""
echo "Frame Stats:"
adb shell dumpsys gfxinfo $PACKAGE | grep -A5 "Total frames"
```

---

## Quick Exercises

### Exercise 1: Screenshot Gallery (5 min)

Take 5 screenshots with 2-second intervals:

```bash
for i in {1..5}; do
    adb exec-out screencap -p > "screen_$i.png"
    echo "Captured screen_$i.png"
    sleep 2
done
```

### Exercise 2: App Launcher (10 min)

Create a script that launches your top 3 apps:

```bash
#!/bin/bash
APPS=("com.android.chrome" "com.google.android.apps.maps" "com.spotify.music")

for app in "${APPS[@]}"; do
    echo "Launching: $app"
    adb shell monkey -p $app -c android.intent.category.LAUNCHER 1
    sleep 3
    adb exec-out screencap -p > "${app##*.}.png"
done
```

### Exercise 3: Device Report (15 min)

Generate a comprehensive device report:

```bash
#!/bin/bash
REPORT="device_report_$(date +%Y%m%d).txt"

{
    echo "=== DEVICE REPORT ==="
    echo "Generated: $(date)"
    echo ""

    echo "=== DEVICE INFO ==="
    echo "Model: $(adb shell getprop ro.product.model)"
    echo "Android: $(adb shell getprop ro.build.version.release)"
    echo "Serial: $(adb shell getprop ro.serialno)"
    echo ""

    echo "=== STORAGE ==="
    adb shell df -h
    echo ""

    echo "=== BATTERY ==="
    adb shell dumpsys battery
    echo ""

    echo "=== INSTALLED APPS (Third-Party) ==="
    adb shell pm list packages -3
} > "$REPORT"

echo "Report saved: $REPORT"
```

---

## External Resources

### Official Documentation

- [Android Developer - ADB](https://developer.android.com/studio/command-line/adb)
- [Android Developer - logcat](https://developer.android.com/studio/command-line/logcat)
- [Android Developer - UI Automator](https://developer.android.com/training/testing/ui-automator)

### Community Resources

- [ADB Shell Commands List](https://adbshell.com/)
- [XDA Developers Forums](https://forum.xda-developers.com/)
- [Stack Overflow - ADB Tag](https://stackoverflow.com/questions/tagged/adb)

### Video Tutorials

- Search "ADB tutorial" on YouTube
- Android development channels often cover ADB

### Practice Environments

- Android Emulator (Android Studio)
- Physical test device (recommended)

---

## Next Steps

After completing these tutorials:

1. **Explore SKILL.md** - Complete command reference
2. **Try USE_CASES.md** - Real-world workflows
3. **Read GUIDELINES.md** - Best practices
4. **Check ERROR_HANDLING.md** - When things go wrong

Happy learning!
