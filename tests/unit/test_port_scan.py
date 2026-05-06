"""Unit tests for :mod:`adb_android_control.port_scan`.

Doctrine: AAA (Law 3); pure-function tests for ``rewrite_devices_config``;
DI'd ``check_port_fn`` / ``adb_connect_fn`` for ``PortScanner`` (Laws 5/6).
No real network, no real subprocess.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from adb_android_control.port_scan import (
    PortScanner,
    read_last_port,
    rewrite_devices_config,
    save_last_port,
    update_devices_file,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# rewrite_devices_config — pure
# ---------------------------------------------------------------------------


class TestRewriteDevicesConfig:
    def test_updates_named_entry_in_place(self) -> None:
        # Arrange
        content = "ZFOLD7=10.0.0.1:5555\nOTHER=192.168.1.5:5555\n"

        # Act
        result = rewrite_devices_config(content, name="ZFOLD7", ip="10.0.0.2", port=42891)

        # Assert
        assert "ZFOLD7=10.0.0.2:42891" in result
        assert "OTHER=192.168.1.5:5555" in result  # unchanged

    def test_preserves_comment_lines(self) -> None:
        # Arrange
        content = "# my devices\nZFOLD7=10.0.0.1:5555\n# end\n"

        # Act
        result = rewrite_devices_config(content, name="ZFOLD7", ip="10.0.0.1", port=9999)

        # Assert
        assert "# my devices" in result
        assert "# end" in result
        assert "ZFOLD7=10.0.0.1:9999" in result

    def test_no_change_when_name_absent(self) -> None:
        # Arrange
        content = "OTHER=10.0.0.1:5555\n"

        # Act
        result = rewrite_devices_config(content, name="ZFOLD7", ip="10.0.0.1", port=9999)

        # Assert — same content, just round-tripped through split/join
        assert result.strip() == content.strip()

    def test_empty_input_returns_empty(self) -> None:
        # Arrange + Act
        result = rewrite_devices_config("", name="X", ip="y", port=1)

        # Assert
        assert result == ""


# ---------------------------------------------------------------------------
# update_devices_file / save_last_port / read_last_port
# ---------------------------------------------------------------------------


class TestFilesystemHelpers:
    def test_update_devices_file_no_op_when_missing(self, tmp_path: Path) -> None:
        # Arrange
        config = tmp_path / "missing"

        # Act — must NOT raise
        update_devices_file(config, name="X", ip="1.2.3.4", port=42)

        # Assert
        assert not config.exists()

    def test_update_devices_file_writes_back(self, tmp_path: Path) -> None:
        # Arrange
        config = tmp_path / "devices"
        config.write_text("MYDEV=1.2.3.4:5555\n", encoding="utf-8")

        # Act
        update_devices_file(config, name="MYDEV", ip="5.6.7.8", port=9999)

        # Assert
        assert "MYDEV=5.6.7.8:9999" in config.read_text(encoding="utf-8")

    def test_save_and_read_last_port_round_trip(self, tmp_path: Path) -> None:
        # Arrange
        state = tmp_path / "last"

        # Act
        save_last_port(state, 42891)
        recovered = read_last_port(state)

        # Assert
        assert recovered == 42891

    def test_read_last_port_returns_none_when_missing(self, tmp_path: Path) -> None:
        # Arrange + Act + Assert
        assert read_last_port(tmp_path / "nope") is None

    def test_read_last_port_returns_none_for_garbage(self, tmp_path: Path) -> None:
        # Arrange
        state = tmp_path / "last"
        state.write_text("not a port", encoding="utf-8")

        # Act + Assert — internal lesson (adaptive fault tolerance) graceful degradation
        assert read_last_port(state) is None


# ---------------------------------------------------------------------------
# PortScanner — DI'd probes
# ---------------------------------------------------------------------------


class TestPortScannerFindOpen:
    def _build_scanner(
        self,
        *,
        open_ports: set[int] | None = None,
        adb_ports: set[int] | None = None,
    ) -> PortScanner:
        opens = open_ports or set()
        adbs = adb_ports or set()
        return PortScanner(
            check_port_fn=lambda _ip, p: p in opens,
            adb_connect_fn=lambda _ip, p: p in adbs,
            max_workers=4,
        )

    def test_returns_only_open_ports_sorted(self) -> None:
        # Arrange
        scanner = self._build_scanner(open_ports={5557, 5555, 5556})

        # Act
        result = scanner.find_open_ports("10.0.0.1", start=5550, end=5560)

        # Assert
        assert result == [5555, 5556, 5557]

    def test_returns_empty_when_start_greater_than_end(self) -> None:
        # Arrange
        scanner = self._build_scanner(open_ports={5555})

        # Act
        result = scanner.find_open_ports("10.0.0.1", start=6000, end=5000)

        # Assert
        assert result == []

    def test_returns_empty_when_no_ports_open(self) -> None:
        # Arrange
        scanner = self._build_scanner(open_ports=set())

        # Act
        result = scanner.find_open_ports("10.0.0.1", start=5550, end=5560)

        # Assert
        assert result == []


class TestPortScannerFindAdbPort:
    def test_returns_first_adb_compatible_open_port(self) -> None:
        # Arrange — ports 5555, 5556 open; only 5556 actually speaks ADB
        scanner = PortScanner(
            check_port_fn=lambda _ip, p: p in {5555, 5556},
            adb_connect_fn=lambda _ip, p: p == 5556,
            max_workers=4,
        )

        # Act
        result = scanner.find_adb_port("10.0.0.1", start=5550, end=5560)

        # Assert
        assert result == 5556

    def test_returns_zero_when_no_open_port_speaks_adb(self) -> None:
        # Arrange
        scanner = PortScanner(
            check_port_fn=lambda _ip, p: p in {5555, 5556},
            adb_connect_fn=lambda _ip, _p: False,
            max_workers=4,
        )

        # Act
        result = scanner.find_adb_port("10.0.0.1", start=5550, end=5560)

        # Assert
        assert result == 0

    def test_returns_zero_when_no_ports_open(self) -> None:
        # Arrange
        adb_called: list[int] = []

        def _adb_connect(_ip: str, port: int) -> bool:
            adb_called.append(port)
            return True

        scanner = PortScanner(
            check_port_fn=lambda _ip, _p: False,
            adb_connect_fn=_adb_connect,
            max_workers=4,
        )

        # Act
        result = scanner.find_adb_port("10.0.0.1", start=5550, end=5560)

        # Assert
        assert result == 0
        # ADB-connect must NOT be invoked when no ports are open
        assert adb_called == []
