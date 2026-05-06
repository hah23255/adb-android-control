"""Test harness for adb-android-control.

Doctrine: Master Tester Doctrine — Law 5 (isolation), Law 6 (no direct
subprocess mocking — use the Poison-Pill harness below), Law 8
(determinism via freezegun + seeded random).

Every test gets:
  - ``mock_adb``: a Poison-Pill subprocess mock. ANY unregistered
    ``adb …`` argv invocation raises :class:`UnmockedADBCallError` with
    the exact argv the code attempted, surfacing the missing mock
    immediately.
  - ``fake_device``: a deterministic :class:`FakeDevice` fixture.
  - ``frozen_clock``: pytest fixture for
    ``freeze_time("2026-05-05T00:00:00Z")``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
from freezegun import freeze_time

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

# ---------------------------------------------------------------------------
# Poison-Pill subprocess mock (Doctrine Pattern: Poison-Pill Mock)
# ---------------------------------------------------------------------------


class UnmockedADBCallError(AssertionError):
    """Raised when production code shells out to an unregistered argv.

    Catching this in a test means the code is reaching outside its
    expected bounds — either the test forgot to register a handler,
    or the code is doing something the test author didn't anticipate.
    Either way, the test fails loudly and immediately.

    Doctrine Law 6 + Pattern: Poison-Pill Mock.
    """


@dataclass(frozen=True)
class _MockResult:
    """Immutable result for a mocked subprocess call."""

    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


class PoisonPillADB:
    """Strict subprocess mock for ``adb`` invocations.

    Usage in a test::

        def test_battery_level(mock_adb):
            mock_adb.register(
                ["adb", "shell", "dumpsys", "battery"],
                stdout="level: 87\\n",
            )
            ctrl = ADBController()
            assert ctrl.get_battery_level() == 87

        def test_unmocked_call_fails(mock_adb):
            ctrl = ADBController()
            with pytest.raises(UnmockedADBCallError):
                ctrl.do_something_unanticipated()
    """

    def __init__(self) -> None:
        self._registry: dict[tuple[str, ...], _MockResult] = {}
        self._call_log: list[tuple[str, ...]] = []

    def register(
        self,
        argv: list[str],
        *,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
    ) -> None:
        """Register a deterministic response for an exact argv match."""
        self._registry[tuple(argv)] = _MockResult(
            stdout=stdout, stderr=stderr, returncode=returncode
        )

    def call_log(self) -> list[tuple[str, ...]]:
        """Return the ordered argv tuples that were invoked during the test."""
        return list(self._call_log)

    def __call__(
        self, argv: list[str], *_args: object, **_kwargs: object
    ) -> _MockResult:
        """Stand-in for ``subprocess.run``. Fails loud on unregistered argv."""
        key = tuple(argv)
        self._call_log.append(key)
        result = self._registry.get(key)
        if result is None:
            raise UnmockedADBCallError(
                f"Test failed: code shelled out to an unregistered argv.\n"
                f"  argv: {list(argv)!r}\n"
                f"  registered: {[list(k) for k in self._registry]!r}\n"
                f"Add `mock_adb.register(<argv>, stdout=...)` to the test, "
                f"or check why the code is reaching outside its expected bounds."
            )
        return result


@pytest.fixture
def mock_adb(monkeypatch: pytest.MonkeyPatch) -> PoisonPillADB:
    """Poison-Pill subprocess mock. Patches ``subprocess.run`` for the test."""
    import subprocess

    pill = PoisonPillADB()

    def _patched_run(
        argv: list[str], *args: object, **kwargs: object
    ) -> _MockResult:
        return pill(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _patched_run)
    return pill


# ---------------------------------------------------------------------------
# Deterministic time (Doctrine Law 8)
# ---------------------------------------------------------------------------


@pytest.fixture
def frozen_clock() -> Iterator[None]:
    """Pin time to 2026-05-05T00:00:00Z for the duration of the test."""
    with freeze_time("2026-05-05T00:00:00Z"):
        yield


# ---------------------------------------------------------------------------
# Fake device fixture (Doctrine Pattern: Test Data Factory)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FakeDevice:
    """Deterministic fake device — never holds real PII."""

    serial: str = "FAKE_SERIAL_0001"
    model: str = "Pixel-Test"
    android_version: str = "16"
    sdk_version: int = 36
    screen_size: tuple[int, int] = (1080, 2400)
    battery_level: int = 87


@pytest.fixture
def fake_device() -> FakeDevice:
    """Default fake device for tests that don't care about specifics."""
    return FakeDevice()


@pytest.fixture
def fake_device_factory() -> Callable[..., FakeDevice]:
    """Factory for building fake devices with overrides."""

    def _factory(**overrides: Any) -> FakeDevice:
        return FakeDevice(**overrides)

    return _factory


# ---------------------------------------------------------------------------
# Pytest configuration hooks
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip integration/device tests by default. Run with -m integration to opt in."""
    if config.getoption("-m"):
        return

    skip_integration = pytest.mark.skip(reason="needs --markers integration")
    skip_device = pytest.mark.skip(reason="needs --markers device (real device)")

    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
        if "device" in item.keywords:
            item.add_marker(skip_device)
