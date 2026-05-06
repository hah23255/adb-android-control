"""Unified CLI entrypoint — ``adb-control`` console script.

Wired in ``pyproject.toml``::

    [project.scripts]
    adb-control = "adb_android_control.cli:main"

Subcommand layout::

    adb-control devices              # list connected devices
    adb-control info                 # show device info snapshot
    adb-control shot [PATH]          # take a screenshot
    adb-control monitor MODE         # logcat | perf | events | crash
    adb-control workflow PATH        # run a JSON workflow
    adb-control health               # device-manager health check (JSON)
    adb-control radio [SUBS...]      # wifi/scan/bluetooth/caps (default all)
    adb-control connection [CMD]     # status | check | run [interval]
    adb-control scan-port IP [START] [END]  # scan IP for ADB port
    adb-control --version            # print version
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import argparse
import json
import logging
import sys
from typing import NoReturn

from adb_android_control import __version__
from adb_android_control.controller import ADBController, ADBError


def _setup_logging(verbosity: int) -> None:
    level = logging.WARNING - (verbosity * 10)
    level = max(level, logging.DEBUG)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_devices(args: argparse.Namespace) -> int:
    ctrl = ADBController(device_serial=args.serial)
    devices = ctrl.devices()
    if not devices:
        print("No devices connected.")
        return 1
    for d in devices:
        meta = " ".join(f"{k}={v}" for k, v in d.items() if k not in {"serial", "state"})
        print(f"{d['serial']}\t{d['state']}\t{meta}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    ctrl = ADBController(device_serial=args.serial)
    info = ctrl.get_device_info()
    print(
        json.dumps(
            {
                "serial": info.serial,
                "model": info.model,
                "android_version": info.android_version,
                "sdk_version": info.sdk_version,
                "screen_size": list(info.screen_size),
                "battery_level": info.battery_level,
                "state": info.state.value,
            },
            indent=2,
        )
    )
    return 0


def cmd_shot(args: argparse.Namespace) -> int:
    ctrl = ADBController(device_serial=args.serial)
    path = args.path or "screenshot.png"
    return 0 if ctrl.screenshot(path) else 1


def cmd_monitor(args: argparse.Namespace) -> int:
    # Lazy import to avoid loading threading code unless requested
    from adb_android_control.monitor import (
        CrashEvent,
        CrashMonitor,
        EventMonitor,
        LogcatMonitor,
        PerformanceMonitor,
    )

    if args.mode == "logcat":
        from scripts.adb_monitor import print_log_entry

        LogcatMonitor(args.serial).stream_logs(print_log_entry, filter_level=args.level)
    elif args.mode == "perf":
        from scripts.adb_monitor import print_snapshot

        PerformanceMonitor(args.serial).start_monitoring(
            interval_s=args.interval, callback=print_snapshot
        )
    elif args.mode == "events":
        EventMonitor(args.serial).start_event_capture()
    elif args.mode == "crash":

        def _on_crash(c: CrashEvent) -> None:
            print(f"!!! CRASH: [{c.tag}] {c.message}")

        CrashMonitor(args.serial).start(callback=_on_crash)
    return 0


def cmd_workflow(args: argparse.Namespace) -> int:
    from adb_android_control.automation import ADBAutomation

    auto = ADBAutomation(device_serial=args.serial)
    result = auto.run_from_json(args.path)
    print(
        json.dumps(
            {
                "success": result.success,
                "completed": result.steps_completed,
                "total": result.total_steps,
                "duration_s": result.duration_s,
                "errors": list(result.errors),
                "screenshots": list(result.screenshots),
            },
            indent=2,
        )
    )
    return 0 if result.success else 2


def cmd_health(args: argparse.Namespace) -> int:
    from adb_android_control.automation import DeviceManager

    print(json.dumps(DeviceManager(device_serial=args.serial).health_check(), indent=2))
    return 0


def cmd_radio(args: argparse.Namespace) -> int:
    # Reuse the print helpers in scripts/radio_scan.py — they're CLI-helpers
    from adb_android_control.radio import RadioScanner
    from scripts.radio_scan import (
        print_bluetooth_status,
        print_radio_capabilities,
        print_wifi_scan,
        print_wifi_status,
    )

    scanner = RadioScanner(device_serial=args.serial)
    sections = args.sections or ["all"]
    if "wifi" in sections or "all" in sections:
        print_wifi_status(scanner)
    if "scan" in sections or "all" in sections:
        print_wifi_scan(scanner)
    if "bluetooth" in sections or "bt" in sections or "all" in sections:
        print_bluetooth_status(scanner)
    if "caps" in sections or "all" in sections:
        print_radio_capabilities(scanner)
    return 0


def cmd_connection(args: argparse.Namespace) -> int:
    from adb_android_control.connection_monitor import ConnectionMonitor
    from scripts.connection_monitor import status as print_status

    mon = ConnectionMonitor()
    sub = args.subcommand or "status"
    if sub == "status":
        print_status(mon)
    elif sub == "check":
        for c in mon.check():
            print(f"{c.kind.value}: {c.detail}")
    elif sub == "run":
        mon.run(interval_s=args.interval)
    return 0


def cmd_scan_port(args: argparse.Namespace) -> int:
    from adb_android_control.port_scan import PortScanner

    scanner = PortScanner()
    port = scanner.find_adb_port(args.ip, start=args.start, end=args.end)
    if port:
        print(f"ADB found at {args.ip}:{port}")
        return 0
    print(f"No ADB port found in {args.start}-{args.end} on {args.ip}")
    return 1


# ---------------------------------------------------------------------------
# Argparse wiring
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adb-control",
        description="Comprehensive Android device control via ADB.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase verbosity (-v, -vv)"
    )
    parser.add_argument("-s", "--serial", help="Target device serial")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("devices", help="List connected devices").set_defaults(func=cmd_devices)
    sub.add_parser("info", help="Print device info as JSON").set_defaults(func=cmd_info)

    p_shot = sub.add_parser("shot", help="Take a screenshot")
    p_shot.add_argument("path", nargs="?", help="Output path (default: screenshot.png)")
    p_shot.set_defaults(func=cmd_shot)

    p_mon = sub.add_parser("monitor", help="Real-time monitoring")
    p_mon.add_argument("mode", choices=["logcat", "perf", "events", "crash"])
    p_mon.add_argument(
        "-l",
        "--level",
        default="V",
        choices=["V", "D", "I", "W", "E", "F"],
        help="Logcat level filter (logcat mode only)",
    )
    p_mon.add_argument("-i", "--interval", type=float, default=5.0, help="Perf interval seconds")
    p_mon.set_defaults(func=cmd_monitor)

    p_wf = sub.add_parser("workflow", help="Run a JSON workflow")
    p_wf.add_argument("path", help="Path to workflow.json")
    p_wf.set_defaults(func=cmd_workflow)

    sub.add_parser("health", help="Device health check (JSON)").set_defaults(func=cmd_health)

    p_radio = sub.add_parser("radio", help="Radio scanner (wifi/bluetooth/caps)")
    p_radio.add_argument("sections", nargs="*", help="One or more of: wifi scan bluetooth caps all")
    p_radio.set_defaults(func=cmd_radio)

    p_conn = sub.add_parser("connection", help="Connection monitor")
    p_conn.add_argument("subcommand", nargs="?", choices=["status", "check", "run"])
    p_conn.add_argument("-i", "--interval", type=int, default=10)
    p_conn.set_defaults(func=cmd_connection)

    p_scan = sub.add_parser("scan-port", help="Scan an IP for ADB port")
    p_scan.add_argument("ip")
    p_scan.add_argument("--start", type=int, default=30000)
    p_scan.add_argument("--end", type=int, default=45000)
    p_scan.set_defaults(func=cmd_scan_port)

    return parser


def main(argv: Sequence[str] | None = None) -> NoReturn:
    """Entrypoint. Always calls ``sys.exit`` with the subcommand's return code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    try:
        rc = args.func(args)
    except ADBError as exc:
        print(f"adb-control: error: {exc}", file=sys.stderr)
        sys.exit(3)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    sys.exit(rc)
