"""ADB controller — main interface."""

from __future__ import annotations

import logging
import re
import shlex
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)
# No logging.basicConfig — leave that to apps.

# Typed exception hierarchy.


class ADBError(Exception):
    """Base ADB failure."""


class ADBNotFoundError(ADBError):
    """adb binary missing."""


class DeviceOfflineError(ADBError):
    """Device offline or unauthorized."""


class ADBTimeoutError(ADBError):
    """ADB command timed out."""


class ADBPermissionError(ADBError):
    """Permission denied by ADB."""


class DeviceState(Enum):
    """Device states from `adb devices`."""

    DEVICE = "device"
    OFFLINE = "offline"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class DeviceInfo:
    """Device identity and state snapshot."""

    serial: str
    model: str
    android_version: str
    sdk_version: int
    screen_size: tuple[int, int]
    battery_level: int
    state: DeviceState


DEFAULT_TIMEOUT_S = 30
INSTALL_TIMEOUT_S = 120
TRANSFER_TIMEOUT_S = 300

_BATTERY_LEVEL_RE = re.compile(r"level:\s*(\d+)")
_SCREEN_SIZE_RE = re.compile(r"(\d+)x(\d+)")

# Locate PNG by signature (screencap may prepend a warning banner).
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Fail closed on shell metacharacters.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._/]+$")
_TAG_RE = re.compile(r"^[A-Za-z0-9._]+$")


def _validate_identifier(value: str, name: str = "identifier") -> None:
    """Raise ValueError for unsafe identifiers."""
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"Invalid {name}: {value!r}")


def _adb_run(
    args: list[str], *, timeout: int = DEFAULT_TIMEOUT_S, text: bool = True
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    """Run an adb command with output capture.

    Raises :class:`ADBNotFoundError` when adb is missing and
    :class:`ADBTimeoutError` on timeout. The caller inspects ``returncode``.
    """
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=text,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ADBNotFoundError(
            "ADB binary not found on PATH. Install Android platform-tools "
            "or `pkg install android-tools` on Termux."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ADBTimeoutError(f"Command timed out after {timeout}s: {' '.join(args)}") from exc


class ADBController:
    """Typed wrapper over the `adb` CLI."""

    device_serial: str | None = None

    def __init__(self, device_serial: str | None = None) -> None:
        self.device_serial = device_serial
        self._verify_adb()

    def _verify_adb(self) -> None:
        """Verify ADB is on PATH and runnable."""
        try:
            result = _adb_run(["adb", "version"], timeout=10)
        except ADBTimeoutError as exc:
            raise ADBTimeoutError("`adb version` timed out — adb-server may be wedged.") from exc
        if result.returncode != 0:
            raise ADBError(f"`adb version` exited {result.returncode}: {result.stderr.strip()}")

    def _run(self, cmd: list[str], timeout: int = DEFAULT_TIMEOUT_S) -> str:
        """Run an adb sub-command."""
        full_cmd: list[str] = ["adb"]
        if self.device_serial is not None:
            full_cmd.extend(["-s", self.device_serial])
        full_cmd.extend(cmd)

        logger.debug("Running: %s", " ".join(full_cmd))

        result = _adb_run(full_cmd, timeout=timeout)

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
        """Run a shell command on the device."""
        return self._run(["shell", cmd], timeout=timeout)

    def shell(self, cmd: str, *, timeout: int = DEFAULT_TIMEOUT_S) -> str:
        """Public counterpart to :meth:`_shell`."""
        return self._shell(cmd, timeout=timeout)

    def devices(self) -> list[dict[str, str]]:
        """List connected devices."""
        output = self._run(["devices", "-l"])
        devices: list[dict[str, str]] = []
        for raw_line in output.split("\n")[1:]:
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

    def connect(self, host: str, port: int | None = None) -> bool:
        """Connect to ``host``.

        With no port, the ADB wireless port is auto-discovered per session.
        """
        if port is None:
            from adb_android_control.port_scan import connect_auto

            port = connect_auto(host)
            if not port:
                return False
        try:
            result = self._run(["connect", f"{host}:{port}"])
        except ADBError:
            return False
        return "connected" in result.lower()

    def disconnect(self, host: str | None = None) -> bool:
        """Disconnect wireless (or all)."""
        try:
            if host is not None:
                self._run(["disconnect", host])
            else:
                self._run(["disconnect"])
        except ADBError:
            return False
        return True

    def get_device_info(self) -> DeviceInfo:
        """Device info snapshot."""
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

    def list_packages(self, *, third_party_only: bool = False) -> list[str]:
        """List installed packages."""
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
        """Install an APK."""
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
        """Uninstall a package."""
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
        """Clear app data."""
        _validate_identifier(package, "package")
        try:
            result = self._shell(f"pm clear {package}")
        except ADBError:
            return False
        return "success" in result.lower()

    def force_stop(self, package: str) -> None:
        """Force-stop a package."""
        _validate_identifier(package, "package")
        self._shell(f"am force-stop {package}")

    def start_activity(self, package: str, activity: str) -> None:
        """Start an activity."""
        _validate_identifier(package, "package")
        _validate_identifier(activity, "activity")
        self._shell(f"am start -n {package}/{activity}")

    def start_app(self, package: str) -> None:
        """Launch a package's LAUNCHER activity."""
        _validate_identifier(package, "package")
        self._shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")

    def get_current_activity(self) -> str:
        """Return the raw `mResumedActivity` line."""
        return self._shell("dumpsys activity activities | grep mResumedActivity")

    def push(self, local_path: str | Path, remote_path: str) -> bool:
        """Push a file or directory to the device."""
        try:
            self._run(["push", str(local_path), remote_path], timeout=TRANSFER_TIMEOUT_S)
        except ADBError as exc:
            logger.error("Push failed: %s", exc)
            return False
        return True

    def pull(self, remote_path: str, local_path: str | Path) -> bool:
        """Pull a file from the device."""
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
        """Create a directory (and parents)."""
        self._shell(f"mkdir -p {shlex.quote(path)}")

    def rm(self, path: str, *, recursive: bool = False) -> None:
        """Remove a file or directory."""
        cmd = "rm -rf" if recursive else "rm"
        self._shell(f"{cmd} {shlex.quote(path)}")

    def screenshot(self, local_path: str | Path = "screenshot.png") -> bool:
        """Capture the device screen."""
        argv: list[str] = ["adb"]
        if self.device_serial is not None:
            argv.extend(["-s", self.device_serial])
        argv.extend(["exec-out", "screencap", "-p"])

        try:
            result = _adb_run(argv, text=False)
        except ADBError as exc:
            logger.error("Screenshot failed: %s", exc)
            return False

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
        """Screen recording."""
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
        """Return ``(width, height)`` from `wm size`."""
        output = self._shell("wm size")
        match = _SCREEN_SIZE_RE.search(output)
        if match is None:
            return (0, 0)
        return (int(match.group(1)), int(match.group(2)))

    def tap(self, x: int, y: int) -> None:
        """Tap at screen coordinates ``(x, y)``."""
        self._shell(f"input tap {x} {y}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, *, duration_ms: int = 300) -> None:
        """Swipe between points."""
        self._shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")

    def long_press(self, x: int, y: int, *, duration_ms: int = 1000) -> None:
        """Long-press a point."""
        self._shell(f"input swipe {x} {y} {x} {y} {duration_ms}")

    def input_text(self, text: str) -> None:
        """Type literal text (shell-quoted)."""
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
        """Scroll up."""
        w, h = self.get_screen_size()
        for _ in range(steps):
            self.swipe(w // 2, h // 4, w // 2, h * 3 // 4, duration_ms=200)

    def scroll_down(self, *, steps: int = 1) -> None:
        """Scroll down."""
        w, h = self.get_screen_size()
        for _ in range(steps):
            self.swipe(w // 2, h * 3 // 4, w // 2, h // 4, duration_ms=200)

    def get_battery_level(self) -> int:
        """Return battery level (0-100)."""
        output = self._shell("dumpsys battery | grep level")
        match = _BATTERY_LEVEL_RE.search(output)
        if match is None:
            return 0
        return int(match.group(1))

    def get_property(self, prop: str) -> str:
        """Read an Android property."""
        _validate_identifier(prop, "property")
        return self._shell(f"getprop {prop}")

    def set_setting(self, namespace: str, key: str, value: str) -> None:
        """Set a `Settings` value."""
        _validate_identifier(namespace, "namespace")
        _validate_identifier(key, "key")
        self._shell(f"settings put {namespace} {key} {shlex.quote(value)}")

    def get_setting(self, namespace: str, key: str) -> str:
        """Get a `Settings` value."""
        _validate_identifier(namespace, "namespace")
        _validate_identifier(key, "key")
        return self._shell(f"settings get {namespace} {key}")

    def logcat(self, *, lines: int = 100, filter_tag: str | None = None) -> str:
        """Recent logcat lines, optionally filtered by tag."""
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

    def reboot(self, mode: str | None = None) -> None:
        """Reboot the device (optionally into ``mode``)."""
        cmd: list[str] = ["reboot"]
        if mode is not None:
            cmd.append(mode)
        self._run(cmd)

    def set_stay_awake(self, *, enabled: bool) -> None:
        """Toggle stay-awake-while-charging."""
        value = "usb" if enabled else "false"
        self._shell(f"svc power stayon {value}")
