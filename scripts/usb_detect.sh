#!/data/data/com.termux/files/usr/bin/bash
# USB Device Detection for Termux
# Usage: ./usb_detect.sh
# Note: Requires manual permission grant on Android dialog

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Known USB Vendor IDs
declare -A VENDORS=(
    ["04e8"]="Samsung"
    ["18d1"]="Google"
    ["22b8"]="Motorola"
    ["2717"]="Xiaomi"
    ["2a70"]="OnePlus"
    ["05ac"]="Apple"
    ["0bda"]="Realtek"
    ["8087"]="Intel"
    ["1d6b"]="Linux Foundation"
    ["2109"]="VIA Labs Hub"
    ["0781"]="SanDisk"
    ["090c"]="Silicon Motion"
    ["1a40"]="Terminus Hub"
)

detect_device() {
    local dev="$1"
    python3 -c "
import os, sys
fd = int(os.environ.get('TERMUX_USB_FD', 0))
try:
    data = os.read(fd, 18)
    if len(data) >= 12:
        vid = data[8] | (data[9] << 8)
        pid = data[10] | (data[11] << 8)
        print(f'{vid:04x}:{pid:04x}')
except:
    print('error')
"
}

echo "=== USB Device Detection ==="
echo ""

devices=$(termux-usb -l 2>/dev/null | tr -d '[]" ' | tr ',' '\n' | grep -v '^$')

if [[ -z "$devices" ]]; then
    echo "No USB devices found."
    exit 0
fi

echo "Found USB devices:"
for dev in $devices; do
    echo "  $dev"
done
echo ""
echo "Grant permission when prompted..."
echo ""

for dev in $devices; do
    echo "Checking: $dev"
    result=$(termux-usb -r -e bash -c 'python3 -c "
import os
fd = int(os.environ.get(\"TERMUX_USB_FD\", 0))
data = os.read(fd, 18)
vid = data[8] | (data[9] << 8)
pid = data[10] | (data[11] << 8)
print(f\"{vid:04x}:{pid:04x}\")
"' "$dev" 2>&1) || result="permission_denied"

    if [[ "$result" == "permission_denied" ]]; then
        echo "  Status: Permission denied"
    else
        vid="${result%:*}"
        vendor="${VENDORS[$vid]:-Unknown}"
        echo "  VID:PID: $result"
        echo "  Vendor:  $vendor"
    fi
    echo ""
done
