# adb-android-control

> Control an Android phone from your computer — or from another phone — over USB or Wi-Fi, with a clean Python API and CLI.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-349-brightgreen.svg)](tests/)
[![Type check](https://img.shields.io/badge/mypy-strict-blue.svg)](pyproject.toml)

**Find this project:** `#adb` · `#android` · `#wireless-debugging` · `#termux` · `#automation` · `#python` · `#foldable` · `#zfold` · `#fold7` · `#samsung` · `#claude-code` · `#folding-phone` · `#phone-automation`

**Languages:** [English](#what-it-does) · [Български](#какво-представлява)

---

## What it does

`adb-android-control` wraps the standard Android `adb` tool in a simple, typed Python package and CLI. Works on:

- **Linux, macOS** — your desktop
- **Termux (Android)** — run it on the phone itself, no PC needed (works great on folding phones like the **Galaxy Z Fold**)

Pairs with **Claude Code** as a skill, but works fine on its own.

## Contents

- [Install](#install)
- [Quick start](#quick-start)
  - [1. Connect a device](#1-connect-a-device)
  - [2. Use the CLI](#2-use-the-cli)
  - [3. Use the Python API](#3-use-the-python-api)
  - [4. Run a workflow](#4-run-a-workflow)
- [Commands](#commands)
- [Auto-reconnect (Termux)](#auto-reconnect-termux)
- [Troubleshooting](#troubleshooting)
- [Why this exists](#why-this-exists)
- [Development](#development)

---

## Install

```bash
pip install adb-android-control        # once published to PyPI
# or from this repo:
pip install -e .
```

As a Claude Code skill:

```bash
git clone https://github.com/hah23255/adb-android-control.git \
    ~/.claude/skills/adb-android-control
claude /plugin marketplace add ~/.claude/skills/adb-android-control
```

You also need `adb` itself (Android platform-tools). On Termux: `pkg install android-tools`.

---

## Quick start

### 1. Connect a device

**USB:**

```bash
adb devices        # tap "Allow" on the phone when it asks
```

**Wi-Fi (Android 11+):**

```bash
adb pair    <phone-ip>:<pair-port>   <pair-code>
adb connect <phone-ip>:<connect-port>
```

The pair code and ports come from *Developer options → Wireless debugging* on the phone.

> The auto-reconnect service (below) finds the current Wi-Fi port automatically, so you never hardcode it.

### 2. Use the CLI

```bash
adb-control devices                  # what's connected
adb-control info                     # model, Android version, battery
adb-control shot                     # take a screenshot
adb-control monitor logcat -l W      # live log stream (W = warnings+)
adb-control monitor crash            # watch for crashes
adb-control radio                    # Wi-Fi + Bluetooth status
adb-control health                   # device health check (JSON)
adb-control workflow ./test.json     # run an automation script
adb-control --version
```

### 3. Use the Python API

```python
from adb_android_control import ADBController

ctrl = ADBController()                        # raises ADBNotFoundError if adb is missing
print(ctrl.devices())                         # list of connected devices
info = ctrl.get_device_info()                 # model, version, battery
print(f"{info.model} on Android {info.android_version}")
ctrl.screenshot("screen.png")
ctrl.tap(500, 800)                            # tap at coordinates
```

### 4. Run a workflow

Workflows are JSON files that run a sequence of actions:

```json
{
  "steps": [
    { "action": "start_app",  "params": {"package": "com.example.app"}, "delay": 3 },
    { "action": "tap_center", "delay": 1 },
    { "action": "screenshot", "params": {"path": "after_tap.png"} }
  ]
}
```

```bash
adb-control workflow my-test.json
```

22 step kinds are available (tap, swipe, type text, open apps, take screenshots, and more) — see `adb_android_control/automation.py`.

---

## Commands

| Command | What it does |
|---|---|
| `adb-control devices` | List connected devices |
| `adb-control info` | Device details as JSON |
| `adb-control shot` | Take a screenshot |
| `adb-control monitor MODE` | Live logcat / performance / events / crash watch |
| `adb-control radio` | Wi-Fi + Bluetooth status |
| `adb-control workflow FILE` | Run a JSON workflow |
| `adb-control health` | Device health check |
| `adb-control connection [status\|check\|run]` | Connection monitor |
| `adb-control scan-port IP` | Find the ADB port on a device |
| `adb-control connect NAME [IP]` | Auto-discover and connect (see below) |

---

## Auto-reconnect (Termux)

On Termux, a small service keeps your device connected in the background:

- `termux/setup.sh ZFOLD7 <phone-ip>` installs the service and a few shell helpers.
- Devices are stored in `~/.adb_devices` as `NAME=IP` — **no port**. The port is re-discovered on every connect, so Wi-Fi port changes never break it.
- Helpers: `adb-connect`, `adb-list`, `adb-add`, `adb-reconnect`.

```bash
./termux/setup.sh ZFOLD7 192.168.0.50
adb-connect
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `adb: command not found` | `adb` not installed | Termux: `pkg install android-tools`. Debian/Ubuntu: `sudo apt install adb`. macOS: `brew install --cask android-platform-tools` |
| Device shows `offline` | Stale ADB state | `adb kill-server && adb start-server`; for Wi-Fi, toggle Wireless debugging off/on |
| Device shows `unauthorized` | Host not trusted yet | Tap "Allow" on the phone; if no prompt: `rm ~/.android/adbkey* && adb kill-server && adb start-server` |
| Screenshot is empty | Old `adb`, or a warning printed before the image | `screenshot()` strips foldable warnings automatically; upgrade `adb` to ≥ 1.0.40 |
| Wi-Fi connection loops under proot | Connecting to `127.0.0.1` | Always use the phone's LAN IP (`wlan0`), never loopback |
| `ADBTimeoutError` | A command took too long | Pass a longer timeout or restart the ADB server |

---

## Why this exists

Most Android automation tools are either:

- **Java/Kotlin libraries** — for building Android apps, not for controlling devices from a host
- **UI-test frameworks** (Appium, uiautomator2) — heavyweight, focused on UI tests
- **Bash scripts around adb** — fragile, hard to test

This project is the simple middle ground: a typed Python wrapper around everything `adb` can do, with clear errors, no `shell=True`, and no hidden state.

---

## Development

```bash
pip install -e ".[dev]"
pytest                       # 349 tests + property-based fuzzing
pytest -m property           # property tests only
pytest -m race               # concurrency tests
pytest --cov                 # coverage report
```

The project follows the **Master Tester Doctrine** — see `docs/TESTING_DOCTRINE.md`. In short: every public method has a test, tests never touch the real `subprocess` (a poison-pill `adb` fixture is used instead), and everything is deterministic.

---

## Български

### Какво представлява

`adb-android-control` обвива стандартния инструмент `adb` на Android в проста, типизирана Python библиотека и CLI. Работи на:

- **Linux, macOS** — на вашия компютър
- **Termux (Android)** — директно на телефона, без компютър

Съвместим е с **Claude Code** като умение (skill), но работи самостоятелно.

### Инсталация

```bash
pip install adb-android-control        # след публикуване в PyPI
# или от това хранилище:
pip install -e .
```

Като Claude Code умение:

```bash
git clone https://github.com/hah23255/adb-android-control.git \
    ~/.claude/skills/adb-android-control
claude /plugin marketplace add ~/.claude/skills/adb-android-control
```

Трябва ви и самият `adb` (Android platform-tools). Под Termux: `pkg install android-tools`.

### Бърз старт

**Свързване по USB:**

```bash
adb devices        # натиснете "Allow" на телефона при подкана
```

**Безжично (Android 11+):**

```bash
adb pair    <ip-на-телефона>:<pair-port>   <pair-code>
adb connect <ip-на-телефона>:<connect-port>
```

Кодът за двойка и портовете се намират в *Опции за разработчици → Безжично отстраняване на грешки* (Wireless debugging).

**CLI:**

```bash
adb-control devices                  # какво е свързано
adb-control info                     # модел, версия на Android, батерия
adb-control shot                     # скрийншот
adb-control monitor logcat -l W      # жив лог поток
adb-control monitor crash            # следене за сривове
adb-control radio                    # статус на Wi-Fi + Bluetooth
adb-control workflow ./test.json     # автоматизационен процес
```

**Python API:**

```python
from adb_android_control import ADBController

ctrl = ADBController()
print(ctrl.devices())
info = ctrl.get_device_info()
ctrl.screenshot("screen.png")
```

### Отстраняване на проблеми

| Проблем | Причина | Решение |
|---|---|---|
| `adb: command not found` | `adb` не е инсталиран | Termux: `pkg install android-tools`. Debian/Ubuntu: `sudo apt install adb`. macOS: `brew install --cask android-platform-tools` |
| Устройството е `offline` | Застояло ADB състояние | `adb kill-server && adb start-server`; при безжична връзка изключете/включете Wireless debugging |
| Устройството е `unauthorized` | Хостът не е одобрен | Натиснете "Allow" на телефона; ако няма подкана: `rm ~/.android/adbkey* && adb kill-server && adb start-server` |
| Празен скрийншот | Стар `adb` или предупреждение преди изображението | `screenshot()` премахва предупрежденията за сгъваеми дисплеи автоматично; обновете `adb` до ≥ 1.0.40 |
| Безкраен цикъл под proot | Свързване към `127.0.0.1` | Винаги ползвайте LAN IP адреса на телефона (`wlan0`), не loopback |
| `ADBTimeoutError` | Командата е отнела твърде дълго | Увеличете timeout или рестартирайте ADB сървъра |

### Разработка

```bash
pip install -e ".[dev]"
pytest                       # 349 теста + property-based fuzzing
pytest --cov                 # отчет за покритие
```

Проектът следва **Доктрината на главния тестер** — вижте `docs/TESTING_DOCTRINE.md`. Накратко: всеки публичен метод има тест, тестовете никога не докосват реалния `subprocess` (използва се специална `adb` фикстура), и всичко е детерминистично.
