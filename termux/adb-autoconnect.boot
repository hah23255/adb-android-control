#!/data/data/com.termux/files/usr/bin/bash
# ADB Auto-Connect Boot Script for Termux (v2.0)
# Runs on Termux startup - connects devices, starts monitor

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
SKILL_DIR="$HOME/.claude/skills/adb-android-control"
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

# Try connecting each device, scan if port fails
while IFS='=' read -r name addr; do
    [[ "$name" =~ ^#.*$ ]] && continue
    [[ -z "$addr" ]] && continue
    [[ -z "$name" ]] && continue

    ip="${addr%%:*}"
    port="${addr##*:}"

    log "Connecting $name at $addr"

    # Try current port
    result=$(timeout 5 adb connect "$addr" 2>&1)

    if [[ "$result" == *"connected"* ]]; then
        log "Connected: $name"
    else
        # Scan for new port
        log "Port scan for $name at $ip"
        new_port=$(python3 "$SKILL_DIR/scripts/adb_port_scan.py" "$ip" 30000 50000 2>/dev/null | grep -oP '(?<=:)\d+')

        if [[ -n "$new_port" ]]; then
            log "Found new port: $new_port"
        else
            log "Failed to connect: $name"
        fi
    fi
done < ~/.adb_devices

# Start the auto-reconnect service
sv up adb-autoconnect 2>/dev/null
log "Auto-connect service started"

# Start connection monitor in background
nohup python3 "$SKILL_DIR/scripts/connection_monitor.py" run 30 >> "$HOME/.adb_monitor.log" 2>&1 &
MONITOR_PID=$!
echo "$MONITOR_PID" > "$HOME/.adb_monitor.pid"
log "Connection monitor started (PID: $MONITOR_PID)"

# Notification
termux-notification -t "ADB Ready" -c "Auto-connect and monitor running" --priority low 2>/dev/null

log "Boot script completed"
