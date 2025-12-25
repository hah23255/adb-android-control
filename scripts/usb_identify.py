#!/data/data/com.termux/files/usr/bin/python3
import os, sys, fcntl, struct, ctypes

fd = int(sys.argv[1]) if len(sys.argv) > 1 else 0

vendors = {
    0x04e8:"Samsung", 0x18d1:"Google", 0x22b8:"Motorola", 0x2717:"Xiaomi",
    0x2a70:"OnePlus", 0x05ac:"Apple", 0x0bda:"Realtek", 0x1d6b:"Linux Foundation",
    0x2109:"VIA Hub", 0x0781:"SanDisk", 0x1a40:"Terminus Hub", 0x8087:"Intel",
    0x1004:"LG", 0x0bb4:"HTC", 0x12d1:"Huawei", 0x19d2:"ZTE", 0x0fce:"Sony",
    0x2e8a:"Raspberry Pi", 0x1f3a:"Allwinner", 0x0483:"STMicroelectronics",
    0x1a86:"QinHeng (CH340)", 0x10c4:"Silicon Labs", 0x067b:"Prolific",
}

# USBDEVFS_CONNECTINFO ioctl to get device info
USBDEVFS_CONNECTINFO = 0x5411

try:
    # Try connectinfo ioctl
    buf = ctypes.create_string_buffer(8)
    try:
        fcntl.ioctl(fd, USBDEVFS_CONNECTINFO, buf)
        devnum = buf[0]
        slow = buf[4]
        print(f"Device number: {devnum}")
    except:
        pass

    # Get device descriptor via control transfer
    # struct usbdevfs_ctrltransfer
    USBDEVFS_CONTROL = 0xc0185500

    class CtrlTransfer(ctypes.Structure):
        _fields_ = [
            ("bRequestType", ctypes.c_uint8),
            ("bRequest", ctypes.c_uint8),
            ("wValue", ctypes.c_uint16),
            ("wIndex", ctypes.c_uint16),
            ("wLength", ctypes.c_uint16),
            ("timeout", ctypes.c_uint32),
            ("data", ctypes.c_void_p)
        ]

    data = ctypes.create_string_buffer(18)
    ctrl = CtrlTransfer()
    ctrl.bRequestType = 0x80  # USB_DIR_IN | USB_TYPE_STANDARD | USB_RECIP_DEVICE
    ctrl.bRequest = 0x06      # USB_REQ_GET_DESCRIPTOR
    ctrl.wValue = 0x0100      # USB_DT_DEVICE << 8
    ctrl.wIndex = 0
    ctrl.wLength = 18
    ctrl.timeout = 1000
    ctrl.data = ctypes.cast(data, ctypes.c_void_p)

    ret = fcntl.ioctl(fd, USBDEVFS_CONTROL, ctrl)

    if ret >= 0:
        d = bytes(data)
        vid = d[8] | (d[9] << 8)
        pid = d[10] | (d[11] << 8)
        print(f"VID:PID = {vid:04x}:{pid:04x}")
        print(f"Vendor  = {vendors.get(vid, 'Unknown')}")
    else:
        print(f"ioctl returned: {ret}")

except Exception as e:
    print(f"Error: {e}")
