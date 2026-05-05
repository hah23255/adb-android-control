# Security Policy

## Reporting a vulnerability

Please report security-relevant issues **privately** via:

- **GitHub Security Advisories** (preferred):
  <https://github.com/hah23255/adb-android-control/security/advisories/new>
- Email: open a private issue with a "[security]" prefix or contact
  the maintainer directly.

**Do not file a public issue for vulnerabilities.** We aim to:

- Acknowledge receipt within **72 hours**.
- Triage and assess within **7 days**.
- Ship a fix within **30 days** for High/Critical or **90 days**
  for Medium.

## Threat model

`adb-android-control` operates in a privileged position relative to
the connected Android device — it can install apps, read files,
take screenshots, simulate input, and dump system properties. This
section enumerates what it does NOT defend against, so you can
calibrate your usage.

### In scope (we DO defend against)

| Threat | Mitigation |
|---|---|
| **PII leakage to git** | `gitleaks` pre-commit hook (post-Lesson-48) blocks committing `device.env` or any file matching the leaked-token patterns. `.gitignore` whitelist with `!*.env.example`. |
| **Shell injection on the host** | All `subprocess.run` invocations use argv-list form (no `shell=True`). Audited end-to-end during Phase 2. |
| **Untrusted ADB stdout** | Every parser returns `None` / `[]` / `0` on malformed input rather than raising (internal lesson (adaptive fault tolerance)). Hypothesis-fuzzed for crashes. |
| **Stale state-file corruption** | `ConnectionMonitor` falls back to `last_state=None` on any JSON-decode error rather than crashing. |
| **Stale process handles** | `LogcatMonitor.stop()` + `EventMonitor.stop()` are idempotent and tested for double-call safety. |

### Out of scope (we do NOT defend against)

| Threat | Why not | Caller responsibility |
|---|---|---|
| **Shell injection on the device** | Several methods (e.g. `clear_data`, `force_stop`, `get_property`, `set_setting`, `start_activity`) interpolate caller-supplied strings into shell commands that run *on the device*. If you pass attacker-controlled input here, the attacker gets arbitrary device-shell execution. | Validate package names, property keys, and similar identifiers against an allow-list before passing them in. A future version (Phase 2 of v2.0) will tighten this with a typed `PackageName` newtype. |
| **Malicious `adb` binary on PATH** | We trust the `adb` binary we shell out to. A compromised `adb` on PATH could exfiltrate any data it reads. | Audit your install. Consider pinning `adb` to a known location and using `--adb-path` (forthcoming) or an absolute path. |
| **Network MITM on wireless ADB** | ADB-over-TCP (pre-Android 9) is unencrypted. ADB-over-TLS (Android 9+) uses Conscrypt but trust-on-first-use. | Only use wireless debugging on networks you control. Pair freshly per session if uncertain. |
| **Termux-API responses** | We trust `termux-wifi-connectioninfo` / `termux-notification`. A compromised Termux app could feed us bogus data. | Standard Android app-isolation guarantees apply. Audit your Termux install. |
| **Side-channel timing** | The package makes no defense against timing-attack-style observation of which devices/packages are queried. | Not relevant for typical use cases. |

## Known limitations

- **No signed releases.** Releases on GitHub are not currently signed
  with GPG. Verify integrity via the release page's SHA hashes if
  paranoid.
- **No reproducible builds.** Source-only distribution; pure Python.
  Use `pip install --hash ...` against the PyPI artifact (forthcoming
  in Phase 7) for hash pinning.
- **Pre-1.0 PII leak.** `v1.0.0` shipped a `device.env` containing
  real device identifiers and Wi-Fi BSSID. The full history was
  rewritten via `git filter-repo` in v1.0.1, but: GitHub's archival
  caches and third-party mirrors may retain the leaked blobs. Treat
  the v1.0.0 BSSID/SSID/serial as permanently public. See
  [`docs/TESTING_DOCTRINE.md`](./docs/TESTING_DOCTRINE.md) internal lesson (PII pre-commit gate).

## Disclosure history

| Date | Issue | Resolution |
|---|---|---|
| 2026-05-05 | `v1.0.0` `device.env` PII leak (96 file/commit hits across 8 commits) | `v1.0.1` history rewrite + `gitleaks` pre-commit + `.gitignore` hardening |

## CVE assignment

We will request CVE assignment via GitHub Security Advisories for
any externally-reportable vulnerability. Internal hardening commits
(like internal lesson (PII pre-commit gate)) are not normally CVE-tracked unless they affect
downstream consumers of a released artifact.
