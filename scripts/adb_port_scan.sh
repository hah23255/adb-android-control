#!/data/data/com.termux/files/usr/bin/bash
# ADB Port Scanner - Find wireless debugging port after reconnect
# Usage: ./adb_port_scan.sh [IP] [START_PORT] [END_PORT]

IP="${1:-<DEVICE_IP_HOME>}"
START="${2:-30000}"
END="${3:-45000}"
TIMEOUT=0.3

echo "Scanning $IP for ADB port ($START-$END)..."

found=0
for port in $(seq $START 100 $END); do
    # Scan in chunks of 100
    for p in $(seq $port $((port+99))); do
        [ $p -gt $END ] && break
        (echo > /dev/tcp/$IP/$p) 2>/dev/null && {
            # Test if it's ADB
            result=$(timeout 2 adb connect $IP:$p 2>&1)
            if [[ "$result" == *"connected"* ]]; then
                echo "✓ Found ADB at $IP:$p"
                echo "$p" > ~/.adb_last_port
                # Update config
                sed -i "s/ZFOLD7=.*/ZFOLD7=$IP:$p/" ~/.adb_devices 2>/dev/null
                found=1
                exit 0
            fi
        } &
    done
    wait
done

[ $found -eq 0 ] && echo "No ADB port found. Check Wireless Debugging is enabled."
