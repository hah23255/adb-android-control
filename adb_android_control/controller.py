"""ADB controller — main interface for Android device control.

Doctrine: Master Tester Doctrine, Law 2 (test behaviour, not implementation).
The public API is the contract; `_run` and `_shell` are package-private and
should not be tested directly — instead, test the public methods that
compose them.

Security note: shell-command-injection surface
----------------------------------------------
Several methods (e.g. :meth:`ADBController.clear_data`, :meth:`force_stop`,
:meth:`get_property`, :meth:`set_setting`) interpolate caller-supplied
strings into shell commands that run on the *device*. To close that surface,
identifier arguments (package/activity/property/settings keys, logcat tags)
are validated against an allow-list (:func:`_validate_identifier` /
``_IDENTIFIER_RE`` / ``_TAG_RE``) and raise :class:`ValueError` on anything
containing a shell metacharacter; free-form path/value/text arguments are
``shlex.quote``-d before interpolation. Both fail closed rather than passing
unsafe input to the device shell.
"""

from __future__ import annotations

import logging
import re
import shlex
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)
# Library code does NOT call logging.basicConfig — leave that to the app.


# ---------------------------------------------------------------------------
# Typed exception hierarchy (Phase 2 plan §2.4)
# ---------------------------------------------------------------------------


class ADBError(Exception):
    """Base class for any ADB-operation failure raised by this package."""


class ADBNotFoundError(ADBError):
    """Raised when the `adb` binary is not installed or not on PATH."""


class DeviceOfflineError(ADBError):
    """Raised when the target device is offline or unauthorized."""


class ADBTimeoutError(ADBError):
    """Raised when an ADB command exceeds its timeout."""


class ADBPermissionError(ADBError):
    """Raised when an ADB command fails due to permission denial."""


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class DeviceState(Enum):
    """Device connection states reported by `adb devices`."""

    DEVICE = "device"
    OFFLINE = "offline"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class DeviceInfo:
    """Snapshot of a connected device's identifying & state attributes.

    Frozen so that test fixtures can be safely shared across tests
    (Doctrine Law 5: isolation).
    """

    serial: str
    model: str
    android_version: str
    sdk_version: int
    screen_size: tuple[int, int]
    battery_level: int
    state: DeviceState


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT_S = 30
INSTALL_TIMEOUT_S = 120
TRANSFER_TIMEOUT_S = 300

_BATTERY_LEVEL_RE = re.compile(r"level:\s*(\d+)")
_SCREEN_SIZE_RE = re.compile(r"(\d+)x(\d+)")

# PNG magic number. On multi-display devices (e.g. foldables) `screencap -p`
# prints a "[Warning] Multiple displays were found" banner to stdout ahead of
# the image, so screenshot() locates this signature rather than trusting the
# stream to start with it.
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Allow-list for Android identifiers (package / activity / property / settings
# keys) interpolated into device-side shell commands. Fail closed: reject any
# value containing a shell metacharacter before it can reach the device shell.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._/]+$")
_TAG_RE = re.compile(r"^[A-Za-z0-9._]+$")


def _validate_identifier(value: str, name: str = "identifier") -> None:
    """Raise :class:`ValueError` if ``value`` is not a safe Android identifier."""
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"Invalid {name}: {value!r}")


class ADBController:
    """Thin, typed wrapper over the `adb` CLI for one target device.

    Pass ``device_serial`` to scope every command to a specific device;
    omit it to use the only-connected-device default. ADB binary
    availability is verified eagerly during construction.
    """

    # Class-level default so MagicMock(spec_set=ADBController) sees
    # this attribute (Doctrine Pattern: Poison-Pill Mock — strict mocks
    # introspect via dir(cls); a class-level annotation alone is invisible
    # to dir(), so we provide an explicit default that __init__ overrides
    # per-instance).
    device_serial: str | None = None

    def __init__(self, device_serial: str | None = None) -> None:
        self.device_serial = device_serial
        self._verify_adb()

    # ------------------------------------------------------------------ core

    def _verify_adb(self) -> None:
        """Verify ADB is on PATH and runnable.

        Raises
        ------
        ADBNotFoundError
            If `adb` is not installed or not on PATH.
        """
        try:
            result = subprocess.run(
                ["adb", "version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ADBNotFoundError(
                "ADB binary not found on PATH. Install Android platform-tools "
                "or `pkg install android-tools` on Termux."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ADBTimeoutError("`adb version` timed out — adb-server may be wedged.") from exc

        if result.returncode != 0:
            raise ADBError(f"`adb version` exited {result.returncode}: {result.stderr.strip()}")

    def _run(self, cmd: list[str], timeout: int = DEFAULT_TIMEOUT_S) -> str:
        """Run an ADB sub-command and return stdout.

        Parameters
        ----------
        cmd : list[str]
            ADB sub-command parts, e.g. ``["shell", "getprop", "ro.product.model"]``.
            Always argv-list — never a single string — to avoid shell injection
            on the host side.
        timeout : int
            Seconds before raising :class:`ADBTimeoutError`.

        Raises
        ------
        ADBError, ADBTimeoutError, DeviceOfflineError, ADBPermissionError
        """
        full_cmd: list[str] = ["adb"]
        if self.device_serial is not None:
            full_cmd.extend(["-s", self.device_serial])
        full_cmd.extend(cmd)

        logger.debug("Running: %s", " ".join(full_cmd))

        try:
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ADBTimeoutError(f"Command timed out after {timeout}s: {' '.join(cmd)}") from exc

        if result.returncode != 0:
            stderr = result.stderr.strip()
            stderr_lower = stderr.lower()
            if "device offline" in stderr_lower or "device unauthorized" in stderr_lower:
                raise DeviceOfflineError(stderr)
            if "permission denied" in stderr_lower:
                raise ADBPermissionError(stderr)
            raise ADBError(f"adb {' '.join(cmd)} failed (rc={result.returncode}): {stderr}")

        return result.stdout.strip()

    def _shell(self, cmd: str, timeout: int = DEFAULT_TIMEOUT_S) -> str:
        """Run a shell command on the device. See module-level security note."""
        return self._run(["shell", cmd], timeout=timeout)

    def shell(self, cmd: str, *, timeout: int = DEFAULT_TIMEOUT_S) -> str:
        """Public counterpart to :meth:`_shell` — run a shell command on the device.

        Doctrine Law 2: Other modules in the package compose against this
        public method instead of reaching into ``_shell``. See module-level
        security note for the injection-surface caveat.
        """
        return self._shell(cmd, timeout=timeout)

    # ---------------------------------------------------------- device mgmt

    def devices(self) -> list[dict[str, str]]:
        """List connected devices with their state and metadata.

        Returns one dict per device with at least ``serial`` and ``state``;
        additional ``key:value`` fields from ``adb devices -l`` are merged in.
        """
        output = self._run(["devices", "-l"])
        devices: list[dict[str, str]] = []
        for raw_line in output.split("\n")[1:]:  # skip the "List of devices" header
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            entry: dict[str, str] = {"serial": parts[0], "state": parts[1]}
            for part in parts[2:]:
                if ":" in part:
                    key, val = part.split(":", 1)
                    entry[key] = val
            devices.append(entry)
        return devices

    def connect(self, host: str, port: int = 5555) -> bool:
        """Connect wirelessly to ``host:port``. Returns True on success."""
        try:
            result = self._run(["connect", f"{host}:{port}"])
        except ADBError:
            return False
        return "connected" in result.lower()

    def disconnect(self, host: str | None = None) -> bool:
        """Disconnect a wireless connection. ``host=None`` disconnects all."""
        try:
            if host is not None:
                self._run(["disconnect", host])
            else:
                self._run(["disconnect"])
        except ADBError:
            return False
        return True

    def get_device_info(self) -> DeviceInfo:
        """Aggregate model, version, screen size, and battery into one snapshot."""
        model = self._shell("getprop ro.product.model")
        android_ver = self._shell("getprop ro.build.version.release")
        sdk_raw = self._shell("getprop ro.build.version.sdk")
        try:
            sdk = int(sdk_raw)
        except ValueError as exc:
            raise ADBError(f"Unparseable SDK version: {sdk_raw!r}") from exc

        screen = self.get_screen_size()
        battery = self.get_battery_level()

        return DeviceInfo(
            serial=self.device_serial or "unknown",
            model=model,
            android_version=android_ver,
            sdk_version=sdk,
            screen_size=screen,
            battery_level=battery,
            state=DeviceState.DEVICE,
        )

    # ---------------------------------------------------------- app mgmt

    def list_packages(self, *, third_party_only: bool = False) -> list[str]:
        """List installed package names. Pass ``third_party_only=True`` to skip system apps."""
        cmd = "pm list packages"
        if third_party_only:
            cmd += " -3"
        output = self._shell(cmd)
        return [line.removeprefix("package:") for line in output.split("\n") if line.strip()]

    def install_apk(
        self,
        apk_path: str | Path,
        *,
        replace: bool = True,
        grant_permissions: bool = False,
    ) -> bool:
        """Install an APK file. Returns True on success."""
        cmd: list[str] = ["install"]
        if replace:
            cmd.append("-r")
        if grant_permissions:
            cmd.append("-g")
        cmd.append(str(apk_path))

        try:
            result = self._run(cmd, timeout=INSTALL_TIMEOUT_S)
        except ADBError as exc:
            logger.error("Install failed: %s", exc)
            return False
        return "success" in result.lower()

    def uninstall(self, package: str, *, keep_data: bool = False) -> bool:
        """Uninstall a package. Returns True on success."""
        cmd: list[str] = ["uninstall"]
        if keep_data:
            cmd.append("-k")
        cmd.append(package)

        try:
            result = self._run(cmd)
        except ADBError:
            return False
        return "success" in result.lower()

    def clear_data(self, package: str) -> bool:
        """Clear app data. Raises :class:`ValueError` for an unsafe package name."""
        _validate_identifier(package, "package")
        try:
            result = self._shell(f"pm clear {package}")
        except ADBError:
            return False
        return "success" in result.lower()

    def force_stop(self, package: str) -> None:
        """Force-stop the given package. Raises :class:`ValueError` for an unsafe name."""
        _validate_identifier(package, "package")
        self._shell(f"am force-stop {package}")

    def start_activity(self, package: str, activity: str) -> None:
        """Start a specific activity by ``package/activity`` name."""
        _validate_identifier(package, "package")
        _validate_identifier(activity, "activity")
        self._shell(f"am start -n {package}/{activity}")

    def start_app(self, package: str) -> None:
        """Launch the LAUNCHER activity of a package."""
        _validate_identifier(package, "package")
        self._shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")

    def get_current_activity(self) -> str:
        """Return raw `mResumedActivity` line from `dumpsys activity`."""
        return self._shell("dumpsys activity activities | grep mResumedActivity")

    # ---------------------------------------------------------- file ops

    def push(self, local_path: str | Path, remote_path: str) -> bool:
        """Push a file or directory to the device. Returns True on success."""
        try:
            self._run(["push", str(local_path), remote_path], timeout=TRANSFER_TIMEOUT_S)
        except ADBError as exc:
            logger.error("Push failed: %s", exc)
            return False
        return True

    def pull(self, remote_path: str, local_path: str | Path) -> bool:
        """Pull a file or directory from the device. Returns True on success."""
        try:
            self._run(["pull", remote_path, str(local_path)], timeout=TRANSFER_TIMEOUT_S)
        except ADBError as exc:
            logger.error("Pull failed: %s", exc)
            return False
        return True

    def ls(self, path: str = "/sdcard") -> list[str]:
        """List directory contents at ``path``."""
        output = self._shell(f"ls -la {shlex.quote(path)}")
        return output.split("\n")

    def mkdir(self, path: str) -> None:
        """Create directory (and parents) at ``path``."""
        self._shell(f"mkdir -p {shlex.quote(path)}")

    def rm(self, path: str, *, recursive: bool = False) -> None:
        """Remove a file (or directory if ``recursive=True``)."""
        cmd = "rm -rf" if recursive else "rm"
        self._shell(f"{cmd} {shlex.quote(path)}")

    # ---------------------------------------------------------- screen

    def screenshot(self, local_path: str | Path = "screenshot.png") -> bool:
        """Capture the device screen and write it to ``local_path``."""
        argv: list[str] = ["adb"]
        if self.device_serial is not None:
            argv.extend(["-s", self.device_serial])
        argv.extend(["exec-out", "screencap", "-p"])

        try:
            result = subprocess.run(
                argv,
                capture_output=True,
                timeout=DEFAULT_TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.error("Screenshot timed out")
            return False

        # stderr is bytes here (screencap output is binary, so text=True is not
        # set); decode once for readable log messages.
        raw_err = result.stderr
        stderr = (
            raw_err.decode("utf-8", "replace") if isinstance(raw_err, bytes) else raw_err
        ).strip()

        if result.returncode != 0:
            logger.error("Screenshot failed (rc=%d): %s", result.returncode, stderr)
            return False

        png = result.stdout
        offset = png.find(_PNG_SIGNATURE)
        if offset < 0:
            logger.error(
                "Screenshot produced no PNG data (%d bytes captured); stderr: %s",
                len(png),
                stderr,
            )
            return False
        if offset > 0:
            # Strip a device-emitted warning banner (multi-display foldables) so
            # the written file is a valid PNG.
            logger.warning("Stripped %d non-PNG byte(s) preceding the screencap image", offset)
            png = png[offset:]

        Path(local_path).write_bytes(png)
        return True

    def screen_record(
        self,
        remote_path: str = "/sdcard/recording.mp4",
        *,
        time_limit_s: int = 30,
        bit_rate_bps: int = 4_000_000,
    ) -> subprocess.Popen[bytes]:
        """Start a non-blocking screen recording. Returns the Popen handle."""
        argv: list[str] = ["adb"]
        if self.device_serial is not None:
            argv.extend(["-s", self.device_serial])
        record_cmd = (
            f"screenrecord --time-limit {time_limit_s} "
            f"--bit-rate {bit_rate_bps} {shlex.quote(remote_path)}"
        )
        argv.extend(["shell", record_cmd])
        return subprocess.Popen(argv)

    def get_screen_size(self) -> tuple[int, int]:
        """Return ``(width, height)`` from `wm size`. Returns ``(0, 0)`` if unparseable."""
        output = self._shell("wm size")
        match = _SCREEN_SIZE_RE.search(output)
        if match is None:
            return (0, 0)
        return (int(match.group(1)), int(match.group(2)))

    # ---------------------------------------------------------- input

    def tap(self, x: int, y: int) -> None:
        """Tap at screen coordinates ``(x, y)``."""
        self._shell(f"input tap {x} {y}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, *, duration_ms: int = 300) -> None:
        """Swipe from ``(x1, y1)`` to ``(x2, y2)`` over ``duration_ms``."""
        self._shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")

    def long_press(self, x: int, y: int, *, duration_ms: int = 1000) -> None:
        """Long-press at ``(x, y)`` for ``duration_ms``."""
        self._shell(f"input swipe {x} {y} {x} {y} {duration_ms}")

    def input_text(self, text: str) -> None:
        """Type literal text. The text is shell-quoted before being sent."""
        escaped = shlex.quote(text)
        self._shell(f"input text {escaped}")

    def key_event(self, keycode: int) -> None:
        """Send an Android keycode."""
        self._shell(f"input keyevent {keycode}")

    def press_home(self) -> None:
        """KEYCODE_HOME."""
        self.key_event(3)

    def press_back(self) -> None:
        """KEYCODE_BACK."""
        self.key_event(4)

    def press_menu(self) -> None:
        """KEYCODE_MENU."""
        self.key_event(82)

    def press_enter(self) -> None:
        """KEYCODE_ENTER."""
        self.key_event(66)

    def press_power(self) -> None:
        """KEYCODE_POWER."""
        self.key_event(26)

    def wake_up(self) -> None:
        """KEYCODE_WAKEUP (224)."""
        self.key_event(224)

    def scroll_up(self, *, steps: int = 1) -> None:
        """Scroll up ``steps`` times (swipe down on screen)."""
        w, h = self.get_screen_size()
        for _ in range(steps):
            self.swipe(w // 2, h // 4, w // 2, h * 3 // 4, duration_ms=200)

    def scroll_down(self, *, steps: int = 1) -> None:
        """Scroll down ``steps`` times (swipe up on screen)."""
        w, h = self.get_screen_size()
        for _ in range(steps):
            self.swipe(w // 2, h * 3 // 4, w // 2, h // 4, duration_ms=200)

    # ---------------------------------------------------------- system info

    def get_battery_level(self) -> int:
        """Return battery level (0-100), or 0 if unparseable."""
        output = self._shell("dumpsys battery | grep level")
        match = _BATTERY_LEVEL_RE.search(output)
        if match is None:
            return 0
        return int(match.group(1))

    def get_property(self, prop: str) -> str:
        """Return the value of an Android system property (`getprop`)."""
        _validate_identifier(prop, "property")
        return self._shell(f"getprop {prop}")

    def set_setting(self, namespace: str, key: str, value: str) -> None:
        """Set a `Settings` value (e.g. ``set_setting("global", "airplane_mode_on", "1")``)."""
        _validate_identifier(namespace, "namespace")
        _validate_identifier(key, "key")
        self._shell(f"settings put {namespace} {key} {shlex.quote(value)}")

    def get_setting(self, namespace: str, key: str) -> str:
        """Get a `Settings` value."""
        _validate_identifier(namespace, "namespace")
        _validate_identifier(key, "key")
        return self._shell(f"settings get {namespace} {key}")

    # ---------------------------------------------------------- logcat

    def logcat(self, *, lines: int = 100, filter_tag: str | None = None) -> str:
        """Return the last ``lines`` of logcat, optionally filtered by tag."""
        cmd = "logcat -d"
        if filter_tag is not None:
            if not _TAG_RE.fullmatch(filter_tag):
                raise ValueError(f"Invalid logcat tag: {filter_tag!r}")
            cmd += f" -s {shlex.quote(f'{filter_tag}:*')}"
        cmd += f" | tail -n {lines}"
        return self._shell(cmd)

    def clear_logcat(self) -> None:
        """Clear the logcat buffer."""
        self._shell("logcat -c")

    # ---------------------------------------------------------- power

    def reboot(self, mode: str | None = None) -> None:
        """Reboot the device. ``mode`` can be ``"recovery"``, ``"bootloader"``, etc."""
        cmd: list[str] = ["reboot"]
        if mode is not None:
            cmd.append(mode)
        self._run(cmd)

    def set_stay_awake(self, *, enabled: bool) -> None:
        """Toggle stay-awake-while-charging."""
        value = "usb" if enabled else "false"
        self._shell(f"svc power stayon {value}")
