# ADB Troubleshooting Guide

Common issues and solutions for ADB operations.

## Connection Issues

### Device Not Found

**Symptoms:**
```
error: no devices/emulators found
List of devices attached (empty)
```

**Solutions:**

1. **Restart ADB server:**
   ```bash
   adb kill-server
   adb start-server
   adb devices
   ```

2. **Check USB debugging:**
   - Settings > Developer Options > USB Debugging (enabled)

3. **Wireless reconnect:**
   ```bash
   adb disconnect
   adb connect <device-ip>:<port>
   ```

4. **Re-pair device:**
   ```bash
   adb pair <ip>:<pairing_port> <pairing_code>
   adb connect <ip>:<port>
   ```

### Device Offline

**Symptoms:**
```
List of devices attached
<device-ip>:<port>    offline
```

**Solutions:**

1. **Disconnect and reconnect:**
   ```bash
   adb disconnect <device-ip>:<port>
   adb connect <device-ip>:<port>
   ```

2. **Revoke USB authorizations on device:**
   - Settings > Developer Options > Revoke USB debugging authorizations
   - Reconnect and accept authorization prompt

3. **Restart ADB:**
   ```bash
   adb kill-server
   adb start-server
   ```

### Device Unauthorized

**Symptoms:**
```
List of devices attached
<device-ip>:<port>    unauthorized
```

**Solutions:**

1. **Accept authorization dialog on device**
2. **Check "Always allow from this computer"**
3. **If no dialog appears:**
   ```bash
   adb kill-server
   rm ~/.android/adbkey*
   adb start-server
   ```

### Connection Refused

**Symptoms:**
```
error: cannot connect to <device-ip>:<port>: Connection refused
```

**Solutions:**

1. **Verify device is on same network**
2. **Check wireless debugging is enabled on device**
3. **Re-pair if needed:**
   ```bash
   adb pair <ip>:<pairing_port>
   ```

## Command Issues

### Permission Denied

**Symptoms:**
```
/system/bin/sh: <command>: Permission denied
```

**Solutions:**

1. **Use correct path (sdcard):**
   ```bash
   # Instead of /data/...
   adb push file.txt /sdcard/
   ```

2. **For root operations (rooted devices):**
   ```bash
   adb root
   adb shell <command>
   ```

### File Not Found

**Symptoms:**
```
remote object '/sdcard/file.txt' does not exist
```

**Solutions:**

1. **Verify path exists:**
   ```bash
   adb shell ls -la /sdcard/
   ```

2. **Check for typos in path**

3. **Use absolute paths:**
   ```bash
   adb pull /sdcard/DCIM/Camera/photo.jpg ./
   ```

### Install Failed

**Symptoms:**
```
Failure [INSTALL_FAILED_...]
```

**Common failures and solutions:**

| Error | Solution |
|-------|----------|
| INSTALL_FAILED_ALREADY_EXISTS | `adb install -r app.apk` |
| INSTALL_FAILED_OLDER_SDK | APK requires newer Android |
| INSTALL_FAILED_INSUFFICIENT_STORAGE | Clear storage on device |
| INSTALL_FAILED_INVALID_APK | APK corrupted, re-download |
| INSTALL_PARSE_FAILED_NO_CERTIFICATES | APK not signed |
| INSTALL_FAILED_VERSION_DOWNGRADE | `adb install -d app.apk` |

### Command Timeout

**Symptoms:**
```
error: Command timed out
```

**Solutions:**

1. **Increase timeout:**
   ```bash
   adb -t 60 shell <command>
   ```

2. **Check device responsiveness:**
   ```bash
   adb shell echo "test"
   ```

3. **Restart ADB server**

## Performance Issues

### Slow File Transfer

**Solutions:**

1. **Use compression for text files:**
   ```bash
   tar czf archive.tar.gz folder/
   adb push archive.tar.gz /sdcard/
   adb shell tar xzf /sdcard/archive.tar.gz -C /sdcard/
   ```

2. **Transfer in chunks for large files**

3. **Use USB instead of wireless for large transfers**

### Slow Screenshots

**Solutions:**

1. **Use exec-out (faster):**
   ```bash
   adb exec-out screencap -p > screenshot.png
   ```

2. **Reduce resolution:**
   ```bash
   adb shell screencap -p | convert - -resize 50% screenshot.png
   ```

### Logcat Overwhelming

**Solutions:**

1. **Filter by level:**
   ```bash
   adb logcat *:E  # Errors only
   ```

2. **Filter by tag:**
   ```bash
   adb logcat -s MyApp:*
   ```

3. **Filter by PID:**
   ```bash
   adb logcat --pid=$(adb shell pidof -s com.example.app)
   ```

## Wireless ADB Issues

### Pairing Fails

**Solutions:**

1. **Ensure same WiFi network**
2. **Check pairing port (different from connect port)**
3. **Enter pairing code quickly (expires)**
4. **Disable VPN on both devices**

### Connection Drops

**Solutions:**

1. **Keep device awake:**
   ```bash
   adb shell svc power stayon usb
   ```

2. **Stable WiFi connection required**

3. **Reconnect periodically:**
   ```bash
   adb connect <device-ip>:<port>
   ```

### IP Address Changed

**Solutions:**

1. **Find new IP:**
   - Settings > About Phone > Status > IP Address
   - Or: Settings > WiFi > Connected Network > Details

2. **Set static IP on device**

3. **Reconnect with new IP:**
   ```bash
   adb disconnect
   adb connect <new_ip>:<port>
   ```

## Device-Specific Issues

### Samsung Devices

- May require Samsung USB drivers
- Might need to disable Knox

### Xiaomi/MIUI

- Enable "USB debugging (Security settings)"
- Disable MIUI Optimization

### Huawei/Honor

- May block some ADB commands
- Enable "Allow ADB debugging in charge only mode"

## Diagnostic Commands

```bash
# Check ADB version
adb version

# Detailed device info
adb devices -l

# Check USB connection
lsusb | grep -i android

# Test connection
adb shell echo "OK"

# Get device properties
adb shell getprop | grep -E "ro.product|ro.build"

# Check for errors in logcat
adb logcat *:E -d | tail -50
```

## Reset Everything

If all else fails:

```bash
# Complete reset
adb kill-server
rm -rf ~/.android/adbkey*
adb start-server
# Re-authorize on device
```
