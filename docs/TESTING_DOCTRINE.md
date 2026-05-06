# Testing Doctrine — Project Entrypoint

> **Status:** canonical for this repo. Established 2026-03-05.
> **Scope:** governs all `adb-android-control` test work.
> **Audience:** every human and agent that writes, reviews, or modifies tests.
>
> ⚠️ **The full reference bundle is held privately**, outside this repo,
> as authoritative IP. This file is the project-tailored entrypoint —
> sufficient for day-to-day development. If you need the expanded
> reference material, ask the maintainer.

---

## The 10 Non-Negotiable Laws

1. **Never modify a test to fix CI.** Tests are contracts. Fix the code.
2. **Test behaviour, not implementation.** Public API only.
3. **AAA pattern.** Arrange → Act → Assert. Every test.
4. **DAMP over DRY.** Readability beats brevity in tests.
5. **Isolated tests.** No shared state. Order-independent.
6. **Never mock `subprocess`/`requests` directly.** Use the Poison-Pill
   subprocess mock + `responses` for HTTP.
7. **Ban `# type: ignore` and `cast(Any, …)` in `tests/`.**
8. **Tests must be deterministic.** `freezegun` for time, seeded
   `random.Random(seed=42)`, no real network.
9. **One logical concept per test.**
10. **No tautological tests.** Test business logic, not language mechanics.

## The Oath

> *"I do not test to achieve a percentage. I test to sleep soundly. I assume
> the network is hostile, the user is chaotic, and time is an illusion. My
> tests are the unbreakable contract between the present codebase and its
> future self."*

---

## Python tooling map

| Pattern (canonical) | Python / pytest equivalent |
|---|---|
| Test runner | `pytest` |
| Mock library | `unittest.mock.MagicMock(spec=…)`, `pytest-mock` |
| HTTP mocking | `responses` |
| Subprocess mocking (Law 6) | Poison-Pill `mock_adb` fixture in `tests/conftest.py` |
| Property-based fuzzing | `hypothesis` |
| Strict-mock pattern | `MagicMock(spec=…, spec_set=True)` + descriptive raise on unmocked access |
| Time control | `freezegun` |
| Architectural-boundary linter | `import-linter` |
| Dead-code detector | `vulture` |
| Type-level tests | `assert_type` (Python 3.11+) / `mypy --strict` |
| Ban Any annotations | `mypy --strict` + `disallow_any_explicit = true` + ruff `ANN401` |

---

## Enforcement Map

| Law | Status | Mechanism |
| --- | --- | --- |
| 1   | ✅ **CI-enforced** | `.github/workflows/ci.yml::test-file-integrity` blocks PRs that modify `tests/**/*.py` |
| 2   | 🟡 Convention | Reviewer-enforced. |
| 3   | 🟡 Convention | Reviewer-enforced. AAA marked via section comments in test bodies. |
| 4   | 🟡 Convention | Reviewer-enforced. |
| 5   | ✅ **Enforced** | `pytest-randomly` random order; `tmp_path` per fs test; frozen value objects |
| 6   | ✅ **Enforced** | Poison-Pill `mock_adb` fixture; `subprocess.run` is monkey-patched per-test |
| 7   | ✅ **Enforced** | `mypy --strict` with `disallow_any_explicit = true`; CI gate |
| 8   | ✅ **Enforced** | `freezegun` available; production code exposes `_now`/`now_fn` indirection for DI |
| 9   | 🟡 Convention | Pure parsers extracted as module-level functions for direct testing |
| 10  | 🟡 Convention | Reviewer-enforced. |

Patterns:

| Pattern | Status |
| --- | --- |
| `hypothesis` (property-based) | ✅ used in `tests/property/` |
| `import-linter` (architecture) | ⏸️ planned |
| `vulture` (dead code) | ✅ available via dev deps |
| `freezegun` (deterministic time) | ✅ used in `tests/race/` and elsewhere |
| Poison-Pill subprocess mock | ✅ in `tests/conftest.py` |
| Race-condition tests | ✅ in `tests/race/` |
| Failure injection | ✅ in `tests/unit/test_failure_injection.py` |

---

## Lessons Extracted from Real Failures

Project-specific lessons (named, not numbered):

### Eager-init connection pools cause Vitest hangs

Lazy-initialize connection pools in production code. Eager pool
creation at module level causes open-handle hangs in test runners —
tests importing the module but not calling DB methods open real
connections that block process exit. Fix: Proxy-based lazy init.
Never add teardown hacks or `process.exit()` workarounds until the
eager-init root cause is ruled out.

### Adaptive Fault Tolerance for fragile inputs

When a downstream input source is missing or malformed (e.g. a
parser receives garbage from a flaky CLI tool), fall back to a
documented degraded value (`None`, `[]`, `0`, `""`) rather than
raising. The graceful path is part of the contract; cite it inline
at every `except Exception:` site.

### Automated Verification over Assumed State

Always query the actual state directly, never assume previous
operations succeeded. Cron jobs, gitignore patterns, and async
side-effects all benefit from explicit post-conditions verified
against ground truth.

### Range-only properties miss alignment bugs (issue #4, 2026-05-05)

**Trigger:** `freq_to_channel` Hypothesis property
`assert 1 <= ch <= 14` caught **2 of 59** in-band off-grid mis-mappings
(detection rate **3.4 %**). The other 57 wrong outputs stayed inside
`[1, 14]` and slipped through.

**Insight:** For lookup-table-shaped functions (freq → channel,
vid → vendor, currency code → name, etc.), a property of the form
`assert lo <= f(x) <= hi` checks only that the output stays in its
legal range — it is silent on whether the *right input* produced the
*right output*. The stronger invariant asserts **structural
alignment** between input and output: e.g. `if ch != 0: freq == 2412 +
(ch - 1) * 5`. Cost is similar; detection on this bug class jumps from
3.4 % to 100 %.

**Pattern reinforced:** Property-based fuzzing (§ Advanced Patterns) +
Adaptive Fault Tolerance — the alignment property captures the
function's contract precisely, including the "0 means unknown"
graceful-degradation clause.

**Mitigation:** PR #9 replaces the two range-only 2.4 / 5 GHz
properties with alignment-invariant ones, adds a previously-missing
6 GHz alignment property, and lands the production fix.

### v1.0.0 PII leak (2026-05-05)

The `.gitignore` had `.env` and `device_*.txt` patterns but
`device.env` matched neither (no leading dot, wrong separator).
Result: 96 file/commit hits of personally identifying data shipped
to a public 85-star repo.

**Implication:** This is the *Automated Verification over Assumed
State* pattern applied to git hygiene. Assumption was "the
gitignore catches my dotfiles." Reality required automated
verification — `gitleaks` running pre-commit would have caught it.

**Mitigation:** Phase 7 wired `gitleaks` as a pre-commit hook AND a
CI gate. Recurrence is closed.

---

## How This Governs `adb-android-control`

1. **`adb` outputs** are tested via the doctrine's schema pattern —
   validate parsed shape, never assert on exact stdout strings (Android
   version variants will rot exact-match assertions).
2. **`subprocess.run` invocations** are tested via
   behaviour-over-implementation — verify the right argv is built for an
   intent, not how `_run` builds it.
3. **Determinism in monitor tests** — `freeze_time` for connection-monitor
   reconnect intervals; never `time.sleep` in a test.
4. **No real device required** — every unit test mocks `subprocess`.
   Real-device tests live in `tests/integration/` and are gated to
   nightly CI only.
5. **Architectural boundaries** — `import-linter` will enforce
   `radio.py` cannot import from `controller.py`'s private internals;
   shell scripts cannot be imported from Python; etc.

---

## How to Add a New Lesson

When a real failure teaches the team something:

1. Append a new `### <descriptive title>` subsection to the "Lessons"
   section above.
2. State the trigger in a short noun phrase, the insight in ≤2
   sentences.
3. Map it to the doctrine Law or Pattern it reinforces.
4. Reference commits / PRs / incident IDs by short SHA / number.

Lessons are append-only and **named, not numbered** — numbering would
leak signal about the size of the broader private knowledge base.

---

## References

### Project tooling
- `pyproject.toml` — dev dependencies + lint/test config
- `.pre-commit-config.yaml` — pre-commit hooks (ruff, mypy, pytest, gitleaks)
- `tests/conftest.py` — fixtures + Poison-Pill subprocess mock
- `tests/unit/` — unit tests (default)
- `tests/property/` — Hypothesis property-based tests
- `tests/race/` — threading + concurrency tests
- `.github/workflows/ci.yml` — CI matrix
- `.github/workflows/property-nightly.yml` — deep Hypothesis fuzzing
