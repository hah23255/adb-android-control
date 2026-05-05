# Contributing to `adb-android-control`

> *Thanks for your interest. This project is governed by the
> [Master Tester Doctrine](docs/TESTING_DOCTRINE.md). Read it before
> writing tests. The 10 Laws are non-negotiable.*

## Quick links

- [Doctrine — must-read before writing tests](docs/TESTING_DOCTRINE.md)
- [Architecture — module responsibilities](docs/ARCHITECTURE.md)
- [Migration guide for v1.0.x users](docs/MIGRATING.md)
- [Security policy + reporting channel](SECURITY.md)
- [Troubleshooting decision tree](docs/TROUBLESHOOTING.md)

## Code of Conduct

Be respectful. Be constructive. Be patient. Disagreements about
technical decisions are healthy; disagreements about people are
not.

Reports of unacceptable conduct can be sent privately via the
channels in [`SECURITY.md`](SECURITY.md).

## Getting started

### Prerequisites

| Tool | Why | Install |
|---|---|---|
| `python` 3.10+ | Runtime | system package or [pyenv](https://github.com/pyenv/pyenv) |
| `adb` | What we wrap | `pkg install android-tools` (Termux) / `brew install --cask android-platform-tools` / `apt install adb` |
| `git` | Source control | system package |
| `pre-commit` | Local hook runner | `pip install pre-commit` |

### Fork + clone + install

```bash
gh repo fork hah23255/adb-android-control --clone
cd adb-android-control
pip install -e ".[dev]"
pre-commit install
```

Verify everything works:

```bash
ruff check .
mypy adb_android_control
pytest -q
```

All three should pass on a fresh clone.

## The doctrine-aligned workflow

This project follows the **Master Tester Doctrine** end-to-end. Before
your PR can land, it must align with the 10 Laws + Patterns. The most
common pitfalls:

| Pitfall | Doctrine Law | What to do instead |
|---|---|---|
| Modifying a test to make CI pass | **Law 1** | Fix the production code. If the test is genuinely wrong, open a separate PR explaining *why* with reviewer sign-off — never combine with a "make CI green" change. |
| Asserting `obj._private_field == ...` | **Law 2** | Test the public method that observes the private field's effect. |
| One test per dataclass field | **Law 9** | One test per *behaviour*. A factory test is one concept; a getter test isn't usually a concept. |
| `subprocess.run` mocked directly | **Law 6** | Use the `mock_adb` Poison-Pill fixture from `tests/conftest.py`. |
| `# type: ignore` in a test | **Law 7** | Reshape the type to be testable, or use `cast(SomeRealType, ...)` with rationale. The only allowed exception is `# noqa: B017` for frozen-dataclass `with pytest.raises(Exception):` patterns. |
| `time.sleep(0.1)` in a test | **Law 8** | Use `freezegun` or inject the clock via the production code's `_now`/`now_fn` indirection. |

### Test-first workflow (recommended)

1. **Branch.** `git checkout -b feature/your-thing`
2. **Read the relevant doctrine sections.** Especially:
   [the 10 Laws and project entrypoint](docs/TESTING_DOCTRINE.md),
   the lessons section in that file (Adaptive Fault Tolerance is the
   one you'll engage most often).
3. **Write the failing test first.** Place it under the right
   directory:
   - `tests/unit/` — default; mocks everything
   - `tests/property/` — Hypothesis property-based
   - `tests/race/` — threading + concurrency
   - `tests/integration/` — needs real `adb` (skipped by default)
   - `tests/quarantine/` — known-flaky (must have an open issue link)
4. **Implement the production code** until the test passes.
5. **Run the full suite.** `pytest -q` — including property + race.
6. **Run the linters.** `ruff check .`, `mypy adb_android_control`,
   `pre-commit run --all-files`.
7. **Commit** following Conventional Commits (see below).
8. **Push and open a PR** with the [PR template](.github/PULL_REQUEST_TEMPLATE.md)
   filled in (forthcoming in Phase 7).

## Coding standards

- **Strict mypy.** No `Any` annotations (`disallow_any_explicit = true`).
  No `# type: ignore` in production code; rare exceptions in tests are
  flagged by reviewers.
- **Ruff** for lint + format. Trailing whitespace, import order,
  pep8-naming, flake8-bugbear, flake8-bandit, flake8-use-pathlib,
  pyupgrade, etc. — all enforced.
- **Frozen dataclasses** for value objects. Mutable state lives in
  classes with explicit lifecycles.
- **Pure functions** for parsers, converters, predicates. They live
  at module level so tests can target them directly (Law 9).
- **Dependency injection** for I/O. Class constructors accept
  `adb=ADBController()`, `notifier=...`, `now_fn=...`, etc., so tests
  can substitute fakes (Laws 5 + 6).
- **No `shell=True`.** Argv lists only. `subprocess` calls use
  `check=False` and explicit error mapping.
- **No bare `except:`.** Use specific exception classes. Where you
  must catch broadly for graceful degradation (internal lesson (adaptive fault tolerance)), comment
  the rationale inline.
- **Library code does NOT call `logging.basicConfig`.** That's the
  application's concern; we install logging only in `cli.py`.

## Commit guidelines

We use [Conventional Commits](https://www.conventionalcommits.org/).
Format:

```
<type>(<scope>): <subject>

<body — wrap at 72 chars; explain *why*, not what>

<optional footer — Co-Authored-By, Closes #N, etc.>
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`,
`security`, `perf`, `revert`, `ci`, `build`.

**Scopes:** module names without `_` prefixes — `controller`,
`monitor`, `automation`, `radio`, `connection_monitor`, `port_scan`,
`usb`, `cli`, `tests`, `docs`, `ci`. For multi-scope changes use
`comma,separated` or `<scope>+`.

### Examples

```
test(controller): add Hypothesis property fuzzing on _BATTERY_LEVEL_RE

Adds three property tests covering the regex's never-raises invariant
plus the well-formed-line round-trip identity. Closes the v1.1.0-rc1
property-coverage gap surfaced in code review.

Co-Authored-By: …
```

```
fix(monitor): handle EOF mid-line in LogcatMonitor._read_loop

Reproduces deterministically with a SIGTERM mid-readline injection.
The pre-fix path raised AttributeError on the truncated stdout.

Closes #42
```

### What NOT to do

- ❌ Don't combine refactors with bug fixes in one commit.
- ❌ Don't include "WIP" or "fix typo" commits in PRs — squash before
  merge.
- ❌ Don't skip the body unless the change is genuinely trivial.

## Pull request process

1. Open a draft PR early; you don't have to wait until it's green.
2. The PR template asks specifically for:
   - Which Doctrine Laws the change engages
   - Which test directory the new tests live in
   - Whether any test files were modified (Law 1 gate)
3. CI runs lint, typecheck, tests, coverage delta — all must pass.
4. At least one reviewer must approve. For doctrine-violation
   exceptions (e.g., a deliberately weak test for a known-broken
   subsystem), maintainer sign-off required.
5. Squash-merge is the default. Maintainer may request a rebase
   merge for multi-commit feature branches with clean history.

## Documentation

If your change adds public API, update:

- The relevant module docstring
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) if architectural
- [`docs/USE_CASES.md`](docs/USE_CASES.md) with a new UC entry if
  user-visible
- [`CHANGELOG.md`](CHANGELOG.md) under `[Unreleased]`

For docs-only changes, no test changes are required, but `markdownlint`
runs in pre-commit.

## Testing

See [`docs/TESTING_DOCTRINE.md`](docs/TESTING_DOCTRINE.md) for the
full doctrine. Quick reference:

```bash
pytest                       # all unit + property + race (default)
pytest -m unit               # unit only
pytest -m property           # Hypothesis property tests
pytest -m race               # threading / concurrency
pytest -m integration        # real adb (skipped by default; opt-in)
pytest --cov                 # coverage report
pytest --cov --cov-fail-under=80   # gate at 80% (target — Phase 3 done)
pytest -x -q                 # fail fast, quiet output
pytest tests/unit/test_controller.py::TestPackages   # one class
```

## Review process

Reviewers look for, in order:

1. **Doctrine compliance.** Especially Laws 1, 6, 7, 8.
2. **Test coverage.** Every public method has at least one test.
3. **Type safety.** `mypy --strict` must pass.
4. **Style.** `ruff check .` clean.
5. **Documentation.** Public API has docstrings; CHANGELOG updated.
6. **Architectural fit.** No new circular deps; layering rules
   respected.

A PR that fails (1) is rejected; (2)–(6) are negotiable with
reviewer sign-off.

## Releasing

Releases are cut by maintainers from `main` after a green CI matrix.
Versioning follows [SemVer](https://semver.org/). Releases are tagged
and published via GitHub Releases (PyPI in Phase 7).

## DCO sign-off (forthcoming)

Phase 7 will introduce a Developer Certificate of Origin sign-off
requirement on commits. After that lands, every commit needs:

```
Signed-off-by: Your Name <your.email@example.com>
```

Run `git commit -s` to add this automatically. Pre-existing
contributions are grandfathered.
