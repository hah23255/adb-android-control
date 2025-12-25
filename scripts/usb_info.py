#!/data/data/com.termux/files/usr/bin/python3
"""Read USB device info from file descriptor passed by termux-usb."""
import sys
import os

def get_usb_info(fd):
    """Read USB device descriptor and extract info."""
    try:
        data = os.read(fd, 18)
        if len(data) >= 18:
            vid = data[8] | (data[9] << 8)
            pid = data[10] | (data[11] << 8)
            print(f"Vendor ID:  0x{vid:04x}")
            print(f"Product ID: 0x{pid:04x}")

            # Known devices
            devices = {
                (0x04e8, 0x6860): "Samsung Galaxy (MTP)",
                (0x04e8, 0x6861): "Samsung Galaxy (PTP)",
                (0x04e8, 0x6862): "Samsung Galaxy (RNDIS)",
                (0x18d1, 0x4ee1): "Google Pixel (MTP)",
                (0x18d1, 0x4ee2): "Google Pixel (PTP)",
                (0x22b8, 0x2e82): "Motorola (MTP)",
                (0x2717, 0xff40): "Xiaomi (MTP)",
                (0x2a70, 0x9024): "OnePlus (MTP)",
            }

            key = (vid, pid)
            if key in devices:
                print(f"Device:     {devices[key]}")
            else:
                print(f"Device:     Unknown (0x{vid:04x}:0x{pid:04x})")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fd = int(os.environ.get("TERMUX_USB_FD", sys.argv[1] if len(sys.argv) > 1 else 0))
    get_usb_info(fd)
