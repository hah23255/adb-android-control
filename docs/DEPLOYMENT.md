# Deployment Guide

Getting `adb-android-control` from a checkout to a working install that drives a real
device — on a normal Linux/macOS box, or on-device under Termux (Android/proot).

## Table of Contents
- [Recommended: install with an agent (Claude Code)](#recommended-install-with-an-agent-claude-code)
- [Manual install](#manual-install)
- [Connecting the device](#connecting-the-device)
- [Verification](#verification)
- [Environment gotchas](#environment-gotchas)

---

## Recommended: install with an agent (Claude Code)

**The fastest, most reliable way to install and integrate this toolkit is to hand the job
to a coding agent such as Claude Code.** Installation touches several
environment-specific decisions that an agent resolves dynamically instead of failing on:

- **Isolation / PEP 668** — modern distros refuse `pip install` into the system Python;
  the agent picks `uv tool` / a venv without you debugging an `externally-managed-environment`
  error.
- **Transport quirks** — under Termux/proot, `adb connect 127.0.0.1:<port>` fails
  (`ENOSYS`); the agent connects via the phone's LAN IP instead (see
  [Environment gotchas](#environment-gotchas)).
- **Android 11+ pairing** — the agent walks the pair-then-connect handshake and reads back
  device state, retrying on `offline`.
- **Verification + recovery** — the agent runs real commands against the device, catches
  failures (e.g. the multi-display screenshot banner), and adapts rather than leaving a
  half-working install.

### Steps

1. Install [Claude Code](https://claude.com/claude-code) and open it in the repository.
2. On the phone: **Settings → Developer options → Wireless debugging → ON**, then open
   **"Pair device with pairing code"** and note the IP, pairing port + 6-digit code, and
   the (separate) connect IP:port shown on the main Wireless-debugging screen.
3. Paste the prompt below, filling in those values.

### The prompt

```text
Install and integrate adb-android-control on this system, end to end, and verify it
against my live device. Do it robustly with error-catching — don't leave a half-working
install.

Steps:
1. Install the package so the `adb-control` CLI is on PATH and persists across sessions.
   If system pip is externally-managed (PEP 668), use `uv tool install` (or a venv) — do
   not use --break-system-packages. Install from the `main` branch.
2. Connect my device over wireless debugging:
   - pairing endpoint: <IP>:<PAIR_PORT>   code: <CODE>
   - connect endpoint: <IP>:<CONNECT_PORT>
   Pair first, then connect. If this is a Termux/proot host, connect to the LAN IP, not
   127.0.0.1 (loopback returns ENOSYS in proot). Persist the working endpoint to
   ~/.adb_devices so it auto-reconnects.
3. Verify end-to-end: `adb-control devices`, `info`, `health`, `connection status`, and a
   `shot` screenshot. Confirm the screenshot is a valid PNG. Report any command that
   fails and what you did about it.
4. Summarize final state: install location, CLI version, device state, and anything left
   for me to do (e.g. push, tests).
```

The agent will report back with the verified state and any residual follow-ups.

---

## Manual install

### With `uv` (recommended — isolated, persistent, PEP 668-safe)

```bash
# installs the `adb-control` executable into ~/.local/bin (put it on PATH)
uv tool install .            # from a checkout of the branch you want (e.g. main)
adb-control --version
```

### With `pipx`

```bash
pipx install .
```

### Into a virtualenv

```bash
uv venv .venv && . .venv/bin/activate
uv pip install -e ".[dev]"   # dev extras include pytest for running the suite
```

> On Termux/Android and other PEP 668 "externally-managed" environments, do **not**
> `pip install` into the system Python. Use one of the isolated methods above.

`adb` itself must be on `PATH` at runtime (the toolkit shells out to it).

---

## Connecting the device

Android 11+ wireless debugging is a **pair-then-connect** flow (the pairing port and the
connect port are different and both randomized):

```bash
# 1. pair once (endpoint + code from "Pair device with pairing code")
adb pair <IP>:<PAIR_PORT> <CODE>

# 2. connect (endpoint from the main Wireless-debugging screen)
adb connect <IP>:<CONNECT_PORT>

# 3. persist for auto-reconnect
echo "MYDEVICE=<IP>:<CONNECT_PORT>" > ~/.adb_devices
```

The port changes every time Wireless debugging is toggled; `scripts/adb_port_scan.sh`
rediscovers it.

---

## Verification

```bash
adb-control devices              # device listed in `device` (not `offline`) state
adb-control info                 # model / Android / screen / battery JSON
adb-control health               # full health snapshot
adb-control connection status    # ADB + Wi-Fi signal
adb-control shot /tmp/shot.png   # capture — file must start with the PNG signature
```

A good screenshot begins with the bytes `89 50 4E 47` (`\x89PNG`). See
[TROUBLESHOOTING.md](TROUBLESHOOTING.md) → "Screenshot" if it does not.

---

## Environment gotchas

| Symptom | Cause | Resolution |
|---|---|---|
| `pip install` → `externally-managed-environment` | PEP 668 | Use `uv tool` / `pipx` / a venv (above). |
| `adb connect 127.0.0.1:<port>` → `failed ... Function not implemented` | Termux/proot network namespace returns `ENOSYS` on loopback connect | Connect to the phone's **LAN IP** (wlan0), not `127.0.0.1`. |
| adb pegs a CPU core for hours | A stale reconnect target loops forever in proot | `adb disconnect <target>`; if the server is wedged, kill the `adb ... fork-server` PID — it respawns clean. |
| Device shows `offline` after connect | Not paired / unauthorized (Android 11+) | Complete `adb pair` with the code; re-connect. |
| Screenshot file corrupt on a foldable | Multi-display `screencap` prints a warning ahead of the PNG | Handled: `screenshot()` strips any pre-signature bytes (v2.0.0+). |
