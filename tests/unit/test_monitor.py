"""Unit tests for :mod:`adb_android_control.monitor`.

Doctrine: AAA (Law 3), isolation (Law 5), Poison-Pill subprocess mocks
(Law 6), one logical concept per test (Law 9), no tautologies (Law 10).

Streaming/threading paths (LogcatMonitor.start, PerformanceMonitor.
start_monitoring, EventMonitor.start_event_capture) are deliberately
NOT covered here — those are integration territory (Phase 3). What we
DO cover here:

- Pure parsers (``LogcatMonitor.parse_log_line``,
  ``CrashMonitor.is_crash_entry``)
- :class:`PerformanceMonitor.take_snapshot` with a fully-mocked controller
- Snapshot export (JSON shape)
- Error-degradation paths (each ``_get_*`` returns ``0`` rather than
  raising when the underlying shell call fails)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from freezegun import freeze_time

from adb_android_control.controller import ADBController, ADBError
from adb_android_control.monitor import (
    CrashEvent,
    CrashMonitor,
    LogcatMonitor,
    LogEntry,
    PerformanceMonitor,
    PerformanceSnapshot,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tests.conftest import PoisonPillADB

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# LogcatMonitor.parse_log_line — pure function, parametrize heavily
# ---------------------------------------------------------------------------


class TestLogcatParser:
    @pytest.mark.parametrize(
        ("line", "expected_level", "expected_tag", "expected_message"),
        [
            (
                "01-15 10:23:45.123  1234  5678 D MyTag: Hello world",
                "DEBUG",
                "MyTag",
                "Hello world",
            ),
            (
                "12-31 23:59:59.999     1     2 I System: Ready",
                "INFO",
                "System",
                "Ready",
            ),
            (
                "06-15 12:00:00.000 12345 67890 E AndroidRuntime: FATAL EXCEPTION",
                "ERROR",
                "AndroidRuntime",
                "FATAL EXCEPTION",
            ),
            (
                "01-01 00:00:00.001    99   100 W TagWith.Dots: msg with: colons",
                "WARNING",
                "TagWith.Dots",
                "msg with: colons",
            ),
        ],
    )
    def test_parses_well_formed_logcat_lines(
        self,
        line: str,
        expected_level: str,
        expected_tag: str,
        expected_message: str,
    ) -> None:
        # Arrange + Act
        entry = LogcatMonitor.parse_log_line(line)

        # Assert
        assert entry is not None
        assert entry.level == expected_level
        assert entry.tag == expected_tag
        assert entry.message == expected_message
        assert entry.raw == line

    @pytest.mark.parametrize(
        "garbage_line",
        [
            "",
            "--------- beginning of main",
            "not a logcat line",
            "01-15 10:23:45 missing fields",
            "01-15 10:23:45.123  abc  def D MyTag: pid is not int",
        ],
    )
    def test_returns_none_for_unparseable_lines(self, garbage_line: str) -> None:
        # Arrange + Act
        entry = LogcatMonitor.parse_log_line(garbage_line)

        # Assert — degraded path: skip, don't raise
        # (internal lesson (adaptive fault tolerance) — graceful fallback)
        assert entry is None

    def test_unknown_level_letter_passes_through_uppercased(self) -> None:
        # Arrange — adb on some devices emits non-standard level letters
        line = "01-15 10:23:45.123  1234  5678 X MyTag: weird"

        # Act
        entry = LogcatMonitor.parse_log_line(line)

        # Assert — graceful: keep the letter rather than crashing
        assert entry is not None
        assert entry.level == "X"


# ---------------------------------------------------------------------------
# CrashMonitor.is_crash_entry — pure predicate
# ---------------------------------------------------------------------------


class TestCrashDetection:
    @pytest.mark.parametrize(
        ("level", "message", "expected"),
        [
            ("ERROR", "Java crash detected", True),
            ("ERROR", "Uncaught exception", True),
            ("FATAL", "FATAL EXCEPTION in main", True),
            ("ERROR", "ANR in com.example.app", True),
            ("ERROR", "Force close detected", True),
            ("ERROR", "User logged in successfully", False),  # error level but not a crash keyword
            ("WARNING", "Crash imminent", False),  # crash keyword but not error/fatal
            ("INFO", "exception handled", False),  # both wrong
            ("DEBUG", "user input", False),
        ],
    )
    def test_classifies_crash_entries_by_level_and_keyword(
        self, level: str, message: str, expected: bool
    ) -> None:
        # Arrange
        entry = LogEntry(
            timestamp="01-15 10:23:45.123",
            pid=1,
            tid=2,
            level=level,
            tag="Test",
            message=message,
            raw=f"raw line: {message}",
        )

        # Act
        result = CrashMonitor.is_crash_entry(entry)

        # Assert
        assert result is expected

    def test_keyword_match_is_case_insensitive(self) -> None:
        # Arrange
        entry = LogEntry(
            timestamp="01-15 10:23:45.123",
            pid=1,
            tid=2,
            level="ERROR",
            tag="App",
            message="CRASH at line 42",  # uppercase
            raw="raw",
        )

        # Act + Assert
        assert CrashMonitor.is_crash_entry(entry) is True


# ---------------------------------------------------------------------------
# PerformanceMonitor — DI'd controller
# ---------------------------------------------------------------------------


def _make_mock_controller(**shell_responses: str) -> ADBController:
    """Build a Spec'd MagicMock that quacks like ADBController.

    Doctrine Pattern: Poison-Pill — ``spec_set=True`` means any method
    not on the real ADBController class raises ``AttributeError``.
    """
    mock = MagicMock(spec_set=ADBController)
    mock.device_serial = None

    def _shell_router(cmd: str, **_kwargs: object) -> str:
        if cmd in shell_responses:
            return shell_responses[cmd]
        raise ADBError(f"unmocked shell command: {cmd!r}")

    mock.shell.side_effect = _shell_router
    mock.get_battery_level.return_value = 87
    return mock


class TestPerformanceMonitor:
    def test_take_snapshot_aggregates_all_probes(self) -> None:
        # Arrange
        adb = _make_mock_controller(
            **{
                "top -n 1 -b | grep -E 'CPU|cpu' | head -1": "  user 23.5%  sys 5.0%",
                "cat /proc/meminfo | head -3": (
                    "MemTotal:        8000000 kB\n"
                    "MemFree:         2000000 kB\n"
                    "MemAvailable:    4000000 kB"
                ),
                "df /data | tail -1": "/data 100G 50G 50G 50% /data",
                "ps -A | wc -l": "247",
            }
        )
        mon = PerformanceMonitor(adb=adb)

        # Act
        with freeze_time("2026-05-05T12:00:00Z"):
            snap = mon.take_snapshot()

        # Assert
        assert isinstance(snap, PerformanceSnapshot)
        assert snap.battery_level == 87
        assert snap.cpu_usage == pytest.approx(23.5)
        assert snap.memory_total_mb == 7812  # 8000000 // 1024
        assert snap.memory_used_mb == 3906  # total - available
        assert snap.disk_used_percent == 50.0
        assert snap.running_processes == 247
        assert snap.timestamp == datetime(2026, 5, 5, 12, 0, 0, tzinfo=timezone.utc)
        # Snapshot also recorded in history
        assert mon.snapshots == [snap]

    def test_failed_cpu_query_degrades_to_zero(self) -> None:
        """internal lesson (adaptive fault tolerance).

        Adaptive Fault Tolerance: one bad probe doesn't kill the loop.
        """
        # Arrange — only register the queries that should succeed
        adb = _make_mock_controller(
            **{
                "cat /proc/meminfo | head -3": "MemTotal: 8000000 kB",
                "df /data | tail -1": "/data 50% /data",
                "ps -A | wc -l": "100",
                # CPU query intentionally NOT registered → ADBError → 0.0
            }
        )
        mon = PerformanceMonitor(adb=adb)

        # Act
        snap = mon.take_snapshot()

        # Assert — degraded value, but no exception
        assert snap.cpu_usage == 0.0
        assert snap.memory_total_mb == 7812  # other probes still work
        assert snap.running_processes == 100

    def test_failed_process_count_returns_zero(self) -> None:
        # Arrange
        adb = _make_mock_controller(
            **{
                "top -n 1 -b | grep -E 'CPU|cpu' | head -1": "0% idle",
                "cat /proc/meminfo | head -3": "MemTotal: 8000000 kB",
                "df /data | tail -1": "/data 0%",
                "ps -A | wc -l": "garbage_not_an_int",  # parse failure
            }
        )
        mon = PerformanceMonitor(adb=adb)

        # Act
        snap = mon.take_snapshot()

        # Assert
        assert snap.running_processes == 0

    def test_uses_timezone_aware_utc_timestamps(self) -> None:
        """Doctrine Law 8 — determinism: timestamps are explicit UTC."""
        # Arrange
        adb = _make_mock_controller()
        mon = PerformanceMonitor(adb=adb)

        # Act
        with freeze_time("2026-05-05T00:00:00Z"):
            snap = mon.take_snapshot()

        # Assert
        assert snap.timestamp.tzinfo is not None
        assert snap.timestamp == datetime(2026, 5, 5, tzinfo=timezone.utc)

    def test_export_snapshots_writes_json_with_expected_shape(self, tmp_path: Path) -> None:
        # Arrange
        adb = _make_mock_controller()
        mon = PerformanceMonitor(adb=adb)
        with freeze_time("2026-05-05T00:00:00Z"):
            mon.take_snapshot()

        # Act
        out = tmp_path / "snapshots.json"
        mon.export_snapshots(out)

        # Assert
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 1
        record = data[0]
        # All seven contract keys present (Doctrine Law 2: schema is the contract)
        assert set(record.keys()) == {
            "timestamp",
            "battery",
            "cpu_usage",
            "memory_used_mb",
            "memory_total_mb",
            "disk_used_percent",
            "processes",
        }
        assert record["timestamp"].startswith("2026-05-05T")


# ---------------------------------------------------------------------------
# Dataclass smoke (frozen contract)
# ---------------------------------------------------------------------------


class TestValueObjects:
    def test_log_entry_is_frozen(self) -> None:
        # Arrange
        entry = LogEntry(timestamp="t", pid=1, tid=2, level="INFO", tag="T", message="m", raw="r")

        # Act + Assert — Doctrine Law 5: shared fixtures must be immutable
        with pytest.raises(Exception):  # noqa: B017 — FrozenInstanceError or AttributeError depending on python
            entry.level = "ERROR"  # type: ignore[misc]

    def test_crash_event_is_frozen(self) -> None:
        # Arrange
        crash = CrashEvent(timestamp="t", tag="T", message="m", level="ERROR")

        # Act + Assert
        with pytest.raises(Exception):  # noqa: B017
            crash.level = "FATAL"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CrashMonitor lifecycle (composition over inheritance)
# ---------------------------------------------------------------------------


class TestCrashMonitorComposition:
    def test_holds_a_logcat_monitor(self, mock_adb: PoisonPillADB) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="v1\n")

        # Act
        cm = CrashMonitor(device_serial="EMULATOR-1")

        # Assert — composition: separate, addressable instance
        assert isinstance(cm.logcat, LogcatMonitor)
        assert cm.logcat.device_serial == "EMULATOR-1"

    def test_get_crashes_returns_defensive_copy(self) -> None:
        # Arrange
        cm = CrashMonitor()
        cm.crashes.append(CrashEvent(timestamp="t", tag="T", message="m", level="ERROR"))

        # Act
        result = cm.get_crashes()
        result.clear()  # mutate the copy

        # Assert — internal state unaffected
        assert len(cm.crashes) == 1
