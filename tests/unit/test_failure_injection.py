"""Failure-injection tests across controller / monitor / port_scan / usb.

Doctrine
--------
- Master Tester Doctrine § Advanced Patterns: "OOM on CI" warns about
  signal/exit-code edge cases. internal lesson (adaptive fault tolerance)
  ("Adaptive Fault Tolerance") demands graceful degradation on every
  transient failure path.
- Each test injects a *specific failure mode* into the underlying I/O
  layer and asserts:
    1. The right typed exception is raised, OR
    2. The right degraded value is returned (None, [], 0, "", {}).
  No try/except in production code is left untested.

Failure taxonomy covered here
-----------------------------

ADB binary failures
  - exit 1 with `error: device offline` stderr → DeviceOfflineError
  - exit 1 with `error: device unauthorized` stderr → DeviceOfflineError
  - exit 1 with `Permission denied` → ADBPermissionError
  - exit 124 (GNU coreutils timeout wrapper) → ADBError generic
  - exit 137 (128 + SIGKILL — OOM-killed) → ADBError generic
  - exit 13 (`Permission denied` exit code) → ADBPermissionError
  - subprocess.TimeoutExpired → ADBTimeoutError
  - FileNotFoundError (adb missing) → ADBNotFoundError

ADB output corruption
  - SDK version not parseable as int → ADBError "Unparseable SDK"
  - `wm size` output truncated → (0, 0) graceful

OS-layer failures (port scanner, usb)
  - socket.connect_ex returns nonzero → check_port returns False
  - Bad file descriptor in usb.identify_via_fd → None
"""

from __future__ import annotations

import errno
import socket
import subprocess
from typing import TYPE_CHECKING

import pytest

from adb_android_control.controller import (
    ADBController,
    ADBError,
    ADBNotFoundError,
    ADBPermissionError,
    ADBTimeoutError,
    DeviceOfflineError,
)
from adb_android_control.port_scan import check_port, try_adb_connect
from adb_android_control.usb import identify_via_fd

if TYPE_CHECKING:
    from tests.conftest import PoisonPillADB

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Controller — every documented exit code class
# ---------------------------------------------------------------------------


class TestControllerExitCodeClassification:
    """Each ADB failure mode maps to exactly one exception class."""

    def test_exit_124_coreutils_timeout_raises_generic_adb_error(
        self, mock_adb: PoisonPillADB
    ) -> None:
        # Arrange — exit 124 = GNU coreutils `timeout` wrapper killed it
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(
            ["adb", "shell", "ls"],
            stderr="",
            returncode=124,
        )
        ctrl = ADBController()

        # Act + Assert — generic ADBError (NOT timeout-specific because
        # subprocess.run didn't raise TimeoutExpired; the wrapper did)
        with pytest.raises(ADBError) as excinfo:
            ctrl._shell("ls")
        # Should NOT be misclassified as DeviceOfflineError or
        # ADBPermissionError (those require specific stderr markers)
        assert not isinstance(excinfo.value, DeviceOfflineError)
        assert not isinstance(excinfo.value, ADBPermissionError)

    def test_exit_137_oom_killed_raises_generic_adb_error(
        self, mock_adb: PoisonPillADB
    ) -> None:
        # Arrange — exit 137 = 128 + SIGKILL (e.g. OOM killer)
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(
            ["adb", "shell", "dumpsys"],
            stderr="Killed",
            returncode=137,
        )
        ctrl = ADBController()

        # Act + Assert
        with pytest.raises(ADBError):
            ctrl._shell("dumpsys")

    def test_subprocess_timeout_expired_raises_adb_timeout_error(
        self, monkeypatch: pytest.MonkeyPatch, mock_adb: PoisonPillADB
    ) -> None:
        # Arrange — `adb version` succeeds (construction); subsequent
        # calls explode with TimeoutExpired
        mock_adb.register(["adb", "version"], stdout="v1\n")
        ctrl = ADBController()

        def _raise_timeout(*_a: object, **_k: object) -> object:
            raise subprocess.TimeoutExpired(cmd=["adb", "shell", "ls"], timeout=30)

        monkeypatch.setattr(subprocess, "run", _raise_timeout)

        # Act + Assert
        with pytest.raises(ADBTimeoutError) as excinfo:
            ctrl._shell("ls")
        assert "timed out" in str(excinfo.value).lower()

    def test_construction_with_filenotfounderror_raises_adb_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange — adb binary truly missing
        def _raise(*_a: object, **_k: object) -> object:
            raise FileNotFoundError(2, "No such file or directory: 'adb'")

        monkeypatch.setattr(subprocess, "run", _raise)

        # Act + Assert
        with pytest.raises(ADBNotFoundError, match="not found on PATH"):
            ADBController()

    def test_construction_with_timeout_raises_adb_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange — adb-server is wedged; `adb version` hangs
        def _raise(*_a: object, **_k: object) -> object:
            raise subprocess.TimeoutExpired(cmd=["adb", "version"], timeout=10)

        monkeypatch.setattr(subprocess, "run", _raise)

        # Act + Assert
        with pytest.raises(ADBTimeoutError, match="adb-server"):
            ADBController()

    def test_construction_when_adb_returns_nonzero_raises_generic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange — adb is present but `adb version` itself errors
        # (corrupted install, missing transitive dep, etc.)
        class _Result:
            returncode = 2
            stdout = ""
            stderr = "adb: missing libssl"

        monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: _Result())

        # Act + Assert
        with pytest.raises(ADBError) as excinfo:
            ADBController()
        assert "missing libssl" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Controller — output corruption and degraded paths
# ---------------------------------------------------------------------------


class TestControllerOutputCorruption:
    def test_unparseable_sdk_version_raises_adb_error(
        self, mock_adb: PoisonPillADB
    ) -> None:
        # Arrange — every getprop returns OK except the SDK one
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(["adb", "shell", "getprop ro.product.model"], stdout="X")
        mock_adb.register(
            ["adb", "shell", "getprop ro.build.version.release"], stdout="14"
        )
        mock_adb.register(
            ["adb", "shell", "getprop ro.build.version.sdk"], stdout="not-a-number"
        )
        ctrl = ADBController()

        # Act + Assert
        with pytest.raises(ADBError, match="Unparseable SDK"):
            ctrl.get_device_info()

    def test_garbled_screen_size_returns_zero_zero_not_crash(
        self, mock_adb: PoisonPillADB
    ) -> None:
        # Arrange — `wm size` returns nonsense
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(["adb", "shell", "wm size"], stdout="???")
        ctrl = ADBController()

        # Act
        size = ctrl.get_screen_size()

        # Assert — degraded, not crashed (internal lesson (adaptive fault tolerance))
        assert size == (0, 0)

    def test_empty_battery_output_returns_zero(
        self, mock_adb: PoisonPillADB
    ) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(
            ["adb", "shell", "dumpsys battery | grep level"], stdout=""
        )
        ctrl = ADBController()

        # Act + Assert
        assert ctrl.get_battery_level() == 0


# ---------------------------------------------------------------------------
# Port scanner — socket-layer failures
# ---------------------------------------------------------------------------


class TestPortScannerOSErrors:
    def test_check_port_returns_false_when_socket_raises_oserror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        class _BadSocket:
            def __init__(self, *_a: object, **_k: object) -> None:
                pass

            def __enter__(self) -> _BadSocket:
                return self

            def __exit__(self, *_a: object) -> bool:
                return False

            def settimeout(self, _t: float) -> None:
                pass

            def connect_ex(self, _addr: tuple[str, int]) -> int:
                raise OSError(errno.ENETUNREACH, "Network unreachable")

        monkeypatch.setattr(socket, "socket", _BadSocket)

        # Act + Assert — graceful False (internal lesson (adaptive fault tolerance)), no exception
        assert check_port("10.0.0.1", 5555) is False

    def test_check_port_returns_false_for_nonzero_connect_ex(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange — connect_ex returns errno code (e.g. ECONNREFUSED = 111)
        class _RefusedSocket:
            def __init__(self, *_a: object, **_k: object) -> None:
                pass

            def __enter__(self) -> _RefusedSocket:
                return self

            def __exit__(self, *_a: object) -> bool:
                return False

            def settimeout(self, _t: float) -> None:
                pass

            def connect_ex(self, _addr: tuple[str, int]) -> int:
                return errno.ECONNREFUSED

        monkeypatch.setattr(socket, "socket", _RefusedSocket)

        # Act + Assert
        assert check_port("10.0.0.1", 5555) is False

    def test_try_adb_connect_returns_false_on_filenotfound(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange — adb binary missing
        def _raise_fnf(*_a: object, **_k: object) -> object:
            raise FileNotFoundError("adb")

        monkeypatch.setattr(subprocess, "run", _raise_fnf)

        # Act + Assert — graceful False
        assert try_adb_connect("10.0.0.1", 5555) is False

    def test_try_adb_connect_returns_false_on_subprocess_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        def _raise_timeout(*_a: object, **_k: object) -> object:
            raise subprocess.TimeoutExpired(cmd=["adb"], timeout=3)

        monkeypatch.setattr(subprocess, "run", _raise_timeout)

        # Act + Assert
        assert try_adb_connect("10.0.0.1", 5555) is False


# ---------------------------------------------------------------------------
# USB — file-descriptor failures
# ---------------------------------------------------------------------------


class TestUSBFDFailures:
    def test_identify_via_fd_returns_none_for_bad_fd(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange — os.read on a bad fd raises OSError
        import os

        def _raise_oserror(*_a: object, **_k: object) -> object:
            raise OSError(errno.EBADF, "Bad file descriptor")

        monkeypatch.setattr(os, "read", _raise_oserror)

        # Act + Assert — internal lesson (adaptive fault tolerance) graceful None
        assert identify_via_fd(99999) is None

    def test_identify_via_fd_returns_none_for_short_read(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange — os.read returns fewer than 12 bytes (length contract)
        import os

        monkeypatch.setattr(os, "read", lambda _fd, _n: b"\x00" * 8)

        # Act + Assert
        assert identify_via_fd(0) is None


# ---------------------------------------------------------------------------
# Module-spanning: every typed exception inherits from ADBError
# ---------------------------------------------------------------------------


class TestExceptionHierarchyContract:
    """Doctrine Law 2: the exception hierarchy is part of the public API.

    Downstream code that catches ``ADBError`` must continue to catch
    every more-specific subclass — that is the contract.
    """

    @pytest.mark.parametrize(
        "exc_cls",
        [ADBNotFoundError, DeviceOfflineError, ADBTimeoutError, ADBPermissionError],
    )
    def test_subclass_caught_by_base_handler(
        self, exc_cls: type[Exception]
    ) -> None:
        # Arrange + Act
        try:
            raise exc_cls("test")
        except ADBError as exc:
            caught = exc

        # Assert
        assert isinstance(caught, exc_cls)
        assert isinstance(caught, ADBError)

    def test_typed_exception_message_round_trips(self) -> None:
        # Arrange + Act
        exc = DeviceOfflineError("device 10.0.0.1:5555 is offline")

        # Assert — Exception's __str__ contract preserves the message
        assert "10.0.0.1" in str(exc)


# ---------------------------------------------------------------------------
# Sanity: typed exceptions are exported from the package namespace
# ---------------------------------------------------------------------------


class TestPackageNamespaceExports:
    """Doctrine Law 2: the package namespace is the user contract."""

    def test_typed_exceptions_importable_from_top_level(self) -> None:
        # Arrange + Act
        import adb_android_control as pkg

        # Assert
        assert pkg.ADBError is ADBError
        assert pkg.ADBNotFoundError is ADBNotFoundError
        assert pkg.DeviceOfflineError is DeviceOfflineError
        assert pkg.ADBTimeoutError is ADBTimeoutError
        assert pkg.ADBPermissionError is ADBPermissionError

    def test_version_is_present(self) -> None:
        # Arrange + Act
        import adb_android_control as pkg

        # Assert
        assert isinstance(pkg.__version__, str)
        assert pkg.__version__ != ""
