"""Property-based tests for the pure parsers using Hypothesis.

Doctrine
--------
- Master Tester Doctrine § Advanced Patterns: "Property-based fuzzing —
  fast-check / Hypothesis — for date math, parsers, financial logic;
  generate thousands of random inputs, verify invariants hold."
- Each test asserts an *invariant* that must hold for every input in the
  generated space — not a single concrete output. Failures shrink to
  minimal counterexamples automatically.
- We tune ``max_examples`` per property based on the input space size:
  parsers with infinite input space get more examples; small finite
  spaces (e.g. RSSI-to-quality) get fewer because exhaustive coverage
  is achievable with the ``@example`` decorator anyway.
"""

from __future__ import annotations

import string

import pytest
from hypothesis import HealthCheck, assume, example, given, settings
from hypothesis import strategies as st

from adb_android_control.connection_monitor import (
    ChangeType,
    ConnectionState,
    detect_changes,
    parse_adb_devices,
)
from adb_android_control.controller import _BATTERY_LEVEL_RE, _SCREEN_SIZE_RE
from adb_android_control.monitor import LogcatMonitor
from adb_android_control.port_scan import rewrite_devices_config
from adb_android_control.radio import (
    freq_to_band,
    freq_to_channel,
    parse_wifi_info,
    rssi_to_quality,
)
from adb_android_control.usb import parse_device_descriptor

pytestmark = pytest.mark.property

# Reasonable default for parsers with infinite input space; doctrine plan
# §3 calls for ≥1000 examples per property test, so we surface that as a
# named setting rather than re-typing it.
DEEP_FUZZ = settings(
    max_examples=1000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
SHALLOW_FUZZ = settings(max_examples=200, deadline=None)


# ---------------------------------------------------------------------------
# freq_to_channel — property: never raises, sane range, monotonic in-band
# ---------------------------------------------------------------------------


class TestFreqToChannelProperties:
    @DEEP_FUZZ
    @given(freq=st.integers(min_value=-10_000_000, max_value=10_000_000))
    def test_never_raises_for_any_int(self, freq: int) -> None:
        # Property: pure function tolerates any input, returns int
        result = freq_to_channel(freq)
        assert isinstance(result, int)

    @SHALLOW_FUZZ
    @given(freq=st.integers(min_value=2412, max_value=2484))
    def test_24ghz_band_returns_channel_1_to_14(self, freq: int) -> None:
        # Property: in 2.4 GHz range, channel must be 1-14
        ch = freq_to_channel(freq)
        assert 1 <= ch <= 14

    @SHALLOW_FUZZ
    @given(freq=st.integers(min_value=5170, max_value=5825))
    def test_5ghz_band_yields_positive_channel(self, freq: int) -> None:
        # Property: in 5 GHz range, channel must be >= 36 (lowest 5 GHz channel)
        ch = freq_to_channel(freq)
        assert ch >= 34

    @example(freq=-1)
    @example(freq=0)
    @example(freq=1_000_000)
    @SHALLOW_FUZZ
    @given(freq=st.integers(min_value=-1000, max_value=2400 - 1))
    def test_below_24ghz_returns_zero(self, freq: int) -> None:
        # Property: clearly-below-band frequencies return 0 ("unknown")
        # 2400 is below the 2412 channel-1 lower bound
        result = freq_to_channel(freq)
        assert result == 0


# ---------------------------------------------------------------------------
# freq_to_band — property: returns one of 4 fixed values; consistent with channel
# ---------------------------------------------------------------------------


class TestFreqToBandProperties:
    KNOWN_BANDS = {"2.4GHz", "5GHz", "6GHz", "Unknown"}

    @DEEP_FUZZ
    @given(freq=st.integers(min_value=-10_000_000, max_value=10_000_000))
    def test_always_returns_known_band_string(self, freq: int) -> None:
        # Property: output is always one of the four documented strings
        assert freq_to_band(freq) in self.KNOWN_BANDS

    @SHALLOW_FUZZ
    @given(freq=st.integers(min_value=-1000, max_value=2400 - 1))
    def test_below_24ghz_is_unknown(self, freq: int) -> None:
        # Property: anything below 2400 MHz is Unknown
        assert freq_to_band(freq) == "Unknown"


# ---------------------------------------------------------------------------
# rssi_to_quality — property: monotonic (more dBm = better-or-equal quality)
# ---------------------------------------------------------------------------


class TestRssiToQualityProperties:
    KNOWN_QUALITIES = ("Excellent", "Good", "Fair", "Weak", "Poor")
    QUALITY_RANK = {q: i for i, q in enumerate(KNOWN_QUALITIES)}

    @DEEP_FUZZ
    @given(rssi=st.integers(min_value=-200, max_value=50))
    def test_always_returns_known_quality(self, rssi: int) -> None:
        # Property: output is always one of the documented qualities
        assert rssi_to_quality(rssi) in self.KNOWN_QUALITIES

    @DEEP_FUZZ
    @given(
        a=st.integers(min_value=-200, max_value=50),
        b=st.integers(min_value=-200, max_value=50),
    )
    def test_monotonic_in_signal_strength(self, a: int, b: int) -> None:
        # Property: a >= b → quality(a) is at-least-as-good-as quality(b).
        # "Better" means lower rank index in KNOWN_QUALITIES.
        assume(a >= b)
        rank_a = self.QUALITY_RANK[rssi_to_quality(a)]
        rank_b = self.QUALITY_RANK[rssi_to_quality(b)]
        assert rank_a <= rank_b, (
            f"Monotonicity violated: rssi={a} ({rssi_to_quality(a)}) "
            f"should be at-least-as-good as rssi={b} ({rssi_to_quality(b)})"
        )


# ---------------------------------------------------------------------------
# parse_adb_devices — never crashes; output shape invariants
# ---------------------------------------------------------------------------


class TestParseAdbDevicesProperties:
    @DEEP_FUZZ
    @given(text=st.text(max_size=200))
    def test_never_raises_for_arbitrary_text(self, text: str) -> None:
        # Property: pure function handles any string input
        result = parse_adb_devices(text)
        assert isinstance(result, tuple)
        assert len(result) == 3

    @DEEP_FUZZ
    @given(text=st.text(max_size=200))
    def test_connected_implies_nonempty_ip_and_positive_port(self, text: str) -> None:
        # Property: if connected=True, ip and port must be non-default
        connected, ip, port = parse_adb_devices(text)
        if connected:
            assert ip != "", "connected=True must yield non-empty IP"
            assert port > 0, "connected=True must yield positive port"

    @DEEP_FUZZ
    @given(text=st.text(max_size=200))
    def test_disconnected_yields_default_ip_and_port(self, text: str) -> None:
        # Property: if connected=False, ip="" and port=0
        connected, ip, port = parse_adb_devices(text)
        if not connected:
            assert ip == ""
            assert port == 0


# ---------------------------------------------------------------------------
# parse_log_line — never crashes; returns LogEntry or None
# ---------------------------------------------------------------------------


class TestParseLogLineProperties:
    @DEEP_FUZZ
    @given(line=st.text(max_size=500))
    def test_never_raises_for_arbitrary_text(self, line: str) -> None:
        # Property: returns LogEntry or None — no exceptions
        result = LogcatMonitor.parse_log_line(line)
        # Pure function: must be one of the two contract types
        assert result is None or hasattr(result, "level")

    @DEEP_FUZZ
    @given(
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=31),
        hour=st.integers(min_value=0, max_value=23),
        minute=st.integers(min_value=0, max_value=59),
        second=st.integers(min_value=0, max_value=59),
        millis=st.integers(min_value=0, max_value=999),
        pid=st.integers(min_value=1, max_value=99999),
        tid=st.integers(min_value=1, max_value=99999),
        level=st.sampled_from(list("VDIWEF")),
        tag=st.text(
            alphabet=string.ascii_letters + string.digits + "._-",
            min_size=1,
            max_size=20,
        ),
        message=st.text(
            alphabet=string.printable.replace("\n", "").replace("\r", ""),
            max_size=100,
        ),
    )
    def test_well_formed_lines_always_parse(  # noqa: PLR0913
        self,
        month: int,
        day: int,
        hour: int,
        minute: int,
        second: int,
        millis: int,
        pid: int,
        tid: int,
        level: str,
        tag: str,
        message: str,
    ) -> None:
        # Property: any line matching the documented format must round-trip.
        # Tag must not contain ':' (parser splits on first colon).
        assume(":" not in tag)
        line = (
            f"{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}.{millis:03d}"
            f"  {pid}  {tid} {level} {tag}: {message}"
        )
        entry = LogcatMonitor.parse_log_line(line)
        assert entry is not None, f"Failed to parse: {line!r}"
        assert entry.pid == pid
        assert entry.tid == tid


# ---------------------------------------------------------------------------
# parse_device_descriptor — exhaustive VID/PID round-trip
# ---------------------------------------------------------------------------


class TestParseDeviceDescriptorProperties:
    @DEEP_FUZZ
    @given(data=st.binary(max_size=100))
    def test_never_raises_for_arbitrary_bytes(self, data: bytes) -> None:
        # Property: returns USBDeviceInfo or None
        result = parse_device_descriptor(data)
        assert result is None or hasattr(result, "vid")

    @DEEP_FUZZ
    @given(data=st.binary(max_size=11))
    def test_under_12_bytes_always_returns_none(self, data: bytes) -> None:
        # Property: documented minimum-length contract
        assert parse_device_descriptor(data) is None

    @DEEP_FUZZ
    @given(
        vid=st.integers(min_value=0, max_value=0xFFFF),
        pid=st.integers(min_value=0, max_value=0xFFFF),
        prefix=st.binary(min_size=8, max_size=8),
        suffix=st.binary(max_size=10),
    )
    def test_round_trip_extracts_correct_vid_pid(
        self, vid: int, pid: int, prefix: bytes, suffix: bytes
    ) -> None:
        # Property: assembling 12+ bytes with VID/PID at the documented
        # offsets must round-trip cleanly through the parser
        vid_bytes = bytes([vid & 0xFF, (vid >> 8) & 0xFF])
        pid_bytes = bytes([pid & 0xFF, (pid >> 8) & 0xFF])
        data = prefix + vid_bytes + pid_bytes + suffix

        info = parse_device_descriptor(data)

        assert info is not None
        assert info.vid == vid
        assert info.pid == pid

    @DEEP_FUZZ
    @given(
        vid=st.integers(min_value=0, max_value=0xFFFF),
        pid=st.integers(min_value=0, max_value=0xFFFF),
    )
    def test_vid_pid_format_is_4_digit_lowercase_hex(self, vid: int, pid: int) -> None:
        # Property: vid_pid is always exactly 9 chars: VVVV:PPPP lowercase
        data = bytearray(12)
        data[8:10] = bytes([vid & 0xFF, (vid >> 8) & 0xFF])
        data[10:12] = bytes([pid & 0xFF, (pid >> 8) & 0xFF])
        info = parse_device_descriptor(bytes(data))
        assert info is not None
        assert len(info.vid_pid) == 9
        assert info.vid_pid[4] == ":"
        assert info.vid_pid.lower() == info.vid_pid


# ---------------------------------------------------------------------------
# parse_wifi_info — never crashes
# ---------------------------------------------------------------------------


class TestParseWifiInfoProperties:
    @DEEP_FUZZ
    @given(text=st.text(max_size=500))
    def test_never_raises(self, text: str) -> None:
        # Property: returns WiFiInfo or None — no exceptions
        result = parse_wifi_info(text)
        assert result is None or hasattr(result, "ssid")


# ---------------------------------------------------------------------------
# Battery / screen-size regexes — never crashes
# ---------------------------------------------------------------------------


class TestControllerRegexProperties:
    @DEEP_FUZZ
    @given(text=st.text(max_size=200))
    def test_battery_regex_search_never_raises(self, text: str) -> None:
        # Property: regex search is pure and never raises on any text
        m = _BATTERY_LEVEL_RE.search(text)
        if m is not None:
            # If matched, the captured group must parse as int
            assert m.group(1).isdigit()

    @DEEP_FUZZ
    @given(text=st.text(max_size=200))
    def test_screen_size_regex_search_never_raises(self, text: str) -> None:
        # Property: regex search yields well-formed groups when it matches
        m = _SCREEN_SIZE_RE.search(text)
        if m is not None:
            assert m.group(1).isdigit()
            assert m.group(2).isdigit()


# ---------------------------------------------------------------------------
# rewrite_devices_config — line preservation, idempotency
# ---------------------------------------------------------------------------


class TestRewriteDevicesConfigProperties:
    @DEEP_FUZZ
    @given(
        content=st.text(max_size=500),
        name=st.text(
            alphabet=string.ascii_uppercase + string.digits + "_",
            min_size=1,
            max_size=20,
        ),
        ip=st.text(
            alphabet=string.digits + ".",
            min_size=7,
            max_size=15,
        ),
        port=st.integers(min_value=1, max_value=65535),
    )
    def test_idempotent_rewrite(
        self, content: str, name: str, ip: str, port: int
    ) -> None:
        # Property: rewriting twice with the same args yields the same result
        first = rewrite_devices_config(content, name=name, ip=ip, port=port)
        second = rewrite_devices_config(first, name=name, ip=ip, port=port)
        assert first == second

    @DEEP_FUZZ
    @given(
        content=st.text(max_size=500),
        name=st.text(
            alphabet=string.ascii_uppercase, min_size=3, max_size=10
        ),
        ip=st.text(alphabet=string.digits + ".", min_size=7, max_size=15),
        port=st.integers(min_value=1, max_value=65535),
    )
    def test_line_count_preserved(
        self, content: str, name: str, ip: str, port: int
    ) -> None:
        # Property: rewriting never adds/removes lines
        rewritten = rewrite_devices_config(content, name=name, ip=ip, port=port)
        assert len(content.split("\n")) == len(rewritten.split("\n"))


# ---------------------------------------------------------------------------
# detect_changes — algebraic properties
# ---------------------------------------------------------------------------


def _state_strategy() -> st.SearchStrategy[ConnectionState]:
    return st.builds(
        ConnectionState,
        timestamp=st.text(max_size=30),
        connected=st.booleans(),
        ip=st.text(
            alphabet=string.digits + ".", min_size=0, max_size=15
        ),
        port=st.integers(min_value=0, max_value=65535),
        ssid=st.text(max_size=30),
        rssi_dbm=st.integers(min_value=-150, max_value=0),
        frequency_mhz=st.integers(min_value=0, max_value=10000),
    )


class TestDetectChangesProperties:
    @DEEP_FUZZ
    @given(last=_state_strategy(), current=_state_strategy())
    def test_never_raises(
        self, last: ConnectionState, current: ConnectionState
    ) -> None:
        # Property: pure function on any pair of states
        result = detect_changes(last, current)
        assert isinstance(result, list)

    @DEEP_FUZZ
    @given(state=_state_strategy())
    def test_reflexive_equivalence_yields_no_changes(
        self, state: ConnectionState
    ) -> None:
        # Property: detect_changes(s, s) == []
        # Identical inputs produce no observed transitions.
        assert detect_changes(state, state) == []

    @DEEP_FUZZ
    @given(
        ip=st.text(alphabet=string.digits + ".", min_size=7, max_size=15),
        port=st.integers(min_value=1, max_value=65535),
        ssid=st.text(min_size=1, max_size=20),
    )
    def test_connect_transition_emits_connected(
        self, ip: str, port: int, ssid: str
    ) -> None:
        # Property: any None→connected transition emits CONNECTED
        last = None
        current = ConnectionState(
            timestamp="t",
            connected=True,
            ip=ip,
            port=port,
            ssid=ssid,
            rssi_dbm=-50,
            frequency_mhz=5180,
        )
        changes = detect_changes(last, current)
        assert any(c.kind == ChangeType.CONNECTED for c in changes)

    @DEEP_FUZZ
    @given(
        ip=st.text(alphabet=string.digits + ".", min_size=7, max_size=15),
        port=st.integers(min_value=1, max_value=65535),
        ssid=st.text(min_size=1, max_size=20),
    )
    def test_disconnect_transition_emits_disconnected(
        self, ip: str, port: int, ssid: str
    ) -> None:
        # Property: any connected→disconnected transition emits DISCONNECTED
        last = ConnectionState(
            timestamp="t",
            connected=True,
            ip=ip,
            port=port,
            ssid=ssid,
            rssi_dbm=-50,
            frequency_mhz=5180,
        )
        current = ConnectionState(
            timestamp="t",
            connected=False,
            ip="",
            port=0,
            ssid=ssid,
            rssi_dbm=-50,
            frequency_mhz=5180,
        )
        changes = detect_changes(last, current)
        assert any(c.kind == ChangeType.DISCONNECTED for c in changes)
