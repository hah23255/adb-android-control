#!/data/data/com.termux/files/usr/bin/bash
# ADB Control - Manage ADB auto-connect and monitor
# Usage: adb-control [start|stop|status|restart|scan|log|monitor]

MONITOR_PID_FILE="$HOME/.adb_monitor.pid"
LOGFILE="$HOME/.adb_connect.log"
MONITOR_LOG="$HOME/.adb_monitor.log"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

start_monitor() {
    if [ -f "$MONITOR_PID_FILE" ]; then
        pid=$(cat "$MONITOR_PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${YELLOW}Monitor already running (PID: $pid)${NC}"
            return
        fi
    fi

    nohup adb-control connection run -i 30 >> "$MONITOR_LOG" 2>&1 &
    echo $! > "$MONITOR_PID_FILE"
    echo -e "${GREEN}Monitor started (PID: $!)${NC}"
}

stop_monitor() {
    if [ -f "$MONITOR_PID_FILE" ]; then
        pid=$(cat "$MONITOR_PID_FILE")
        if kill "$pid" 2>/dev/null; then
            echo -e "${GREEN}Monitor stopped (PID: $pid)${NC}"
            rm -f "$MONITOR_PID_FILE"
        else
            echo -e "${YELLOW}Monitor not running${NC}"
            rm -f "$MONITOR_PID_FILE"
        fi
    else
        echo -e "${YELLOW}Monitor not running${NC}"
    fi
}

status() {
    echo "=== ADB Control Status ==="
    echo ""

    echo "ADB Devices:"
    adb devices -l 2>/dev/null | grep -v "^List" | while read line; do
        [ -n "$line" ] && echo "  $line"
    done
    echo ""

    echo -n "Auto-connect service: "
    if sv status adb-autoconnect 2>/dev/null | grep -q "run:"; then
        echo -e "${GREEN}running${NC}"
    else
        echo -e "${RED}stopped${NC}"
    fi

    echo -n "Connection monitor:   "
    if [ -f "$MONITOR_PID_FILE" ]; then
        pid=$(cat "$MONITOR_PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${GREEN}running (PID: $pid)${NC}"
        else
            echo -e "${RED}stopped (stale PID)${NC}"
        fi
    else
        echo -e "${RED}stopped${NC}"
    fi

    echo ""
    adb-control connection status 2>/dev/null
}

scan() {
    source ~/.adb_devices 2>/dev/null
    while IFS='=' read -r name addr; do
        [[ "$name" =~ ^#.*$ ]] && continue
        [[ -z "$addr" ]] && continue
        ip="${addr%%:*}"
        echo "Scanning $ip for ADB port..."
        adb-control scan-port "$ip"
    done < ~/.adb_devices 2>/dev/null
}

show_log() {
    lines="${1:-50}"
    echo "=== Connection Log (last $lines lines) ==="
    tail -n "$lines" "$LOGFILE" 2>/dev/null
    echo ""
    echo "=== Monitor Log (last $lines lines) ==="
    tail -n "$lines" "$MONITOR_LOG" 2>/dev/null
}

case "${1:-status}" in
    start)
        sv up adb-autoconnect 2>/dev/null
        start_monitor
        ;;
    stop)
        sv down adb-autoconnect 2>/dev/null
        stop_monitor
        ;;
    restart)
        sv restart adb-autoconnect 2>/dev/null
        stop_monitor
        sleep 1
        start_monitor
        ;;
    status)
        status
        ;;
    scan)
        scan
        ;;
    log)
        show_log "${2:-50}"
        ;;
    monitor)
        adb-control connection run -i "${2:-10}"
        ;;
    *)
        echo "Usage: adb-control [start|stop|status|restart|scan|log|monitor]"
        echo ""
        echo "Commands:"
        echo "  start    - Start auto-connect service and monitor"
        echo "  stop     - Stop all services"
        echo "  status   - Show current status"
        echo "  restart  - Restart all services"
        echo "  scan     - Scan for ADB port"
        echo "  log [n]  - Show last n lines of logs"
        echo "  monitor  - Run monitor in foreground"
        ;;
esac
