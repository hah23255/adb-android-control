"""Unit tests for :mod:`adb_android_control.cli`.

Doctrine: AAA (Law 3); the CLI is glue — we test that argparse plumbing
routes correctly and that ``main()`` exits with the subcommand's return
code. Subcommand bodies are tested in their own module's test file.
"""

from __future__ import annotations

import argparse

import pytest

from adb_android_control import __version__
from adb_android_control.cli import build_parser, main

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Argparse layout
# ---------------------------------------------------------------------------


class TestArgparseLayout:
    def test_parser_has_all_documented_subcommands(self) -> None:
        # Arrange + Act
        parser = build_parser()

        # Assert — drill into the subparsers action to enumerate
        sub_actions = [
            a for a in parser._actions if isinstance(a, argparse._SubParsersAction)  # noqa: SLF001
        ]
        assert sub_actions, "Parser must have a subparsers action"
        choices = set(sub_actions[0].choices.keys())
        assert choices == {
            "devices",
            "info",
            "shot",
            "monitor",
            "workflow",
            "health",
            "radio",
            "connection",
            "scan-port",
        }

    def test_version_flag_prints_package_version(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Arrange + Act + Assert
        with pytest.raises(SystemExit) as excinfo:
            build_parser().parse_args(["--version"])
        assert excinfo.value.code == 0
        captured = capsys.readouterr()
        assert __version__ in captured.out

    @pytest.mark.parametrize(
        ("argv", "expected_command"),
        [
            (["devices"], "devices"),
            (["info"], "info"),
            (["shot"], "shot"),
            (["shot", "/tmp/x.png"], "shot"),
            (["health"], "health"),
            (["radio", "wifi", "scan"], "radio"),
            (["scan-port", "10.0.0.1"], "scan-port"),
            (["scan-port", "10.0.0.1", "--start", "5550", "--end", "5560"], "scan-port"),
            (["monitor", "logcat"], "monitor"),
            (["monitor", "perf", "--interval", "2.5"], "monitor"),
            (["workflow", "/tmp/wf.json"], "workflow"),
            (["connection"], "connection"),
            (["connection", "check"], "connection"),
        ],
    )
    def test_subcommand_parsing_routes_to_correct_command(
        self, argv: list[str], expected_command: str
    ) -> None:
        # Arrange
        parser = build_parser()

        # Act
        ns = parser.parse_args(argv)

        # Assert
        assert ns.command == expected_command
        assert callable(ns.func)

    def test_serial_flag_is_global(self) -> None:
        # Arrange
        parser = build_parser()

        # Act
        ns = parser.parse_args(["-s", "EMULATOR-1", "devices"])

        # Assert
        assert ns.serial == "EMULATOR-1"
        assert ns.command == "devices"

    def test_verbose_flag_count_accumulates(self) -> None:
        # Arrange
        parser = build_parser()

        # Act
        ns_one = parser.parse_args(["-v", "devices"])
        ns_two = parser.parse_args(["-vv", "devices"])

        # Assert
        assert ns_one.verbose == 1
        assert ns_two.verbose == 2


# ---------------------------------------------------------------------------
# main() exit-code routing
# ---------------------------------------------------------------------------


class TestMainExitCodes:
    def test_main_exits_with_subcommand_return_code(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange — install a fake subcommand handler
        from adb_android_control import cli

        def _fake_devices(_args: argparse.Namespace) -> int:
            return 7

        monkeypatch.setattr(cli, "cmd_devices", _fake_devices)

        # Act + Assert — must exit with code 7
        with pytest.raises(SystemExit) as excinfo:
            main(["devices"])
        assert excinfo.value.code == 7

    def test_main_exits_3_on_adb_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Arrange
        from adb_android_control import cli
        from adb_android_control.controller import ADBError

        def _raise_adb_error(_args: argparse.Namespace) -> int:
            raise ADBError("device offline")

        monkeypatch.setattr(cli, "cmd_devices", _raise_adb_error)

        # Act + Assert
        with pytest.raises(SystemExit) as excinfo:
            main(["devices"])
        assert excinfo.value.code == 3
        captured = capsys.readouterr()
        assert "device offline" in captured.err

    def test_main_exits_130_on_keyboard_interrupt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange — Ctrl-C semantics: exit 130 (128 + SIGINT)
        from adb_android_control import cli

        def _raise_interrupt(_args: argparse.Namespace) -> int:
            raise KeyboardInterrupt

        monkeypatch.setattr(cli, "cmd_devices", _raise_interrupt)

        # Act + Assert
        with pytest.raises(SystemExit) as excinfo:
            main(["devices"])
        assert excinfo.value.code == 130
