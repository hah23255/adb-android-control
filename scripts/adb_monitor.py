#!/usr/bin/env python3
"""
ADB Monitor - Real-time device monitoring and log streaming.
Provides continuous monitoring of device state, logs, and performance.
"""

import subprocess
import threading
import queue
import time
import re
import signal
import sys
import json
from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from adb_controller import ADBController


@dataclass
class LogEntry:
    """Parsed logcat entry."""
    timestamp: str
    pid: int
    tid: int
    level: str
    tag: str
    message: str
    raw: str


@dataclass
class PerformanceSnapshot:
    """Device performance snapshot."""
    timestamp: datetime
    battery_level: int
    cpu_usage: float
    memory_used_mb: int
    memory_total_mb: int
    disk_used_percent: float
    running_processes: int


class LogcatMonitor:
    """Real-time logcat monitoring."""

    LEVELS = {'V': 'VERBOSE', 'D': 'DEBUG', 'I': 'INFO',
              'W': 'WARNING', 'E': 'ERROR', 'F': 'FATAL'}

    def __init__(self, device_serial: Optional[str] = None):
        self.device_serial = device_serial
        self.process: Optional[subprocess.Popen] = None
        self.running = False
        self.log_queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None

    def _parse_log_line(self, line: str) -> Optional[LogEntry]:
        """Parse logcat line into LogEntry."""
        pattern = r'^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\s+(\d+)\s+(\d+)\s+([VDIWEF])\s+([^:]+):\s*(.*)$'
        match = re.match(pattern, line)

        if match:
            return LogEntry(
                timestamp=match.group(1),
                pid=int(match.group(2)),
                tid=int(match.group(3)),
                level=self.LEVELS.get(match.group(4), match.group(4)),
                tag=match.group(5).strip(),
                message=match.group(6),
                raw=line
            )
        return None

    def start(self, filter_level: str = 'V',
              filter_tags: Optional[List[str]] = None,
              filter_package: Optional[str] = None) -> None:
        """Start logcat streaming."""
        if self.running:
            return

        cmd = ['adb']
        if self.device_serial:
            cmd.extend(['-s', self.device_serial])
        cmd.extend(['logcat', '-v', 'threadtime'])

        if filter_level != 'V':
            cmd.extend([f'*:{filter_level}'])

        if filter_tags:
            for tag in filter_tags:
                cmd.extend(['-s', f'{tag}:*'])

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        self.running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self) -> None:
        """Read logcat output continuously."""
        while self.running and self.process:
            line = self.process.stdout.readline()
            if line:
                entry = self._parse_log_line(line.strip())
                if entry:
                    self.log_queue.put(entry)
            else:
                break

    def stop(self) -> None:
        """Stop logcat streaming."""
        self.running = False
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None

    def get_logs(self, max_count: int = 100) -> List[LogEntry]:
        """Get buffered logs."""
        logs = []
        while not self.log_queue.empty() and len(logs) < max_count:
            try:
                logs.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        return logs

    def stream_logs(self, callback: Callable[[LogEntry], None],
                    filter_level: str = 'V') -> None:
        """Stream logs to callback."""
        self.start(filter_level)

        try:
            while self.running:
                try:
                    entry = self.log_queue.get(timeout=1)
                    callback(entry)
                except queue.Empty:
                    continue
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


class PerformanceMonitor:
    """Real-time performance monitoring."""

    def __init__(self, device_serial: Optional[str] = None):
        self.adb = ADBController(device_serial)
        self.running = False
        self.snapshots: List[PerformanceSnapshot] = []

    def take_snapshot(self) -> PerformanceSnapshot:
        """Take performance snapshot."""
        battery = self._get_battery()
        cpu = self._get_cpu_usage()
        memory = self._get_memory()
        disk = self._get_disk_usage()
        processes = self._get_process_count()

        snapshot = PerformanceSnapshot(
            timestamp=datetime.now(),
            battery_level=battery,
            cpu_usage=cpu,
            memory_used_mb=memory['used'],
            memory_total_mb=memory['total'],
            disk_used_percent=disk,
            running_processes=processes
        )

        self.snapshots.append(snapshot)
        return snapshot

    def _get_battery(self) -> int:
        """Get battery level."""
        return self.adb.get_battery_level()

    def _get_cpu_usage(self) -> float:
        """Get CPU usage percentage."""
        try:
            output = self.adb._shell("top -n 1 -b | grep -E 'CPU|cpu' | head -1")
            match = re.search(r'(\d+(?:\.\d+)?)[%\s]*(?:cpu|user|idle)', output, re.I)
            if match:
                return float(match.group(1))
        except Exception:
            pass
        return 0.0

    def _get_memory(self) -> Dict[str, int]:
        """Get memory usage in MB."""
        try:
            output = self.adb._shell("cat /proc/meminfo | head -3")
            total = used = 0
            for line in output.split('\n'):
                if 'MemTotal' in line:
                    total = int(re.search(r'(\d+)', line).group(1)) // 1024
                elif 'MemAvailable' in line:
                    available = int(re.search(r'(\d+)', line).group(1)) // 1024
                    used = total - available
            return {'total': total, 'used': used}
        except Exception:
            return {'total': 0, 'used': 0}

    def _get_disk_usage(self) -> float:
        """Get disk usage percentage."""
        try:
            output = self.adb._shell("df /data | tail -1")
            match = re.search(r'(\d+)%', output)
            if match:
                return float(match.group(1))
        except Exception:
            pass
        return 0.0

    def _get_process_count(self) -> int:
        """Get running process count."""
        try:
            output = self.adb._shell("ps -A | wc -l")
            return int(output.strip())
        except Exception:
            return 0

    def start_monitoring(self, interval: float = 5.0,
                         callback: Optional[Callable[[PerformanceSnapshot], None]] = None) -> None:
        """Start continuous monitoring."""
        self.running = True

        while self.running:
            snapshot = self.take_snapshot()
            if callback:
                callback(snapshot)
            time.sleep(interval)

    def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self.running = False

    def export_snapshots(self, filepath: str) -> None:
        """Export snapshots to JSON."""
        data = []
        for s in self.snapshots:
            data.append({
                'timestamp': s.timestamp.isoformat(),
                'battery': s.battery_level,
                'cpu_usage': s.cpu_usage,
                'memory_used_mb': s.memory_used_mb,
                'memory_total_mb': s.memory_total_mb,
                'disk_used_percent': s.disk_used_percent,
                'processes': s.running_processes
            })

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)


class EventMonitor:
    """Monitor device events (touches, keys, etc)."""

    def __init__(self, device_serial: Optional[str] = None):
        self.adb = ADBController(device_serial)
        self.process: Optional[subprocess.Popen] = None
        self.running = False

    def start_event_capture(self, device: str = '/dev/input/event0',
                            callback: Optional[Callable[[str], None]] = None) -> None:
        """Start capturing input events."""
        cmd = ['adb']
        if self.adb.device_serial:
            cmd.extend(['-s', self.adb.device_serial])
        cmd.extend(['shell', 'getevent', '-lt', device])

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        self.running = True

        try:
            while self.running:
                line = self.process.stdout.readline()
                if line:
                    if callback:
                        callback(line.strip())
                    else:
                        print(line.strip())
                else:
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop event capture."""
        self.running = False
        if self.process:
            self.process.terminate()
            self.process.wait()


class CrashMonitor:
    """Monitor for app crashes."""

    def __init__(self, device_serial: Optional[str] = None):
        self.logcat = LogcatMonitor(device_serial)
        self.crashes: List[Dict] = []

    def start(self, packages: Optional[List[str]] = None,
              callback: Optional[Callable[[Dict], None]] = None) -> None:
        """Start crash monitoring."""

        def check_crash(entry: LogEntry):
            is_crash = (
                    entry.level in ('ERROR', 'FATAL') and
                    any(kw in entry.message.lower() for kw in
                        ['crash', 'exception', 'fatal', 'anr', 'force close'])
            )

            if is_crash:
                crash_info = {
                    'timestamp': entry.timestamp,
                    'tag': entry.tag,
                    'message': entry.message,
                    'level': entry.level
                }
                self.crashes.append(crash_info)
                if callback:
                    callback(crash_info)

        self.logcat.stream_logs(check_crash, filter_level='E')

    def stop(self) -> None:
        """Stop crash monitoring."""
        self.logcat.stop()

    def get_crashes(self) -> List[Dict]:
        """Get recorded crashes."""
        return self.crashes


def print_log_entry(entry: LogEntry) -> None:
    """Pretty print log entry."""
    level_colors = {
        'VERBOSE': '\033[37m',
        'DEBUG': '\033[34m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'FATAL': '\033[35m'
    }
    reset = '\033[0m'
    color = level_colors.get(entry.level, '')

    print(f"{color}[{entry.timestamp}] {entry.level[0]} {entry.tag}: {entry.message}{reset}")


def print_snapshot(snapshot: PerformanceSnapshot) -> None:
    """Pretty print performance snapshot."""
    print(f"\n--- {snapshot.timestamp.strftime('%H:%M:%S')} ---")
    print(f"Battery: {snapshot.battery_level}%")
    print(f"CPU: {snapshot.cpu_usage:.1f}%")
    print(f"Memory: {snapshot.memory_used_mb}/{snapshot.memory_total_mb} MB")
    print(f"Disk: {snapshot.disk_used_percent:.1f}%")
    print(f"Processes: {snapshot.running_processes}")


def main():
    """Demo monitoring."""
    import argparse

    parser = argparse.ArgumentParser(description='ADB Monitor')
    parser.add_argument('mode', choices=['logcat', 'perf', 'events', 'crash'],
                        help='Monitor mode')
    parser.add_argument('-s', '--serial', help='Device serial')
    parser.add_argument('-l', '--level', default='V',
                        choices=['V', 'D', 'I', 'W', 'E', 'F'],
                        help='Log level filter')
    parser.add_argument('-i', '--interval', type=float, default=5.0,
                        help='Perf monitor interval')

    args = parser.parse_args()

    def signal_handler(sig, frame):
        print("\nStopping...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    if args.mode == 'logcat':
        print("Starting logcat monitor (Ctrl+C to stop)...")
        monitor = LogcatMonitor(args.serial)
        monitor.stream_logs(print_log_entry, args.level)

    elif args.mode == 'perf':
        print(f"Starting performance monitor (interval: {args.interval}s, Ctrl+C to stop)...")
        monitor = PerformanceMonitor(args.serial)
        monitor.start_monitoring(args.interval, print_snapshot)

    elif args.mode == 'events':
        print("Starting event monitor (Ctrl+C to stop)...")
        monitor = EventMonitor(args.serial)
        monitor.start_event_capture()

    elif args.mode == 'crash':
        print("Starting crash monitor (Ctrl+C to stop)...")

        def on_crash(crash):
            print(f"\n!!! CRASH DETECTED !!!")
            print(json.dumps(crash, indent=2))

        monitor = CrashMonitor(args.serial)
        monitor.start(callback=on_crash)


if __name__ == '__main__':
    main()
