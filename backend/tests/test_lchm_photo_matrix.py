"""Tests for the LCHM photo matrix analysis tool (tools/lchm_photo_matrix.py).

These cover parser-driven extraction, statistics, pairwise diff and byte diff.
They exercise confirmed facts only (fixture A photo_distinterval = 20.6) plus
the pure tool logic with synthetic byte edits (no fake Litchi missions).
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lchm_photo_matrix import (  # noqa: E402
    SENTINEL,
    analyze_file,
    extract_photo_blocks,
    format_byte_diff,
    pairwise_photo_diff,
    photo_blocks_rel,
    trailer_byte_diff,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "litchi"
FIXTURE_A = FIXTURES_DIR / "Mission (3).lchm"


def _analysis() -> object:
    return analyze_file(FIXTURE_A)


def test_extract_photo_blocks_count():
    a = _analysis()
    assert len(a.photo_blocks) == 10
    assert a.waypoint_count == 10


def test_photo_blocks_distinterval_matches_csv():
    a = _analysis()
    stored = [b.distinterval for b in a.photo_blocks]
    assert stored == [
        pytest.approx(20.6),
        pytest.approx(20.6),
        pytest.approx(20.6),
        pytest.approx(20.6),
        pytest.approx(-1.0),
        pytest.approx(20.6),
        pytest.approx(20.6),
        pytest.approx(20.6),
        pytest.approx(-1.0),
        pytest.approx(-1.0),
    ]


def test_sentinel_detection():
    a = _analysis()
    assert a.photo_blocks[0].is_sentinel is False
    assert a.photo_blocks[4].is_sentinel is True
    assert a.sentinel_count() == 3
    assert len(a.valid_distintervals()) == 7


def test_photo_statistics_ignore_sentinels():
    a = _analysis()
    s = a.photo_statistics()
    assert s["valid"] == 7
    assert s["sentinel"] == 3
    assert s["min"] == pytest.approx(20.6)
    assert s["max"] == pytest.approx(20.6)
    assert s["mean"] == pytest.approx(20.6)
    assert s["median"] == pytest.approx(20.6)
    assert a.unique_distintervals() == [pytest.approx(20.6)]


def test_derived_time_floor1():
    a = _analysis()
    times = sorted(set(round(t, 1) for t in a.derived_times()))
    assert times == [5.0]


def test_extract_photo_blocks_empty_without_trailer():
    # exported missions carry no trailer: header-only file yields no blocks
    data = FIXTURE_A.read_bytes()[:604][:604]
    blocks = extract_photo_blocks(data, len(data), 0)
    assert blocks == []


def test_pairwise_diff_no_change_identical():
    a = _analysis()
    rows = pairwise_photo_diff(a, a)
    assert all(r.candidate_photo_change is False for r in rows)
    assert all(r.diff == pytest.approx(0.0) for r in rows)


def test_pairwise_diff_candidate_on_dist_change():
    a = _analysis()
    edited = bytearray(a.data)
    off = a.trailer_start + photo_blocks_rel(a.waypoint_count)
    edited[off : off + 4] = struct.pack(">f", 10.0)
    tmp = Path(__file__).parent / "fixtures" / "litchi" / "_tmp_matrix_synth.lchm"
    tmp.write_bytes(bytes(edited))
    try:
        b = analyze_file(tmp)
        rows = pairwise_photo_diff(a, b)
        assert rows[0].candidate_photo_change is True
        assert rows[0].new == pytest.approx(10.0)
        assert rows[1].candidate_photo_change is False
    finally:
        tmp.unlink(missing_ok=True)


def test_trailer_byte_diff_candidate_marking():
    a = _analysis()
    edited = bytearray(a.data)
    off = a.trailer_start + photo_blocks_rel(a.waypoint_count)
    edited[off : off + 4] = struct.pack(">f", 10.0)
    tmp = Path(__file__).parent / "fixtures" / "litchi" / "_tmp_matrix_synth.lchm"
    tmp.write_bytes(bytes(edited))
    try:
        b = analyze_file(tmp)
        changes = trailer_byte_diff(a, b)
        assert changes
        for c in changes:
            assert c.section == "trailer"
        text = format_byte_diff(a, b)
        assert "candidate photo_distinterval change" in text
        assert "20.6000" in text
        assert "10.0000" in text
    finally:
        tmp.unlink(missing_ok=True)


def test_trailer_byte_diff_no_changes_identical():
    a = _analysis()
    changes = trailer_byte_diff(a, a)
    assert changes == []


def test_sentinel_constant_value():
    assert SENTINEL == -1.0


def test_photo_blocks_rel_scales_with_waypoint_count():
    # 10 wp -> settings_start = 6 + 10*10 = 106; blocks at 106 + 106 = 212
    assert photo_blocks_rel(10) == 212
    # 65 wp -> settings_start = 6 + 65*10 = 656; blocks at 656 + 106 = 762
    assert photo_blocks_rel(65) == 762


def test_fixture_timeinterval_is_zero_or_absent():
    # fixture A (10 wp) stores 0.0 there (distance-based capture), not 5.0
    a = _analysis()
    assert a.timeinterval in (0.0, None)


def test_synthetic_65wp_timeinterval_extraction():
    # build a minimal synthetic trailer where rel 666-669 holds a global f32
    from lchm_photo_matrix import read_timeinterval  # noqa: E402

    n = 65
    settings = 6 + n * 10  # 656
    trailer = bytearray(settings + 106 + n * 8)
    trailer[settings + 10 : settings + 14] = struct.pack(">f", 3.0)
    data = b"\x00" * 44 + bytearray(n * 56) + bytes(trailer)
    assert read_timeinterval(data, 44 + n * 56, n) == pytest.approx(3.0)
