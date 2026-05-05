# Performance

> *Measured baselines for `adb-android-control`. Real numbers come from
> `pytest-benchmark` runs against a real device matrix in CI (Phase 7).
> The methodology and placeholders below are stable; the numbers will
> tighten as Phase 7 lands.*

## Methodology

### What we measure

| Metric | Why it matters |
|---|---|
| **Subprocess overhead per `adb` call** | Dominant cost on the host side; affects every operation |
| **Parse latency** for each pure parser | Hot-path for monitor / scan loops |
| **Throughput** of `LogcatMonitor` | Determines how many devices a host can monitor concurrently |
| **`PortScanner` scan rate** | Shapes wireless-debug reconnect UX |
| **Memory of long-running monitors** | OOM-on-CI prevention (doctrine Pattern row) |
| **Test-suite runtime** | CI cycle time; bounded < 60 s for unit + property |

### How we measure

- **`pytest-benchmark`** for micro-benchmarks of pure parsers and
  CLI argv parsing.
- **Custom timing harness** for full subprocess round-trips (ADB
  wraps a real binary; we can't mock the wall-clock cost).
- **`tracemalloc`** for memory snapshots before/after long monitor
  sessions.
- **Reference hardware:**
  - **CI host:** GitHub Actions `ubuntu-24.04`, 4 vCPU, 16 GB RAM
  - **Reference device:** Pixel-class emulator + a physical Android 14+
    device on a known LAN

We publish benchmark deltas on every PR (Phase 7 CI step).

## Baselines (placeholder — real numbers in Phase 7)

### Pure-parser micro-benchmarks (target: < 100 µs per call)

| Function | Input size | Target latency | Status |
|---|---|---|---|
| `freq_to_channel` | 1 int | < 1 µs | ⏸️ measure |
| `freq_to_band` | 1 int | < 1 µs | ⏸️ measure |
| `rssi_to_quality` | 1 int | < 1 µs | ⏸️ measure |
| `parse_adb_devices` | 200 B output | < 50 µs | ⏸️ measure |
| `parse_log_line` | 200 B line | < 30 µs | ⏸️ measure |
| `parse_wifi_info` | 1 KB output | < 100 µs | ⏸️ measure |
| `parse_device_descriptor` | 18 B | < 10 µs | ⏸️ measure |
| `parse_scan_results` | 5 KB output × 20 networks | < 1 ms | ⏸️ measure |
| `detect_changes` | 2 ConnectionState | < 5 µs | ⏸️ measure |
| `rewrite_devices_config` | 500 B config | < 100 µs | ⏸️ measure |

### Subprocess round-trip (target: < 50 ms warm `adb-server`)

| Operation | Target | Status |
|---|---|---|
| `ADBController.__init__()` (eager `adb version`) | < 50 ms | ⏸️ measure |
| `ctrl.devices()` | < 50 ms | ⏸️ measure |
| `ctrl.shell("getprop ro.product.model")` | < 80 ms | ⏸️ measure |
| `ctrl.get_device_info()` (5 sub-calls) | < 250 ms | ⏸️ measure |
| `ctrl.screenshot()` (1080p PNG) | < 500 ms | ⏸️ measure |

### Long-running monitor stability (target: stable RSS over 1 h)

| Monitor | Target | Status |
|---|---|---|
| `LogcatMonitor` (1 device, ~1 KLOC/sec) | < 50 MB RSS, stable | ⏸️ measure |
| `PerformanceMonitor` (5 s interval, 1 h) | < 30 MB RSS, stable | ⏸️ measure |
| `CrashMonitor` (1 device) | < 50 MB RSS, stable | ⏸️ measure |
| `ConnectionMonitor` (10 s interval) | < 20 MB RSS, stable | ⏸️ measure |

### Port scanner throughput

| Scenario | Target | Status |
|---|---|---|
| 5K port range, 100 workers, all closed | < 10 s | ⏸️ measure |
| 5K port range, 100 workers, 1 open ADB | < 12 s | ⏸️ measure |

### Test-suite runtime (target: < 60 s on CI matrix)

| Suite | Target | Phase 3 measured (local) |
|---|---|---|
| Unit (`-m unit`) | < 30 s | TBD |
| Property (`-m property`, default Hypothesis budget) | < 60 s | TBD |
| Property (deep, `max_examples=1000`) | < 5 min | TBD |
| Race (`-m race`) | < 10 s | TBD |
| Integration (`-m integration`) | < 5 min | nightly only |

## Known performance pitfalls

### `adb-server` cold start
Every `ADBController.__init__()` invokes `adb version`. If the daemon
isn't running, ADB starts it — which can take 2–5 seconds. **Reuse a
single `ADBController` across operations**; don't construct one per
call.

### Concurrent invocations and the lock-free state file
`ConnectionMonitor` writes to `~/.adb_state.json` without a lock. If
you run multiple monitor instances concurrently, the last writer
wins. Documented in
[`tests/race/test_concurrent.py::TestConnectionMonitorConcurrency`].
This is intentional for v1.1.x; locking lands in v2.0 if benchmarks
show contention is real.

### Hypothesis property tests can be CPU-heavy
The `DEEP_FUZZ` setting (`max_examples=1000`) is intended for
nightly runs. PR CI uses `SHALLOW_FUZZ` (200) by default. Override
with:

```bash
HYPOTHESIS_PROFILE=ci pytest -m property
```

### Subprocess fan-out
`PortScanner` spawns up to 100 threads (default `max_workers`). On
small VMs (1 vCPU) this can swamp the system. Pass a smaller
`max_workers` for memory-/CPU-constrained hosts:

```python
scanner = PortScanner(max_workers=16)
```

## How to add a benchmark

1. Add a `tests/benchmark/test_<name>.py` file (forthcoming directory).
2. Use `pytest-benchmark`:

   ```python
   def test_freq_to_channel_micro(benchmark):
       result = benchmark(freq_to_channel, 5500)
       assert result == 100
   ```

3. Run with `pytest --benchmark-only tests/benchmark/`.
4. Compare against baseline:

   ```bash
   pytest --benchmark-only --benchmark-compare=baseline.json
   ```

5. Update this doc's tables when a target is hit or when the
   baseline shifts > 10 %.

## Reporting a regression

If a PR slows something down by > 10 %, the CI bench comparison
will surface it. The rule:

| Slowdown | Reviewer action |
|---|---|
| < 5 % | accept silently |
| 5–10 % | call out in PR; require rationale comment |
| 10–25 % | require benchmark + rationale |
| > 25 % | block merge unless major-version bump |

A `revert` is preferred over a "we'll fix it later" commit. If the
regression is intentional (e.g., a security-hardening cost), document
it here in a "Performance trade-offs" section.

## Performance trade-offs

This section is a graveyard for deliberate slowdowns we've accepted:

*(none yet — populated as Phase 7 surfaces real numbers)*
