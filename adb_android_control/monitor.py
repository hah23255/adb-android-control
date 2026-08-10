"""Real-time logcat, performance, crash monitoring."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

import json
import logging
import queue
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar

from adb_android_control.controller import ADBController

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LogEntry:
    """One parsed logcat line."""

    timestamp: str
    pid: int
    tid: int
    level: str
    tag: str
    message: str
    raw: str


@dataclass(frozen=True)
class PerformanceSnapshot:
    """Performance reading at a point in time."""

    timestamp: datetime
    battery_level: int
    cpu_usage: float
    memory_used_mb: int
    memory_total_mb: int
    disk_used_percent: float
    running_processes: int


@dataclass(frozen=True)
class CrashEvent:
    """A crash detected in logcat."""

    timestamp: str
    tag: str
    message: str
    level: str


_LOGCAT_LINE_RE = re.compile(
    r"^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)"  # timestamp
    r"\s+(\d+)\s+(\d+)"  # pid, tid
    r"\s+([A-Z])"  # level
    r"\s+([^:]+):"  # tag
    r"\s*(.*)$"  # message
)


class LogcatMonitor:
    """Stream and parse logcat asynchronously."""

    LEVELS: ClassVar[dict[str, str]] = {
        "V": "VERBOSE",
        "D": "DEBUG",
        "I": "INFO",
        "W": "WARNING",
        "E": "ERROR",
        "F": "FATAL",
    }

    def __init__(self, device_serial: str | None = None) -> None:
        self.device_serial: str | None = device_serial
        self.process: subprocess.Popen[str] | None = None
        self.running: bool = False
        self.log_queue: queue.Queue[LogEntry] = queue.Queue()
        self._thread: threading.Thread | None = None

    @staticmethod
    def parse_log_line(line: str) -> LogEntry | None:
        """Parse one logcat line into a :class:`LogEntry`."""
        match = _LOGCAT_LINE_RE.match(line)
        if match is None:
            return None
        level_letter = match.group(4)
        return LogEntry(
            timestamp=match.group(1),
            pid=int(match.group(2)),
            tid=int(match.group(3)),
            level=LogcatMonitor.LEVELS.get(level_letter, level_letter),
            tag=match.group(5).strip(),
            message=match.group(6),
            raw=line,
        )

    def start(
        self,
        *,
        filter_level: str = "V",
        filter_tags: list[str] | None = None,
    ) -> None:
        """Spawn logcat and begin streaming."""
        if self.running:
            return

        cmd: list[str] = ["adb"]
        if self.device_serial is not None:
            cmd.extend(["-s", self.device_serial])
        cmd.extend(["logcat", "-v", "threadtime"])
        if filter_level != "V":
            cmd.append(f"*:{filter_level}")
        if filter_tags:
            for tag in filter_tags:
                cmd.extend(["-s", f"{tag}:*"])

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self) -> None:
        """Drain ``stdout`` into ``log_queue``."""
        if self.process is None or self.process.stdout is None:
            return
        while self.running:
            line = self.process.stdout.readline()
            if not line:
                break
            entry = self.parse_log_line(line.strip())
            if entry is not None:
                self.log_queue.put(entry)

    def stop(self) -> None:
        """Terminate the subprocess and reset."""
        self.running = False
        if self.process is not None:
            self.process.terminate()
            self.process.wait()
            self.process = None

    def get_logs(self, max_count: int = 100) -> list[LogEntry]:
        """Drain up to ``max_count`` queued entries."""
        logs: list[LogEntry] = []
        while not self.log_queue.empty() and len(logs) < max_count:
            try:
                logs.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        return logs

    def stream_logs(
        self,
        callback: Callable[[LogEntry], None],
        *,
        filter_level: str = "V",
    ) -> None:
        """Block-stream logs to ``callback``."""
        self.start(filter_level=filter_level)
        try:
            while self.running:
                try:
                    entry = self.log_queue.get(timeout=1)
                except queue.Empty:
                    continue
                callback(entry)
        except KeyboardInterrupt:
            pass  # Ctrl-C ends the stream; cleanup in `finally`
        finally:
            self.stop()


# Accepts `80%user` and `user 23.5%` formats.
_CPU_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_MEMINFO_KB_RE = re.compile(r"(\d+)")
_DISK_PCT_RE = re.compile(r"(\d+)%")

# Module-level so tests probe with the same commands.
_CPU_PROBE_CMD = "top -n 1 -b | grep -E 'CPU|cpu' | head -1"
_MEMORY_PROBE_CMD = "cat /proc/meminfo | head -3"
_DISK_PROBE_CMD = "df /data | tail -1"
_PROCESS_COUNT_PROBE_CMD = "ps -A | wc -l"


class PerformanceMonitor:
    """Periodic device-performance snapshots."""

    def __init__(
        self,
        device_serial: str | None = None,
        *,
        adb: ADBController | None = None,
    ) -> None:
        self.adb: ADBController = adb if adb is not None else ADBController(device_serial)
        self.running: bool = False
        self.snapshots: list[PerformanceSnapshot] = []

    def take_snapshot(self) -> PerformanceSnapshot:
        """Compose a snapshot from device queries."""
        memory = self._get_memory()
        snapshot = PerformanceSnapshot(
            timestamp=datetime.now(tz=timezone.utc),
            battery_level=self._get_battery(),
            cpu_usage=self._get_cpu_usage(),
            memory_used_mb=memory["used"],
            memory_total_mb=memory["total"],
            disk_used_percent=self._get_disk_usage(),
            running_processes=self._get_process_count(),
        )
        self.snapshots.append(snapshot)
        return snapshot

    def _get_battery(self) -> int:
        return self.adb.get_battery_level()

    def _get_cpu_usage(self) -> float:
        try:
            output = self.adb.shell(_CPU_PROBE_CMD)
        except Exception:  # noqa: BLE001 — any failure → 0
            return 0.0
        match = _CPU_PCT_RE.search(output)
        return float(match.group(1)) if match else 0.0

    def _get_memory(self) -> dict[str, int]:
        try:
            output = self.adb.shell(_MEMORY_PROBE_CMD)
        except Exception:  # noqa: BLE001
            return {"total": 0, "used": 0}
        total = used = 0
        for line in output.split("\n"):
            kb_match = _MEMINFO_KB_RE.search(line)
            if kb_match is None:
                continue
            kb = int(kb_match.group(1))
            if "MemTotal" in line:
                total = kb // 1024
            elif "MemAvailable" in line:
                used = total - (kb // 1024)
        return {"total": total, "used": max(0, used)}

    def _get_disk_usage(self) -> float:
        try:
            output = self.adb.shell(_DISK_PROBE_CMD)
        except Exception:  # noqa: BLE001
            return 0.0
        match = _DISK_PCT_RE.search(output)
        return float(match.group(1)) if match else 0.0

    def _get_process_count(self) -> int:
        try:
            output = self.adb.shell(_PROCESS_COUNT_PROBE_CMD)
        except Exception:  # noqa: BLE001
            return 0
        try:
            return int(output.strip())
        except ValueError:
            return 0

    def start_monitoring(
        self,
        *,
        interval_s: float = 5.0,
        callback: Callable[[PerformanceSnapshot], None] | None = None,
    ) -> None:
        """Snapshot every ``interval_s``."""
        self.running = True
        while self.running:
            snapshot = self.take_snapshot()
            if callback is not None:
                callback(snapshot)
            time.sleep(interval_s)

    def stop_monitoring(self) -> None:
        """Signal the loop to exit."""
        self.running = False

    def export_snapshots(self, filepath: str | Path) -> None:
        """Dump snapshots as JSON to ``filepath``."""
        data = [
            {
                "timestamp": s.timestamp.isoformat(),
                "battery": s.battery_level,
                "cpu_usage": s.cpu_usage,
                "memory_used_mb": s.memory_used_mb,
                "memory_total_mb": s.memory_total_mb,
                "disk_used_percent": s.disk_used_percent,
                "processes": s.running_processes,
            }
            for s in self.snapshots
        ]
        Path(filepath).write_text(json.dumps(data, indent=2), encoding="utf-8")


# Events (input devices)


class EventMonitor:
    """Capture raw input events from an input device."""

    def __init__(
        self,
        device_serial: str | None = None,
        *,
        adb: ADBController | None = None,
    ) -> None:
        self.adb: ADBController = adb if adb is not None else ADBController(device_serial)
        self.process: subprocess.Popen[str] | None = None
        self.running: bool = False

    def start_event_capture(
        self,
        device: str = "/dev/input/event0",
        *,
        callback: Callable[[str], None] | None = None,
    ) -> None:
        """Stream getevent; blocks until stopped."""
        cmd: list[str] = ["adb"]
        if self.adb.device_serial is not None:
            cmd.extend(["-s", self.adb.device_serial])
        cmd.extend(["shell", "getevent", "-lt", device])

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.running = True

        try:
            while self.running and self.process.stdout is not None:
                line = self.process.stdout.readline()
                if not line:
                    break
                stripped = line.strip()
                if callback is not None:
                    callback(stripped)
                else:
                    print(stripped)  # noqa: T201
        except KeyboardInterrupt:
            # Ctrl-C ends the capture; teardown is in `finally`.
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the capture and reset state."""
        self.running = False
        if self.process is not None:
            self.process.terminate()
            self.process.wait()
            self.process = None


# Crashes


_CRASH_KEYWORDS: tuple[str, ...] = (
    "crash",
    "exception",
    "fatal",
    "anr",
    "force close",
)


class CrashMonitor:
    """Watch logcat for crash-class entries."""

    def __init__(self, device_serial: str | None = None) -> None:
        self.logcat: LogcatMonitor = LogcatMonitor(device_serial)
        self.crashes: list[CrashEvent] = []

    @staticmethod
    def is_crash_entry(entry: LogEntry) -> bool:
        """Pure predicate."""
        if entry.level not in ("ERROR", "FATAL"):
            return False
        msg_lower = entry.message.lower()
        return any(keyword in msg_lower for keyword in _CRASH_KEYWORDS)

    def start(self, *, callback: Callable[[CrashEvent], None] | None = None) -> None:
        """Start streaming and capturing crashes."""

        def _on_entry(entry: LogEntry) -> None:
            if not self.is_crash_entry(entry):
                return
            crash = CrashEvent(
                timestamp=entry.timestamp,
                tag=entry.tag,
                message=entry.message,
                level=entry.level,
            )
            self.crashes.append(crash)
            if callback is not None:
                callback(crash)

        self.logcat.stream_logs(_on_entry, filter_level="E")

    def stop(self) -> None:
        """Tear down the underlying logcat stream."""
        self.logcat.stop()

    def get_crashes(self) -> list[CrashEvent]:
        """Return a defensive copy of crashes."""
        return list(self.crashes)
