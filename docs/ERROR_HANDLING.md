# Error Handling Guide

Comprehensive guide to ADB errors, their causes, and solutions.

## Table of Contents

1. [Connection Errors](#connection-errors)
2. [Installation Errors](#installation-errors)
3. [Permission Errors](#permission-errors)
4. [File Operation Errors](#file-operation-errors)
5. [Shell Command Errors](#shell-command-errors)
6. [Performance Issues](#performance-issues)
7. [Error Codes Reference](#error-codes-reference)

---

## Connection Errors

### E001: No Devices Found

```
error: no devices/emulators found
```

**Causes:**
- Device not connected
- USB debugging disabled
- ADB server not running
- Driver issues (Windows)

**Solutions:**

```bash
# Step 1: Restart ADB server
adb kill-server
adb start-server

# Step 2: Check USB debugging
# On device: Settings > Developer Options > USB Debugging

# Step 3: Reconnect device
adb devices

# Step 4: For wireless, reconnect
adb connect <DEVICE_IP_HOME>:5555
```

**Prevention:**
- Keep USB debugging enabled during development
- Use `adb devices` before running commands

---

### E002: Device Offline

```
List of devices attached
XXXXXXXX    offline
```

**Causes:**
- Connection interrupted
- Device sleeping
- Authorization revoked

**Solutions:**

```bash
# Step 1: Disconnect and reconnect
adb disconnect
adb connect <ip>:<port>

# Step 2: If USB, unplug and replug

# Step 3: Restart ADB
adb kill-server
adb start-server

# Step 4: Revoke and re-authorize
# On device: Settings > Developer Options > Revoke USB debugging
# Reconnect and accept prompt
```

---

### E003: Device Unauthorized

```
List of devices attached
XXXXXXXX    unauthorized
```

**Causes:**
- Authorization prompt not accepted
- RSA key not trusted

**Solutions:**

```bash
# Step 1: Check device screen for authorization dialog
# Accept and check "Always allow"

# Step 2: If no dialog, reset keys
adb kill-server
rm ~/.android/adbkey*
adb start-server
# Reconnect - new dialog will appear

# Step 3: Verify
adb devices
```

---

### E004: Connection Refused

```
error: cannot connect to <DEVICE_IP_HOME>:5555: Connection refused
```

**Causes:**
- Wireless debugging disabled
- Wrong IP/port
- Firewall blocking
- Device on different network

**Solutions:**

```bash
# Step 1: Verify wireless debugging enabled
# Settings > Developer Options > Wireless Debugging

# Step 2: Get correct IP/port from device settings

# Step 3: Re-pair if needed
adb pair <ip>:<pairing_port>

# Step 4: Connect with correct port
adb connect <ip>:<port>
```

---

### E005: Connection Reset

```
error: closed
error: connection reset by peer
```

**Causes:**
- Network instability
- Device disconnected from WiFi
- ADB daemon crashed

**Solutions:**

```bash
# Reconnect
adb disconnect
adb connect <ip>:<port>

# If persistent, use USB instead
```

---

## Installation Errors

### E010: Install Failed - Already Exists

```
Failure [INSTALL_FAILED_ALREADY_EXISTS]
```

**Solution:**

```bash
# Use replace flag
adb install -r app.apk
```

---

### E011: Install Failed - Version Downgrade

```
Failure [INSTALL_FAILED_VERSION_DOWNGRADE]
```

**Solutions:**

```bash
# Option 1: Allow downgrade
adb install -r -d app.apk

# Option 2: Uninstall first
adb uninstall com.example.app
adb install app.apk
```

---

### E012: Install Failed - Insufficient Storage

```
Failure [INSTALL_FAILED_INSUFFICIENT_STORAGE]
```

**Solutions:**

```bash
# Check storage
adb shell df -h

# Clear caches
adb shell pm trim-caches 999999999999

# Remove unused apps
adb uninstall com.unused.app
```

---

### E013: Install Failed - Invalid APK

```
Failure [INSTALL_PARSE_FAILED_NOT_APK]
Failure [INSTALL_PARSE_FAILED_NO_CERTIFICATES]
```

**Causes:**
- Corrupted APK file
- APK not signed
- Wrong file type

**Solutions:**

```bash
# Verify APK
file app.apk
# Should show: "Zip archive data"

# Check APK signature
apksigner verify app.apk

# Re-download or rebuild APK
```

---

### E014: Install Failed - Conflicting Provider

```
Failure [INSTALL_FAILED_CONFLICTING_PROVIDER]
```

**Cause:** Another app uses same content provider authority.

**Solutions:**

```bash
# Find conflicting app
adb shell dumpsys package providers | grep <authority>

# Uninstall conflicting app or change authority in your app
```

---

### E015: Install Failed - Test Only

```
Failure [INSTALL_FAILED_TEST_ONLY]
```

**Solution:**

```bash
# Allow test APKs
adb install -t app.apk
```

---

## Permission Errors

### E020: Permission Denied - Shell

```
/system/bin/sh: <command>: Permission denied
```

**Causes:**
- Command requires root
- Accessing protected directory

**Solutions:**

```bash
# Use accessible paths
adb push file.txt /sdcard/   # Instead of /data/

# For rooted devices
adb root
adb shell <command>
```

---

### E021: Permission Denied - File Access

```
remote object '/data/data/com.app/...' does not exist
adb: error: failed to stat remote object
```

**Solutions:**

```bash
# For debug apps, use run-as
adb shell run-as com.app.debug cat files/data.txt

# Use accessible paths
adb pull /sdcard/file.txt ./
```

---

### E022: Security Exception

```
java.lang.SecurityException: Permission Denial
```

**Causes:**
- Runtime permission not granted
- Protected API access

**Solutions:**

```bash
# Grant runtime permission
adb shell pm grant com.app android.permission.CAMERA

# Check granted permissions
adb shell dumpsys package com.app | grep "granted=true"
```

---

## File Operation Errors

### E030: Remote Object Does Not Exist

```
adb: error: remote object '/sdcard/file.txt' does not exist
```

**Solutions:**

```bash
# Verify file exists
adb shell ls -la /sdcard/file.txt

# Check exact path
adb shell find /sdcard -name "file.txt"
```

---

### E031: Cannot Create File

```
adb: error: cannot create 'file.txt': Permission denied
```

**Solutions:**

```bash
# Check local directory permissions
ls -la ./

# Use different output path
adb pull /sdcard/file.txt /tmp/

# Check disk space
df -h .
```

---

### E032: Push Failed - Read Only

```
adb: error: failed to copy 'file' to '/system/file': Read-only file system
```

**Causes:**
- System partition is read-only
- Device not rooted

**Solutions:**

```bash
# Use writable location
adb push file.txt /sdcard/

# For rooted devices
adb root
adb remount
adb push file.txt /system/
```

---

## Shell Command Errors

### E040: Command Not Found

```
/system/bin/sh: <cmd>: not found
```

**Causes:**
- Command doesn't exist on Android
- Different binary name

**Solutions:**

```bash
# Check available commands
adb shell ls /system/bin/

# Use toybox/busybox variants
adb shell toybox ls
```

---

### E041: Syntax Error

```
/system/bin/sh: syntax error: unexpected ...
```

**Causes:**
- Shell differences (Android uses mksh/sh)
- Quoting issues

**Solutions:**

```bash
# Use proper quoting
adb shell "echo 'hello world'"

# Escape special characters
adb shell input text "Hello\ World"

# Use single commands
adb shell ls
adb shell pwd
```

---

### E042: Argument List Too Long

```
/system/bin/sh: Argument list too long
```

**Solution:**

```bash
# Split into multiple commands
# Instead of: adb shell rm /sdcard/photos/*
adb shell "cd /sdcard/photos && find . -type f -delete"
```

---

## Performance Issues

### E050: Command Timeout

```
error: Command timed out
```

**Solutions:**

```bash
# Increase timeout
adb -t 120 shell <long_command>

# Run in background
adb shell "<command>" &

# For file transfers, check connection
adb shell echo "test"
```

---

### E051: Slow File Transfer

**Causes:**
- Large file size
- Wireless connection
- USB 2.0 port

**Solutions:**

```bash
# Compress before transfer
tar czf archive.tar.gz folder/
adb push archive.tar.gz /sdcard/

# Use USB 3.0 port

# Split large files
split -b 100M largefile part_
for f in part_*; do adb push $f /sdcard/; done
```

---

### E052: Out of Memory

```
error: out of memory
```

**Solutions:**

```bash
# Reduce buffer size for screencap
adb shell screencap -p /sdcard/s.png
adb pull /sdcard/s.png ./

# Clear device memory
adb shell am kill-all
```

---

## Error Codes Reference

### Installation Error Codes

| Code | Meaning |
|------|---------|
| INSTALL_FAILED_ALREADY_EXISTS | App already installed |
| INSTALL_FAILED_INVALID_APK | APK is malformed |
| INSTALL_FAILED_INVALID_URI | Invalid file path |
| INSTALL_FAILED_INSUFFICIENT_STORAGE | Not enough space |
| INSTALL_FAILED_DUPLICATE_PACKAGE | Package exists |
| INSTALL_FAILED_NO_SHARED_USER | Shared user mismatch |
| INSTALL_FAILED_UPDATE_INCOMPATIBLE | Signatures don't match |
| INSTALL_FAILED_SHARED_USER_INCOMPATIBLE | Shared user incompatible |
| INSTALL_FAILED_MISSING_SHARED_LIBRARY | Missing required library |
| INSTALL_FAILED_REPLACE_COULDNT_DELETE | Can't replace existing |
| INSTALL_FAILED_DEXOPT | DEX optimization failed |
| INSTALL_FAILED_OLDER_SDK | SDK version too low |
| INSTALL_FAILED_CONFLICTING_PROVIDER | Provider conflict |
| INSTALL_FAILED_NEWER_SDK | SDK version too high |
| INSTALL_FAILED_TEST_ONLY | Test APK on production |
| INSTALL_FAILED_CPU_ABI_INCOMPATIBLE | Wrong CPU architecture |
| INSTALL_FAILED_MISSING_FEATURE | Missing hardware feature |
| INSTALL_FAILED_CONTAINER_ERROR | Container error |
| INSTALL_FAILED_INVALID_INSTALL_LOCATION | Invalid install location |
| INSTALL_FAILED_MEDIA_UNAVAILABLE | SD card unavailable |
| INSTALL_FAILED_VERIFICATION_TIMEOUT | Verification timeout |
| INSTALL_FAILED_VERIFICATION_FAILURE | Verification failed |
| INSTALL_FAILED_PACKAGE_CHANGED | Package changed during install |
| INSTALL_FAILED_UID_CHANGED | UID changed |
| INSTALL_FAILED_VERSION_DOWNGRADE | Version downgrade |
| INSTALL_PARSE_FAILED_NOT_APK | Not an APK file |
| INSTALL_PARSE_FAILED_BAD_MANIFEST | Invalid manifest |
| INSTALL_PARSE_FAILED_UNEXPECTED_EXCEPTION | Parser exception |
| INSTALL_PARSE_FAILED_NO_CERTIFICATES | Not signed |
| INSTALL_PARSE_FAILED_INCONSISTENT_CERTIFICATES | Certificate mismatch |

### ADB Error Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Generic failure |
| 2 | Command not found |
| 126 | Permission denied |
| 127 | Command not found |
| 137 | Killed (SIGKILL) |
| 143 | Terminated (SIGTERM) |

---

## Debugging Checklist

When encountering errors:

- [ ] Check device connection: `adb devices`
- [ ] Verify ADB version: `adb version`
- [ ] Test basic command: `adb shell echo "test"`
- [ ] Check device logs: `adb logcat -d | tail -50`
- [ ] Restart ADB server: `adb kill-server && adb start-server`
- [ ] Check exact error message and code
- [ ] Search this guide for error code
- [ ] Try alternative approach
