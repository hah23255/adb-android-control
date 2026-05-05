# Master Tester Doctrine — Project Entrypoint (Python edition)

> **Status:** canonical. Established by HH directive on 2026-03-05.
> Bundle landed in repo on 2026-05-05.
> **Scope:** governs all `adb-android-control` test work.
> **Audience:** every human and agent that writes, reviews, or modifies tests.
>
> ⚠️ **This file is the project-tailored entrypoint.** The full canonical
> 27-file bundle (originally written for TypeScript / Vitest / MSW) lives at
> [`docs/master-tester-doctrine/`](./master-tester-doctrine/README.md). When
> the project entrypoint and the bundle disagree, **the bundle is
> authoritative on philosophy**; this file is authoritative on the **Python
> tooling translation**.

---

## The 10 Non-Negotiable Laws (verbatim from doctrine)

1. **Never modify a test to fix CI.** Tests are contracts. Fix the code.
2. **Test behaviour, not implementation.** Public API only.
3. **AAA pattern.** Arrange → Act → Assert. Every test.
4. **DAMP over DRY.** Readability beats brevity in tests.
5. **Isolated tests.** No shared state. Order-independent.
6. **Never mock `fetch`/`axios` directly. Use MSW.** *(In Python: never
   mock `subprocess.Popen`/`requests.get` directly. Use the Poison-Pill
   subprocess mock + `responses` for HTTP.)*
7. **Ban `as any` in test files.** *(In Python: ban `# type: ignore` and
   `cast(Any, …)` in `tests/`.)*
8. **Tests must be deterministic.** *(In Python: `freezegun` for time,
   seeded `random.Random()`, no real network.)*
9. **One logical concept per test.**
10. **No tautological tests.** Test business logic, not language mechanics.

## The Oath

> *"I do not test to achieve a percentage. I test to sleep soundly. I assume
> the network is hostile, the user is chaotic, and time is an illusion. My
> tests are the unbreakable contract between the present codebase and its
> future self."*

---

## Doctrine ↔ Python tooling map

| TS / Vitest pattern (canonical) | Python / pytest equivalent (this repo) |
|---|---|
| `vitest` test runner | `pytest` |
| `vi.mocked()` / `vi.spyOn()` | `unittest.mock.MagicMock(spec=…)`, `pytest-mock` |
| **MSW** (network mocking — Law 6) | **`responses`** (HTTP), **`pytest-subprocess`** + Poison-Pill (subprocess) |
| `fast-check` (property-based) | **`hypothesis`** |
| Proxy-based Poison-Pill mock | `MagicMock(spec=…, spec_set=True)` + `__getattr__` raise |
| `vi.useFakeTimers()` | **`freezegun`** |
| `dependency-cruiser` (architecture) | **`import-linter`** |
| `knip` (dead code) | **`vulture`** |
| `expect-type` (type-level tests) | `assert_type` (Python 3.11+) / `mypy --strict` |
| `as any` ban | `# type: ignore` ban via `mypy --strict` + `ruff TCH/ANN` |
| Coverage thresholds (80/70/75/80) | `pytest-cov` `--cov-fail-under=80` (target — Phase 1.b) |

---

## Enforcement Map (this repo)

| Law | Status as of v1.0.1 | Mechanism |
| --- | --- | --- |
| 1   | ⚠️ **Not yet CI-enforced** | Phase 7 will add `.github/workflows/ci.yml::test-file-integrity` mirroring the `gw2-compliance-agent` pattern (PR diff scan against `*.test.py`/`tests/**`). |
| 2   | 🟡 Convention | Reviewer-enforced. |
| 3   | 🟡 Convention | Reviewer-enforced. AAA marked via section comments in test bodies. |
| 4   | 🟡 Convention | Reviewer-enforced. |
| 5   | ✅ **Enforced** | `pytest` per-test isolation by default; module-level fixtures avoided; `tmp_path` over shared dirs. |
| 6   | 🟡 **Tooling installed, not yet wired** | `pytest-subprocess` + Poison-Pill skeleton at `tests/conftest.py`. Unmocked `subprocess.run` calls fail loud. |
| 7   | ⚠️ **Not yet enforced** | `mypy --strict` will catch `cast(Any)`. Phase 1 will add `ruff` rule `ANN401` (no `Any` annotations) project-wide. |
| 8   | 🟡 Per-test | Tests using time / random must call `freeze_time(…)` / `random.Random(seed=42)`. Reviewer-enforced. |
| 9   | 🟡 Convention | Reviewer-enforced. |
| 10  | 🟡 Convention | Reviewer-enforced. |

Patterns:

| Pattern | Status |
| --- | --- |
| `hypothesis` (property-based) | 🟡 Phase 3 |
| `import-linter` (architecture) | 🟡 Phase 7 |
| `vulture` (dead code) | 🟡 Phase 7 |
| `freezegun` (deterministic time) | 🟡 Phase 1 install, Phase 3 use |
| Poison-Pill subprocess mock | 🟡 Phase 1.c |

---

## Lessons Extracted from Real Failures

Canonical lessons (IDs preserved from the master lessons database):

| #   | Trigger                      | Insight                                                                                                                                                                                                                       |
| --- | ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 35  | 8 CI runs to trace a hang    | Lazy-initialize connection pools in production code. Eager `PrismaClient` (or any pool) at module level causes open-handle hangs. Fix: Proxy-based lazy init. Never add teardown hacks until eager-init root cause is ruled out. |
| 36  | Gaslight architecture        | Study patterns before implementation. Research time is not overhead — it's the multiplier that compresses implementation time.                                                                                                |
| 41  | GitHub trends script missing | Adaptive Fault Tolerance: fall back to previous data rather than failing the process.                                                                                                                                         |
| 44  | Clerk middleware CORS        | Next.js Auth: use `auth()` for RSC checks, not `auth.protect()` — avoids `MIDDLEWARE_INVOCATION_FAILED`.                                                                                                                       |
| 47  | End-of-Day cron              | Automated Verification over Assumed State: always query logs directly, never assume previous cron actions succeeded.                                                                                                          |

### Project-specific addenda (this repo)

#### internal lesson (PII pre-commit gate) (proposed) — *"v1.0.0 device.env PII leak"* (2026-05-05)

The `.gitignore` had `.env` and `device_*.txt` patterns but `device.env`
matched neither (no leading dot, wrong separator). Result: 96 file/commit
hits of personally identifying data shipped to a public 85-star repo.

**Doctrine implication:** This is the *internal lesson (automated verification)* pattern (Automated
Verification over Assumed State) applied to git hygiene. Assumption was
"the gitignore catches my dotfiles." The reality required automated
verification — `gitleaks` running pre-commit would have caught it.

**Mitigation in this repo:** Phase 7 wires `gitleaks` as a pre-commit
hook and a CI gate. Recurrence is closed.

---

## How This Governs `adb-android-control`

1. **`adb` outputs are tested via the doctrine's schema pattern** — validate
   parsed shape, never assert on exact stdout strings (Android version
   variants will rot exact-match assertions).
2. **`subprocess.run` invocations are tested via behaviour-over-implementation** —
   verify the right argv is built for an intent, not how `_run` builds it.
3. **Determinism in monitor tests** — `freeze_time` for connection-monitor
   reconnect intervals; never `time.sleep` in a test.
4. **No real device required** — every unit test mocks `subprocess`. Real-device
   tests live in `tests/integration/` and are gated to nightly CI only.
5. **Architectural boundaries** — `import-linter` (Phase 7) will enforce:
   `radio_scan.py` cannot import from `controller.py`'s private internals;
   shell scripts cannot be imported from Python; etc.

---

## How to Add a New Lesson

When a real failure teaches the team something:

1. Append a new row to the lessons table above with the next available `#`.
2. State the trigger in a short noun phrase, the insight in ≤2 sentences.
3. Map it to the doctrine Law or Pattern it reinforces.
4. Add a `#### Lesson N — title` subsection under "Project-specific addenda"
   with commit / PR / incident references.

Lessons are append-only.

---

## References

### Canonical bundle (authoritative)
- [`docs/master-tester-doctrine/README.md`](./master-tester-doctrine/README.md)
- [`docs/master-tester-doctrine/doctrine/MASTER-TESTER-DOCTRINE.md`](./master-tester-doctrine/doctrine/MASTER-TESTER-DOCTRINE.md)
- [`docs/master-tester-doctrine/doctrine/oath-of-the-master-tester.md`](./master-tester-doctrine/doctrine/oath-of-the-master-tester.md)
- [`docs/master-tester-doctrine/SKILL.md`](./master-tester-doctrine/SKILL.md) — 4-phase execution protocol
- [`docs/master-tester-doctrine/AGENTS.md`](./master-tester-doctrine/AGENTS.md) — agent integration rules

### Project tooling
- `pyproject.toml` — dev dependencies + lint/test config
- `.pre-commit-config.yaml` — pre-commit hooks (ruff, mypy, pytest, gitleaks)
- `tests/conftest.py` — fixtures + Poison-Pill subprocess mock
- `.github/workflows/ci.yml` — CI matrix (Phase 7)
