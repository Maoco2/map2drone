from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.modules.export import ExportWaypoint, MissionExportData, get_exporter
from app.modules.export.litchi_lchm import (
    LCHM_HEADER_SIZE,
    LCHM_WAYPOINT_RECORD_SIZE,
    LchmHeadingMode,
    LchmPathMode,
    parse_lchm,
)
from app.modules.planning.turn_radius.engine import TurnRadiusEngine
from app.modules.planning.turn_radius.geometry import make_transformer, utm_epsg_for
from app.modules.planning.turn_radius.integration import apply_turn_radii, compute_turn_radius_plan
from app.modules.planning.turn_radius.models import TurnRadiusInput

REFERENCE = Path(__file__).parent / "fixtures" / "litchi" / "real" / "area_grid_74_time5_curve.lchm"

BASE = (-3.5, 37.0)


def _ll(dx: float, dy: float) -> tuple[float, float]:
    epsg = utm_epsg_for(*BASE)
    fwd = make_transformer(4326, epsg)
    back = make_transformer(epsg, 4326)
    x, y = fwd.transform(*BASE)
    return back.transform(x + dx, y + dy)


def _grid_waypoints() -> list[ExportWaypoint]:
    wps = []
    lines = [(0, 0), (300, 0)], [(300, -100), (0, -100)], [(0, -200), (300, -200)]
    for i, ((x0, y0), (x1, y1)) in enumerate(lines):
        h = 90.0 if i % 2 == 0 else 270.0
        for x, y in ((x0, y0), (x1, y1)):
            lon, lat = _ll(x, y)
            wps.append(ExportWaypoint(latitude=lat, longitude=lon, altitude=100.0, heading=h))
    return wps


# ── Adapter ─────────────────────────────────────────────────────────────────


def test_apply_turn_radii_auto_sets_uniform_curve_size():
    wps = _grid_waypoints()
    options = {"turn_radius": {"mode": "AUTO", "speed_ms": 6.8, "line_spacing_m": 100.0}}
    out, plan, warnings = apply_turn_radii(wps, options, default_speed=6.8)
    assert plan is not None
    assert plan.radius_m > 0
    assert plan.status in ("VALID", "CONSTRAINED")
    assert all(wp.curve_size == plan.radius_m for wp in out)
    assert not warnings


def test_apply_turn_radii_none_clears_curve_size():
    wps = _grid_waypoints()
    for wp in wps:
        wp.curve_size = 12.6
    options = {"turn_radius": {"mode": "NONE"}}
    out, plan, warnings = apply_turn_radii(wps, options, default_speed=6.8)
    assert plan is None
    assert all(wp.curve_size == 0.0 for wp in out)


def test_apply_turn_radii_manual_valid():
    wps = _grid_waypoints()
    options = {"turn_radius": {"mode": "MANUAL", "manual_radius_m": 12.0}}
    out, plan, warnings = apply_turn_radii(wps, options, default_speed=6.8)
    assert plan.radius_m == pytest.approx(12.0)
    assert all(wp.curve_size == pytest.approx(12.0) for wp in out)


def test_apply_turn_radii_manual_invalid_blocks():
    wps = _grid_waypoints()
    options = {"turn_radius": {"mode": "MANUAL", "manual_radius_m": 0.1}}
    out, plan, warnings = apply_turn_radii(wps, options, default_speed=6.8)
    assert plan.status == "INVALID"
    assert plan.radius_m == 0.0
    assert all(wp.curve_size == 0.0 for wp in out)
    assert warnings


def test_compute_turn_radius_plan_none():
    plan, warnings = compute_turn_radius_plan(_grid_waypoints(), {"mode": "NONE"}, recommended_speed=6.8)
    assert plan is None
    assert warnings == []


def test_compute_turn_radius_plan_auto():
    wps = _grid_waypoints()
    plan, warnings = compute_turn_radius_plan(
        wps, {"mode": "AUTO", "speed_ms": 6.8, "line_spacing_m": 100.0}, recommended_speed=6.8
    )
    assert plan is not None
    assert plan.status in ("VALID", "CONSTRAINED")
    assert plan.radius_m > 0
    assert plan.geometry["type"] == "FeatureCollection"
    # compute_turn_radius_plan does NOT mutate the waypoints.
    assert all(wp.curve_size == 0.0 for wp in wps)


def test_compute_turn_radius_plan_manual():
    plan, warnings = compute_turn_radius_plan(
        _grid_waypoints(), {"mode": "MANUAL", "manual_radius_m": 12.0}, recommended_speed=6.8
    )
    assert plan.radius_m == pytest.approx(12.0)
    assert plan.status in ("VALID", "CONSTRAINED")


def test_compute_turn_radius_plan_corridor_geometry():
    wps = _grid_waypoints()
    features = []
    for (x0, y0), (x1, y1) in [((0, 15), (300, 15)), ((0, -15), (300, -15))]:
        lon0, lat0 = _ll(x0, y0)
        lon1, lat1 = _ll(x1, y1)
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[lon0, lat0], [lon1, lat1]]},
                "properties": {"type": "scan"},
            }
        )
    plan, warnings = compute_turn_radius_plan(
        wps,
        {"mode": "AUTO", "speed_ms": 6.8},
        mission_type="LINEAR_CORRIDOR",
        line_spacing=30.0,
        recommended_speed=6.8,
        flight_lines_geojson={"type": "FeatureCollection", "features": features},
    )
    assert plan is not None
    assert plan.mission_type == "LINEAR_CORRIDOR"
    assert plan.turn_count == 1
    assert plan.radius_m == pytest.approx((30.0 - 8.0) / 2.0)


# ── LCHM export consumes curve_size ─────────────────────────────────────────


def test_lchm_export_serializes_engine_radius():
    exporter = get_exporter("litchi_lchm")
    wps = _grid_waypoints()
    options = {"turn_radius": {"mode": "AUTO", "speed_ms": 6.8, "line_spacing_m": 100.0}}
    wps, plan, _ = apply_turn_radii(wps, options, default_speed=6.8)
    mission = MissionExportData(
        project_name="turn_radius_grid",
        waypoints=wps,
        speed_ms=6.8,
        options={"path_mode": "CURVED_TURNS", "heading_mode": "CUSTOM_POI"},
    )
    result = exporter.export(mission)
    parsed = parse_lchm(result.data)
    assert parsed.path_mode == LchmPathMode.CURVED_TURNS
    assert parsed.heading_mode == LchmHeadingMode.CUSTOM_POI
    # Uniform engine radius on every interior waypoint; exporter zeroes first/last.
    for i, wp in enumerate(parsed.waypoints):
        rec = result.data[LCHM_HEADER_SIZE + i * LCHM_WAYPOINT_RECORD_SIZE :]
        radius_bytes = struct.unpack(">f", rec[36:40])[0]
        if i in (0, len(parsed.waypoints) - 1):
            assert wp.curve_radius_m == 0.0
            assert radius_bytes == 0.0
        else:
            assert wp.curve_radius_m == pytest.approx(plan.radius_m, abs=0.001)
            assert radius_bytes == pytest.approx(plan.radius_m, abs=0.001)


# ── API wiring (_build_mission) ─────────────────────────────────────────────


def test_build_mission_applies_turn_radii():
    from app.api.v1.endpoints import _build_mission
    from app.schemas.schemas import ExportRequest, ExportWaypointSchema

    wps = []
    lines = [(0, 0), (300, 0)], [(300, -100), (0, -100)]
    for i, ((x0, y0), (x1, y1)) in enumerate(lines):
        h = 90.0 if i % 2 == 0 else 270.0
        for x, y in ((x0, y0), (x1, y1)):
            lon, lat = _ll(x, y)
            wps.append(ExportWaypointSchema(latitude=lat, longitude=lon, altitude=100.0, heading=h))

    req = ExportRequest(
        project_name="turn_radius_api",
        waypoints=wps,
        speed=6.8,
        options={"turn_radius": {"mode": "AUTO", "speed_ms": 6.8, "line_spacing_m": 100.0}},
    )
    mission = _build_mission(req)
    result_radius = mission.options["turn_radius_result"]["radius_m"]
    assert result_radius > 0
    assert all(wp.curve_size == pytest.approx(result_radius) for wp in mission.waypoints)


def test_build_mission_without_turn_radius_unchanged():
    from app.api.v1.endpoints import _build_mission
    from app.schemas.schemas import ExportRequest, ExportWaypointSchema

    lon, lat = _ll(0, 0)
    req = ExportRequest(
        project_name="plain",
        waypoints=[ExportWaypointSchema(latitude=lat, longitude=lon, altitude=100.0, heading=0.0)],
        speed=6.8,
    )
    mission = _build_mission(req)
    assert all(wp.curve_size == 0.0 for wp in mission.waypoints)
    assert "turn_radius" not in mission.options


# ── Regression vs physical file (no hardcoded final value) ──────────────────


def test_regression_area_grid_74_curve():
    """Reproduce the physical file's turn radius from its own data.

    The reference mission (area_grid_74_time5_curve.lchm) flies at ~6.81 m/s
    with a median curve radius of ~12.637 m. The engine derives the implied
    lateral acceleration from those two values (a_lat = v² / (R/1.25)) and
    must reproduce the observed radius — the formula is validated against the
    real file instead of hardcoding 12.637.
    """
    assert REFERENCE.exists(), f"reference fixture missing: {REFERENCE}"
    data = REFERENCE.read_bytes()
    parsed = parse_lchm(data)

    assert parsed.path_mode == LchmPathMode.CURVED_TURNS
    assert parsed.heading_mode == LchmHeadingMode.CUSTOM_POI
    assert parsed.waypoint_count == 74

    radii = sorted(wp.curve_radius_m for wp in parsed.waypoints if wp.curve_radius_m > 0)
    speeds = sorted(wp.speed for wp in parsed.waypoints)
    assert len(radii) == 72  # first and last waypoint carry no curve
    observed = radii[len(radii) // 2]
    survey_speed = speeds[len(speeds) // 2]

    assert observed == pytest.approx(12.637, abs=0.01)  # sanity of the fixture itself
    implied_a_lat = survey_speed**2 / (observed / 1.25)

    engine = TurnRadiusEngine()
    inp = TurnRadiusInput(
        speed_ms=survey_speed,
        max_lateral_acceleration_ms2=implied_a_lat,
        line_spacing_m=100.0,
        safety_factor=1.25,
    )
    res = engine.plan_turn(
        start=(0.0, 0.0),
        heading_in=90.0,
        heading_out=270.0,
        turn_angle_deg=180.0,
        turn_direction="RIGHT",
        inp=inp,
        epsg=32630,
        crs_name="WGS 84 / UTM zone 30N",
    )
    assert res.safe_radius_m == pytest.approx(observed, rel=0.01)
    assert res.radius_m == pytest.approx(observed, rel=0.01)
