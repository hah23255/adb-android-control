"""Watch ADB/Wi-Fi state over time and react to changes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

import contextlib
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

# _sleep indirection for test patching.
_sleep: Callable[[float], None] = time.sleep


@dataclass(frozen=True)
class ConnectionState:
    """ADB+Wi-Fi state at a moment in time."""

    timestamp: str
    connected: bool
    ip: str
    port: int
    ssid: str
    rssi_dbm: int
    frequency_mhz: int


class ChangeType(Enum):
    """State transitions ``detect_changes`` can report."""

    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    PORT_CHANGED = "PORT_CHANGED"
    NETWORK_CHANGED = "NETWORK_CHANGED"
    WIFI_CHANGED = "WIFI_CHANGED"
    SIGNAL_CHANGED = "SIGNAL_CHANGED"


@dataclass(frozen=True)
class Change:
    """A change between two states."""

    kind: ChangeType
    detail: str


# RSSI delta (dB) above which a signal change is considered "significant"
SIGNAL_CHANGE_DB_THRESHOLD = 10


def _diff_connectivity(last: ConnectionState, current: ConnectionState) -> Change | None:
    """Connectivity transition (dis/connected, port, network)."""
    if last.connected and not current.connected:
        return Change(ChangeType.DISCONNECTED, f"Lost connection to {last.ip}:{last.port}")
    if not last.connected and current.connected:
        return Change(ChangeType.CONNECTED, f"{current.ip}:{current.port}")
    if current.connected and last.port != current.port:
        return Change(ChangeType.PORT_CHANGED, f"{last.port} → {current.port}")
    if current.connected and last.ip != current.ip:
        return Change(ChangeType.NETWORK_CHANGED, f"{last.ip} → {current.ip}")
    return None


def _diff_network(last: ConnectionState, current: ConnectionState) -> Change | None:
    """Wi-Fi network change."""
    if last.ssid != current.ssid and current.ssid != "Unknown":
        return Change(ChangeType.WIFI_CHANGED, f"{last.ssid} → {current.ssid}")
    return None


def _diff_signal(
    last: ConnectionState, current: ConnectionState, *, threshold_db: int
) -> Change | None:
    """Signal-strength change beyond the threshold."""
    if abs(last.rssi_dbm - current.rssi_dbm) > threshold_db:
        return Change(
            ChangeType.SIGNAL_CHANGED,
            f"{last.rssi_dbm}dB → {current.rssi_dbm}dB",
        )
    return None


def detect_changes(
    last: ConnectionState | None,
    current: ConnectionState,
    *,
    signal_threshold_db: int = SIGNAL_CHANGE_DB_THRESHOLD,
) -> list[Change]:
    """Diff two states into :class:`Change` items."""
    if last is None:
        if current.connected:
            return [Change(ChangeType.CONNECTED, f"{current.ip}:{current.port}")]
        return []

    changes: list[Change] = []
    for diff in (
        _diff_connectivity(last, current),
        _diff_network(last, current),
        _diff_signal(last, current, threshold_db=signal_threshold_db),
    ):
        if diff is not None:
            changes.append(diff)
    return changes


def parse_adb_devices(output: str) -> tuple[bool, str, int]:
    """Parse ``adb devices`` into ``(connected, ip, port)``."""
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
    """Run ``adb devices``; sane defaults on failure."""
    try:
        result = subprocess.run(
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
        result = subprocess.run(
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


def termux_notifier(title: str, message: str) -> None:
    """Notify via ``termux-notification``; silent on failure."""
    with contextlib.suppress(FileNotFoundError, subprocess.TimeoutExpired):
        subprocess.run(
            [
                "termux-notification",
                "-t",
                title,
                "-c",
                message,
                "--priority",
                "high",
            ],
            timeout=5,
            check=False,
        )


def null_notifier(_title: str, _message: str) -> None:
    """No-op notifier for tests."""


# Change kinds that should trigger a user-facing notification by default
_NOTIFY_ON_KINDS: frozenset[ChangeType] = frozenset(
    {ChangeType.DISCONNECTED, ChangeType.PORT_CHANGED, ChangeType.NETWORK_CHANGED}
)


class ConnectionMonitor:
    """Stateful probe comparator over time."""

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
        """Persist ``state`` to ``state_file``."""
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

    def log(self, msg: str) -> None:
        """Log a timestamped line to file and stdout."""
        ts = self._now_fn().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} {msg}"
        print(line)  # noqa: T201
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def get_current_state(self) -> ConnectionState:
        """Compose the current state from probes."""
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

    def update_config(self, ip: str, port: int) -> None:
        """Rewrite matching ``~/.adb_devices`` entries to the new port."""
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

    def check(self) -> list[Change]:
        """Probe, diff, react; return the changes."""
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
        """Continuous loop; stops on KeyboardInterrupt."""
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
