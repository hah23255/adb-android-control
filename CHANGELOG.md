# Changelog

All notable changes to `adb-android-control` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- **Shell-injection hardening in `ADBController`** — caller-supplied identifiers
  (package / activity / property / settings namespace+key / logcat tag) are now
  validated against an allow-list (`_validate_identifier`, `^[A-Za-z0-9._/]+$`) and
  raise `ValueError` before reaching the device shell; free-form path/value/text
  arguments (`ls`, `mkdir`, `rm`, `screen_record`, `set_setting` value, `input_text`,
  `logcat` tag) are `shlex.quote`-d. Previously these were interpolated raw, so a
  crafted argument could execute arbitrary commands on the device. `input_text` also
  replaces broken single-quote escaping with `shlex.quote`. Implements the allow-list
  the v2.0 module security note had deferred. (Salvaged from a branch audit.)

### Added
- `docs/TROUBLESHOOTING.md` — Termux/proot LAN-vs-loopback (`ENOSYS`) guidance and
  runaway reconnect-loop recovery (section C); expanded multi-display screenshot banner
  diagnosis (section G).
- `docs/ERROR_HANDLING.md` — **E060**: corrupt screenshot on multi-display devices, with
  the PNG-signature check and the safe capture-then-pull path.

### Changed
- `PerformanceMonitor` — the four device probe commands (`cpu`, `memory`, `disk`,
  `process-count`) are now module-level constants (`_CPU_PROBE_CMD` &c.) shared by the
  production code and its tests, so the two can no longer silently drift. Prevents the
  regression class behind issue #7 (a fixture/production string mismatch that routed every
  reading to the graceful-degradation `0.0` path). No runtime behavior change.

## [2.0.2] — 2026-07-05 — Packaging, foldable & version-metadata fixes

### Fixed
- **Packaging** — `cli.py` no longer imports from the non-packaged `scripts/`
  directory. The CLI print helpers now live in a new `adb_android_control.cli_helpers`
  module, so `adb-control monitor|radio|connection` work after `pip install` instead of
  raising `ModuleNotFoundError`.
- **Foldable screenshots** — `controller.screenshot()` strips the `[Warning] Multiple
  displays were found` banner that `screencap` prints to stdout ahead of the PNG on
  multi-display devices (e.g. Z Fold7), and fails cleanly when no PNG is present.
- **Version metadata** — `adb_android_control/__init__.py` `__version__` is bumped to
  match `pyproject.toml` and `VERSION` (v2.0.1 shipped with `__version__` still "2.0.0",
  so `adb-control --version` misreported).

### Added
- `docs/DEPLOYMENT.md` — deployment guide with an agent-driven install flow and prompt.
- `PITCH.md` — project executive summary.

## [2.0.1] — 2026-05-06 — Correctness + CI restoration patch

First post-GA patch release. Three landed PRs:

- **#9** — `radio.freq_to_channel` off-grid alignment fix (closes #4)
- **#10** — CI restoration (4 test failures fixed + 70 → 0 ruff errors,
  ruff format applied)
- **#11** — README refresh (stale numbers + project status)

### Fixed
- `radio.freq_to_channel` no longer fabricates channel numbers for
  off-grid Wi-Fi frequencies. Previously, frequencies in the 2.4 GHz
  gap band (2473-2483 MHz) and any non-5-MHz-aligned 5 GHz / 6 GHz
  frequency would return invalid channel numbers (e.g. 13 from 2473,
  15 from 2483, 34 from 5171, 164 from 5824). They now correctly
  return `0` ("unknown"). The function validates input alignment to
  the canonical IEEE 802.11 channel-center grid in addition to the
  per-band frequency range. Closes #4. (#9)
- `monitor.LogcatMonitor.parse_log_line` now accepts any uppercase
  level letter, matching the documented contract for unknown levels.
  (#10)
- `monitor.PerformanceMonitor` CPU probe parser hardened against
  ordering of `top -n 1` output lines. (#10)
- `controller._run` argv mocking pattern documented; two error-class
  tests (`test_device_offline_stderr_raises_device_offline_error`,
  `test_device_unauthorized_also_raises_device_offline_error`)
  realigned with the production "joined-form `shell <cmd>`" contract.
  (#10)

### Changed
- `radio.freq_to_channel` 5 GHz formula simplified from
  `(freq - 5170) // 5 + 34` to the algebraically equivalent
  `(freq - 5000) // 5`, matching the natural 802.11 channel
  convention (`channel = freq / 5 - 1000`) and making alignment
  visible in the source. (#9)
- `radio.freq_to_band` docstring now documents that band
  classification is intentionally permissive (coarser than channel)
  and refers callers to `freq_to_channel` for the strict mapping.
  (#9)
- README: stale test count (273 → 338), test/code ratio
  (1.56:1 → 1.59:1), CLI version example (`1.1.0-rc1` → `2.0.0`),
  project-status table, and pre-GA blurbs corrected. (#11)

### Added
- Alignment-invariant Hypothesis properties for all three Wi-Fi bands
  (`test_24ghz_alignment_invariant`, `test_5ghz_alignment_invariant`,
  `test_6ghz_alignment_invariant`). These replace range-only
  properties whose detection rate on this bug class was 3.4 %; the
  new properties catch every off-grid mis-mapping (100 %). (#9)
- Hand-written gap-band, off-grid, and band-boundary parametrised
  tests in `tests/unit/test_radio.py::TestFrequencyToChannel`. (#9)
- Doctrine lesson "Range-only properties miss alignment bugs" added
  to `docs/TESTING_DOCTRINE.md` § Lessons. (#9)
- Investigation archive at
  `memory/investigations/2026-05-05-freq-to-channel-rca/` documenting
  the issue #4 RCA, expanded scope (60× original estimate), and
  doctrine lesson candidates. (operator workspace, not in repo)

### CI / quality housekeeping (#10)
- Removed all 70 ruff errors on main: 4 introduced by #9 (3 en-dashes
  + 1 mathematical UNION), 66 pre-existing (line-length, import
  ordering, `S108` tmp-path warnings, unused-noqa, etc.).
- Applied `ruff format` repo-wide (23 files reformatted).
- Verified all 6 test-matrix combinations green (3.10 / 3.11 / 3.12 ×
  ubuntu-latest / macos-latest).
- Total tests: 338 (was 273 pre-#9).

## [2.0.0] — 2026-05-05 — Public GA 🚀

First public release after the v1.0.x → v2.0 rebuild. The package is
production-ready: typed, tested, documented, governed.

### Headline numbers
- **9 modules** in `adb_android_control/`, fully type-annotated
- **273+ tests** across unit / property / race directories
- **~1.76 : 1 test/code ratio**
- **mypy --strict** clean with `disallow_any_explicit = true`
- **CI matrix**: Python 3.10 / 3.11 / 3.12 × Linux / macOS
- **Hypothesis property tests** (~10–20K examples per CI run)
- **Race-condition + failure-injection** test suites
- **CodeQL + gitleaks + Dependabot** integrated

### Added since 1.0.x

**Package & CLI**
- Proper Python package at `adb_android_control/` with `py.typed` marker
- Unified `adb-control` console-script (9 subcommands)
- `pip install -e ".[dev]"` workflow for contributors
- Backwards-compat shims at `scripts/*.py` (deprecated; will be removed in v3.0)

**Typed exception hierarchy** (`adb_android_control.controller`)
- `ADBError` (base)
- `ADBNotFoundError`, `DeviceOfflineError`, `ADBTimeoutError`, `ADBPermissionError`

**Test infrastructure**
- Poison-Pill `subprocess.run` mock (`tests/conftest.py::PoisonPillADB`) — fails loud on unmocked argv
- Hypothesis property tests for every pure parser
- Race-condition tests for concurrent monitors and port-scan timing
- Failure-injection test suite covering ADB exit codes 124 / 137 / 13 / TimeoutExpired / FileNotFoundError

**Documentation**
- `README.md` (rewritten with badges, 30-second pitch, Mermaid arch diagram)
- `docs/ARCHITECTURE.md` (3 Mermaid diagrams, per-module responsibility table)
- `docs/TESTING_DOCTRINE.md` (project-tailored testing entrypoint with 10 Laws)
- `docs/MIGRATING.md` (1.0 → 1.1 → 2.0 migration paths)
- `docs/TROUBLESHOOTING.md` (12-node Mermaid decision tree)
- `docs/USE_CASES.md` (verified recipes)
- `docs/PERFORMANCE.md` (methodology + baseline targets)
- `SECURITY.md` (threat model + disclosure SLAs + CVE policy)
- `CONTRIBUTING.md` (doctrine-aligned workflow, Conventional Commits)

**CI & governance**
- `.github/workflows/ci.yml` — 6-cell test matrix, lint, typecheck, gitleaks,
  build, Codecov upload, Law 1 PR gate (`test-file-integrity`)
- `.github/workflows/codeql.yml` — Python security-extended + security-and-quality
- `.github/workflows/property-nightly.yml` — Hypothesis deep-fuzz
  (`max_examples=1000`)
- `.github/dependabot.yml` — pip + Actions weekly, grouped
- `.github/PULL_REQUEST_TEMPLATE.md` — 10-Law doctrine checklist
- `.github/ISSUE_TEMPLATE/{bug,feature,config}.yml` — structured forms with
  PII-scrubbing requirement
- `.github/CODEOWNERS` — high-blast-radius paths flagged
- `.pre-commit-config.yaml` — ruff, mypy, gitleaks, markdownlint

**Visual**
- Logo SVG (512×512) + OpenGraph banner SVG (1280×640)
- 3 VHS `.tape` recipes for demo GIFs (quickstart / monitor / reconnect)
- Design-tokens reference

**Security**
- Full repo-history rewrite to purge v1.0.0 PII (96 file/commit hits redacted)
- Hardened `.gitignore` patterns
- `device.env.example` template
- Reference-doctrine bundle held privately off-repo

### Changed
- All `subprocess.run` invocations use argv-list form (no `shell=True`)
- timezone-aware UTC `datetime.now(tz=timezone.utc)` throughout
- All public API uses frozen dataclasses for value objects
- WiFiInfo / BluetoothInfo field names now carry units (`rssi_dbm`,
  `frequency_mhz`, `link_speed_mbps`)
- `automation.execute_step` returns typed `StepOutcome` (was `bool | str`)
- `connection_monitor` uses typed `ChangeType` enum (was string tuples)

### Deprecated
- `from scripts.adb_* import *` — use `from adb_android_control.* import *`
- Shims emit `DeprecationWarning` and will be removed in v3.0

### Removed
- Module-level `logging.basicConfig` from library code
- All bare `except:` clauses in production code

### Security
- v1.0.0 device.env PII leak fully purged from history (v1.0.1 release)
- gitleaks pre-commit + CI gate prevents recurrence

## [1.1.0-rc1] — 2026-05-05 (private)

### Added
- **Testing Doctrine** (HH directive 2026-03-05) installed as the
  canonical testing methodology. Project entrypoint at
  `docs/TESTING_DOCTRINE.md`. Reference bundle held privately
  off-repo.
- **Python package layout**: all runtime code now lives in
  `adb_android_control/` as a proper installable package with strict
  type hints throughout.
- **Typed exception hierarchy** in `controller.py`:
  - `ADBError` (base)
  - `ADBNotFoundError` — adb binary missing
  - `DeviceOfflineError` — device offline / unauthorized
  - `ADBTimeoutError` — command timeout
  - `ADBPermissionError` — permission denied
- **Public `ADBController.shell()`** — replaces inter-module reliance on
  the private `_shell` (Doctrine Law 2).
- **205 unit tests** across 7 test files using the Poison-Pill subprocess
  mock, `freezegun`, and `spec_set` MagicMock injection (see commits
  `8880d15`, `de51abc`, `facc2e1`, `b4da9c3`, `fb6de6c`, `4156899`).
- **Frozen value objects** throughout: `DeviceInfo`, `LogEntry`,
  `PerformanceSnapshot`, `CrashEvent`, `AutomationStep`, `StepOutcome`,
  `AutomationResult`, `InstallAndLaunchResult`, `WiFiInfo`, `BluetoothInfo`,
  `ConnectionState`, `Change`, `USBDeviceInfo`.
- **Pure-function extraction** for parsers and converters — `freq_to_channel`,
  `freq_to_band`, `rssi_to_quality`, `parse_log_line`, `parse_wifi_info`,
  `parse_scan_results`, `parse_bluetooth_info`, `parse_bluetooth_devices`,
  `parse_link_stats`, `parse_adb_devices`, `detect_changes`,
  `parse_device_descriptor`, `rewrite_devices_config`.
- **Dependency injection** across all classes for test substitutability:
  `adb=ADBController`, `notifier`, `adb_status_fn`, `wifi_info_fn`,
  `now_fn`, `check_port_fn`, `adb_connect_fn`, etc.
- **Python toolchain**: `pyproject.toml` with strict pytest, ruff, mypy,
  hypothesis, freezegun, import-linter, vulture, pdoc; pre-commit hooks
  with gitleaks (re-prevents the v1.0.0 PII incident class).
- **`ChangeType` enum** in `connection_monitor.py` — typed transitions
  replace the v1.0.0 string-tuple events.
- **`StepOutcome` typed result** in `automation.py` — replaces the
  v1.0.0 `bool | str` union.

### Changed
- `monitor.py` `parse_log_line` and `is_crash_entry` are now `@staticmethod`
  pure predicates — directly testable.
- `automation.py` step dispatch is now a dict-of-handlers instead of a
  long `if/elif` chain.
- `radio.py` field names now carry units: `rssi_dbm`, `frequency_mhz`,
  `link_speed_mbps`, etc.
- `connection_monitor.py` paths, notifier, and probes are all injectable.
- All `subprocess.run` invocations use argv lists; `shell=True` removed
  everywhere (security hardening).
- timezone-aware UTC `datetime.now(tz=timezone.utc)` replaces naive
  timestamps (Doctrine Law 8 — determinism).
- `scripts/*.py` reduced to deprecation shims (will be removed in v2.0).

### Deprecated
- `from scripts.adb_controller import ...` — use
  `from adb_android_control import ...`. Shim emits `DeprecationWarning`.
- Same for `scripts.adb_monitor`, `scripts.adb_automation`,
  `scripts.radio_scan`, `scripts.connection_monitor`,
  `scripts.adb_port_scan`, `scripts.usb_identify`, `scripts.usb_info`.

### Removed
- Module-level `logging.basicConfig(...)` from library code (was a
  side-effect-on-import hazard).
- Bare `except:` everywhere — replaced with specific exceptions or
  documented Lesson-41 graceful-degradation `except Exception:` with
  inline rationale.

### internal lesson (PII pre-commit gate) logged
- **2026-05-05** — `device.env` PII leak (96 file/commit hits across
  v1.0.0 history). Mitigation: `git filter-repo` purge + tightened
  `.gitignore` patterns + `gitleaks` pre-commit hook. Recorded in
  `docs/TESTING_DOCTRINE.md` under "Lessons Extracted from Real Failures".

## [1.0.1] — 2026-05-05

### Security
- **CRITICAL**: Purged personally-identifying device data from full repo
  history (96 file/commit hits) via `git filter-repo`. Categories
  redacted: device serial, Android ID, WiFi BSSID + SSID, Bluetooth name,
  internal IPs across two networks, full device fingerprint.
- Added `device.env.example` template with explicit "never commit"
  warnings on geolocation-sensitive fields.
- Hardened `.gitignore` with `device.env`, `*.env` (with `!*.env.example`
  exception), `LOGBOOK.md`, `private/`, `personal/` patterns.

### Note
- This release **rewrites repo history**. All commit SHAs prior to
  v1.0.1 are gone. Forks and clones must rebase or re-clone.
- Force-push does not retroactively redact GitHub's archival caches or
  third-party mirrors — leaked data should be considered permanently
  public regardless of this release.

## [1.0.0] — 2025-12-25

### Added
**Core Functionality:**
- Complete ADB command reference in SKILL.md
- App management (install, uninstall, list, clear data, force stop)
- File operations (push, pull, ls, mkdir, rm)
- Screen control (screenshot, screen recording)
- Input simulation (tap, swipe, text, key events)
- Shell access and command execution
- Logcat viewing and filtering
- Device info retrieval (battery, memory, storage, props)
- System settings manipulation

**Python Scripts:**
- `adb_controller.py` — main controller (~450 LOC)
- `adb_automation.py` — workflow automation and app testing (~425 LOC)
- `adb_monitor.py` — real-time monitoring (~430 LOC)

**Reference Documentation:**
- Complete key event codes reference (100+ keycodes)
- Troubleshooting guide for common issues
- Automation workflow examples

**Automation Features:**
- AppTester class for automated app testing
- DeviceManager for health checks and cleanup
- PerformanceMonitor for real-time metrics
- LogcatMonitor for log streaming
- CrashMonitor for crash detection

### Wireless ADB Support
- Full wireless debugging support
- Pairing and connection management
- Auto-reconnect capabilities

### Known Limitations (v1.0.0 — addressed in 1.1.0)
- ~~No tests~~ → 205 unit tests in 1.1.0
- ~~No type checking~~ → strict mypy in 1.1.0
- ~~`shell=True` in some scripts~~ → argv-only in 1.1.0
- ~~`bool | str` mixed return type in `_execute_step`~~ → typed
  `StepOutcome` in 1.1.0
- ~~`_shell` private-access in monitor / automation~~ → public
  `shell()` in 1.1.0

### Planned for v2.0
- UI element detection and interaction
- OCR-based text recognition
- Multi-device support
- Workflow recording and playback
- Removal of `scripts/*.py` shims (deprecated in 1.1.0)
