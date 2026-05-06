"""Fast ADB port scanner — find the wireless-debugging port after reconnect.

Doctrine note
-------------
- ``check_port`` (TCP socket probe) and ``try_adb_connect`` (subprocess
  invocation) are module-level functions and DI'd into the
  :class:`PortScanner` class so tests substitute fakes (Doctrine Law 5).
- The thread-pool fan-out (``concurrent.futures``) is wrapped so tests
  can inject a synchronous executor.
- ``rewrite_devices_config`` is a pure function: ``(content, ip, port)
  → new_content`` — testable without filesystem.
"""

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


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------


def check_port(ip: str, port: int, *, timeout_s: float = 0.5) -> bool:
    """Return True if a TCP connect to ``ip:port`` succeeds within ``timeout_s``."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout_s)
            return sock.connect_ex((ip, port)) == 0
    except OSError:
        return False


def try_adb_connect(ip: str, port: int, *, timeout_s: int = 3) -> bool:
    """Run ``adb connect ip:port`` and return True on success."""
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
    return "connected" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Pure config rewriter
# ---------------------------------------------------------------------------


def rewrite_devices_config(content: str, *, name: str, ip: str, port: int) -> str:
    """Update lines starting with ``{name}=`` to point at ``{ip}:{port}``.

    Pure function: input string in, output string out. Comments and other
    lines are preserved untouched.
    """
    new_lines: list[str] = []
    for line in content.split("\n"):
        if line.startswith(f"{name}="):
            new_lines.append(f"{name}={ip}:{port}")
        else:
            new_lines.append(line)
    return "\n".join(new_lines)


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


class PortScanner:
    """Fan out port checks across a range, then probe the open ports for ADB."""

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
        """Return the list of TCP ports in ``[start, end]`` accepting connections."""
        if start > end:
            return []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = {executor.submit(self._check_port, ip, p): p for p in range(start, end + 1)}
            return sorted(
                futures[future]
                for future in concurrent.futures.as_completed(futures)
                if future.result()
            )

    def find_adb_port(self, ip: str, *, start: int = 30000, end: int = 45000) -> int:
        """Scan a port range for ADB. Returns the matching port, or 0 if none."""
        logger.info("Scanning %s ports %d-%d", ip, start, end)
        for port in self.find_open_ports(ip, start=start, end=end):
            if self._adb_connect(ip, port):
                return port
        return 0


# ---------------------------------------------------------------------------
# Filesystem helpers (thin wrappers — testable via tmp_path)
# ---------------------------------------------------------------------------


def update_devices_file(
    config_file: Path,
    *,
    name: str,
    ip: str,
    port: int,
) -> None:
    """Update the ``name=`` entry in ``config_file`` to ``ip:port``. No-op if missing."""
    if not config_file.exists():
        return
    content = config_file.read_text(encoding="utf-8")
    config_file.write_text(
        rewrite_devices_config(content, name=name, ip=ip, port=port),
        encoding="utf-8",
    )


def save_last_port(state_file: Path, port: int) -> None:
    """Persist the most-recently-found ADB port for fast reconnect."""
    state_file.write_text(str(port), encoding="utf-8")


def read_last_port(state_file: Path) -> int | None:
    """Read the last-saved ADB port; ``None`` if missing or unparseable."""
    if not state_file.exists():
        return None
    try:
        return int(state_file.read_text(encoding="utf-8").strip())
    except ValueError:
        return None
