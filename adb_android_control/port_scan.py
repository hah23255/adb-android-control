"""ADB wireless-debug port scanner."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

import concurrent.futures
import logging
import socket
import subprocess

logger = logging.getLogger(__name__)


def check_port(ip: str, port: int, *, timeout_s: float = 0.5) -> bool:
    """True if ``ip:port`` accepts a TCP connection."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout_s)
            return sock.connect_ex((ip, port)) == 0
    except OSError:
        return False


def device_is_online(ip: str, port: int, *, timeout_s: int = 3) -> bool:
    """True if the device is online."""
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == f"{ip}:{port}" and parts[1] == "device":
            return True
    return False


def try_adb_connect(ip: str, port: int, *, timeout_s: int = 3) -> bool:
    """Connect and verify online."""
    try:
        result = subprocess.run(
            ["adb", "connect", f"{ip}:{port}"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    if "connected" not in result.stdout.lower():
        return False
    return device_is_online(ip, port, timeout_s=timeout_s)


def rewrite_devices_config(content: str, *, name: str, ip: str, port: int) -> str:
    """Rewrite the ``{name}=`` line to ``ip:port``."""
    new_lines: list[str] = []
    for line in content.split("\n"):
        if line.startswith(f"{name}="):
            new_lines.append(f"{name}={ip}:{port}")
        else:
            new_lines.append(line)
    return "\n".join(new_lines)


def rewrite_devices_ip(content: str, *, name: str, ip: str) -> str:
    """Rewrite the ``{name}=`` line to ``ip``."""
    new_lines: list[str] = []
    for line in content.split("\n"):
        if line.startswith(f"{name}="):
            new_lines.append(f"{name}={ip}")
        else:
            new_lines.append(line)
    return "\n".join(new_lines)


class PortScanner:
    """Fan out port checks, probe for ADB."""

    def __init__(
        self,
        *,
        check_port_fn: Callable[[str, int], bool] = check_port,
        adb_connect_fn: Callable[[str, int], bool] = try_adb_connect,
        max_workers: int = 100,
    ) -> None:
        self._check_port = check_port_fn
        self._adb_connect = adb_connect_fn
        self._max_workers = max_workers

    def find_open_ports(self, ip: str, *, start: int, end: int) -> list[int]:
        """Open TCP ports in ``[start, end]``."""
        if start > end:
            return []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = {executor.submit(self._check_port, ip, p): p for p in range(start, end + 1)}
            return sorted(
                futures[future]
                for future in concurrent.futures.as_completed(futures)
                if future.result()
            )

    def find_adb_port(self, ip: str, *, start: int = 30000, end: int = 50000) -> int:
        """Find an ADB port in ``[start, end]``; 0 if none."""
        logger.info("Scanning %s ports %d-%d", ip, start, end)
        for port in self.find_open_ports(ip, start=start, end=end):
            if self._adb_connect(ip, port):
                return port
        return 0


def connect_auto(
    ip: str,
    *,
    hint_port: int | None = None,
    start: int = 30000,
    end: int = 50000,
    max_workers: int = 100,
) -> int:
    """Connect to ``ip`` via a discovered ADB port."""
    if hint_port is not None and try_adb_connect(ip, hint_port):
        return hint_port
    scanner = PortScanner(max_workers=max_workers)
    for port in scanner.find_open_ports(ip, start=start, end=end):
        if try_adb_connect(ip, port):
            return port
    return 0


def update_devices_file(
    config_file: Path,
    *,
    name: str,
    ip: str,
    port: int,
) -> None:
    """Rewrite the ``{name}=`` entry to ``ip:port``."""
    if not config_file.exists():
        return
    content = config_file.read_text(encoding="utf-8")
    config_file.write_text(
        rewrite_devices_config(content, name=name, ip=ip, port=port),
        encoding="utf-8",
    )


def update_devices_ip(config_file: Path, *, name: str, ip: str) -> None:
    """Rewrite the ``{name}=`` entry to ``ip``."""
    if not config_file.exists():
        return
    content = config_file.read_text(encoding="utf-8")
    config_file.write_text(
        rewrite_devices_ip(content, name=name, ip=ip),
        encoding="utf-8",
    )


def save_last_port(state_file: Path, port: int) -> None:
    """Persist the last-found ADB port."""
    state_file.write_text(str(port), encoding="utf-8")


def read_last_port(state_file: Path) -> int | None:
    """Read the last-found ADB port; ``None`` if missing."""
    if not state_file.exists():
        return None
    try:
        return int(state_file.read_text(encoding="utf-8").strip())
    except ValueError:
        return None
