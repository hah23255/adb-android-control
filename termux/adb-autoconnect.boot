#!/data/data/com.termux/files/usr/bin/bash
# ADB Auto-Connect Boot Script for Termux (v3.0)
# Runs on Termux startup: connects devices via `adb-control connect`,
# then starts the autoconnect service. No ports hardcoded.

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
LOGFILE="$HOME/.adb_connect.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [BOOT] $1" >> "$LOGFILE"
}

source ~/.adb_devices 2>/dev/null

log "Boot script started"

# Keep device awake
termux-wake-lock

# Wait for network
sleep 3

# Connect each configured device (discovery handled by adb-control)
while IFS='=' read -r name addr; do
    [[ "$name" =~ ^#.*$ ]] && continue
    [[ -z "$addr" ]] && continue
    ip="${addr%%:*}"
    log "Connecting $name at $ip"
    if adb-control connect "$name" "$ip" >> "$LOGFILE" 2>&1; then
        log "Connected: $name"
    else
        log "Failed to connect: $name"
    fi
done < ~/.adb_devices 2>/dev/null

# Start the auto-reconnect service
sv up adb-autoconnect 2>/dev/null
log "Auto-connect service started"

# Notification
termux-notification -t "ADB Ready" -c "Auto-connect running" --priority low 2>/dev/null

log "Boot script completed"
