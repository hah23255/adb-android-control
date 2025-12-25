# ADB Android Control - Development Logbook

## 2024-12-25

### Session: USB Device Detection & Auto-Connect

#### Completed
1. **ADB Auto-Connect Service** - Persistent wireless ADB connection
   - Created `termux/adb-autoconnect.service` - background daemon
   - Created `termux/adb-autoconnect.boot` - Termux startup script
   - Created `termux/setup.sh` - one-command installer
   - Added shell helpers: `adb-list`, `adb-add`, `adb-connect`, `adb-reconnect`
   - Committed: `25acafb`

2. **Device Configuration**
   - Z Fold 7 (SM-F966B) configured at `<DEVICE_IP_HOME>:<ADB_PORT_HOME>`
   - Auto-reconnect interval: 30 seconds
   - Config file: `~/.adb_devices`

#### Completed
3. **USB Device Detection** - Identifying USB-connected devices ✓
   - Created `scripts/usb_info.py` - USB descriptor reader
   - Created `scripts/usb_detect.sh` - interactive USB detection script
   - Created `~/usbid.py` - working USB identifier via ioctl
   - **TESTED & VALIDATED**: Successfully identified USB device
   - Device: Raspberry Pi RP2040 (VID:PID 2e8a:000f)

#### Root Cause Analysis: USB Detection Methods

| Method | Result | Root Cause |
|--------|--------|------------|
| `lsusb` | Failed | Requires root, unavailable in Termux |
| `pyusb` | Failed | libusb backend needs root for USB access |
| `os.read(fd)` | Failed | Returns 0 bytes - wrong API |
| `libusb ctypes` | Segfault | Memory issues with ctypes bindings |
| **`fcntl.ioctl`** | **SUCCESS** | USBDEVFS_CONTROL ioctl works! |

**Working Solution:**
1. `termux-usb -r -e script.py /dev/bus/usb/XXX/YYY`
2. Script receives FD as `sys.argv[1]`
3. Use `fcntl.ioctl(fd, USBDEVFS_CONTROL, ctrl_struct)` to get descriptor
4. Parse VID/PID from 18-byte device descriptor

#### Edge Cases Documented
- `termux-usb -e` with complex scripts may timeout
- Permission dialogs block non-interactive execution
- USB device may be hub/accessory, not Android phone

#### Known Issues
- USB detection requires manual user interaction (Android limitation)
- Cannot auto-detect USB devices in background service
- pyusb module path issues in Termux Python environment

#### Next Steps
- Test `usb_detect.sh` interactively with user
- Add USB device to ADB if it's an Android phone
- Document USB workflow in SKILL.md

---

## Device Registry

| Name | Model | IP:Port | Status |
|------|-------|---------|--------|
| Z Fold 7 | SM-F966B | <DEVICE_IP_HOME>:<ADB_PORT_HOME> | Active |

---

## Files Changed This Session

| File | Action | Description |
|------|--------|-------------|
| termux/adb-autoconnect.service | Created | Auto-reconnect daemon |
| termux/adb-autoconnect.boot | Created | Boot startup script |
| termux/setup.sh | Created | Installation script |
| SKILL.md | Updated | Added Termux Auto-Connect docs |
| scripts/usb_info.py | Created | USB device identifier |
| scripts/usb_detect.sh | Created | Interactive USB detection |
| LOGBOOK.md | Created | Development tracking |

## Commits

| Hash | Message | Status |
|------|---------|--------|
| 25acafb | feat: add Termux auto-connect service | Pushed |
| pending | feat: add USB detection scripts | Not committed |
