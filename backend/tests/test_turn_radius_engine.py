from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from app.modules.planning.turn_radius.engine import TurnRadiusEngine
from app.modules.planning.turn_radius.geometry import generate_circular_arc, signed_turn_angle
from app.modules.planning.turn_radius.models import TurnRadiusInput, TurnRadiusMode, TurnStatus


def _engine() -> TurnRadiusEngine:
    return TurnRadiusEngine()


def _plan(engine, inp, start=(0.0, 0.0), h_in=90.0, h_out=270.0, angle=180.0, direction="RIGHT", epsg=32630):
    return engine.plan_turn(
        start=start,
        heading_in=h_in,
        heading_out=h_out,
        turn_angle_deg=angle,
        turn_direction=direction,
        inp=inp,
        epsg=epsg,
        crs_name="WGS 84 / UTM zone 30N",
    )


# ── Physics ─────────────────────────────────────────────────────────────────


def test_dynamic_radius_formula():
    assert TurnRadiusEngine.calculate_dynamic_radius(6.8, 4.5) == pytest.approx(6.8**2 / 4.5, rel=1e-9)


def test_dynamic_radius_raises_on_non_positive():
    with pytest.raises(ValueError):
        TurnRadiusEngine.calculate_dynamic_radius(0, 4.5)
    with pytest.raises(ValueError):
        TurnRadiusEngine.calculate_dynamic_radius(6.8, 0)


def test_safe_radius_formula():
    assert TurnRadiusEngine.calculate_safe_radius(10.0, 1.25) == pytest.approx(12.5)


def test_safe_radius_rejects_factor_below_one():
    with pytest.raises(ValueError):
        TurnRadiusEngine.calculate_safe_radius(10.0, 0.9)


def test_speed_variation_increases_radius():
    r1 = _plan(_engine(), TurnRadiusInput(speed_ms=5.0, line_spacing_m=100.0)).radius_m
    r2 = _plan(_engine(), TurnRadiusInput(speed_ms=10.0, line_spacing_m=100.0)).radius_m
    assert r2 > r1


# ── Available radius (analytic) ─────────────────────────────────────────────


def test_available_radius_uturn_spacing():
    inp = TurnRadiusInput(speed_ms=6.8, line_spacing_m=26.0, turn_angle_deg=180.0, turn_clearance_m=4.0)
    res = _plan(_engine(), inp)
    assert res.available_radius_m == pytest.approx((26.0 - 2 * 4.0) / 2.0)
    assert res.status == TurnStatus.CONSTRAINED.value
    assert res.radius_m == pytest.approx(9.0)


def test_available_radius_length_constraint():
    inp = TurnRadiusInput(speed_ms=6.8, line_spacing_m=100.0, available_length_m=20.0, turn_clearance_m=4.0)
    res = _plan(_engine(), inp)
    assert res.available_radius_m == pytest.approx(16.0)


def test_available_radius_takes_min_of_constraints():
    inp = TurnRadiusInput(speed_ms=6.8, line_spacing_m=30.0, available_length_m=10.0, turn_clearance_m=4.0)
    res = _plan(_engine(), inp)
    # width -> (30-8)/2 = 11 ; length -> 10-4 = 6
    assert res.available_radius_m == pytest.approx(6.0)


def test_available_radius_unconstrained_returns_max():
    inp = TurnRadiusInput(speed_ms=6.8)
    assert _engine().calculate_available_radius(inp, 180.0, (0.0, 0.0), 90.0, 270.0, "RIGHT") == pytest.approx(50.0)


def test_available_radius_geometric_matches_analytic():
    # Maneuver region: 30 m of free space below the line start (y in [-30, 30]).
    boundary = Polygon([(-60.0, -30.0), (60.0, -30.0), (60.0, 30.0), (-60.0, 30.0)])
    inp = TurnRadiusInput(speed_ms=6.8, turn_angle_deg=180.0, turn_clearance_m=4.0, available_length_m=30.0)
    engine = _engine()
    analytic = engine.calculate_available_radius(inp, 180.0, (0.0, 0.0), 90.0, 270.0, "RIGHT")
    geometric = engine.calculate_available_radius(inp, 180.0, (0.0, 0.0), 90.0, 270.0, "RIGHT", boundary=boundary)
    assert analytic == pytest.approx(26.0)  # length 30 - clearance 4
    assert geometric == pytest.approx(13.0, abs=0.5)  # 2R + clearance <= 30


# ── Geometry ────────────────────────────────────────────────────────────────


def test_generate_arc_right_start_and_tangents():
    arc, center = generate_circular_arc((0.0, 0.0), 90.0, 270.0, 10.0, "RIGHT", 180.0)
    start = arc.coords[0]
    end = arc.coords[-1]
    assert start == pytest.approx((0.0, 0.0))
    # RIGHT U-turn radius 10: center 10 m south of start, end 20 m south.
    assert center.x == pytest.approx(0.0, abs=1e-6)
    assert center.y == pytest.approx(-10.0, abs=1e-6)
    assert end == pytest.approx((0.0, -20.0), abs=0.05)


def test_generate_arc_left():
    arc, center = generate_circular_arc((0.0, 0.0), 270.0, 90.0, 10.0, "LEFT", 180.0)
    assert center.y == pytest.approx(-10.0, abs=1e-6)
    assert arc.coords[-1] == pytest.approx((0.0, -20.0), abs=0.05)


def test_arc_length_formula():
    from app.modules.planning.turn_radius.geometry import arc_length

    assert arc_length(10.0, 180.0) == pytest.approx(10.0 * 3.141592653589793)
    assert arc_length(10.0, 90.0) == pytest.approx(10.0 * 3.141592653589793 / 2)


def test_turn_distance_and_duration():
    res = _plan(_engine(), TurnRadiusInput(speed_ms=6.8, line_spacing_m=100.0))
    assert res.turn_distance_m == pytest.approx(res.radius_m * 3.141592653589793, rel=0.01)
    assert res.turn_duration_s == pytest.approx(res.turn_distance_m / res.turn_speed_ms, rel=1e-6)


def test_signed_turn_angle():
    assert signed_turn_angle(90.0, 270.0) == pytest.approx(180.0)
    assert signed_turn_angle(270.0, 90.0) == pytest.approx(180.0)
    assert signed_turn_angle(0.0, 90.0) == pytest.approx(90.0)
    assert signed_turn_angle(0.0, 350.0) == pytest.approx(-10.0)
    assert signed_turn_angle(0.0, 180.0) == pytest.approx(180.0)
    assert signed_turn_angle(180.0, 0.0) == pytest.approx(180.0)


# ── Modes / validation ──────────────────────────────────────────────────────


def test_plan_auto_valid():
    res = _plan(_engine(), TurnRadiusInput(speed_ms=6.8, line_spacing_m=100.0))
    assert res.status == TurnStatus.VALID.value
    assert res.radius_m == pytest.approx(res.safe_radius_m)
    assert not res.warnings


def test_plan_auto_constrained_not_silent():
    res = _plan(_engine(), TurnRadiusInput(speed_ms=6.8, line_spacing_m=26.0))
    assert res.status == TurnStatus.CONSTRAINED.value
    assert res.radius_m == pytest.approx(9.0)
    assert any("NOT reduced silently" in w for w in res.warnings)
    assert any("Mitigations" in w for w in res.warnings)


def test_plan_manual_warning_not_blocking():
    inp = TurnRadiusInput(speed_ms=6.8, mode=TurnRadiusMode.MANUAL, manual_radius_m=60.0)
    res = _plan(_engine(), inp)
    assert res.status == TurnStatus.CONSTRAINED.value
    assert res.radius_m == pytest.approx(60.0)
    assert any("maximum" in w for w in res.warnings)


def test_plan_manual_invalid_below_min():
    inp = TurnRadiusInput(speed_ms=6.8, mode=TurnRadiusMode.MANUAL, manual_radius_m=0.5)
    res = _plan(_engine(), inp)
    assert res.status == TurnStatus.INVALID.value


def test_plan_none():
    res = _plan(_engine(), TurnRadiusInput(speed_ms=6.8, mode=TurnRadiusMode.NONE))
    assert res.status == TurnStatus.NONE.value
    assert res.radius_m == 0.0


def test_validate_turn_invalid_zero():
    engine = _engine()
    status, warnings = engine.validate_turn(0.0, 180.0, 2.0, 50.0)
    assert status == TurnStatus.INVALID
    assert warnings


def test_validate_turn_constrained_over_max():
    engine = _engine()
    status, warnings = engine.validate_turn(60.0, 180.0, 2.0, 50.0)
    assert status == TurnStatus.CONSTRAINED
    assert warnings


def test_validate_turn_valid():
    engine = _engine()
    status, warnings = engine.validate_turn(10.0, 180.0, 2.0, 50.0)
    assert status == TurnStatus.VALID
    assert not warnings


def test_plan_turn_geojson_geometry():
    res = _plan(_engine(), TurnRadiusInput(speed_ms=6.8, line_spacing_m=100.0), epsg=32630)
    fc = res.geometry
    assert fc.get("type") == "FeatureCollection"
    kinds = {f["properties"]["kind"] for f in fc.get("features", [])}
    assert {"turn_arc", "turn_center", "clearance_buffer"} <= kinds


def test_geometry_coordinates_are_lonlat_not_degrees_meters():
    res = _plan(_engine(), TurnRadiusInput(speed_ms=6.8, line_spacing_m=100.0), epsg=32630)
    arc = next(f for f in res.geometry["features"] if f["properties"]["kind"] == "turn_arc")
    coords = arc["geometry"]["coordinates"]
    for lon, lat in coords:
        assert -180 <= lon <= 180
        assert -90 <= lat <= 90
        assert abs(lon) < 180 and abs(lat) < 90


def test_clearance_affects_available_radius():
    inp = TurnRadiusInput(speed_ms=6.8, line_spacing_m=30.0, turn_clearance_m=8.0)
    res = _plan(_engine(), inp)
    assert res.available_radius_m == pytest.approx((30.0 - 16.0) / 2.0)


def test_photo_capture_not_recommended_during_turn():
    res = _plan(_engine(), TurnRadiusInput(speed_ms=6.8, line_spacing_m=100.0))
    assert res.photo_capture_recommended_during_turn is False


def test_turn_extension_auto_equals_radius():
    res = _plan(_engine(), TurnRadiusInput(speed_ms=6.8, line_spacing_m=100.0))
    assert res.extension_before_m == pytest.approx(res.radius_m)
    assert res.extension_after_m == pytest.approx(res.radius_m)


def test_turn_extension_explicit():
    res = _plan(_engine(), TurnRadiusInput(speed_ms=6.8, line_spacing_m=100.0, turn_extension_m=15.0))
    assert res.extension_before_m == 15.0
    assert res.extension_after_m == 15.0


def test_determinism():
    engine = _engine()
    inp = TurnRadiusInput(speed_ms=6.8, line_spacing_m=30.0)
    a = _plan(engine, inp)
    b = _plan(engine, inp)
    assert a.model_dump() == b.model_dump()
