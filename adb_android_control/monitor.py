"""Real-time monitoring: logcat streaming, performance snapshots, crashes.

Doctrine note
-------------
This module composes against the public :class:`adb_android_control.controller.ADBController`
API only — never against ``_shell`` / ``_run``. The controller exposes
:meth:`ADBController.shell` for module-friendly shell access.

The streaming primitives (logcat, getevent) use ``subprocess.Popen``
directly because they need long-lived stdout pipes that don't fit
``ADBController._run``'s capture-and-return pattern. This is the one
deliberate carve-out from Law 2 in this module — flagged.

Testability
-----------
- :meth:`LogcatMonitor.parse_log_line` is a pure ``@staticmethod`` so it
  can be unit-tested without spinning up subprocesses or threads.
- :class:`PerformanceMonitor` accepts an injected
  :class:`ADBController` so tests can pass a Poison-Pill-mocked instance.
- ``time.sleep`` and threading-based monitors are NOT covered by unit
  tests — those are integration-test territory (Phase 3).
"""

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


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LogEntry:
    """One parsed logcat line.

    Frozen so a test fixture can be safely shared (Doctrine Law 5).
    """

    timestamp: str
    pid: int
    tid: int
    level: str
    tag: str
    message: str
    raw: str


@dataclass(frozen=True)
class PerformanceSnapshot:
    """Aggregated device-performance reading at a point in time."""

    timestamp: datetime
    battery_level: int
    cpu_usage: float
    memory_used_mb: int
    memory_total_mb: int
    disk_used_percent: float
    running_processes: int


@dataclass(frozen=True)
class CrashEvent:
    """One detected crash from the logcat stream."""

    timestamp: str
    tag: str
    message: str
    level: str


# ---------------------------------------------------------------------------
# Logcat
# ---------------------------------------------------------------------------


_LOGCAT_LINE_RE = re.compile(
    r"^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)"  # timestamp
    r"\s+(\d+)\s+(\d+)"  # pid, tid
    r"\s+([A-Z])"  # level — accept any uppercase
    r"\s+([^:]+):"  # tag    letter so non-standard
    r"\s*(.*)$"  # message  letters (e.g. some
)  # vendor adb builds emit X)
# are passed through rather
# than dropped (Adaptive
# Fault Tolerance pattern).


class LogcatMonitor:
    """Stream and parse logcat output asynchronously.

    The streaming subprocess and queue are owned by this instance; you
    must call :meth:`stop` (or use it as a context manager) to clean up.
    """

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
        """Parse a single logcat line into a :class:`LogEntry`, or ``None``.

        Pure function — no I/O, no instance state. Unit tests call this
        directly to verify parser behaviour without spinning up a
        subprocess.
        """
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
        """Spawn the logcat subprocess and begin streaming.

        Idempotent: a second call while running is a no-op.
        """
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
        """Drain ``stdout`` into ``log_queue`` until the subprocess closes."""
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
        """Terminate the subprocess and reset state."""
        self.running = False
        if self.process is not None:
            self.process.terminate()
            self.process.wait()
            self.process = None

    def get_logs(self, max_count: int = 100) -> list[LogEntry]:
        """Drain up to ``max_count`` queued entries (non-blocking)."""
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
        """Block-stream logs to ``callback``. Stops on KeyboardInterrupt."""
        self.start(filter_level=filter_level)
        try:
            while self.running:
                try:
                    entry = self.log_queue.get(timeout=1)
                except queue.Empty:
                    continue
                callback(entry)
        except KeyboardInterrupt:
            # Ctrl-C is the expected way to end a blocking stream; teardown
            # happens in `finally`, so nothing to do here.
            pass
        finally:
            self.stop()


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


# Match the first percentage value on a CPU-grepped line. The shell pipeline
# already filters to CPU lines via `grep -E 'CPU|cpu'`, so the regex does not
# need to re-validate the keyword. This accepts both real Android top format
# (`80%user 0%nice 50%sys`) and userland tools that emit `user 23.5%` order.
_CPU_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_MEMINFO_KB_RE = re.compile(r"(\d+)")
_DISK_PCT_RE = re.compile(r"(\d+)%")


class PerformanceMonitor:
    """Periodic device-performance snapshots.

    Dependency-injection note: pass an existing :class:`ADBController` if
    you've already constructed one (saves the eager ``adb version`` probe);
    otherwise one is created here.
    """

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
        """Compose a snapshot from the four device queries. Always succeeds.

        Each underlying query is best-effort; degraded values fall back to
        ``0`` rather than raising, because the snapshot's value is *trend
        over time* — one bad reading shouldn't kill the monitoring loop.
        """
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

    # -- individual probes ---------------------------------------------------

    def _get_battery(self) -> int:
        return self.adb.get_battery_level()

    def _get_cpu_usage(self) -> float:
        try:
            output = self.adb.shell("top -n 1 -b | grep -E 'CPU|cpu' | head -1")
        except Exception:  # noqa: BLE001 — degraded path: any failure → 0
            return 0.0
        match = _CPU_PCT_RE.search(output)
        return float(match.group(1)) if match else 0.0

    def _get_memory(self) -> dict[str, int]:
        try:
            output = self.adb.shell("cat /proc/meminfo | head -3")
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
            output = self.adb.shell("df /data | tail -1")
        except Exception:  # noqa: BLE001
            return 0.0
        match = _DISK_PCT_RE.search(output)
        return float(match.group(1)) if match else 0.0

    def _get_process_count(self) -> int:
        try:
            output = self.adb.shell("ps -A | wc -l")
        except Exception:  # noqa: BLE001
            return 0
        try:
            return int(output.strip())
        except ValueError:
            return 0

    # -- monitoring loop -----------------------------------------------------

    def start_monitoring(
        self,
        *,
        interval_s: float = 5.0,
        callback: Callable[[PerformanceSnapshot], None] | None = None,
    ) -> None:
        """Block-loop ``take_snapshot`` every ``interval_s`` until ``stop_monitoring``."""
        self.running = True
        while self.running:
            snapshot = self.take_snapshot()
            if callback is not None:
                callback(snapshot)
            time.sleep(interval_s)

    def stop_monitoring(self) -> None:
        """Signal the loop to exit at the top of its next iteration."""
        self.running = False

    def export_snapshots(self, filepath: str | Path) -> None:
        """Dump :attr:`snapshots` as JSON to ``filepath``."""
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


# ---------------------------------------------------------------------------
# Events (input devices)
# ---------------------------------------------------------------------------


class EventMonitor:
    """Capture raw input events from a /dev/input/eventN device."""

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
        """Stream getevent output. Blocks until SIGINT or :meth:`stop`."""
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
            # Ctrl-C is the expected way to end the capture loop; teardown
            # happens in `finally`, so nothing to do here.
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


# ---------------------------------------------------------------------------
# Crashes
# ---------------------------------------------------------------------------


_CRASH_KEYWORDS: tuple[str, ...] = (
    "crash",
    "exception",
    "fatal",
    "anr",
    "force close",
)


class CrashMonitor:
    """Watch the logcat stream for crash-class log entries.

    Composition over inheritance: holds a :class:`LogcatMonitor` rather
    than extending it, so the two have independent lifecycles.
    """

    def __init__(self, device_serial: str | None = None) -> None:
        self.logcat: LogcatMonitor = LogcatMonitor(device_serial)
        self.crashes: list[CrashEvent] = []

    @staticmethod
    def is_crash_entry(entry: LogEntry) -> bool:
        """Pure predicate — testable in isolation."""
        if entry.level not in ("ERROR", "FATAL"):
            return False
        msg_lower = entry.message.lower()
        return any(keyword in msg_lower for keyword in _CRASH_KEYWORDS)

    def start(self, *, callback: Callable[[CrashEvent], None] | None = None) -> None:
        """Start streaming and capture crashes. Blocking."""

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
        """Return a defensive copy of recorded crashes."""
        return list(self.crashes)
