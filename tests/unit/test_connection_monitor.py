"""Unit tests for :mod:`adb_android_control.connection_monitor`.

Doctrine: AAA (Law 3), pure-function tests where possible (Law 9), full
DI (Law 5 + 6 — no real subprocess/clock/filesystem outside ``tmp_path``).

Race-condition + property-based coverage lands in Phase 3.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from adb_android_control.connection_monitor import (
    Change,
    ChangeType,
    ConnectionMonitor,
    ConnectionState,
    detect_changes,
    parse_adb_devices,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _state(**overrides: Any) -> ConnectionState:
    """Build a ConnectionState with sensible defaults; tests override fields."""
    base = {
        "timestamp": "2026-05-05T00:00:00+00:00",
        "connected": True,
        "ip": "10.0.0.1",
        "port": 5555,
        "ssid": "TestNet",
        "rssi_dbm": -55,
        "frequency_mhz": 5180,
    }
    base.update(overrides)
    return ConnectionState(**base)


@pytest.fixture
def fixed_clock() -> datetime:
    """A fixed UTC instant returned by all `now_fn` calls in fixtures below."""
    return datetime(2026, 5, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def monitor_factory(
    tmp_path: Path,
    fixed_clock: datetime,
) -> Any:
    """Factory: build a ConnectionMonitor with all I/O wired to tmp / fakes."""

    def _factory(
        *,
        adb_status: tuple[bool, str, int] = (True, "10.0.0.1", 5555),
        wifi: dict[str, Any] | None = None,
        seed_state: ConnectionState | None = None,
    ) -> ConnectionMonitor:
        wifi = wifi if wifi is not None else {
            "ssid": "TestNet",
            "rssi": -55,
            "frequency_mhz": 5180,
        }
        state_file = tmp_path / "state.json"
        if seed_state is not None:
            state_file.write_text(
                json.dumps(
                    {
                        "timestamp": seed_state.timestamp,
                        "connected": seed_state.connected,
                        "ip": seed_state.ip,
                        "port": seed_state.port,
                        "ssid": seed_state.ssid,
                        "rssi_dbm": seed_state.rssi_dbm,
                        "frequency_mhz": seed_state.frequency_mhz,
                    }
                ),
                encoding="utf-8",
            )

        notifier_calls: list[tuple[str, str]] = []

        def _notifier(title: str, msg: str) -> None:
            notifier_calls.append((title, msg))

        mon = ConnectionMonitor(
            config_file=tmp_path / "devices",
            log_file=tmp_path / "monitor.log",
            state_file=state_file,
            notifier=_notifier,
            adb_status_fn=lambda: adb_status,
            wifi_info_fn=lambda: wifi,
            now_fn=lambda: fixed_clock,
        )
        # Attach the recorder so tests can introspect notifier calls
        mon.notifier_calls = notifier_calls  # type: ignore[attr-defined]
        return mon

    return _factory


# ---------------------------------------------------------------------------
# parse_adb_devices — pure function
# ---------------------------------------------------------------------------


class TestParseAdbDevices:
    def test_parses_connected_device_with_port(self) -> None:
        # Arrange
        output = "List of devices attached\n10.0.0.1:5555\tdevice\n"

        # Act
        result = parse_adb_devices(output)

        # Assert
        assert result == (True, "10.0.0.1", 5555)

    def test_parses_connected_ipv4_with_high_port(self) -> None:
        # Arrange
        output = "List of devices attached\n192.168.1.50:42891\tdevice\n"

        # Act
        result = parse_adb_devices(output)

        # Assert
        assert result == (True, "192.168.1.50", 42891)

    def test_returns_disconnected_when_no_device_line(self) -> None:
        # Arrange
        output = "List of devices attached\n\n"

        # Act
        result = parse_adb_devices(output)

        # Assert
        assert result == (False, "", 0)

    def test_skips_non_ip_serial_devices(self) -> None:
        # Arrange — USB-attached device has no host:port form
        output = "List of devices attached\nABCDEF1234567890\tdevice\n"

        # Act
        result = parse_adb_devices(output)

        # Assert — USB devices not currently supported by this parser
        assert result == (False, "", 0)

    def test_skips_offline_devices(self) -> None:
        # Arrange
        output = (
            "List of devices attached\n"
            "10.0.0.1:5555\toffline\n"
            "10.0.0.2:5555\tdevice\n"
        )

        # Act
        result = parse_adb_devices(output)

        # Assert — picks the first `\tdevice` entry
        assert result == (True, "10.0.0.2", 5555)

    def test_garbage_port_is_skipped(self) -> None:
        # Arrange
        output = "List of devices attached\n10.0.0.1:notaport\tdevice\n"

        # Act
        result = parse_adb_devices(output)

        # Assert
        assert result == (False, "", 0)


# ---------------------------------------------------------------------------
# detect_changes — pure logic
# ---------------------------------------------------------------------------


class TestDetectChanges:
    def test_first_state_with_connection_emits_connected(self) -> None:
        # Arrange + Act
        changes = detect_changes(None, _state(connected=True))

        # Assert
        assert len(changes) == 1
        assert changes[0].kind == ChangeType.CONNECTED
        assert "10.0.0.1:5555" in changes[0].detail

    def test_first_state_disconnected_emits_nothing(self) -> None:
        # Arrange + Act
        changes = detect_changes(None, _state(connected=False, ip="", port=0))

        # Assert
        assert changes == []

    def test_disconnect_transition(self) -> None:
        # Arrange
        last = _state(connected=True)
        current = _state(connected=False, ip="", port=0)

        # Act
        changes = detect_changes(last, current)

        # Assert
        kinds = [c.kind for c in changes]
        assert ChangeType.DISCONNECTED in kinds

    def test_reconnect_transition(self) -> None:
        # Arrange
        last = _state(connected=False, ip="", port=0)
        current = _state(connected=True, ip="10.0.0.1", port=5555)

        # Act
        changes = detect_changes(last, current)

        # Assert
        assert any(c.kind == ChangeType.CONNECTED for c in changes)

    def test_port_change_while_connected(self) -> None:
        # Arrange
        last = _state(port=5555)
        current = _state(port=42891)

        # Act
        changes = detect_changes(last, current)

        # Assert
        kinds = [c.kind for c in changes]
        assert ChangeType.PORT_CHANGED in kinds
        port_change = next(c for c in changes if c.kind == ChangeType.PORT_CHANGED)
        assert "5555 → 42891" in port_change.detail

    def test_network_switch_while_connected(self) -> None:
        # Arrange
        last = _state(ip="10.0.0.1", port=5555)
        current = _state(ip="192.168.1.5", port=5555)

        # Act
        changes = detect_changes(last, current)

        # Assert
        kinds = [c.kind for c in changes]
        assert ChangeType.NETWORK_CHANGED in kinds

    def test_ssid_change(self) -> None:
        # Arrange
        last = _state(ssid="HomeNet")
        current = _state(ssid="OfficeNet")

        # Act
        changes = detect_changes(last, current)

        # Assert
        kinds = [c.kind for c in changes]
        assert ChangeType.WIFI_CHANGED in kinds

    def test_ssid_change_to_unknown_is_suppressed(self) -> None:
        """Avoid noisy notifications when WiFi info briefly unavailable."""
        # Arrange
        last = _state(ssid="HomeNet")
        current = _state(ssid="Unknown")

        # Act
        changes = detect_changes(last, current)

        # Assert
        kinds = [c.kind for c in changes]
        assert ChangeType.WIFI_CHANGED not in kinds

    def test_signal_change_above_threshold_emits(self) -> None:
        # Arrange — 15 dB delta > 10 dB threshold
        last = _state(rssi_dbm=-50)
        current = _state(rssi_dbm=-65)

        # Act
        changes = detect_changes(last, current)

        # Assert
        kinds = [c.kind for c in changes]
        assert ChangeType.SIGNAL_CHANGED in kinds

    def test_signal_change_below_threshold_suppressed(self) -> None:
        # Arrange — 5 dB delta < 10 dB threshold
        last = _state(rssi_dbm=-50)
        current = _state(rssi_dbm=-55)

        # Act
        changes = detect_changes(last, current)

        # Assert — only signal-change suppression matters here
        kinds = [c.kind for c in changes]
        assert ChangeType.SIGNAL_CHANGED not in kinds

    def test_custom_signal_threshold_overrides_default(self) -> None:
        # Arrange
        last = _state(rssi_dbm=-50)
        current = _state(rssi_dbm=-55)  # 5 dB delta

        # Act — with threshold=3, 5 dB is now significant
        changes = detect_changes(last, current, signal_threshold_db=3)

        # Assert
        kinds = [c.kind for c in changes]
        assert ChangeType.SIGNAL_CHANGED in kinds

    def test_no_changes_when_states_equivalent(self) -> None:
        # Arrange
        last = _state()
        current = _state()  # identical

        # Act
        changes = detect_changes(last, current)

        # Assert
        assert changes == []


# ---------------------------------------------------------------------------
# ConnectionMonitor — DI'd I/O
# ---------------------------------------------------------------------------


class TestConnectionMonitorPersistence:
    def test_initial_load_with_no_state_file(self, monitor_factory: Any) -> None:
        # Arrange + Act
        mon = monitor_factory()

        # Assert
        assert mon.last_state is None

    def test_loads_seed_state_from_file(self, monitor_factory: Any) -> None:
        # Arrange
        seed = _state(ip="10.0.0.99", port=12345)

        # Act
        mon = monitor_factory(seed_state=seed)

        # Assert
        assert mon.last_state is not None
        assert mon.last_state.ip == "10.0.0.99"
        assert mon.last_state.port == 12345

    def test_corrupt_state_file_yields_none(
        self, tmp_path: Path, monitor_factory: Any
    ) -> None:
        # Arrange — write garbage that isn't JSON
        state_file = tmp_path / "state.json"
        state_file.write_text("not json", encoding="utf-8")

        # Act
        mon = ConnectionMonitor(
            config_file=tmp_path / "devices",
            log_file=tmp_path / "log",
            state_file=state_file,
            notifier=lambda *_a, **_k: None,
            adb_status_fn=lambda: (False, "", 0),
            wifi_info_fn=dict,
        )

        # Assert — internal lesson (adaptive fault tolerance): don't crash on bad state, start fresh
        assert mon.last_state is None

    def test_save_state_round_trips(
        self, tmp_path: Path, monitor_factory: Any
    ) -> None:
        # Arrange
        mon = monitor_factory()
        state = _state(ip="10.5.5.5", port=6666)

        # Act
        mon.save_state(state)

        # Assert
        data = json.loads(mon.state_file.read_text(encoding="utf-8"))
        assert data["ip"] == "10.5.5.5"
        assert data["port"] == 6666


class TestConnectionMonitorCheck:
    def test_first_check_emits_connected_change_and_notifies(
        self, monitor_factory: Any
    ) -> None:
        # Arrange — no prior state, currently connected
        mon = monitor_factory(adb_status=(True, "10.0.0.1", 5555))

        # Act
        changes = mon.check()

        # Assert
        assert any(c.kind == ChangeType.CONNECTED for c in changes)
        # Connected (first transition) is NOT in _NOTIFY_ON_KINDS — so no
        # user notification (we only notify on disruptions, not first
        # connect)
        assert mon.notifier_calls == []  # type: ignore[attr-defined]

    def test_disconnect_triggers_notifier(self, monitor_factory: Any) -> None:
        # Arrange — last state was connected; now offline
        mon = monitor_factory(
            adb_status=(False, "", 0),
            seed_state=_state(connected=True),
        )

        # Act
        mon.check()

        # Assert
        assert any(
            "DISCONNECTED" in msg
            for _title, msg in mon.notifier_calls  # type: ignore[attr-defined]
        )

    def test_port_change_triggers_config_update(
        self, tmp_path: Path, monitor_factory: Any
    ) -> None:
        # Arrange
        config = tmp_path / "devices"
        config.write_text("MYDEV=10.0.0.1:5555\n", encoding="utf-8")
        mon = monitor_factory(
            adb_status=(True, "10.0.0.1", 42891),
            seed_state=_state(connected=True, port=5555),
        )
        mon.config_file = config

        # Act
        mon.check()

        # Assert
        assert "MYDEV=10.0.0.1:42891" in config.read_text(encoding="utf-8")

    def test_no_changes_with_steady_state(self, monitor_factory: Any) -> None:
        # Arrange — last state matches current
        steady = _state(connected=True, ip="10.0.0.1", port=5555)
        mon = monitor_factory(seed_state=steady)

        # Act
        changes = mon.check()

        # Assert
        assert changes == []
        assert mon.notifier_calls == []  # type: ignore[attr-defined]


class TestConnectionMonitorConfigUpdate:
    def test_no_op_when_config_file_missing(
        self, tmp_path: Path, monitor_factory: Any
    ) -> None:
        # Arrange
        mon = monitor_factory()
        mon.config_file = tmp_path / "doesnt_exist"

        # Act — should NOT raise
        mon.update_config("10.0.0.1", 5555)

        # Assert — silently no-op
        assert not mon.config_file.exists()

    def test_updates_only_matching_ip_lines(
        self, tmp_path: Path, monitor_factory: Any
    ) -> None:
        # Arrange
        config = tmp_path / "devices"
        config.write_text(
            "DEV1=10.0.0.1:5555\n"
            "DEV2=10.0.0.2:5555\n"
            "# comment line\n"
            "DEV3=10.0.0.1:9999\n",
            encoding="utf-8",
        )
        mon = monitor_factory()
        mon.config_file = config

        # Act
        mon.update_config("10.0.0.1", 7777)

        # Assert
        result = config.read_text(encoding="utf-8")
        assert "DEV1=10.0.0.1:7777" in result
        assert "DEV2=10.0.0.2:5555" in result  # unchanged (different IP)
        assert "# comment line" in result  # comments preserved
        assert "DEV3=10.0.0.1:7777" in result  # both 10.0.0.1 lines updated


# ---------------------------------------------------------------------------
# Value object frozen contract
# ---------------------------------------------------------------------------


class TestValueObjects:
    def test_connection_state_is_frozen(self) -> None:
        # Arrange + Act + Assert
        s = _state()
        with pytest.raises(Exception):  # noqa: B017
            s.connected = False  # type: ignore[misc]

    def test_change_is_frozen(self) -> None:
        # Arrange + Act + Assert
        c = Change(ChangeType.CONNECTED, "x")
        with pytest.raises(Exception):  # noqa: B017
            c.detail = "y"  # type: ignore[misc]

    def test_change_type_enum_values_are_stable(self) -> None:
        """The wire-format value of each ChangeType is part of the contract.

        Doctrine Law 2: serialised values are public API. Renaming them
        breaks downstream log-watchers.
        """
        # Arrange + Act + Assert
        assert ChangeType.CONNECTED.value == "CONNECTED"
        assert ChangeType.DISCONNECTED.value == "DISCONNECTED"
        assert ChangeType.PORT_CHANGED.value == "PORT_CHANGED"
        assert ChangeType.NETWORK_CHANGED.value == "NETWORK_CHANGED"
        assert ChangeType.WIFI_CHANGED.value == "WIFI_CHANGED"
        assert ChangeType.SIGNAL_CHANGED.value == "SIGNAL_CHANGED"
