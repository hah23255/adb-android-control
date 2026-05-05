"""High-level workflow automation, app testing, and device management.

Doctrine note
-------------
- Composes against :class:`ADBController`'s public API only (Law 2).
- ``time.sleep`` is referenced via the module-level ``_sleep`` alias so
  tests can monkey-patch it without touching real wall-clock.
- ``_execute_step`` always returns a :class:`StepOutcome` (never the
  bool|str union the v1.0 implementation returned) — typed result.

Step dispatch
-------------
Step kinds are looked up in a frozen dictionary at module load.
Adding a new step kind = add an entry to ``_STEP_HANDLERS`` and
the corresponding test row in ``test_automation.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from adb_android_control.controller import ADBController

logger = logging.getLogger(__name__)

# Indirection so tests can monkey-patch this without touching `time` itself.
_sleep: Callable[[float], None] = time.sleep
_now: Callable[[], float] = time.monotonic


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AutomationStep:
    """One step in a workflow.

    ``params`` is intentionally a plain dict (not typed) so workflows
    can be authored as JSON. Validation happens at dispatch time.
    """

    action: str
    params: dict[str, Any] = field(default_factory=dict)
    delay_after_s: float = 0.5
    description: str = ""


@dataclass(frozen=True)
class StepOutcome:
    """Internal result of a single step execution."""

    success: bool
    artifact_path: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class AutomationResult:
    """Public result of running a workflow."""

    success: bool
    steps_completed: int
    total_steps: int
    duration_s: float
    errors: tuple[str, ...] = ()
    screenshots: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Core automation engine
# ---------------------------------------------------------------------------


class ADBAutomation:
    """High-level dispatcher: turns :class:`AutomationStep` objects into ADB calls."""

    def __init__(
        self,
        device_serial: str | None = None,
        *,
        adb: ADBController | None = None,
    ) -> None:
        self.adb: ADBController = adb if adb is not None else ADBController(device_serial)
        self.screen_width, self.screen_height = self.adb.get_screen_size()

    # -- step handlers (one per action kind, all return StepOutcome) ----------

    def _do_tap(self, params: dict[str, Any]) -> StepOutcome:
        x = int(params.get("x", self.screen_width // 2))
        y = int(params.get("y", self.screen_height // 2))
        self.adb.tap(x, y)
        return StepOutcome(success=True)

    def _do_tap_center(self, _params: dict[str, Any]) -> StepOutcome:
        self.adb.tap(self.screen_width // 2, self.screen_height // 2)
        return StepOutcome(success=True)

    def _do_tap_percent(self, params: dict[str, Any]) -> StepOutcome:
        x = int(self.screen_width * float(params.get("x_pct", 0.5)))
        y = int(self.screen_height * float(params.get("y_pct", 0.5)))
        self.adb.tap(x, y)
        return StepOutcome(success=True)

    def _do_swipe(self, params: dict[str, Any]) -> StepOutcome:
        self.adb.swipe(
            int(params.get("x1", 0)),
            int(params.get("y1", 0)),
            int(params.get("x2", 0)),
            int(params.get("y2", 0)),
            duration_ms=int(params.get("duration", 300)),
        )
        return StepOutcome(success=True)

    def _do_swipe_up(self, params: dict[str, Any]) -> StepOutcome:
        self.adb.scroll_down(steps=int(params.get("steps", 1)))
        return StepOutcome(success=True)

    def _do_swipe_down(self, params: dict[str, Any]) -> StepOutcome:
        self.adb.scroll_up(steps=int(params.get("steps", 1)))
        return StepOutcome(success=True)

    def _do_swipe_left(self, _params: dict[str, Any]) -> StepOutcome:
        mid_y = self.screen_height // 2
        self.adb.swipe(
            int(self.screen_width * 0.8), mid_y,
            int(self.screen_width * 0.2), mid_y,
            duration_ms=200,
        )
        return StepOutcome(success=True)

    def _do_swipe_right(self, _params: dict[str, Any]) -> StepOutcome:
        mid_y = self.screen_height // 2
        self.adb.swipe(
            int(self.screen_width * 0.2), mid_y,
            int(self.screen_width * 0.8), mid_y,
            duration_ms=200,
        )
        return StepOutcome(success=True)

    def _do_long_press(self, params: dict[str, Any]) -> StepOutcome:
        self.adb.long_press(
            int(params.get("x", self.screen_width // 2)),
            int(params.get("y", self.screen_height // 2)),
            duration_ms=int(params.get("duration", 1000)),
        )
        return StepOutcome(success=True)

    def _do_text(self, params: dict[str, Any]) -> StepOutcome:
        self.adb.input_text(str(params.get("text", "")))
        return StepOutcome(success=True)

    def _do_key(self, params: dict[str, Any]) -> StepOutcome:
        self.adb.key_event(int(params.get("keycode", 0)))
        return StepOutcome(success=True)

    def _do_home(self, _params: dict[str, Any]) -> StepOutcome:
        self.adb.press_home()
        return StepOutcome(success=True)

    def _do_back(self, _params: dict[str, Any]) -> StepOutcome:
        self.adb.press_back()
        return StepOutcome(success=True)

    def _do_menu(self, _params: dict[str, Any]) -> StepOutcome:
        self.adb.press_menu()
        return StepOutcome(success=True)

    def _do_enter(self, _params: dict[str, Any]) -> StepOutcome:
        self.adb.press_enter()
        return StepOutcome(success=True)

    def _do_power(self, _params: dict[str, Any]) -> StepOutcome:
        self.adb.press_power()
        return StepOutcome(success=True)

    def _do_wake(self, _params: dict[str, Any]) -> StepOutcome:
        self.adb.wake_up()
        return StepOutcome(success=True)

    def _do_screenshot(self, params: dict[str, Any]) -> StepOutcome:
        path = str(params.get("path", f"screenshot_{int(_now() * 1000)}.png"))
        ok = self.adb.screenshot(path)
        return StepOutcome(success=ok, artifact_path=path if ok else None)

    def _do_start_app(self, params: dict[str, Any]) -> StepOutcome:
        self.adb.start_app(str(params.get("package", "")))
        return StepOutcome(success=True)

    def _do_stop_app(self, params: dict[str, Any]) -> StepOutcome:
        self.adb.force_stop(str(params.get("package", "")))
        return StepOutcome(success=True)

    def _do_wait(self, params: dict[str, Any]) -> StepOutcome:
        _sleep(float(params.get("seconds", 1)))
        return StepOutcome(success=True)

    def _do_shell(self, params: dict[str, Any]) -> StepOutcome:
        self.adb.shell(str(params.get("command", "")))
        return StepOutcome(success=True)

    # -- dispatch ------------------------------------------------------------

    @property
    def _handlers(self) -> dict[str, Callable[[dict[str, Any]], StepOutcome]]:
        """Mapping from action name to handler. Override in subclasses to extend."""
        return {
            "tap": self._do_tap,
            "tap_center": self._do_tap_center,
            "tap_percent": self._do_tap_percent,
            "swipe": self._do_swipe,
            "swipe_up": self._do_swipe_up,
            "swipe_down": self._do_swipe_down,
            "swipe_left": self._do_swipe_left,
            "swipe_right": self._do_swipe_right,
            "long_press": self._do_long_press,
            "text": self._do_text,
            "key": self._do_key,
            "home": self._do_home,
            "back": self._do_back,
            "menu": self._do_menu,
            "enter": self._do_enter,
            "power": self._do_power,
            "wake": self._do_wake,
            "screenshot": self._do_screenshot,
            "start_app": self._do_start_app,
            "stop_app": self._do_stop_app,
            "wait": self._do_wait,
            "shell": self._do_shell,
        }

    def execute_step(self, step: AutomationStep) -> StepOutcome:
        """Execute a single step. Always returns a :class:`StepOutcome`."""
        handler = self._handlers.get(step.action.lower())
        if handler is None:
            logger.warning("Unknown action: %s", step.action)
            return StepOutcome(success=False, error=f"unknown action: {step.action}")
        try:
            outcome = handler(step.params)
        except Exception as exc:  # noqa: BLE001 — workflow tolerance per internal lesson (adaptive fault tolerance)
            logger.error("Step failed: %s", exc)
            return StepOutcome(success=False, error=str(exc))
        if step.delay_after_s > 0:
            _sleep(step.delay_after_s)
        return outcome

    def run_workflow(
        self,
        steps: list[AutomationStep],
        *,
        stop_on_error: bool = True,
    ) -> AutomationResult:
        """Run a list of steps. Returns an :class:`AutomationResult`."""
        start_time = _now()
        completed = 0
        errors: list[str] = []
        screenshots: list[str] = []

        for i, step in enumerate(steps):
            logger.info(
                "Step %d/%d: %s — %s",
                i + 1,
                len(steps),
                step.action,
                step.description,
            )
            outcome = self.execute_step(step)
            if outcome.artifact_path is not None:
                screenshots.append(outcome.artifact_path)
            if outcome.success:
                completed += 1
            else:
                errors.append(f"Step {i + 1} ({step.action}): {outcome.error or 'failed'}")
                if stop_on_error:
                    break

        return AutomationResult(
            success=not errors,
            steps_completed=completed,
            total_steps=len(steps),
            duration_s=_now() - start_time,
            errors=tuple(errors),
            screenshots=tuple(screenshots),
        )

    def run_from_json(self, json_path: str | Path) -> AutomationResult:
        """Load steps from a JSON file and execute them.

        Expected JSON shape::

            {"steps": [
                {"action": "tap", "params": {"x": 100, "y": 200}, "delay": 0.5,
                 "description": "tap the button"},
                ...
            ]}
        """
        data = json.loads(Path(json_path).read_text(encoding="utf-8"))
        steps = [
            AutomationStep(
                action=step_data["action"],
                params=step_data.get("params", {}),
                delay_after_s=float(step_data.get("delay", 0.5)),
                description=step_data.get("description", ""),
            )
            for step_data in data.get("steps", [])
        ]
        return self.run_workflow(steps)


# ---------------------------------------------------------------------------
# AppTester — install / launch / smoke / stress
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstallAndLaunchResult:
    install_succeeded: bool
    launch_attempted: bool
    screenshots: tuple[str, ...] = ()


class AppTester(ADBAutomation):
    """Specialised automation for app-install and app-test flows."""

    def install_and_launch(
        self,
        apk_path: str | Path,
        package: str,
        *,
        take_screenshot: bool = True,
        post_launch_wait_s: float = 3.0,
    ) -> InstallAndLaunchResult:
        """Install the APK then launch its main activity. Returns a typed result."""
        installed = self.adb.install_apk(apk_path, replace=True)
        if not installed:
            return InstallAndLaunchResult(install_succeeded=False, launch_attempted=False)

        self.adb.start_app(package)
        _sleep(post_launch_wait_s)

        screenshots: list[str] = []
        if take_screenshot:
            path = f"launch_{int(_now() * 1000)}.png"
            if self.adb.screenshot(path):
                screenshots.append(path)

        return InstallAndLaunchResult(
            install_succeeded=True,
            launch_attempted=True,
            screenshots=tuple(screenshots),
        )

    def test_basic_navigation(
        self,
        package: str,
        *,
        num_actions: int = 10,
    ) -> AutomationResult:
        """Heuristic smoke: launch + load + (tap/swipe/back) x N + screenshot."""
        steps: list[AutomationStep] = [
            AutomationStep("start_app", {"package": package}, description="Launch app"),
            AutomationStep("wait", {"seconds": 3}, description="Wait for load"),
            AutomationStep(
                "screenshot", {"path": "nav_start.png"}, description="Initial state"
            ),
        ]
        for i in range(num_actions):
            kind = i % 3
            if kind == 0:
                steps.append(AutomationStep("tap_center", description=f"Tap {i + 1}"))
            elif kind == 1:
                steps.append(AutomationStep("swipe_up", description=f"Scroll {i + 1}"))
            else:
                steps.append(AutomationStep("back", description=f"Back {i + 1}"))
        steps.append(
            AutomationStep("screenshot", {"path": "nav_end.png"}, description="Final state")
        )
        return self.run_workflow(steps)

    def stress_test(
        self,
        package: str,
        *,
        duration_s: int = 60,
        events_per_second: int = 10,
    ) -> dict[str, Any]:
        """Run `monkey` stress test for the configured duration."""
        total_events = duration_s * events_per_second
        self.adb.shell(f"monkey -p {package} --throttle 100 -v {total_events}")
        return {
            "duration_s": duration_s,
            "events": total_events,
            "package": package,
        }


# ---------------------------------------------------------------------------
# DeviceManager — health / cleanup / batch ops
# ---------------------------------------------------------------------------


class DeviceManager(ADBAutomation):
    """Bulk device-management workflows."""

    def health_check(self) -> dict[str, Any]:
        """Aggregate device, screen, battery, storage, memory into one snapshot."""
        info = self.adb.get_device_info()
        return {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "device": {
                "model": info.model,
                "android": info.android_version,
                "sdk": info.sdk_version,
            },
            "screen": {
                "width": info.screen_size[0],
                "height": info.screen_size[1],
            },
            "battery": {"level": info.battery_level},
            "storage": self._get_storage_info(),
            "memory": self._get_memory_info(),
        }

    def _get_storage_info(self) -> dict[str, str]:
        try:
            output = self.adb.shell("df -h /data | tail -1")
        except Exception:  # noqa: BLE001 — internal lesson (adaptive fault tolerance) graceful degradation
            return {}
        parts = output.split()
        if len(parts) < 4:
            return {}
        return {
            "total": parts[1],
            "used": parts[2],
            "available": parts[3],
            "use_percent": parts[4] if len(parts) > 4 else "N/A",
        }

    def _get_memory_info(self) -> dict[str, str]:
        try:
            output = self.adb.shell("cat /proc/meminfo | head -3")
        except Exception:  # noqa: BLE001
            return {}
        memory: dict[str, str] = {}
        for line in output.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                memory[key.strip()] = value.strip()
        return memory

    def cleanup_device(
        self,
        *,
        clear_local_tmp: bool = True,
        clear_downloads: bool = False,
    ) -> dict[str, list[str]]:
        """Best-effort device cleanup. Returns the list of locations cleared."""
        cleared: list[str] = []
        if clear_local_tmp:
            try:
                self.adb.shell("rm -rf /data/local/tmp/*")
                cleared.append("local_tmp")
            except Exception as exc:  # noqa: BLE001
                logger.warning("clear local_tmp failed: %s", exc)
        if clear_downloads:
            try:
                self.adb.shell("rm -rf /sdcard/Download/*")
                cleared.append("downloads")
            except Exception as exc:  # noqa: BLE001
                logger.warning("clear downloads failed: %s", exc)
        return {"cleared": cleared}

    def batch_uninstall(
        self,
        packages: list[str],
        *,
        keep_data: bool = False,
    ) -> dict[str, bool]:
        """Uninstall many packages; returns a per-package success map."""
        return {pkg: self.adb.uninstall(pkg, keep_data=keep_data) for pkg in packages}

    def extract_all_apks(self, output_dir: str | Path = "./apks") -> list[str]:
        """Pull all third-party APK files locally. Returns successfully-extracted paths."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        extracted: list[str] = []
        for pkg in self.adb.list_packages(third_party_only=True):
            try:
                apk_path = self.adb.shell(f"pm path {pkg}").split(":")[-1].strip()
            except Exception as exc:  # noqa: BLE001
                logger.error("pm path %s failed: %s", pkg, exc)
                continue
            local_path = out_dir / f"{pkg}.apk"
            if self.adb.pull(apk_path, local_path):
                extracted.append(str(local_path))
                logger.info("Extracted: %s", pkg)
        return extracted


# ---------------------------------------------------------------------------
# ScreenRecorder — independent of ADBAutomation (different lifecycle)
# ---------------------------------------------------------------------------


class ScreenRecorder:
    """Wraps ADBController's screen-record Popen with start/stop/pull semantics."""

    def __init__(self, adb: ADBController) -> None:
        self.adb: ADBController = adb
        self.recording: bool = False

    def start(
        self,
        filename: str = "recording.mp4",
        *,
        time_limit_s: int = 180,
        bit_rate_bps: int = 4_000_000,
    ) -> None:
        """Begin recording. No-op if already recording."""
        if self.recording:
            logger.warning("Already recording")
            return
        remote_path = f"/sdcard/{filename}"
        self.adb.screen_record(
            remote_path, time_limit_s=time_limit_s, bit_rate_bps=bit_rate_bps
        )
        self.recording = True
        logger.info("Recording started: %s", remote_path)

    def stop_and_pull(
        self,
        local_path: str | Path = "./recording.mp4",
        *,
        remote_filename: str = "recording.mp4",
        settle_s: float = 1.0,
    ) -> bool:
        """Wait briefly for the file to flush, pull it, then delete the remote copy."""
        remote_path = f"/sdcard/{remote_filename}"
        _sleep(settle_s)
        if not self.adb.pull(remote_path, local_path):
            return False
        self.adb.rm(remote_path)
        self.recording = False
        logger.info("Recording saved: %s", local_path)
        return True
