"""Unit tests for :mod:`adb_android_control.automation`.

Doctrine: AAA (Law 3), no real time/sleep (Law 8 — `_sleep` and `_now`
monkey-patched), no shared state across tests (Law 5), public API
behaviour-only (Law 2).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from adb_android_control import automation
from adb_android_control.automation import (
    ADBAutomation,
    AppTester,
    AutomationResult,
    AutomationStep,
    DeviceManager,
    InstallAndLaunchResult,
    ScreenRecorder,
    StepOutcome,
)
from adb_android_control.controller import ADBController, DeviceInfo, DeviceState

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[float]]:
    """Replace `_sleep` with a recorder and `_now` with a deterministic counter.

    Doctrine Law 8 — determinism: tests using these fixtures never wait
    on real wall-clock and can assert exact elapsed durations.
    """
    sleep_log: list[float] = []
    counter = iter(range(0, 1_000_000))

    def _fake_sleep(seconds: float) -> None:
        sleep_log.append(seconds)

    def _fake_now() -> float:
        return float(next(counter))

    monkeypatch.setattr(automation, "_sleep", _fake_sleep)
    monkeypatch.setattr(automation, "_now", _fake_now)
    yield sleep_log


@pytest.fixture
def mock_controller() -> ADBController:
    """A spec_set ADBController mock pre-loaded with sensible defaults.

    `get_screen_size` returns a fixed (1080, 2400) so `tap_center`
    coordinates are deterministic.
    """
    mock = MagicMock(spec_set=ADBController)
    mock.device_serial = None
    mock.get_screen_size.return_value = (1080, 2400)
    mock.get_battery_level.return_value = 87
    mock.screenshot.return_value = True
    mock.install_apk.return_value = True
    mock.pull.return_value = True
    mock.uninstall.return_value = True
    mock.list_packages.return_value = []
    mock.shell.return_value = ""
    mock.get_device_info.return_value = DeviceInfo(
        serial="FAKE",
        model="Pixel-Test",
        android_version="16",
        sdk_version=36,
        screen_size=(1080, 2400),
        battery_level=87,
        state=DeviceState.DEVICE,
    )
    return mock


# ---------------------------------------------------------------------------
# Step dispatch — every action kind exercised
# ---------------------------------------------------------------------------


class TestStepDispatch:
    @pytest.mark.parametrize(
        ("action", "params", "expected_method", "expected_args"),
        [
            ("tap", {"x": 100, "y": 200}, "tap", (100, 200)),
            ("tap_center", {}, "tap", (540, 1200)),  # 1080/2, 2400/2
            ("home", {}, "press_home", ()),
            ("back", {}, "press_back", ()),
            ("menu", {}, "press_menu", ()),
            ("enter", {}, "press_enter", ()),
            ("power", {}, "press_power", ()),
            ("wake", {}, "wake_up", ()),
            ("text", {"text": "hello"}, "input_text", ("hello",)),
            ("key", {"keycode": 4}, "key_event", (4,)),
            ("start_app", {"package": "com.foo"}, "start_app", ("com.foo",)),
            ("stop_app", {"package": "com.foo"}, "force_stop", ("com.foo",)),
            ("shell", {"command": "ls"}, "shell", ("ls",)),
        ],
    )
    def test_known_actions_call_correct_controller_method(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
        action: str,
        params: dict[str, object],
        expected_method: str,
        expected_args: tuple[object, ...],
    ) -> None:
        # Arrange
        auto = ADBAutomation(adb=mock_controller)
        step = AutomationStep(action, params, delay_after_s=0)

        # Act
        outcome = auto.execute_step(step)

        # Assert
        assert outcome.success is True
        method = getattr(mock_controller, expected_method)
        method.assert_called_once_with(*expected_args)

    def test_unknown_action_returns_failed_outcome(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        auto = ADBAutomation(adb=mock_controller)

        # Act
        outcome = auto.execute_step(AutomationStep("teleport", {}, delay_after_s=0))

        # Assert
        assert outcome.success is False
        assert outcome.error is not None
        assert "teleport" in outcome.error

    def test_action_lookup_is_case_insensitive(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        auto = ADBAutomation(adb=mock_controller)

        # Act
        outcome = auto.execute_step(AutomationStep("TAP_CENTER", {}, delay_after_s=0))

        # Assert
        assert outcome.success is True

    def test_handler_exception_is_caught_and_returned_as_failure(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        mock_controller.tap.side_effect = RuntimeError("boom")
        auto = ADBAutomation(adb=mock_controller)

        # Act — internal lesson (adaptive fault tolerance): graceful
        # degradation, no exception bubbles
        outcome = auto.execute_step(AutomationStep("tap", {"x": 1, "y": 2}, delay_after_s=0))

        # Assert
        assert outcome.success is False
        assert outcome.error == "boom"

    def test_screenshot_action_returns_artifact_path(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        auto = ADBAutomation(adb=mock_controller)

        # Act
        outcome = auto.execute_step(
            AutomationStep("screenshot", {"path": "out.png"}, delay_after_s=0)
        )

        # Assert
        assert outcome.success is True
        assert outcome.artifact_path == "out.png"


# ---------------------------------------------------------------------------
# Step delay (mockable via _sleep)
# ---------------------------------------------------------------------------


class TestStepDelay:
    def test_delay_after_step_calls_sleep(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        auto = ADBAutomation(adb=mock_controller)
        step = AutomationStep("home", delay_after_s=2.5)

        # Act
        auto.execute_step(step)

        # Assert
        assert 2.5 in stub_clock

    def test_zero_delay_skips_sleep(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        auto = ADBAutomation(adb=mock_controller)

        # Act
        auto.execute_step(AutomationStep("home", delay_after_s=0))

        # Assert
        assert stub_clock == []

    def test_wait_action_sleeps_for_requested_seconds(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        auto = ADBAutomation(adb=mock_controller)

        # Act
        auto.execute_step(AutomationStep("wait", {"seconds": 7}, delay_after_s=0))

        # Assert — only the wait sleep, not delay_after
        assert stub_clock == [7.0]


# ---------------------------------------------------------------------------
# run_workflow contract
# ---------------------------------------------------------------------------


class TestRunWorkflow:
    def test_all_steps_succeed_returns_success_result(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        auto = ADBAutomation(adb=mock_controller)
        steps = [
            AutomationStep("home", delay_after_s=0),
            AutomationStep("back", delay_after_s=0),
        ]

        # Act
        result = auto.run_workflow(steps)

        # Assert
        assert isinstance(result, AutomationResult)
        assert result.success is True
        assert result.steps_completed == 2
        assert result.total_steps == 2
        assert result.errors == ()

    def test_failed_step_with_stop_on_error_aborts_workflow(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        auto = ADBAutomation(adb=mock_controller)
        steps = [
            AutomationStep("home", delay_after_s=0),
            AutomationStep("nonexistent", delay_after_s=0),
            AutomationStep("back", delay_after_s=0),  # should not run
        ]

        # Act
        result = auto.run_workflow(steps, stop_on_error=True)

        # Assert
        assert result.success is False
        assert result.steps_completed == 1
        assert len(result.errors) == 1
        # Third step must NOT have been dispatched
        mock_controller.press_back.assert_not_called()

    def test_failed_step_with_continue_on_error_finishes_workflow(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        auto = ADBAutomation(adb=mock_controller)
        steps = [
            AutomationStep("home", delay_after_s=0),
            AutomationStep("nonexistent", delay_after_s=0),
            AutomationStep("back", delay_after_s=0),
        ]

        # Act
        result = auto.run_workflow(steps, stop_on_error=False)

        # Assert
        assert result.success is False  # has errors
        assert result.steps_completed == 2  # 2 of 3 succeeded
        mock_controller.press_back.assert_called_once()

    def test_screenshots_collected_into_result_tuple(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        auto = ADBAutomation(adb=mock_controller)
        steps = [
            AutomationStep("screenshot", {"path": "a.png"}, delay_after_s=0),
            AutomationStep("home", delay_after_s=0),
            AutomationStep("screenshot", {"path": "b.png"}, delay_after_s=0),
        ]

        # Act
        result = auto.run_workflow(steps)

        # Assert
        assert result.screenshots == ("a.png", "b.png")


# ---------------------------------------------------------------------------
# run_from_json
# ---------------------------------------------------------------------------


class TestRunFromJson:
    def test_loads_steps_from_json_file(
        self,
        tmp_path: Path,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        workflow = {
            "steps": [
                {"action": "home", "params": {}, "delay": 0, "description": "go home"},
                {"action": "tap", "params": {"x": 50, "y": 50}, "delay": 0},
            ]
        }
        path = tmp_path / "wf.json"
        path.write_text(json.dumps(workflow), encoding="utf-8")
        auto = ADBAutomation(adb=mock_controller)

        # Act
        result = auto.run_from_json(path)

        # Assert
        assert result.steps_completed == 2
        mock_controller.press_home.assert_called_once()
        mock_controller.tap.assert_called_once_with(50, 50)


# ---------------------------------------------------------------------------
# AppTester.install_and_launch
# ---------------------------------------------------------------------------


class TestAppTester:
    def test_install_failure_short_circuits_with_typed_result(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        mock_controller.install_apk.return_value = False
        tester = AppTester(adb=mock_controller)

        # Act
        result = tester.install_and_launch("/tmp/app.apk", "com.foo")  # noqa: S108

        # Assert
        assert isinstance(result, InstallAndLaunchResult)
        assert result.install_succeeded is False
        assert result.launch_attempted is False
        mock_controller.start_app.assert_not_called()

    def test_install_success_then_launch_with_screenshot(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        tester = AppTester(adb=mock_controller)

        # Act
        result = tester.install_and_launch(
            "/tmp/app.apk",  # noqa: S108
            "com.foo",
            take_screenshot=True,
        )

        # Assert
        assert result.install_succeeded is True
        assert result.launch_attempted is True
        assert len(result.screenshots) == 1
        mock_controller.start_app.assert_called_once_with("com.foo")
        mock_controller.screenshot.assert_called_once()

    def test_stress_test_invokes_monkey_with_total_events(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        tester = AppTester(adb=mock_controller)

        # Act
        result = tester.stress_test("com.foo", duration_s=10, events_per_second=5)

        # Assert
        assert result == {"duration_s": 10, "events": 50, "package": "com.foo"}
        mock_controller.shell.assert_called_once_with("monkey -p com.foo --throttle 100 -v 50")


# ---------------------------------------------------------------------------
# DeviceManager
# ---------------------------------------------------------------------------


class TestDeviceManager:
    def test_health_check_returns_complete_schema(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        mock_controller.shell.side_effect = lambda cmd: {
            "df -h /data | tail -1": "/data 50G 25G 25G 50% /data",
            "cat /proc/meminfo | head -3": (
                "MemTotal: 8000000 kB\nMemFree: 2000000 kB\nMemAvailable: 4000000 kB"
            ),
        }[cmd]
        mgr = DeviceManager(adb=mock_controller)

        # Act
        health = mgr.health_check()

        # Assert — schema completeness (Doctrine Law 2)
        assert set(health.keys()) == {
            "timestamp",
            "device",
            "screen",
            "battery",
            "storage",
            "memory",
        }
        assert health["device"]["model"] == "Pixel-Test"
        assert health["screen"]["width"] == 1080
        assert health["battery"]["level"] == 87
        assert health["storage"]["use_percent"] == "50%"
        assert "MemTotal" in health["memory"]

    def test_cleanup_device_only_clears_requested_locations(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        mgr = DeviceManager(adb=mock_controller)

        # Act
        result = mgr.cleanup_device(clear_local_tmp=True, clear_downloads=False)

        # Assert
        assert result == {"cleared": ["local_tmp"]}
        # Only the local_tmp shell call should have been made
        called_cmds = [call.args[0] for call in mock_controller.shell.call_args_list]
        assert "rm -rf /data/local/tmp/*" in called_cmds
        assert "rm -rf /sdcard/Download/*" not in called_cmds

    def test_batch_uninstall_returns_per_package_outcome(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        mock_controller.uninstall.side_effect = [True, False, True]
        mgr = DeviceManager(adb=mock_controller)

        # Act
        result = mgr.batch_uninstall(["a", "b", "c"])

        # Assert
        assert result == {"a": True, "b": False, "c": True}


# ---------------------------------------------------------------------------
# ScreenRecorder
# ---------------------------------------------------------------------------


class TestScreenRecorder:
    def test_start_marks_recording_and_calls_screen_record(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        rec = ScreenRecorder(adb=mock_controller)

        # Act
        rec.start("clip.mp4", time_limit_s=30, bit_rate_bps=2_000_000)

        # Assert
        assert rec.recording is True
        mock_controller.screen_record.assert_called_once_with(
            "/sdcard/clip.mp4", time_limit_s=30, bit_rate_bps=2_000_000
        )

    def test_double_start_is_idempotent(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        rec = ScreenRecorder(adb=mock_controller)
        rec.start()

        # Act — second start while already recording
        rec.start()

        # Assert — still only one underlying call
        assert mock_controller.screen_record.call_count == 1

    def test_stop_and_pull_pulls_then_removes_remote(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        rec = ScreenRecorder(adb=mock_controller)
        rec.recording = True

        # Act
        ok = rec.stop_and_pull("./out.mp4")

        # Assert
        assert ok is True
        assert rec.recording is False
        mock_controller.pull.assert_called_once_with("/sdcard/recording.mp4", "./out.mp4")
        mock_controller.rm.assert_called_once_with("/sdcard/recording.mp4")

    def test_stop_and_pull_returns_false_when_pull_fails(
        self,
        stub_clock: list[float],
        mock_controller: ADBController,
    ) -> None:
        # Arrange
        mock_controller.pull.return_value = False
        rec = ScreenRecorder(adb=mock_controller)
        rec.recording = True

        # Act
        ok = rec.stop_and_pull("./out.mp4")

        # Assert
        assert ok is False
        # Recording flag stays True (nothing was successfully pulled/removed)
        assert rec.recording is True
        mock_controller.rm.assert_not_called()


# ---------------------------------------------------------------------------
# Value-object frozen contract
# ---------------------------------------------------------------------------


class TestValueObjects:
    def test_automation_result_is_frozen(self) -> None:
        # Arrange
        r = AutomationResult(
            success=True,
            steps_completed=1,
            total_steps=1,
            duration_s=0.5,
        )

        # Act + Assert
        with pytest.raises(Exception):  # noqa: B017 — FrozenInstanceError varies by Python
            r.success = False  # type: ignore[misc]

    def test_step_outcome_carries_error_message(self) -> None:
        # Arrange + Act
        out = StepOutcome(success=False, error="something broke")

        # Assert
        assert out.success is False
        assert out.error == "something broke"
        assert out.artifact_path is None
