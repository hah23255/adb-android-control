"""Unified CLI entrypoint — ``adb-control`` console script."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import argparse
import json
import logging
import sys
from pathlib import Path
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


# Subcommand handlers


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


def _monitor_logcat(args: argparse.Namespace) -> None:
    """Stream logcat to stdout with a level filter."""
    from adb_android_control.cli_helpers import print_log_entry
    from adb_android_control.monitor import LogcatMonitor

    LogcatMonitor(args.serial).stream_logs(print_log_entry, filter_level=args.level)


def _monitor_perf(args: argparse.Namespace) -> None:
    """Print periodic performance snapshots."""
    from adb_android_control.cli_helpers import print_snapshot
    from adb_android_control.monitor import PerformanceMonitor

    PerformanceMonitor(args.serial).start_monitoring(
        interval_s=args.interval, callback=print_snapshot
    )


def _monitor_events(args: argparse.Namespace) -> None:
    """Stream input events."""
    from adb_android_control.monitor import EventMonitor

    EventMonitor(args.serial).start_event_capture()


def _monitor_crash(args: argparse.Namespace) -> None:
    """Watch for crash log entries."""
    from adb_android_control.monitor import CrashEvent, CrashMonitor

    def _on_crash(c: CrashEvent) -> None:
        print(f"!!! CRASH: [{c.tag}] {c.message}")

    CrashMonitor(args.serial).start(callback=_on_crash)


def cmd_monitor(args: argparse.Namespace) -> int:
    # Lazy import to avoid loading threading code unless requested
    if args.mode == "logcat":
        _monitor_logcat(args)
    elif args.mode == "perf":
        _monitor_perf(args)
    elif args.mode == "events":
        _monitor_events(args)
    elif args.mode == "crash":
        _monitor_crash(args)
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
    from adb_android_control.cli_helpers import (
        print_bluetooth_status,
        print_radio_capabilities,
        print_wifi_scan,
        print_wifi_status,
    )
    from adb_android_control.radio import RadioScanner

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
    from adb_android_control.cli_helpers import status as print_status
    from adb_android_control.connection_monitor import ConnectionMonitor

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


def _device_ip_from_config(config: Path, name: str) -> str | None:
    """Read ``name=IP`` from the device config; ``None`` if missing."""
    if not config.exists():
        return None
    for line in config.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(f"{name}="):
            found = line.split("=", 1)[1].strip()
            return found.split(":")[0]  # tolerate a legacy NAME=IP:PORT line
    return None


def _connect_device(config: Path, state: Path, name: str, ip: str, args: argparse.Namespace) -> int:
    """Discover the ADB port, connect, persist state, and print the result."""
    from adb_android_control.port_scan import (
        connect_auto,
        read_last_port,
        save_last_port,
        update_device_entry,
    )

    hint = read_last_port(state)
    port = connect_auto(
        ip,
        hint_port=hint,
        start=args.start,
        end=args.end,
        max_workers=args.workers,
    )
    if port:
        save_last_port(state, port)
        update_device_entry(config, name=name, ip=ip)
        print(f"Connected: {name} at {ip}:{port}")
        return 0
    print(f"No ADB port found on {ip} in {args.start}-{args.end}")
    return 1


def cmd_connect(args: argparse.Namespace) -> int:
    """Discover and connect to a configured device by name."""
    home = Path.home()
    config = home / ".adb_devices"
    state = home / ".adb_last_port"

    ip = args.ip
    if ip is None:
        if not config.exists():
            print(f"Config {config} not found. Run `adb-control add {args.name} IP` first.")
            return 1
        ip = _device_ip_from_config(config, args.name)
        if ip is None:
            print(f"Device '{args.name}' not found in {config}.")
            return 1

    return _connect_device(config, state, args.name, ip, args)


# Argparse wiring


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase verbosity (-v, -vv)"
    )
    parser.add_argument("-s", "--serial", help="Target device serial")


def _add_scan_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start", type=int, default=30000)
    parser.add_argument("--end", type=int, default=50000)


def _add_shot_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("shot", help="Take a screenshot")
    p.add_argument("path", nargs="?", help="Output path (default: screenshot.png)")
    p.set_defaults(func=cmd_shot)


def _add_monitor_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("monitor", help="Real-time monitoring")
    p.add_argument("mode", choices=["logcat", "perf", "events", "crash"])
    p.add_argument(
        "-l",
        "--level",
        default="V",
        choices=["V", "D", "I", "W", "E", "F"],
        help="Logcat level filter (logcat mode only)",
    )
    p.add_argument("-i", "--interval", type=float, default=5.0, help="Perf interval seconds")
    p.set_defaults(func=cmd_monitor)


def _add_workflow_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("workflow", help="Run a JSON workflow")
    p.add_argument("path", help="Path to workflow.json")
    p.set_defaults(func=cmd_workflow)


def _add_radio_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("radio", help="Radio scanner (wifi/bluetooth/caps)")
    p.add_argument("sections", nargs="*", help="One or more of: wifi scan bluetooth caps all")
    p.set_defaults(func=cmd_radio)


def _add_connection_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("connection", help="Connection monitor")
    p.add_argument("subcommand", nargs="?", choices=["status", "check", "run"])
    p.add_argument("-i", "--interval", type=int, default=10)
    p.set_defaults(func=cmd_connection)


def _add_scan_port_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("scan-port", help="Scan an IP for ADB port")
    p.add_argument("ip")
    _add_scan_args(p)
    p.set_defaults(func=cmd_scan_port)


def _add_connect_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("connect", help="Discover and connect a device by name")
    p.add_argument("name", help="Device name from ~/.adb_devices")
    p.add_argument("ip", nargs="?", help="IP override (default: from ~/.adb_devices)")
    _add_scan_args(p)
    p.add_argument("--workers", type=int, default=100, help="Scan threads")
    p.set_defaults(func=cmd_connect)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adb-control",
        description="Comprehensive Android device control via ADB.",
    )
    _add_common_args(parser)

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("devices", help="List connected devices").set_defaults(func=cmd_devices)
    sub.add_parser("info", help="Print device info as JSON").set_defaults(func=cmd_info)
    _add_shot_parser(sub)
    _add_monitor_parser(sub)
    _add_workflow_parser(sub)
    sub.add_parser("health", help="Device health check (JSON)").set_defaults(func=cmd_health)
    _add_radio_parser(sub)
    _add_connection_parser(sub)
    _add_scan_port_parser(sub)
    _add_connect_parser(sub)

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
