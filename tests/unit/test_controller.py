"""Unit tests for :mod:`adb_android_control.controller`.

Doctrine: AAA (Law 3), isolation (Law 5), Poison-Pill subprocess mocks
(Law 6), one logical concept per test (Law 9), no tautologies (Law 10).

Tests are grouped by behaviour, not by source-line — each ``Test*`` class
documents an observable contract. We never test private methods directly
(Law 2: behaviour, not implementation).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from adb_android_control.controller import (
    ADBController,
    ADBError,
    ADBNotFoundError,
    ADBPermissionError,
    ADBTimeoutError,
    DeviceInfo,
    DeviceOfflineError,
    DeviceState,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tests.conftest import PoisonPillADB

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Construction / ADB-availability contract
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_construction_succeeds_when_adb_present(self, mock_adb: PoisonPillADB) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="Android Debug Bridge v1.0.41\n")

        # Act
        ctrl = ADBController()

        # Assert
        assert ctrl.device_serial is None

    def test_construction_with_serial_scopes_subsequent_calls(
        self, mock_adb: PoisonPillADB
    ) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(["adb", "-s", "EMULATOR-1", "devices", "-l"], stdout="\n")

        # Act
        ctrl = ADBController(device_serial="EMULATOR-1")
        ctrl.devices()

        # Assert — every subsequent call should include `-s EMULATOR-1`
        assert ("adb", "-s", "EMULATOR-1", "devices", "-l") in mock_adb.call_log()

    def test_missing_adb_binary_raises_actionable_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        import subprocess as sp

        def _raise_filenotfound(*_a: object, **_k: object) -> object:
            raise FileNotFoundError("[Errno 2] No such file or directory: 'adb'")

        monkeypatch.setattr(sp, "run", _raise_filenotfound)

        # Act + Assert
        with pytest.raises(ADBNotFoundError, match="not found on PATH"):
            ADBController()


# ---------------------------------------------------------------------------
# Error classification (typed exception hierarchy)
# ---------------------------------------------------------------------------


class TestErrorClassification:
    def test_device_offline_stderr_raises_device_offline_error(
        self, mock_adb: PoisonPillADB
    ) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="v1\n")
        # NB: ADBController._shell forwards ``cmd`` as a single argv element
        # to ``_run(["shell", cmd])`` — see controller.py:200. The mock argv
        # therefore matches that joined form, not a split form.
        mock_adb.register(
            ["adb", "shell", "getprop ro.product.model"],
            stderr="error: device offline",
            returncode=1,
        )
        ctrl = ADBController()

        # Act + Assert
        with pytest.raises(DeviceOfflineError):
            ctrl.get_property("ro.product.model")

    def test_device_unauthorized_also_raises_device_offline_error(
        self, mock_adb: PoisonPillADB
    ) -> None:
        # Arrange — unauthorized devices share the offline-class semantics
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(
            ["adb", "shell", "wm size"],
            stderr="error: device unauthorized.\nThis adb server's $ADB_VENDOR_KEYS is not set",
            returncode=1,
        )
        ctrl = ADBController()

        # Act + Assert
        with pytest.raises(DeviceOfflineError):
            ctrl.get_screen_size()

    def test_permission_denied_raises_adb_permission_error(self, mock_adb: PoisonPillADB) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(
            ["adb", "shell", "cat /data/secret"],
            stderr="cat: /data/secret: Permission denied",
            returncode=1,
        )
        ctrl = ADBController()

        # Act + Assert
        with pytest.raises(ADBPermissionError):
            ctrl._shell("cat /data/secret")

    def test_typed_errors_inherit_from_adbe_rror(self) -> None:
        # Arrange + Act + Assert — base-class catch-all must work
        assert issubclass(ADBNotFoundError, ADBError)
        assert issubclass(DeviceOfflineError, ADBError)
        assert issubclass(ADBTimeoutError, ADBError)
        assert issubclass(ADBPermissionError, ADBError)


# ---------------------------------------------------------------------------
# `devices` parsing
# ---------------------------------------------------------------------------


class TestDevicesListing:
    def test_empty_list_when_no_devices(self, mock_adb: PoisonPillADB) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(["adb", "devices", "-l"], stdout="List of devices attached\n\n")
        ctrl = ADBController()

        # Act
        result = ctrl.devices()

        # Assert
        assert result == []

    def test_parses_single_device_with_metadata(self, mock_adb: PoisonPillADB) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(
            ["adb", "devices", "-l"],
            stdout=(
                "List of devices attached\n"
                "EMULATOR-1 device product:sdk_gphone model:Pixel transport_id:1\n"
            ),
        )
        ctrl = ADBController()

        # Act
        result = ctrl.devices()

        # Assert
        assert len(result) == 1
        assert result[0]["serial"] == "EMULATOR-1"
        assert result[0]["state"] == "device"
        assert result[0]["product"] == "sdk_gphone"
        assert result[0]["model"] == "Pixel"
        assert result[0]["transport_id"] == "1"

    def test_skips_blank_lines_in_output(self, mock_adb: PoisonPillADB) -> None:
        # Arrange — adb sometimes emits blank lines between entries
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(
            ["adb", "devices", "-l"],
            stdout="List of devices attached\n\nEMULATOR-1 device\n\n\nEMULATOR-2 offline\n",
        )
        ctrl = ADBController()

        # Act
        result = ctrl.devices()

        # Assert
        assert [d["serial"] for d in result] == ["EMULATOR-1", "EMULATOR-2"]


# ---------------------------------------------------------------------------
# `connect` / `disconnect` semantics (boolean return)
# ---------------------------------------------------------------------------


class TestConnectDisconnect:
    def test_connect_returns_true_when_adb_reports_connected(self, mock_adb: PoisonPillADB) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(
            ["adb", "connect", "10.0.0.1:5555"],
            stdout="connected to 10.0.0.1:5555\n",
        )
        ctrl = ADBController()

        # Act
        ok = ctrl.connect("10.0.0.1")

        # Assert
        assert ok is True

    def test_connect_returns_false_when_adb_errors(self, mock_adb: PoisonPillADB) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(
            ["adb", "connect", "10.0.0.1:5555"],
            stderr="failed to connect to '10.0.0.1:5555': Connection refused",
            returncode=1,
        )
        ctrl = ADBController()

        # Act
        ok = ctrl.connect("10.0.0.1")

        # Assert
        assert ok is False

    def test_disconnect_all_when_no_host_given(self, mock_adb: PoisonPillADB) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(["adb", "disconnect"], stdout="\n")
        ctrl = ADBController()

        # Act
        ok = ctrl.disconnect()

        # Assert
        assert ok is True
        assert ("adb", "disconnect") in mock_adb.call_log()


# ---------------------------------------------------------------------------
# Device info aggregation
# ---------------------------------------------------------------------------


class TestDeviceInfo:
    def _register_device_info_calls(
        self,
        mock_adb: PoisonPillADB,
        *,
        model: str = "Pixel-Test",
        version: str = "16",
        sdk: str = "36",
        screen: str = "Physical size: 1080x2400",
        battery: str = "level: 87",
    ) -> None:
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(["adb", "shell", "getprop ro.product.model"], stdout=model)
        mock_adb.register(["adb", "shell", "getprop ro.build.version.release"], stdout=version)
        mock_adb.register(["adb", "shell", "getprop ro.build.version.sdk"], stdout=sdk)
        mock_adb.register(["adb", "shell", "wm size"], stdout=screen)
        mock_adb.register(["adb", "shell", "dumpsys battery | grep level"], stdout=battery)

    def test_aggregates_all_fields_into_device_info(self, mock_adb: PoisonPillADB) -> None:
        # Arrange
        self._register_device_info_calls(mock_adb)
        ctrl = ADBController()

        # Act
        info = ctrl.get_device_info()

        # Assert
        assert isinstance(info, DeviceInfo)
        assert info.model == "Pixel-Test"
        assert info.android_version == "16"
        assert info.sdk_version == 36
        assert info.screen_size == (1080, 2400)
        assert info.battery_level == 87
        assert info.state == DeviceState.DEVICE

    def test_unparseable_sdk_version_raises_adb_error(self, mock_adb: PoisonPillADB) -> None:
        # Arrange — corrupted property output
        self._register_device_info_calls(mock_adb, sdk="not-a-number")
        ctrl = ADBController()

        # Act + Assert
        with pytest.raises(ADBError, match="Unparseable SDK"):
            ctrl.get_device_info()

    def test_missing_screen_size_returns_zero_zero_not_crash(self, mock_adb: PoisonPillADB) -> None:
        # Arrange — simulate a device that returns garbage from `wm size`
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(["adb", "shell", "wm size"], stdout="(no display)\n")
        ctrl = ADBController()

        # Act
        size = ctrl.get_screen_size()

        # Assert — graceful degradation, no exception
        assert size == (0, 0)


# ---------------------------------------------------------------------------
# Package management
# ---------------------------------------------------------------------------


class TestPackages:
    def test_list_packages_strips_package_prefix(self, mock_adb: PoisonPillADB) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(
            ["adb", "shell", "pm list packages"],
            stdout=(
                "package:com.android.settings\n"
                "package:com.example.app\n"
                "package:com.android.systemui\n"
            ),
        )
        ctrl = ADBController()

        # Act
        pkgs = ctrl.list_packages()

        # Assert
        assert pkgs == [
            "com.android.settings",
            "com.example.app",
            "com.android.systemui",
        ]

    def test_third_party_only_uses_minus_three_flag(self, mock_adb: PoisonPillADB) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(
            ["adb", "shell", "pm list packages -3"],
            stdout="package:com.example.app\n",
        )
        ctrl = ADBController()

        # Act
        pkgs = ctrl.list_packages(third_party_only=True)

        # Assert — verifies flag was passed (Law 2: behaviour observable via call log)
        assert ("adb", "shell", "pm list packages -3") in mock_adb.call_log()
        assert pkgs == ["com.example.app"]

    def test_install_apk_returns_true_on_success(
        self, tmp_path: Path, mock_adb: PoisonPillADB
    ) -> None:
        # Arrange
        apk = tmp_path / "test.apk"
        apk.write_bytes(b"fake-apk")
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(
            ["adb", "install", "-r", str(apk)],
            stdout="Performing Streamed Install\nSuccess\n",
        )
        ctrl = ADBController()

        # Act
        ok = ctrl.install_apk(apk)

        # Assert
        assert ok is True

    def test_install_apk_returns_false_when_adb_errors(
        self, tmp_path: Path, mock_adb: PoisonPillADB
    ) -> None:
        # Arrange
        apk = tmp_path / "test.apk"
        apk.write_bytes(b"fake-apk")
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(
            ["adb", "install", "-r", str(apk)],
            stderr="adb: failed to install: INSTALL_FAILED_INSUFFICIENT_STORAGE",
            returncode=1,
        )
        ctrl = ADBController()

        # Act
        ok = ctrl.install_apk(apk)

        # Assert
        assert ok is False


# ---------------------------------------------------------------------------
# Battery parsing edge cases
# ---------------------------------------------------------------------------


class TestBattery:
    @pytest.mark.parametrize(
        ("dumpsys_output", "expected_level"),
        [
            ("level: 87", 87),
            ("  level: 100", 100),
            ("  level: 0", 0),
            ("level:42", 42),  # no space — adb sometimes does this
        ],
    )
    def test_parses_well_formed_levels(
        self, mock_adb: PoisonPillADB, dumpsys_output: str, expected_level: int
    ) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(["adb", "shell", "dumpsys battery | grep level"], stdout=dumpsys_output)
        ctrl = ADBController()

        # Act + Assert
        assert ctrl.get_battery_level() == expected_level

    def test_returns_zero_when_no_match(self, mock_adb: PoisonPillADB) -> None:
        # Arrange — degraded path: device returns empty string
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(["adb", "shell", "dumpsys battery | grep level"], stdout="")
        ctrl = ADBController()

        # Act + Assert
        assert ctrl.get_battery_level() == 0


# ---------------------------------------------------------------------------
# Convenience input methods — verify keycodes at module API boundary
# ---------------------------------------------------------------------------


class TestKeyEvents:
    @pytest.mark.parametrize(
        ("method", "expected_keycode"),
        [
            ("press_home", 3),
            ("press_back", 4),
            ("press_menu", 82),
            ("press_enter", 66),
            ("press_power", 26),
            ("wake_up", 224),
        ],
    )
    def test_convenience_methods_send_correct_keycode(
        self,
        mock_adb: PoisonPillADB,
        method: str,
        expected_keycode: int,
    ) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(["adb", "shell", f"input keyevent {expected_keycode}"], stdout="")
        ctrl = ADBController()

        # Act
        getattr(ctrl, method)()

        # Assert — confirms the keycode mapping rather than testing implementation
        assert (
            "adb",
            "shell",
            f"input keyevent {expected_keycode}",
        ) in mock_adb.call_log()


class TestScreenshot:
    """screencap output handling, including multi-display warning banners."""

    def test_screenshot_strips_multidisplay_warning_prefix(
        self, mock_adb: PoisonPillADB, tmp_path: Path
    ) -> None:
        # Arrange — foldables print a banner to stdout ahead of the PNG bytes.
        png_body = b"\x89PNG\r\n\x1a\n\x00\x01real-image-bytes"
        banner = b"[Warning] Multiple displays were found...\n"
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(
            ["adb", "exec-out", "screencap", "-p"],
            stdout=banner + png_body,  # type: ignore[arg-type]
        )
        ctrl = ADBController()
        out = tmp_path / "shot.png"

        # Act
        ok = ctrl.screenshot(out)

        # Assert — banner stripped, file is a valid PNG.
        assert ok is True
        assert out.read_bytes() == png_body

    def test_screenshot_fails_cleanly_when_no_png_present(
        self, mock_adb: PoisonPillADB, tmp_path: Path
    ) -> None:
        # Arrange
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(
            ["adb", "exec-out", "screencap", "-p"],
            stdout=b"error: no image",  # type: ignore[arg-type]
        )
        ctrl = ADBController()
        out = tmp_path / "shot.png"

        # Act + Assert — no PNG signature => failure, nothing written.
        assert ctrl.screenshot(out) is False
        assert not out.exists()


# ---------------------------------------------------------------------------
# Shell-injection hardening — identifier allow-list + shlex.quote
# ---------------------------------------------------------------------------


class TestShellInjectionHardening:
    """Caller strings must not be able to break out of the device shell."""

    @pytest.mark.parametrize(
        ("call", "arg"),
        [
            ("clear_data", "com.evil;rm -rf /"),
            ("force_stop", "pkg name"),
            ("start_app", "pkg|nc attacker 1"),
            ("get_property", "ro.prod$(id)"),
        ],
    )
    def test_identifier_methods_reject_shell_metacharacters(
        self, mock_adb: PoisonPillADB, call: str, arg: str
    ) -> None:
        # Arrange — only the construction probe is registered; a rejected call
        # must raise BEFORE it ever shells out (so the poison-pill never fires).
        mock_adb.register(["adb", "version"], stdout="v1\n")
        ctrl = ADBController()

        # Act + Assert
        with pytest.raises(ValueError, match="Invalid"):
            getattr(ctrl, call)(arg)

    def test_set_setting_rejects_unsafe_key(self, mock_adb: PoisonPillADB) -> None:
        mock_adb.register(["adb", "version"], stdout="v1\n")
        ctrl = ADBController()
        with pytest.raises(ValueError, match="Invalid key"):
            ctrl.set_setting("system", "brightness; reboot", "10")

    def test_logcat_rejects_unsafe_tag(self, mock_adb: PoisonPillADB) -> None:
        mock_adb.register(["adb", "version"], stdout="v1\n")
        ctrl = ADBController()
        with pytest.raises(ValueError, match="Invalid logcat tag"):
            ctrl.logcat(filter_tag='Tag" ; rm -rf /')

    def test_valid_identifier_still_accepted(self, mock_adb: PoisonPillADB) -> None:
        # A well-formed dotted package name must pass through unchanged.
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(["adb", "shell", "pm clear com.example.app"], stdout="Success\n")
        ctrl = ADBController()
        assert ctrl.clear_data("com.example.app") is True

    def test_path_argument_is_shell_quoted(self, mock_adb: PoisonPillADB) -> None:
        # A path containing a space is quoted so the device shell keeps it one arg.
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(["adb", "shell", "ls -la '/sdcard/my dir'"], stdout="")
        ctrl = ADBController()
        ctrl.ls("/sdcard/my dir")  # must not raise UnmockedADBCallError

    def test_input_text_is_shell_quoted(self, mock_adb: PoisonPillADB) -> None:
        # Multi-word text is shlex-quoted rather than passed with broken escaping.
        mock_adb.register(["adb", "version"], stdout="v1\n")
        mock_adb.register(["adb", "shell", "input text 'hello world'"], stdout="")
        ctrl = ADBController()
        ctrl.input_text("hello world")  # must not raise UnmockedADBCallError
