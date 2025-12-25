#!/data/data/com.termux/files/usr/bin/python3
"""Fast ADB port scanner - finds wireless debugging port after reconnect."""

import socket
import subprocess
import sys
import concurrent.futures
from pathlib import Path

def check_port(ip: str, port: int, timeout: float = 0.5) -> bool:
    """Check if port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except:
        return False

def try_adb_connect(ip: str, port: int) -> bool:
    """Try to connect via ADB."""
    try:
        result = subprocess.run(
            ["adb", "connect", f"{ip}:{port}"],
            capture_output=True, text=True, timeout=3
        )
        return "connected" in result.stdout.lower()
    except:
        return False

def scan_ports(ip: str, start: int = 30000, end: int = 45000) -> int:
    """Scan port range for ADB."""
    print(f"Scanning {ip} ports {start}-{end}...")

    # First find open ports
    open_ports = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_port, ip, p): p for p in range(start, end + 1)}
        for future in concurrent.futures.as_completed(futures):
            port = futures[future]
            if future.result():
                open_ports.append(port)

    print(f"Found {len(open_ports)} open ports, testing ADB...")

    # Test each open port for ADB
    for port in sorted(open_ports):
        if try_adb_connect(ip, port):
            return port

    return 0

def update_config(ip: str, port: int):
    """Update ~/.adb_devices with new port."""
    config_file = Path.home() / ".adb_devices"
    if config_file.exists():
        content = config_file.read_text()
        # Update ZFOLD7 line
        lines = []
        for line in content.split('\n'):
            if line.startswith("ZFOLD7="):
                lines.append(f"ZFOLD7={ip}:{port}")
            else:
                lines.append(line)
        config_file.write_text('\n'.join(lines))

    # Save last port
    (Path.home() / ".adb_last_port").write_text(str(port))

def main():
    ip = sys.argv[1] if len(sys.argv) > 1 else "<DEVICE_IP_HOME>"
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 30000
    end = int(sys.argv[3]) if len(sys.argv) > 3 else 45000

    port = scan_ports(ip, start, end)

    if port:
        print(f"\n✓ ADB found at {ip}:{port}")
        update_config(ip, port)
        print(f"Config updated. Use: adb -s {ip}:{port} shell")
    else:
        print("\n✗ No ADB port found.")
        print("Ensure Wireless Debugging is enabled on device.")

if __name__ == "__main__":
    main()
