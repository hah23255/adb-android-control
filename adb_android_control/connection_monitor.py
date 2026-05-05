"""Watch ADB / Wi-Fi connection state over time and react to changes.

Doctrine note
-------------
- ``detect_changes`` is a pure function: takes two states, returns the
  diff. Doctrine Law 9 — one concept per test target.
- I/O dependencies (state-file read/write, notifications, sleep) are
  injectable via constructor parameters so tests can substitute fakes.
- This module is the **race-condition surface** of the package — Phase 3
  will add Hypothesis property tests and concurrent-state tests here.
- The continuous ``run()`` loop is intentionally not unit-tested in
  this batch; integration coverage lands in Phase 3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

import json
import logging
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Indirections so tests can monkey-patch without touching real time.
_sleep: Callable[[float], None] = time.sleep


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConnectionState:
    """Snapshot of ADB+Wi-Fi state at a moment in time."""

    timestamp: str
    connected: bool
    ip: str
    port: int
    ssid: str
    rssi_dbm: int
    frequency_mhz: int


class ChangeType(Enum):
    """Kinds of state transitions ``detect_changes`` can report."""

    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    PORT_CHANGED = "PORT_CHANGED"
    NETWORK_CHANGED = "NETWORK_CHANGED"
    WIFI_CHANGED = "WIFI_CHANGED"
    SIGNAL_CHANGED = "SIGNAL_CHANGED"


@dataclass(frozen=True)
class Change:
    """A single observed change between two states."""

    kind: ChangeType
    detail: str


# RSSI delta (dB) above which a signal change is considered "significant"
SIGNAL_CHANGE_DB_THRESHOLD = 10


# ---------------------------------------------------------------------------
# Pure detection logic (no I/O — testable in isolation)
# ---------------------------------------------------------------------------


def detect_changes(
    last: ConnectionState | None,
    current: ConnectionState,
    *,
    signal_threshold_db: int = SIGNAL_CHANGE_DB_THRESHOLD,
) -> list[Change]:
    """Compute the list of :class:`Change` items between two states.

    Pure function: no I/O, no clock, no exceptions. Doctrine Law 9.
    """
    changes: list[Change] = []

    if last is None:
        if current.connected:
            changes.append(
                Change(ChangeType.CONNECTED, f"{current.ip}:{current.port}")
            )
        return changes

    if last.connected and not current.connected:
        changes.append(
            Change(
                ChangeType.DISCONNECTED,
                f"Lost connection to {last.ip}:{last.port}",
            )
        )
    elif not last.connected and current.connected:
        changes.append(
            Change(ChangeType.CONNECTED, f"{current.ip}:{current.port}")
        )
    elif current.connected and last.port != current.port:
        changes.append(
            Change(ChangeType.PORT_CHANGED, f"{last.port} → {current.port}")
        )
    elif current.connected and last.ip != current.ip:
        changes.append(
            Change(ChangeType.NETWORK_CHANGED, f"{last.ip} → {current.ip}")
        )

    if last.ssid != current.ssid and current.ssid != "Unknown":
        changes.append(
            Change(ChangeType.WIFI_CHANGED, f"{last.ssid} → {current.ssid}")
        )

    if abs(last.rssi_dbm - current.rssi_dbm) > signal_threshold_db:
        changes.append(
            Change(
                ChangeType.SIGNAL_CHANGED,
                f"{last.rssi_dbm}dB → {current.rssi_dbm}dB",
            )
        )

    return changes


# ---------------------------------------------------------------------------
# adb / termux probes (small, standalone — DI'd in the monitor class)
# ---------------------------------------------------------------------------


def parse_adb_devices(output: str) -> tuple[bool, str, int]:
    """Parse `adb devices` output into ``(connected, ip, port)``.

    Returns ``(False, "", 0)`` if no host:port-style device line is present.
    """
    for line in output.split("\n"):
        if "\tdevice" not in line:
            continue
        addr = line.split("\t")[0]
        if ":" not in addr:
            continue
        ip, port_str = addr.rsplit(":", 1)
        try:
            return True, ip, int(port_str)
        except ValueError:
            continue
    return False, "", 0


def fetch_adb_status(timeout_s: int = 5) -> tuple[bool, str, int]:
    """Run ``adb devices`` and parse the result. Returns sane defaults on failure."""
    try:
        result = subprocess.run(  # noqa: S603, S607
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, "", 0
    if result.returncode != 0:
        return False, "", 0
    return parse_adb_devices(result.stdout)


def fetch_wifi_info(timeout_s: int = 5) -> dict[str, Any]:
    """Call ``termux-wifi-connectioninfo``. Empty dict on failure."""
    try:
        result = subprocess.run(  # noqa: S603, S607
            ["termux-wifi-connectioninfo"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Notifier interface (testable via injection)
# ---------------------------------------------------------------------------


def termux_notifier(title: str, message: str) -> None:
    """Default notifier — invokes ``termux-notification``. Silent on failure."""
    try:
        subprocess.run(  # noqa: S603, S607
            [
                "termux-notification",
                "-t", title,
                "-c", message,
                "--priority", "high",
            ],
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def null_notifier(_title: str, _message: str) -> None:
    """No-op notifier — useful in tests."""


# ---------------------------------------------------------------------------
# Connection monitor
# ---------------------------------------------------------------------------


# Change kinds that should trigger a user-facing notification by default
_NOTIFY_ON_KINDS: frozenset[ChangeType] = frozenset(
    {ChangeType.DISCONNECTED, ChangeType.PORT_CHANGED, ChangeType.NETWORK_CHANGED}
)


class ConnectionMonitor:
    """Stateful monitor that compares each new probe to the previous saved state.

    Paths (config / log / state) and the I/O probes are all injectable
    so tests can drive the monitor with a fake clock, fake subprocess,
    and a tmp_path filesystem.
    """

    def __init__(
        self,
        *,
        config_file: Path | None = None,
        log_file: Path | None = None,
        state_file: Path | None = None,
        notifier: Callable[[str, str], None] = termux_notifier,
        adb_status_fn: Callable[[], tuple[bool, str, int]] = fetch_adb_status,
        wifi_info_fn: Callable[[], dict[str, Any]] = fetch_wifi_info,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        home = Path.home()
        self.config_file: Path = config_file or (home / ".adb_devices")
        self.log_file: Path = log_file or (home / ".adb_monitor.log")
        self.state_file: Path = state_file or (home / ".adb_state.json")
        self.notifier: Callable[[str, str], None] = notifier
        self._adb_status_fn = adb_status_fn
        self._wifi_info_fn = wifi_info_fn
        self._now_fn: Callable[[], datetime] = (
            now_fn if now_fn is not None else (lambda: datetime.now(tz=timezone.utc))
        )
        self.last_state: ConnectionState | None = None
        self._load_state()

    # -- state persistence ---------------------------------------------------

    def _load_state(self) -> None:
        if not self.state_file.exists():
            self.last_state = None
            return
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            self.last_state = ConnectionState(**data)
        except (json.JSONDecodeError, TypeError, ValueError):
            self.last_state = None

    def save_state(self, state: ConnectionState) -> None:
        """Atomically persist ``state`` to ``state_file``."""
        payload = {
            "timestamp": state.timestamp,
            "connected": state.connected,
            "ip": state.ip,
            "port": state.port,
            "ssid": state.ssid,
            "rssi_dbm": state.rssi_dbm,
            "frequency_mhz": state.frequency_mhz,
        }
        self.state_file.write_text(json.dumps(payload), encoding="utf-8")

    # -- logging -------------------------------------------------------------

    def log(self, msg: str) -> None:
        """Append a timestamped line to the log file (and stdout)."""
        ts = self._now_fn().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} {msg}"
        print(line)  # noqa: T201
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    # -- probes --------------------------------------------------------------

    def get_current_state(self) -> ConnectionState:
        """Compose the current ADB+Wi-Fi state from the injected probes."""
        wifi = self._wifi_info_fn()
        connected, ip, port = self._adb_status_fn()
        return ConnectionState(
            timestamp=self._now_fn().isoformat(),
            connected=connected,
            ip=ip,
            port=port,
            ssid=str(wifi.get("ssid", "Unknown")),
            rssi_dbm=int(wifi.get("rssi", 0)),
            frequency_mhz=int(wifi.get("frequency_mhz", 0)),
        )

    # -- config rewrite ------------------------------------------------------

    def update_config(self, ip: str, port: int) -> None:
        """Rewrite ``~/.adb_devices`` to point matching entries at the new port."""
        if not self.config_file.exists():
            return
        content = self.config_file.read_text(encoding="utf-8")
        new_lines: list[str] = []
        for line in content.split("\n"):
            if "=" in line and not line.startswith("#"):
                name, addr = line.split("=", 1)
                if ip in addr:
                    new_lines.append(f"{name}={ip}:{port}")
                    continue
            new_lines.append(line)
        self.config_file.write_text("\n".join(new_lines), encoding="utf-8")

    # -- main check / loop ---------------------------------------------------

    def check(self) -> list[Change]:
        """One probe→detect→react cycle. Returns the changes observed."""
        current = self.get_current_state()
        changes = detect_changes(self.last_state, current)

        for change in changes:
            self.log(f"[{change.kind.value}] {change.detail}")
            if change.kind == ChangeType.PORT_CHANGED and current.connected:
                self.update_config(current.ip, current.port)
                self.log(f"[CONFIG_UPDATED] {current.ip}:{current.port}")
            if change.kind in _NOTIFY_ON_KINDS:
                self.notifier("ADB Monitor", f"{change.kind.value}: {change.detail}")

        self.last_state = current
        self.save_state(current)
        return changes

    def run(self, *, interval_s: int = 10) -> None:
        """Continuous monitor loop — terminates on KeyboardInterrupt."""
        self.log("[MONITOR_START] Connection monitor started")
        self.notifier("ADB Monitor", "Monitoring started")
        while True:
            try:
                self.check()
                _sleep(interval_s)
            except KeyboardInterrupt:
                self.log("[MONITOR_STOP] Stopped by user")
                break
            except Exception as exc:  # noqa: BLE001 — internal lesson (adaptive fault tolerance)
                self.log(f"[ERROR] {exc}")
                _sleep(interval_s)
