#!/data/data/com.termux/files/usr/bin/bash
# ADB Auto-Connect Setup for Termux
# Usage: ./setup.sh [DEVICE_NAME] [IP:PORT]
# Example: ./setup.sh ZFOLD7 <DEVICE_IP_HOME>:<ADB_PORT_HOME>

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$PREFIX/var/service/adb-autoconnect"
BOOT_DIR="$HOME/.termux/boot"
DEVICE_NAME="${1:-}"
DEVICE_ADDR="${2:-}"

info() { echo -e "\033[1;32m[INFO]\033[0m $1"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $1"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $1"; exit 1; }

# Check dependencies
command -v adb >/dev/null || error "ADB not installed. Run: pkg install android-tools"
command -v sv >/dev/null || { warn "termux-services not found. Installing..."; pkg install termux-services -y; }

# Create device config if provided
if [[ -n "$DEVICE_NAME" && -n "$DEVICE_ADDR" ]]; then
    info "Adding device: $DEVICE_NAME=$DEVICE_ADDR"
    if [[ -f ~/.adb_devices ]]; then
        grep -v "^${DEVICE_NAME}=" ~/.adb_devices > ~/.adb_devices.tmp || true
        mv ~/.adb_devices.tmp ~/.adb_devices
    fi
    echo "${DEVICE_NAME}=${DEVICE_ADDR}" >> ~/.adb_devices
elif [[ ! -f ~/.adb_devices ]]; then
    info "Creating default config file..."
    cat > ~/.adb_devices << 'EOF'
# ADB Device Configuration
# Format: DEVICE_NAME=IP:PORT
# Example: MYPHONE=192.168.1.100:5555
EOF
fi

# Install service
info "Installing adb-autoconnect service..."
mkdir -p "$SERVICE_DIR"
cp "$SCRIPT_DIR/adb-autoconnect.service" "$SERVICE_DIR/run"
chmod +x "$SERVICE_DIR/run"

# Install boot script
info "Installing boot script..."
mkdir -p "$BOOT_DIR"
cp "$SCRIPT_DIR/adb-autoconnect.boot" "$BOOT_DIR/adb-autoconnect"
chmod +x "$BOOT_DIR/adb-autoconnect"

# Add shell helpers to bashrc
if ! grep -q "adb-connect()" ~/.bashrc 2>/dev/null; then
    info "Adding shell helpers to ~/.bashrc..."
    cat >> ~/.bashrc << 'EOF'

# ADB Auto-Connect Helpers
source ~/.adb_devices 2>/dev/null

adb-connect() {
    local device="${1:-}"
    if [[ -z "$device" ]]; then
        while IFS='=' read -r name addr; do
            [[ "$name" =~ ^#.*$ ]] && continue
            [[ -z "$addr" ]] && continue
            adb connect "$addr"
        done < ~/.adb_devices
    elif [[ "$device" == *:* ]]; then
        adb connect "$device"
    else
        local addr
        addr=$(grep "^${device}=" ~/.adb_devices | cut -d= -f2)
        [[ -n "$addr" ]] && adb connect "$addr" || echo "Device not found: $device"
    fi
}

adb-reconnect() {
    adb kill-server
    adb start-server
    sleep 1
    adb-connect "$@"
}

adb-add() {
    [[ $# -lt 2 ]] && { echo "Usage: adb-add NAME IP:PORT"; return 1; }
    grep -v "^${1}=" ~/.adb_devices > ~/.adb_devices.tmp 2>/dev/null || true
    mv ~/.adb_devices.tmp ~/.adb_devices
    echo "${1}=${2}" >> ~/.adb_devices
    echo "Added: ${1}=${2}"
    sv restart adb-autoconnect 2>/dev/null
}

adb-list() {
    echo "Configured devices:"
    grep -v "^#" ~/.adb_devices | grep "=" | while IFS='=' read -r name addr; do
        status=$(adb devices | grep -q "${addr%%:*}" && echo "connected" || echo "disconnected")
        printf "  %-15s %s (%s)\n" "$name" "$addr" "$status"
    done
}
EOF
fi

# Start service
info "Starting service..."
sv up adb-autoconnect 2>/dev/null || warn "Could not start service. Try: sv up adb-autoconnect"

# Connect now if device provided
if [[ -n "$DEVICE_ADDR" ]]; then
    info "Connecting to $DEVICE_ADDR..."
    adb connect "$DEVICE_ADDR"
fi

info "Setup complete!"
echo ""
echo "Commands:"
echo "  adb-list        - Show configured devices"
echo "  adb-add NAME IP:PORT - Add new device"
echo "  adb-connect [NAME]   - Connect to device(s)"
echo "  adb-reconnect        - Restart ADB and reconnect"
echo ""
echo "Service:"
echo "  sv status adb-autoconnect"
echo "  sv restart adb-autoconnect"
