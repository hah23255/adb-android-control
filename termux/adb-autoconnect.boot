#!/data/data/com.termux/files/usr/bin/bash
# ADB Auto-Connect Boot Script for Termux
# Runs on Termux startup to establish ADB connections

source ~/.adb_devices 2>/dev/null

termux-wake-lock
sleep 5

# Connect all configured devices
while IFS='=' read -r name addr; do
    [[ "$name" =~ ^#.*$ ]] && continue
    [[ -z "$addr" ]] && continue
    adb connect "$addr" 2>/dev/null
done < ~/.adb_devices

# Start the auto-reconnect service
sv up adb-autoconnect 2>/dev/null
