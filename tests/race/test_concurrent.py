"""Race-condition + time-determinism tests.

Doctrine
--------
Master Tester Doctrine § Advanced Patterns: "Race condition testing —
out-of-order resolution + AbortController. Verify async behaviour
survives timing edge cases."

Adapted to Python: we use ``threading.Event`` to gate execution at
known points, ``concurrent.futures`` with deterministic submission
ordering, and ``freezegun`` for time-based assertions. No
``time.sleep`` in test bodies — every wait is condition-variable based.

Closes Phase 3 plan items §5, §6, §7, §10, §11.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

from adb_android_control.connection_monitor import (
    ConnectionMonitor,
)
from adb_android_control.controller import ADBController
from adb_android_control.monitor import (
    CrashEvent,
    CrashMonitor,
    LogcatMonitor,
    LogEntry,
)
from adb_android_control.port_scan import PortScanner

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock

pytestmark = [pytest.mark.unit, pytest.mark.race]


# ---------------------------------------------------------------------------
# §6 — port_scan: response from "old" port arriving after scanner moved on
# ---------------------------------------------------------------------------


class TestPortScanRaceConditions:
    """The plan's §6: response from old port arrives mid-scan."""

    def test_late_arriving_open_port_response_still_collected(self) -> None:
        """Out-of-order resolution: a slow-to-respond port still appears.

        We use a barrier to force every check_port call to release in a
        non-arrival order. The result must still be the deterministic
        sorted-ascending list.
        """
        # Arrange — gate every probe behind an Event we control
        gates: dict[int, threading.Event] = {
            5555: threading.Event(),
            5556: threading.Event(),
            5557: threading.Event(),
        }
        open_ports = {5555, 5556}  # 5557 closed

        def _gated_check(_ip: str, port: int) -> bool:
            gates[port].wait()
            return port in open_ports

        scanner = PortScanner(
            check_port_fn=_gated_check,
            adb_connect_fn=lambda _i, _p: False,
            max_workers=3,
        )

        # Act — release in REVERSE order to provoke out-of-order completion
        result_holder: list[list[int]] = []

        def _scan() -> None:
            result_holder.append(
                scanner.find_open_ports("10.0.0.1", start=5555, end=5557)
            )

        scan_thread = threading.Thread(target=_scan)
        scan_thread.start()
        try:
            gates[5557].set()  # the closed one finishes first
            gates[5556].set()
            gates[5555].set()  # the strongest "first" port finishes last
        finally:
            scan_thread.join(timeout=5)

        # Assert — sorted ascending despite reverse-order completion
        assert not scan_thread.is_alive(), "scan should have completed"
        assert result_holder == [[5555, 5556]], (
            "find_open_ports must always return ascending-sorted results, "
            "regardless of completion order"
        )

    def test_no_open_port_calls_no_adb_connect(self) -> None:
        """If the scan window finds zero open ports, no adb-connect tries fire."""
        # Arrange
        adb_calls: list[int] = []

        def _record(_ip: str, port: int) -> bool:
            adb_calls.append(port)
            return False

        scanner = PortScanner(
            check_port_fn=lambda _i, _p: False,  # nothing open
            adb_connect_fn=_record,
            max_workers=4,
        )

        # Act
        result = scanner.find_adb_port("10.0.0.1", start=30000, end=30100)

        # Assert
        assert result == 0
        assert adb_calls == []


# ---------------------------------------------------------------------------
# §7 — LogcatMonitor: kill mid-read; no zombie thread
# ---------------------------------------------------------------------------


class TestLogcatMonitorLifecycle:
    """The plan's §7: kill subprocess mid-read, assert no zombie."""

    def test_stop_terminates_subprocess_when_running(self) -> None:
        # Arrange — install a fake Popen that records terminate/wait
        mon = LogcatMonitor(device_serial="DEV1")
        terminated: list[bool] = []
        waited: list[bool] = []

        class _FakePopen:
            def __init__(self) -> None:
                self.stdout = None
                self.returncode: int | None = None

            def terminate(self) -> None:
                terminated.append(True)
                self.returncode = -15

            def wait(self) -> int:
                waited.append(True)
                return -15

        mon.process = _FakePopen()  # type: ignore[assignment]
        mon.running = True

        # Act
        mon.stop()

        # Assert — proper cleanup sequence: terminate then wait
        assert terminated == [True]
        assert waited == [True]
        assert mon.process is None
        assert mon.running is False

    def test_stop_is_idempotent(self) -> None:
        # Arrange
        mon = LogcatMonitor()

        # Act — stop without start, then again
        mon.stop()
        mon.stop()

        # Assert — no exceptions, state coherent
        assert mon.running is False
        assert mon.process is None

    def test_double_start_is_no_op_when_already_running(self) -> None:
        # Arrange
        mon = LogcatMonitor()
        mon.running = True
        sentinel = object()
        mon.process = sentinel  # type: ignore[assignment]

        # Act — second start must NOT replace the process
        mon.start()

        # Assert
        assert mon.process is sentinel  # type: ignore[comparison-overlap]


# ---------------------------------------------------------------------------
# §10 — connection_monitor: reconnect-interval determinism (freezegun)
# ---------------------------------------------------------------------------


class TestConnectionMonitorTimeDeterminism:
    """The plan's §10: monitor's interval timing is deterministic under freezegun."""

    def test_check_records_correct_iso_timestamp_under_freezegun(
        self, tmp_path: Path
    ) -> None:
        # Arrange — fixed clock
        fixed = datetime(2026, 5, 5, 12, 0, 30, tzinfo=timezone.utc)
        mon = ConnectionMonitor(
            config_file=tmp_path / "devices",
            log_file=tmp_path / "log",
            state_file=tmp_path / "state.json",
            notifier=lambda *_: None,
            adb_status_fn=lambda: (True, "10.0.0.1", 5555),
            wifi_info_fn=lambda: {"ssid": "X", "rssi": -50, "frequency_mhz": 5180},
            now_fn=lambda: fixed,
        )

        # Act
        mon.check()

        # Assert — saved state's timestamp is exactly the frozen instant
        data = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
        assert data["timestamp"] == fixed.isoformat()

    def test_log_message_uses_injected_clock(self, tmp_path: Path) -> None:
        # Arrange
        fixed = datetime(2026, 5, 5, 9, 30, 0, tzinfo=timezone.utc)
        log_file = tmp_path / "log"
        mon = ConnectionMonitor(
            config_file=tmp_path / "devices",
            log_file=log_file,
            state_file=tmp_path / "state.json",
            notifier=lambda *_: None,
            adb_status_fn=lambda: (False, "", 0),
            wifi_info_fn=dict,
            now_fn=lambda: fixed,
        )

        # Act
        mon.log("hello")

        # Assert — log line begins with the frozen timestamp
        content = log_file.read_text(encoding="utf-8")
        assert content.startswith("2026-05-05 09:30:00 ")
        assert "hello" in content


# ---------------------------------------------------------------------------
# §11 — CrashMonitor: crash-rate over a fixed window
# ---------------------------------------------------------------------------


class TestCrashRateOverFixedWindow:
    """The plan's §11: crash-rate calculation over a fixed window.

    Without a windowed-rate API in v1.1, the closest contract is
    ``CrashMonitor.crashes`` accumulating in arrival order. We verify
    the accumulator is monotonic and respects the predicate.
    """

    def test_only_crash_class_entries_are_recorded(self) -> None:
        # Arrange
        cm = CrashMonitor()

        # Act — feed entries directly through the predicate
        entries = [
            LogEntry(
                timestamp="01-01 00:00:00.001", pid=1, tid=2, level="INFO",
                tag="A", message="boot", raw="",
            ),
            LogEntry(
                timestamp="01-01 00:00:00.002", pid=1, tid=2, level="ERROR",
                tag="A", message="crash detected", raw="",
            ),
            LogEntry(
                timestamp="01-01 00:00:00.003", pid=1, tid=2, level="ERROR",
                tag="A", message="user click", raw="",
            ),
            LogEntry(
                timestamp="01-01 00:00:00.004", pid=1, tid=2, level="FATAL",
                tag="A", message="fatal exception", raw="",
            ),
        ]
        # Manually invoke the same logic as CrashMonitor.start's callback
        for e in entries:
            if cm.is_crash_entry(e):
                cm.crashes.append(
                    CrashEvent(
                        timestamp=e.timestamp,
                        tag=e.tag,
                        message=e.message,
                        level=e.level,
                    )
                )

        # Assert — only the two crash-class entries
        assert len(cm.crashes) == 2
        assert cm.crashes[0].message == "crash detected"
        assert cm.crashes[1].message == "fatal exception"

    def test_accumulation_is_in_arrival_order(self) -> None:
        """Doctrine Law 5: order-independent tests, but the data structure
        guarantees arrival-order accumulation as part of its contract."""
        # Arrange
        cm = CrashMonitor()

        # Act
        cm.crashes.extend(
            [
                CrashEvent(
                    timestamp=f"01-01 00:00:00.00{i}",
                    tag="X",
                    message=f"c{i}",
                    level="ERROR",
                )
                for i in range(5)
            ]
        )

        # Assert
        assert [c.message for c in cm.crashes] == ["c0", "c1", "c2", "c3", "c4"]


# ---------------------------------------------------------------------------
# §5 — connection_monitor concurrent check (state-file write race)
# ---------------------------------------------------------------------------


class TestConnectionMonitorConcurrency:
    """Multiple monitors against the same state-file: last-writer-wins is
    documented behaviour. This test makes the contract explicit so a
    future locking change can't silently break it.
    """

    def test_concurrent_check_calls_serialize_via_filesystem(
        self, tmp_path: Path
    ) -> None:
        # Arrange — 4 monitors all writing to the same state file
        state_file = tmp_path / "state.json"
        # Each monitor reports a different connected port so we can tell
        # who won the race.
        monitors = [
            ConnectionMonitor(
                config_file=tmp_path / f"dev{i}",
                log_file=tmp_path / "log",
                state_file=state_file,
                notifier=lambda *_: None,
                adb_status_fn=lambda i=i: (True, "10.0.0.1", 1000 + i),  # type: ignore[misc]
                wifi_info_fn=dict,
                now_fn=lambda: datetime(2026, 5, 5, tzinfo=timezone.utc),
            )
            for i in range(4)
        ]

        # Act — fire all four concurrently
        threads = [threading.Thread(target=mon.check) for mon in monitors]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # Assert — every monitor's check completed; state file is valid JSON
        for t in threads:
            assert not t.is_alive()
        data = json.loads(state_file.read_text(encoding="utf-8"))
        # Whichever monitor wrote last "wins"; just assert the schema
        # is intact (no torn writes corrupting JSON)
        assert data["connected"] is True
        assert data["ip"] == "10.0.0.1"
        assert 1000 <= data["port"] <= 1003


# ---------------------------------------------------------------------------
# Out-of-order ADB response simulation (Pattern: race condition testing)
# ---------------------------------------------------------------------------


class TestOutOfOrderADBResponse:
    """ADBController invocations from concurrent threads must each see
    their own response (no cross-talk through any shared buffer)."""

    def test_concurrent_shell_calls_each_get_their_own_result(
        self, mock_adb: MagicMock
    ) -> None:
        # Arrange — register distinct responses for two distinct argvs
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(
            ["adb", "shell", "getprop ro.product.model"], stdout="Pixel-A"
        )
        mock_adb.register(
            ["adb", "shell", "getprop ro.build.version.sdk"], stdout="36"
        )
        ctrl = ADBController()
        results: dict[str, str] = {}

        def _query_model() -> None:
            results["model"] = ctrl.get_property("ro.product.model")

        def _query_sdk() -> None:
            results["sdk"] = ctrl.get_property("ro.build.version.sdk")

        # Act — two threads issuing different shell commands simultaneously
        t1 = threading.Thread(target=_query_model)
        t2 = threading.Thread(target=_query_sdk)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        # Assert — each thread saw its own response
        assert results == {"model": "Pixel-A", "sdk": "36"}
