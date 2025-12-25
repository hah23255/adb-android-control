# ADB Setup Guide

Complete guide to enable ADB (Android Debug Bridge) on your Android device.

## Table of Contents

1. [Enable Developer Options](#enable-developer-options)
2. [Enable USB Debugging](#enable-usb-debugging)
3. [Enable Wireless Debugging](#enable-wireless-debugging)
4. [Pairing and Connecting](#pairing-and-connecting)
5. [Verification](#verification)
6. [Security Considerations](#security-considerations)

---

## Enable Developer Options

Developer Options is hidden by default on Android devices. Follow these steps to unlock it:

### Standard Android (Stock, Pixel, OnePlus, etc.)

1. Open **Settings**
2. Scroll down and tap **About Phone**
3. Find **Build Number**
4. Tap **Build Number** 7 times consecutively
5. You'll see a message: "You are now a developer!"
6. Go back to Settings - **Developer Options** now appears

### Samsung (One UI)

1. Open **Settings**
2. Tap **About Phone**
3. Tap **Software Information**
4. Tap **Build Number** 7 times
5. Enter your PIN/pattern if prompted
6. Developer Options appears under Settings

### Xiaomi (MIUI)

1. Open **Settings**
2. Tap **About Phone**
3. Tap **MIUI Version** 7 times
4. Developer Options appears under **Additional Settings**

### Huawei (EMUI)

1. Open **Settings**
2. Tap **About Phone**
3. Tap **Build Number** 7 times
4. Developer Options appears under **System & Updates**

### OnePlus (OxygenOS)

1. Open **Settings**
2. Tap **About Phone**
3. Tap **Build Number** 7 times
4. Developer Options appears under Settings

---

## Enable USB Debugging

After enabling Developer Options:

1. Go to **Settings** > **Developer Options**
2. Scroll down to **Debugging** section
3. Toggle **USB Debugging** ON
4. Confirm the security prompt

### Additional Settings (Recommended)

While in Developer Options, also enable:

- **Stay Awake**: Screen stays on while charging
- **USB Configuration**: Set to MTP or PTP for file access

### Samsung-Specific

On Samsung devices, you may also need to enable:
- **USB Debugging (Security Settings)** - allows installing apps via ADB

### Xiaomi/MIUI-Specific

On Xiaomi devices, also enable:
- **USB Debugging (Security Settings)**
- **Install via USB**
- Disable **MIUI Optimization** (optional, for better compatibility)

---

## Enable Wireless Debugging

Wireless debugging allows ADB over WiFi without USB cable.

### Requirements

- Android 11 or higher
- Device and computer on same WiFi network

### Steps

1. Go to **Settings** > **Developer Options**
2. Toggle **Wireless Debugging** ON
3. Confirm the security prompt
4. Tap on **Wireless Debugging** to open settings
5. Note your device's **IP Address** and **Port**

---

## Pairing and Connecting

### First-Time Pairing

Pairing is required before first wireless connection:

1. In Wireless Debugging settings, tap **Pair device with pairing code**
2. Note the **Pairing Code**, **IP Address**, and **Port**
3. On your computer/Termux, run:

```bash
adb pair <IP_ADDRESS>:<PAIRING_PORT>
```

4. Enter the **Pairing Code** when prompted
5. You should see: "Successfully paired"

**Example:**
```bash
adb pair <DEVICE_IP_HOME>:37997
# Enter pairing code: 482390
# Successfully paired to <DEVICE_IP_HOME>:37997
```

### Connecting After Pairing

After pairing, connect using the main port (not pairing port):

1. In Wireless Debugging settings, note the **IP Address** and **Port** (under device name)
2. Connect:

```bash
adb connect <IP_ADDRESS>:<PORT>
```

**Example:**
```bash
adb connect <DEVICE_IP_HOME>:5555
# connected to <DEVICE_IP_HOME>:5555
```

### USB Connection (Alternative)

If you prefer USB:

1. Connect device via USB cable
2. On device, select **File Transfer/MTP** mode
3. Accept the "Allow USB debugging?" prompt on device
4. Check "Always allow from this computer" for convenience

```bash
adb devices
# List of devices attached
# XXXXXXXX    device
```

---

## Verification

### Check Connection

```bash
# List connected devices
adb devices

# Expected output:
# List of devices attached
# <DEVICE_IP_HOME>:5555    device
```

### Test Basic Commands

```bash
# Get device model
adb shell getprop ro.product.model

# Get Android version
adb shell getprop ro.build.version.release

# Take test screenshot
adb exec-out screencap -p > test.png
```

### Connection States

| State | Meaning | Action |
|-------|---------|--------|
| `device` | Connected and ready | Good to go! |
| `offline` | Connected but not responding | Reconnect |
| `unauthorized` | Not authorized | Accept prompt on device |
| `no permissions` | Permission issue | Check udev rules (Linux) |

---

## Security Considerations

### ⚠️ Important Security Notes

1. **USB Debugging gives full device access**
   - Anyone with ADB access can install apps, access files, read data
   - Only enable when needed

2. **Disable when not in use**
   - Toggle off USB/Wireless debugging when finished
   - Especially important in public/shared networks

3. **Authorization prompts**
   - Always verify the computer fingerprint before allowing
   - Don't check "Always allow" on untrusted computers

4. **Revoke authorizations periodically**
   - Settings > Developer Options > Revoke USB debugging authorizations

5. **Wireless debugging risks**
   - Only use on trusted private networks
   - Never enable on public WiFi
   - Pairing code provides some protection

### Best Practices

```bash
# Disconnect when done
adb disconnect

# Kill ADB server when not in use
adb kill-server
```

### For Development Only

Developer Options should only be enabled on:
- Development/test devices
- Personal devices you fully control
- Not on primary devices with sensitive data (unless necessary)

---

## Troubleshooting Setup

### Developer Options Not Appearing

- Ensure you tapped Build Number exactly 7 times
- Try rebooting the device
- Check if parental controls are blocking it

### USB Debugging Toggle Grayed Out

- Disable any MDM (Mobile Device Management) profiles
- Factory reset may be required if enterprise-locked

### Wireless Debugging Not Available

- Requires Android 11+
- Some manufacturer ROMs disable this feature
- Check for system updates

### "Allow USB Debugging?" Not Appearing

```bash
adb kill-server
adb start-server
```
Then reconnect device.

### Connection Refused

- Verify same WiFi network
- Check firewall settings
- Ensure wireless debugging is still enabled

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────┐
│                 ADB QUICK SETUP                         │
├─────────────────────────────────────────────────────────┤
│ 1. Settings > About Phone > Tap Build Number 7x        │
│ 2. Settings > Developer Options > USB Debugging ON     │
│ 3. Settings > Developer Options > Wireless Debugging   │
│ 4. adb pair <IP>:<PAIR_PORT>                           │
│ 5. adb connect <IP>:<PORT>                             │
│ 6. adb devices                                         │
└─────────────────────────────────────────────────────────┘
```
