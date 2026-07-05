# adb-android-control — Executive Summary

**One line:** A typed, tested Python toolkit that turns any Android phone into a
scriptable, headless device — controlled from the phone itself, over Termux, with no
root and no PC in the loop.

## The pitch

Every "Android automation" tool on the market assumes a desktop driving a phone over
USB. This one flips that: it runs **on the device**, talks to Android's own debug bridge
over loopback Wi-Fi, and exposes the whole surface — apps, files, input, screen, radios,
USB — as a clean CLI and a JSON workflow engine. That's a category most people don't even
know is possible, and this project already has it working and packaged as a **v2.0.0 GA**
release.

## What it actually does (9 CLI verbs, 22 workflow step-kinds)

`devices · info · shot · monitor · workflow · health · radio · connection · scan-port` —
plus a scripting layer covering app install/uninstall, file push/pull, taps/swipes/text,
screenshots and screen recording, logcat/dumpsys, Wi-Fi/Bluetooth scanning, USB device
identification (down to recognizing a Google Coral Edge TPU), and self-healing
wireless-ADB reconnection.

## Why it's credible, not a toy

The engineering is the moat. Proof points:

- **More test code than product code** — 4,725 lines of tests against 2,978 lines of
  package (a 1.5:1 ratio), 309 tests, a documented testing doctrine, property-based
  fuzzing, and race-condition suites.
- **Typed and strict** — frozen value objects throughout, `mypy --strict`, `ruff`, and a
  real CI matrix (lint / typecheck / test / build) with CodeQL, Dependabot, CODEOWNERS,
  and issue templates.
- **17 documentation files** — architecture, error-handling catalog, setup, migration,
  troubleshooting, use-cases. This reads like a product, not a script.

## Where it stands today

A security and correctness pass is merged to `main`: device-side shell-injection closed
with allow-list validation and `shlex.quote`, the JSON workflow engine sandboxed (no
arbitrary `adb shell` or `rm -rf` by default), process lifecycles fixed, the operational
scripts hardened (fast bounded port-scan, strict-mode bash, de-personalized config), and
the docs reconciled to the code. **304 / 309 tests green**, verified end-to-end.

## The honest gaps

- **5 pre-existing test failures** remain — error-classification and parser edge cases,
  unrelated to the merged work. A half-day to clear.
- **Coverage gate is set to 30%** (docs aim for 80%) — the suite is strong but the
  enforced floor is conservative.

## The one-sentence sell

An on-device Android control plane with genuine engineering discipline — the kind of
niche, hard-to-build capability that's worth far more as a polished open-source calling
card than the afternoon it takes to push it live.
