#!/usr/bin/env python3
"""Backwards-compatibility shim — canonical module is now
:mod:`adb_android_control.monitor`. Will be removed in v2.0.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import FrameType

import argparse
import json
import signal
import sys
import warnings

from adb_android_control.monitor import (
    CrashEvent,
    CrashMonitor,
    EventMonitor,
    LogcatMonitor,
    LogEntry,
    PerformanceMonitor,
    PerformanceSnapshot,
)

warnings.warn(
    "scripts.adb_monitor is deprecated; import from adb_android_control.monitor instead. "
    "This shim will be removed in v2.0.",
    DeprecationWarning,
    stacklevel=2,
)


# ---------------------------------------------------------------------------
# CLI helpers (only used by `python -m scripts.adb_monitor` demo entrypoint)
# ---------------------------------------------------------------------------


_LEVEL_COLORS: dict[str, str] = {
    "VERBOSE": "\033[37m",
    "DEBUG": "\033[34m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "FATAL": "\033[35m",
}
_RESET = "\033[0m"


def print_log_entry(entry: LogEntry) -> None:
    """ANSI-coloured pretty-print of a :class:`LogEntry`."""
    color = _LEVEL_COLORS.get(entry.level, "")
    print(f"{color}[{entry.timestamp}] {entry.level[0]} {entry.tag}: {entry.message}{_RESET}")


def print_snapshot(snapshot: PerformanceSnapshot) -> None:
    """Compact pretty-print of a :class:`PerformanceSnapshot`."""
    print(f"\n--- {snapshot.timestamp.strftime('%H:%M:%S')} ---")
    print(f"Battery: {snapshot.battery_level}%")
    print(f"CPU: {snapshot.cpu_usage:.1f}%")
    print(f"Memory: {snapshot.memory_used_mb}/{snapshot.memory_total_mb} MB")
    print(f"Disk: {snapshot.disk_used_percent:.1f}%")
    print(f"Processes: {snapshot.running_processes}")


def main() -> None:
    """CLI entry — supports logcat / perf / events / crash modes."""
    parser = argparse.ArgumentParser(description="ADB Monitor")
    parser.add_argument(
        "mode",
        choices=["logcat", "perf", "events", "crash"],
        help="Monitor mode",
    )
    parser.add_argument("-s", "--serial", help="Device serial")
    parser.add_argument(
        "-l",
        "--level",
        default="V",
        choices=["V", "D", "I", "W", "E", "F"],
        help="Log level filter",
    )
    parser.add_argument(
        "-i", "--interval", type=float, default=5.0, help="Perf monitor interval (s)"
    )
    args = parser.parse_args()

    def signal_handler(_sig: int, _frame: FrameType | None) -> None:
        print("\nStopping...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    if args.mode == "logcat":
        print("Starting logcat monitor (Ctrl+C to stop)...")
        LogcatMonitor(args.serial).stream_logs(print_log_entry, filter_level=args.level)
    elif args.mode == "perf":
        print(f"Starting performance monitor (interval: {args.interval}s, Ctrl+C to stop)...")
        PerformanceMonitor(args.serial).start_monitoring(
            interval_s=args.interval, callback=print_snapshot
        )
    elif args.mode == "events":
        print("Starting event monitor (Ctrl+C to stop)...")
        EventMonitor(args.serial).start_event_capture()
    elif args.mode == "crash":
        print("Starting crash monitor (Ctrl+C to stop)...")

        def on_crash(crash: CrashEvent) -> None:
            print("\n!!! CRASH DETECTED !!!")
            print(
                json.dumps(
                    {
                        "timestamp": crash.timestamp,
                        "tag": crash.tag,
                        "message": crash.message,
                        "level": crash.level,
                    },
                    indent=2,
                )
            )

        CrashMonitor(args.serial).start(callback=on_crash)


__all__ = [
    "CrashEvent",
    "CrashMonitor",
    "EventMonitor",
    "LogEntry",
    "LogcatMonitor",
    "PerformanceMonitor",
    "PerformanceSnapshot",
    "main",
    "print_log_entry",
    "print_snapshot",
]


if __name__ == "__main__":
    main()
