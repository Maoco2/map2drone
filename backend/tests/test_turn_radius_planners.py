from __future__ import annotations

import pytest

from app.modules.export.models import ExportWaypoint
from app.modules.planning.turn_radius.geometry import make_transformer, utm_epsg_for
from app.modules.planning.turn_radius.models import TurnRadiusInput, TurnStatus
from app.modules.planning.turn_radius.planners import (
    CorridorTurnPlanner,
    GridTurnPlanner,
    reconstruct_lines_from_waypoints,
)
from app.schemas.schemas import CorridorGeometry, CorridorResponse, WaypointSchema

BASE = (-3.5, 37.0)


def _ll(dx: float, dy: float) -> tuple[float, float]:
    """(lon, lat) for a UTM-meter offset around BASE."""
    epsg = utm_epsg_for(*BASE)
    fwd = make_transformer(4326, epsg)
    back = make_transformer(epsg, 4326)
    x, y = fwd.transform(*BASE)
    return back.transform(x + dx, y + dy)


def _grid_waypoints():
    """3 serpentine lines, spacing 30 m, headings 90 / 270 / 90."""
    wps = []
    lines = [(0, 0), (300, 0)], [(300, -30), (0, -30)], [(0, -60), (300, -60)]
    for i, ((x0, y0), (x1, y1)) in enumerate(lines):
        h = 90.0 if i % 2 == 0 else 270.0
        for x, y in ((x0, y0), (x1, y1)):
            lon, lat = _ll(x, y)
            wps.append(ExportWaypoint(latitude=lat, longitude=lon, altitude=100.0, heading=h))
    return wps


def _line_feature(x0, y0, x1, y1):
    lon0, lat0 = _ll(x0, y0)
    lon1, lat1 = _ll(x1, y1)
    return {
        "type": "Feature",
        "id": "cl",
        "geometry": {"type": "LineString", "coordinates": [[lon0, lat0], [lon1, lat1]]},
        "properties": {"type": "scan", "line": 0},
    }


def _serpentine_waypoints(lines):
    """Waypoints tracing the serpentine flight path of the given lines."""
    wps = []
    for i, ((x0, y0), (x1, y1)) in enumerate(lines):
        h = 90.0 if i % 2 == 0 else 270.0
        if i % 2 == 1:
            x0, x1 = x1, x0
        for x, y in ((x0, y0), (x1, y1)):
            lon, lat = _ll(x, y)
            wps.append(WaypointSchema(latitude=lat, longitude=lon, altitude=100.0, heading=h))
    return wps


def _corridor_response(lines, spacing: float, waypoints=None):
    features = [_line_feature(x0, y0, x1, y1) for (x0, y0), (x1, y1) in lines]
    geometry = CorridorGeometry(
        flight_lines_geojson={"type": "FeatureCollection", "features": features},
        epsg_out=4326,
        crs_name="WGS84",
    )
    if waypoints is None:
        waypoints = _serpentine_waypoints(lines)
    return CorridorResponse(
        waypoints=waypoints,
        total_distance=1000.0,
        estimated_time_sec=100.0,
        photo_count=10,
        battery_count=1,
        gsd=2.0,
        footprint_width=50.0,
        footprint_height=40.0,
        line_spacing=spacing,
        photo_spacing=10.0,
        recommended_speed_ms=6.8,
        geometry=geometry,
    )


# ── Reconstruction ──────────────────────────────────────────────────────────


def test_reconstruct_lines_from_waypoints():
    wps = _grid_waypoints()
    lines, headings, epsg, crs_name, groups = reconstruct_lines_from_waypoints(wps)
    assert len(lines) == 3
    assert headings[0] == pytest.approx(90.0, abs=0.1)
    assert headings[1] == pytest.approx(270.0, abs=0.1)
    assert groups == {0: [0, 1], 1: [2, 3], 2: [4, 5]}
    assert epsg >= 32600


# ── Grid planner ────────────────────────────────────────────────────────────


def test_grid_plan_valid_wide_spacing():
    plan = GridTurnPlanner().plan_from_waypoints(
        _grid_waypoints(),
        TurnRadiusInput(speed_ms=6.8, line_spacing_m=100.0),
        line_spacing=100.0,
        recommended_speed=6.8,
    )
    assert plan.status == TurnStatus.VALID.value
    assert plan.turn_count == 2
    assert plan.radius_m == pytest.approx(plan.turns[0].safe_radius_m)


def test_grid_plan_constrained_by_spacing():
    plan = GridTurnPlanner().plan_from_waypoints(
        _grid_waypoints(),
        TurnRadiusInput(speed_ms=6.8, line_spacing_m=30.0),
        line_spacing=30.0,
        recommended_speed=6.8,
    )
    assert plan.status == TurnStatus.CONSTRAINED.value
    assert plan.radius_m == pytest.approx((30.0 - 2 * 4.0) / 2.0)
    assert plan.per_waypoint_curve_size == {1: plan.radius_m, 3: plan.radius_m}


def test_grid_plan_irregular_spacing_uses_min():
    # Line spacings 20 m and 40 m -> the tightest (20-8)/2 = 6 m governs.
    wps = []
    lines = [(0, 0), (300, 0)], [(300, -20), (0, -20)], [(0, -60), (300, -60)]
    for i, ((x0, y0), (x1, y1)) in enumerate(lines):
        h = 90.0 if i % 2 == 0 else 270.0
        for x, y in ((x0, y0), (x1, y1)):
            lon, lat = _ll(x, y)
            wps.append(ExportWaypoint(latitude=lat, longitude=lon, altitude=100.0, heading=h))
    plan = GridTurnPlanner().plan_from_waypoints(wps, TurnRadiusInput(speed_ms=6.8), recommended_speed=6.8)
    assert plan.status == TurnStatus.CONSTRAINED.value
    assert plan.radius_m == pytest.approx(6.0, abs=0.01)


def test_grid_single_line_no_turns():
    wps = _grid_waypoints()[:2]
    plan = GridTurnPlanner().plan_from_waypoints(wps, TurnRadiusInput(speed_ms=6.8), recommended_speed=6.8)
    assert plan.turn_count == 0
    assert plan.status == TurnStatus.NONE.value


def test_grid_plan_deterministic():
    a = GridTurnPlanner().plan_from_waypoints(
        _grid_waypoints(), TurnRadiusInput(speed_ms=6.8, line_spacing_m=100.0), line_spacing=100.0
    )
    b = GridTurnPlanner().plan_from_waypoints(
        _grid_waypoints(), TurnRadiusInput(speed_ms=6.8, line_spacing_m=100.0), line_spacing=100.0
    )
    assert a.model_dump() == b.model_dump()


# ── Corridor planner ────────────────────────────────────────────────────────


def test_corridor_symmetric_valid():
    resp = _corridor_response([((0, 50), (300, 50)), ((0, -50), (300, -50))], spacing=100.0)
    plan = CorridorTurnPlanner().plan(resp, TurnRadiusInput(speed_ms=6.8))
    assert plan.status == TurnStatus.VALID.value
    assert plan.turn_count == 2  # one 90° turn per corner waypoint
    assert plan.turns[0].turn_angle_deg == pytest.approx(90.0, abs=1.0)


def test_corridor_asymmetric_valid():
    # Flight lines at +40 m and -10 m from the centerline -> 50 m separation.
    resp = _corridor_response([((0, 40), (300, 40)), ((0, -10), (300, -10))], spacing=50.0)
    plan = CorridorTurnPlanner().plan(resp, TurnRadiusInput(speed_ms=6.8))
    assert plan.status == TurnStatus.VALID.value
    assert plan.turn_count == 2
    assert plan.radius_m == pytest.approx(plan.turns[0].safe_radius_m)


def test_corridor_constrained_by_tight_spacing():
    resp = _corridor_response([((0, 15), (300, 15)), ((0, -15), (300, -15))], spacing=30.0)
    plan = CorridorTurnPlanner().plan(resp, TurnRadiusInput(speed_ms=6.8))
    assert plan.status == TurnStatus.CONSTRAINED.value
    assert plan.turn_count == 2
    assert plan.radius_m == pytest.approx((30.0 - 8.0) / 2.0)
    assert plan.per_waypoint_curve_size == {1: plan.radius_m, 2: plan.radius_m}


def test_corridor_single_line_bend_gets_turn():
    # Single flight line with a bend: the vertex waypoint gets its own turn.
    wps = [
        WaypointSchema(latitude=lat, longitude=lon, altitude=100.0, heading=90.0)
        for lon, lat in [_ll(0, 0), _ll(300, 0), _ll(300, 100)]
    ]
    resp = _corridor_response([((0, 0), (300, 0)), ((300, 0), (300, 100))], spacing=100.0, waypoints=wps)
    plan = CorridorTurnPlanner().plan(resp, TurnRadiusInput(speed_ms=6.8))
    assert plan.turn_count == 1
    assert plan.turns[0].turn_angle_deg == pytest.approx(90.0, abs=1.0)
    assert plan.per_waypoint_curve_size == {1: plan.radius_m}
    assert plan.status == TurnStatus.VALID.value


def test_corridor_turn_angle_90():
    # L-shaped single corner: one 90° turn at the corner waypoint.
    wps = [
        WaypointSchema(latitude=lat, longitude=lon, altitude=100.0, heading=90.0)
        for lon, lat in [_ll(0, 50), _ll(300, 50), _ll(300, -50)]
    ]
    resp = _corridor_response(
        [((0, 50), (300, 50)), ((300, 50), (300, -50))],
        spacing=50.0,
        waypoints=wps,
    )
    plan = CorridorTurnPlanner().plan(resp, TurnRadiusInput(speed_ms=6.8, line_spacing_m=50.0))
    assert plan.turn_count == 1
    assert plan.turns[0].turn_angle_deg == pytest.approx(90.0, abs=1.0)
    assert plan.status == TurnStatus.VALID.value


def test_corridor_single_line_no_turns():
    resp = _corridor_response([((0, 0), (300, 0))], spacing=100.0)
    plan = CorridorTurnPlanner().plan(resp, TurnRadiusInput(speed_ms=6.8))
    assert plan.turn_count == 0
    assert plan.status == TurnStatus.NONE.value


# ── Mission geometry ────────────────────────────────────────────────────────


def test_grid_plan_mission_geometry():
    plan = GridTurnPlanner().plan_from_waypoints(
        _grid_waypoints(),
        TurnRadiusInput(speed_ms=6.8, line_spacing_m=100.0),
        line_spacing=100.0,
        recommended_speed=6.8,
    )
    fc = plan.geometry
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 2 * 3  # 2 turns x (arc + center + buffer)
    kinds = {f["properties"]["kind"] for f in fc["features"]}
    assert kinds == {"turn_arc", "turn_center", "clearance_buffer"}
    for f in fc["features"]:
        assert f["properties"]["turn"] in (0, 1)
        geom_type = f["geometry"]["type"]
        coords = f["geometry"]["coordinates"]
        if geom_type == "Point":
            coords = [coords]
        elif geom_type == "Polygon":
            coords = coords[0]
        assert all(-180 <= c[0] <= 180 and -90 <= c[1] <= 90 for c in coords)


def test_corridor_plan_mission_geometry():
    resp = _corridor_response([((0, 15), (300, 15)), ((0, -15), (300, -15))], spacing=30.0)
    plan = CorridorTurnPlanner().plan(resp, TurnRadiusInput(speed_ms=6.8))
    assert plan.geometry["type"] == "FeatureCollection"
    assert len(plan.geometry["features"]) == 2 * 3  # 2 corner turns x (arc + center + buffer)


def test_no_turns_geometry_empty():
    plan = GridTurnPlanner().plan_from_waypoints(
        _grid_waypoints()[:2], TurnRadiusInput(speed_ms=6.8), recommended_speed=6.8
    )
    assert plan.geometry == {"type": "FeatureCollection", "features": []}
