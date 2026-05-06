"""
Smoke tests for the test harness itself.

Per the Master Tester Doctrine: the test harness is part of the test
contract. If the Poison-Pill mock or the fixtures don't behave the way
the doctrine requires, every downstream test is suspect. So we test
the harness explicitly.

Each test follows AAA (Doctrine Law 3).
"""

from __future__ import annotations

import subprocess

import pytest

from tests.conftest import PoisonPillADB, UnmockedADBCallError

pytestmark = pytest.mark.unit


class TestPoisonPillADB:
    """The Poison-Pill subprocess mock (Doctrine Law 6 + Pattern)."""

    def test_registered_argv_returns_configured_result(self) -> None:
        # Arrange
        pill = PoisonPillADB()
        pill.register(["adb", "devices"], stdout="List of devices attached\n")

        # Act
        result = pill(["adb", "devices"])

        # Assert
        assert result.stdout == "List of devices attached\n"
        assert result.returncode == 0

    def test_unregistered_argv_raises_with_actionable_message(self) -> None:
        # Arrange
        pill = PoisonPillADB()
        pill.register(["adb", "devices"], stdout="ok\n")

        # Act + Assert
        with pytest.raises(UnmockedADBCallError) as excinfo:
            pill(["adb", "shell", "ls"])
        msg = str(excinfo.value)
        assert "adb" in msg and "shell" in msg and "ls" in msg, (
            "Error message must include the actual argv attempted, so the "
            "test author can register the missing mock without reading the "
            "code."
        )
        assert "register" in msg, "Message must hint at the fix."

    def test_call_log_records_in_order(self) -> None:
        # Arrange
        pill = PoisonPillADB()
        pill.register(["adb", "version"], stdout="v1\n")
        pill.register(["adb", "devices"], stdout="\n")

        # Act
        pill(["adb", "version"])
        pill(["adb", "devices"])
        pill(["adb", "version"])

        # Assert
        assert pill.call_log() == [
            ("adb", "version"),
            ("adb", "devices"),
            ("adb", "version"),
        ]

    def test_distinct_argvs_register_independently(self) -> None:
        # Arrange
        pill = PoisonPillADB()
        pill.register(["adb", "shell", "echo", "hi"], stdout="hi\n")
        pill.register(["adb", "shell", "echo", "bye"], stdout="bye\n")

        # Act
        a = pill(["adb", "shell", "echo", "hi"])
        b = pill(["adb", "shell", "echo", "bye"])

        # Assert — distinct argvs return distinct results
        assert a.stdout == "hi\n"
        assert b.stdout == "bye\n"

    def test_argv_order_matters(self) -> None:
        """Doctrine Law 9: one logical concept — argv equality is order-sensitive."""
        # Arrange
        pill = PoisonPillADB()
        pill.register(["adb", "-s", "device1", "shell", "ls"], stdout="ok\n")

        # Act + Assert
        with pytest.raises(UnmockedADBCallError):
            # Different order = different argv = unmocked
            pill(["adb", "shell", "-s", "device1", "ls"])


class TestMockADBFixture:
    """The pytest fixture that patches subprocess.run."""

    def test_fixture_intercepts_subprocess_run(self, mock_adb: PoisonPillADB) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="Android Debug Bridge v1.0\n")

        # Act
        result = subprocess.run(["adb", "version"])  # type: ignore[call-overload]

        # Assert
        assert result.stdout == "Android Debug Bridge v1.0\n"  # type: ignore[union-attr]

    def test_fixture_resets_between_tests_part_1(self, mock_adb: PoisonPillADB) -> None:
        """Doctrine Law 5 — isolation across tests.

        This test registers a mock; the next test (part_2) should NOT see it.
        """
        # Arrange
        mock_adb.register(["adb", "leak-canary"], stdout="LEAK\n")

        # Act
        result = subprocess.run(["adb", "leak-canary"])  # type: ignore[call-overload]

        # Assert
        assert result.stdout == "LEAK\n"  # type: ignore[union-attr]

    def test_fixture_resets_between_tests_part_2(self, mock_adb: PoisonPillADB) -> None:
        """Verifies the part_1 registration did NOT bleed into this test."""
        # Arrange + Act + Assert
        with pytest.raises(UnmockedADBCallError):
            subprocess.run(["adb", "leak-canary"])  # type: ignore[call-overload]


class TestFakeDevice:
    """Test-data factory fixture (Doctrine Pattern: factories)."""

    def test_default_has_no_real_pii(self, fake_device) -> None:
        """internal lesson (PII pre-commit gate) enforcement.

        Fake fixtures must never hold real values.
        """
        # Arrange + Act
        d = fake_device

        # Assert — placeholder values only
        assert d.serial.startswith("FAKE_")
        assert d.model.startswith("Pixel-")  # generic test name
        # No real BSSID, IP, SSID anywhere in the dataclass

    def test_factory_overrides_apply(self, fake_device_factory) -> None:
        # Arrange + Act
        low_battery = fake_device_factory(battery_level=3)

        # Assert
        assert low_battery.battery_level == 3
        assert low_battery.serial == "FAKE_SERIAL_0001"  # default preserved


class TestFrozenClock:
    """Time determinism (Doctrine Law 8)."""

    def test_time_is_pinned(self, frozen_clock) -> None:
        # Arrange + Act
        from datetime import datetime, timezone

        now = datetime.now(tz=timezone.utc)

        # Assert
        assert now.year == 2026
        assert now.month == 5
        assert now.day == 5
