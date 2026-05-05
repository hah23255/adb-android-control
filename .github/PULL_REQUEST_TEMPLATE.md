<!--
Thanks for the PR. Filling this template fully helps reviewers
align on doctrine compliance.
-->

## What this PR does

<!-- One paragraph. Why does this exist? -->

## How

<!-- Bullet points. Specific changes. -->

-
-
-

## Master Tester Doctrine compliance

<!-- Tick the laws this PR engages. -->

- [ ] **Law 1** — *I did NOT modify a test to make CI pass.*
      (If a test legitimately needs to change, it's in a separate PR
      with reviewer sign-off explaining why.)
- [ ] **Law 2** — Tests target public API only; no `_*`-prefixed
      methods asserted on directly.
- [ ] **Law 3** — Every new test has explicit Arrange/Act/Assert
      structure.
- [ ] **Law 4** — Test names + bodies are DAMP (readable in 30s).
- [ ] **Law 5** — Tests are isolated; no shared mutable state.
- [ ] **Law 6** — `subprocess` mocked via the Poison-Pill `mock_adb`
      fixture, never directly.
- [ ] **Law 7** — No `# type: ignore` / `cast(Any, ...)` added
      (mypy `--strict` clean).
- [ ] **Law 8** — Time / random is deterministic (`freezegun`,
      `_now`/`_sleep` indirection).
- [ ] **Law 9** — One logical concept per test.
- [ ] **Law 10** — No tautological tests (no `typeof === 'function'`
      style assertions).

## Test changes

- [ ] Added new tests in: `tests/<unit|property|race|integration>/...`
- [ ] All existing tests still pass: `pytest -q`
- [ ] Coverage delta: <!-- post the codecov bot's number -->

## Checklist

- [ ] `ruff check .` clean
- [ ] `mypy adb_android_control` clean
- [ ] `pre-commit run --all-files` clean
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] If this is user-visible: docs updated (README / USE_CASES /
      ARCHITECTURE / TROUBLESHOOTING as appropriate)
- [ ] Conventional Commit format used in the squash-merge title

## Related

<!-- Closes #N / Refs #N / etc. -->
