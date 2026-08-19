"""Fase 10D — turn radius + capture interval + LCHM integration (points 6-8).

Validates, on real engine output, the deterministic chain
speed → turn radius → turn time → mission time → battery, the use of the real
arc turn times instead of the ``num_lines * 5`` fallback, the capture-interval
behaviour (integer recommendation, decimal scientific value, floor policy in
the exporter adapter only), the TIME / DISTANCE / NONE modes, and the LCHM
round-trip of an optimized candidate (CURVED_TURNS, radius on interior
waypoints, speed/heading preserved).
"""

import math

import pytest

from app.core.photogrammetry.capture_interval import compute_capture_interval
from app.modules.export.adapters import from_universal_mission
from app.modules.export.litchi_lchm import (
    LchmExporter,
    LchmHeadingMode,
    LchmPathMode,
    normalize_litchi_time_interval,
    parse_lchm,
)
from app.modules.optimizer import evaluate
from app.modules.optimizer.candidate_builder import CandidateBuilder

from .corpus import (
    AUTO_TURN,
    MEDIUM_POLYGON,
    SMALL_POLYGON,
    build_corpus,
    get_case,
    grid_request,
)

# Radius cap on the SMALL grid (speed-independent, space-driven):
# available = (line_spacing - 2 * turn_clearance) / 2 with clearance 4 m.
EXPECTED_AVAILABLE_RADIUS_M = 22.22


def _build(db, *, altitude=100.0, speed=None, turn=None, photo_interval=None, polygon=SMALL_POLYGON):
    req = grid_request(polygon, altitude=altitude, turn_radius=turn)
    values = {"altitude_m": altitude}
    if speed is not None:
        values["speed_mps"] = speed
    if photo_interval is not None:
        values["photo_interval_s"] = photo_interval
    return CandidateBuilder("grid", req, db).build(values)


# ── Speed → radius → turn time → mission time → battery ──────────────────────


def test_speed_drives_turn_radius_and_status(db):
    candidates = {s: _build(db, speed=s, turn=AUTO_TURN) for s in (4.0, 6.8, 10.0, 14.0)}
    r = {s: c.turn_plan.radius_m for s, c in candidates.items()}
    assert r[4.0] == pytest.approx(4.44, abs=0.05)
    assert r[6.8] == pytest.approx(12.84, abs=0.05)
    assert r[10.0] == pytest.approx(EXPECTED_AVAILABLE_RADIUS_M, abs=0.05)
    assert r[14.0] == pytest.approx(EXPECTED_AVAILABLE_RADIUS_M, abs=0.05)
    # radius grows with speed until the space cap holds it back
    assert r[4.0] < r[6.8] < r[10.0] <= r[14.0]
    assert candidates[4.0].turn_plan.status == "VALID"
    assert candidates[6.8].turn_plan.status == "VALID"
    assert candidates[10.0].turn_plan.status == "CONSTRAINED"
    assert candidates[14.0].turn_plan.status == "CONSTRAINED"


def test_radius_scales_with_speed_squared_while_valid(db):
    r4 = _build(db, speed=4.0, turn=AUTO_TURN).turn_plan.radius_m
    r68 = _build(db, speed=6.8, turn=AUTO_TURN).turn_plan.radius_m
    assert r68 / r4 == pytest.approx((6.8 / 4.0) ** 2, rel=0.05)


def test_space_constrained_radius_caps_at_available(db):
    cand = _build(db, speed=14.0, turn=AUTO_TURN)
    plan = cand.turn_plan
    assert plan.status == "CONSTRAINED"
    assert plan.radius_m == pytest.approx(plan.available_radius_m, abs=1e-6)
    assert plan.available_radius_m == pytest.approx(EXPECTED_AVAILABLE_RADIUS_M, abs=0.05)
    # the space-driven cap matches the line spacing minus the turn clearances
    assert plan.available_radius_m == pytest.approx((cand.metrics.line_spacing_m - 2 * 4.0) / 2, abs=0.05)


def test_manual_turn_radius_is_honored(db):
    small = _build(db, speed=6.8, turn={"mode": "MANUAL", "manual_radius_m": 5.0})
    large = _build(db, speed=6.8, turn={"mode": "MANUAL", "manual_radius_m": 25.0})
    assert small.turn_plan.radius_m == 5.0
    assert small.turn_plan.status == "VALID"
    assert evaluate(small).valid is True
    assert large.turn_plan.radius_m == 25.0
    # the engine trusts the manual value, but the validator still guards it:
    # a manual radius beyond the space available on the grid is INVALID
    assert large.turn_plan.status == "VALID"
    assert large.turn_plan.available_radius_m == pytest.approx(EXPECTED_AVAILABLE_RADIUS_M, abs=0.05)
    assert evaluate(large).valid is False
    # a larger radius means a longer arc -> more turn time
    assert large.metrics.turn_time_s > small.metrics.turn_time_s


def test_arc_turn_times_used_instead_of_fallback(db):
    with_turn = _build(db, speed=6.8, turn=AUTO_TURN)
    assert with_turn.metrics.turn_source == "turn_plan"
    plan = with_turn.turn_plan
    expected = sum(t.get("turn_duration_s") or 0.0 for t in plan.turns)
    assert expected > 0
    assert with_turn.metrics.turn_time_s == pytest.approx(round(expected, 1), abs=0.15)

    no_turn = _build(db, speed=6.8)
    assert no_turn.metrics.turn_source == "overhead_fallback"
    num_lines = no_turn.metrics.line_count or no_turn.metrics.num_lines
    assert no_turn.metrics.turn_time_s == pytest.approx(num_lines * 5, abs=1e-6)


def test_battery_recomputed_from_real_flight_time(db):
    # slow, large survey -> several batteries required, always >= 1
    big = _build(db, speed=4.0, polygon=MEDIUM_POLYGON)
    expected = max(1, math.ceil((big.metrics.flight_time_s / 60) / (30 * 0.8)))
    assert expected > 1
    assert big.metrics.battery_count == expected

    small = _build(db, speed=6.8)
    expected_small = max(1, math.ceil((small.metrics.flight_time_s / 60) / (30 * 0.8)))
    assert small.metrics.battery_count == expected_small
    assert small.metrics.battery_count >= 1


# ── Capture interval ─────────────────────────────────────────────────────────


def test_capture_interval_consumed_not_reproduced(db):
    case = get_case(build_corpus(db), "grid_small_time")
    m = case.mission
    ci = compute_capture_interval(
        footprint_length_m=m.metrics.footprint_height_m,
        front_overlap=m.parameters.overlap_frontal,
        flight_speed_mps=m.parameters.speed_ms,
    )
    assert ci.recommended_interval_s == m.capture_plan.commercial_interval_s
    assert ci.ideal_interval_s == pytest.approx(m.capture_plan.scientific_interval_s, rel=1e-3)


def test_speed_forces_capture_interval_change(db):
    observed = {s: _build(db, speed=s).capture_plan.commercial_interval_s for s in (4.0, 6.8, 10.0, 12.0, 15.0)}
    assert observed == {4.0: 6, 6.8: 3, 10.0: 2, 12.0: 2, 15.0: 1}
    values = list(observed.values())
    assert values == sorted(values, reverse=True)  # non-increasing with speed


def test_scientific_decimal_not_floored_in_umm(db):
    cand = _build(db, speed=6.8, photo_interval=5.3)
    assert cand.capture_plan.scientific_interval_s == 5.3
    assert cand.parameters.capture_interval_s == 5.3
    # the commercial (engine) interval is untouched: the floor policy lives in
    # the exporter adapter, never in the universal engine
    assert cand.capture_plan.commercial_interval_s is not None
    export = from_universal_mission(cand)
    assert export.options["photo_capture"]["time_interval_s"] == cand.capture_plan.commercial_interval_s


def test_litchi_floor_policy_never_rounds_up():
    assert normalize_litchi_time_interval(5.3) == 5
    assert normalize_litchi_time_interval(5.7) == 5
    assert normalize_litchi_time_interval(5.0) == 5
    assert normalize_litchi_time_interval(1.0) == 1
    assert normalize_litchi_time_interval(None) is None
    assert normalize_litchi_time_interval(0) is None


def test_adapter_floors_scientific_when_no_commercial(db):
    case = get_case(build_corpus(db), "grid_small_time")
    mission = case.mission.model_copy(deep=True)
    mission.capture_plan.scientific_interval_s = 5.3
    mission.capture_plan.commercial_interval_s = None
    export = from_universal_mission(mission)
    assert export.options["photo_capture"] == {"mode": "TIME", "time_interval_s": 5}


# ── TIME / DISTANCE / NONE modes ─────────────────────────────────────────────


def test_capture_modes_time_distance_none(db):
    corpus = build_corpus(db)

    time_case = get_case(corpus, "grid_small_time")
    time_export = from_universal_mission(time_case.mission)
    assert time_export.options["photo_capture"]["mode"] == "TIME"
    assert (
        time_export.options["photo_capture"]["time_interval_s"] == time_case.mission.capture_plan.commercial_interval_s
    )

    dist_case = get_case(corpus, "grid_small_capture_distance")
    dist_export = from_universal_mission(dist_case.mission)
    assert dist_export.options["photo_capture"] == {"mode": "DISTANCE", "distance_interval_m": 15.0}

    none_case = get_case(corpus, "grid_small_capture_none")
    none_export = from_universal_mission(none_case.mission)
    assert none_export.options.get("photo_capture") is None


def test_distance_capture_exports_to_lchm(db):
    corpus = build_corpus(db)
    dist_case = get_case(corpus, "grid_small_capture_distance")
    result = LchmExporter().export(from_universal_mission(dist_case.mission))
    assert result.data  # serializes without raising (trailer with DISTANCE blocks)


# ── LCHM round-trip of an optimized candidate ────────────────────────────────


def test_lchm_roundtrip_of_turn_candidate(db):
    cand = _build(db, speed=6.8, turn=AUTO_TURN)
    export_data = from_universal_mission(cand)
    assert export_data.options["path_mode"] == "CURVED_TURNS"

    result = LchmExporter().export(export_data)
    parsed = parse_lchm(result.data if isinstance(result.data, bytes) else result.data.encode())

    assert parsed.path_mode == LchmPathMode.CURVED_TURNS
    assert parsed.heading_mode == LchmHeadingMode.FOLLOW_PATH
    assert len(parsed.waypoints) == len(cand.waypoints)

    # coordinates, speed and heading survive the round trip
    for parsed_wp, wp in zip(parsed.waypoints, cand.waypoints):
        assert parsed_wp.latitude == pytest.approx(wp.latitude, abs=1e-7)
        assert parsed_wp.longitude == pytest.approx(wp.longitude, abs=1e-7)
        assert parsed_wp.speed == pytest.approx(6.8, abs=1e-3)
        assert parsed_wp.heading == pytest.approx(wp.heading_deg, abs=1e-3)

    # Litchi encoding: zero curve on the first/last waypoint, the radius on
    # every interior waypoint
    radius = cand.turn_plan.radius_m
    assert parsed.waypoints[0].curve_radius_m == 0.0
    assert parsed.waypoints[-1].curve_radius_m == 0.0
    for interior in parsed.waypoints[1:-1]:
        assert interior.curve_radius_m == pytest.approx(radius, abs=0.05)
