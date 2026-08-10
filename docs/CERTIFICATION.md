# Certification

**Certified:** 2026-08-10 · Version 2.0.3 · Commit `pending`
**Result:** ✅ PASS — all gates green, smoke + e2e shakedown complete.

## Test matrix

| Gate | Result |
|---|---|
| Unit tests | 312 passed |
| Full suite (unit + property + race) | 350 passed |
| Import smoke (all 10 modules) | OK |
| CLI smoke (all 9 subcommands) | OK |
| mypy --strict | 0 errors |
| ruff check + format | clean |
| vulture (dead code) | 0 findings |
| Deprecation warnings as errors | 0 warnings |
| Functions > 30 LOC | 0 (213 total) |
| Comments ratio | 7.2% (< 10% target) |
| Build (sdist + wheel) | OK, `uv build` |
| Wheel install + import (fresh venv) | OK |
| Live device e2e (SM-F966B / Android 16) | OK — model, version, SDK 36, battery, serial auto-resolved |

## Known issues found and fixed during certification

1. **`info` reported `"serial": "unknown"`** with a connected device — fixed by auto-resolving the single connected device (`_resolve_serial`).
2. **Installed CLI lagged the repo** (2.0.2 vs 2.0.3) — refreshed via `uv tool install --from . --force`.
3. **`python -m build` fails in-repo** (local `build/` dir shadows the module) — documented: use `uv build`.

## Environment notes (Termux)

- `/tmp` is not writable in the Android sandbox — scratch work uses `~/tmp`.
- Native binaries (claude, kimi) need `glibc-runner -t` for DNS (`/etc/resolv.conf` missing in sandbox).
