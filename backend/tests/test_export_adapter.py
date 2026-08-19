"""Tests for the export adapter: Universal Mission → MissionExportData → LCHM.

Acceptance: a mission that generates N waypoints, TIME capture, speed S and
CURVED_TURNS must generate exactly that information after passing through the
Universal Mission Model.
"""

import pytest

from app.modules.export import get_exporter
from app.modules.export.adapters import from_universal_mission
from app.modules.export.litchi_lchm import LchmPathMode, parse_lchm
from app.modules.mission import build_universal_mission
from app.schemas.schemas import WaypointSchema


class _FakeCaptureBlock:
    def model_dump(self, mode="json"):
        return {
            "status": "VALID",
            "recommended_interval_s": 5,
            "ideal_interval_s": 5.3,
            "actual_photo_spacing_m": 36.4,
            "required_photo_spacing_m": 37.8,
            "required_front_overlap": 75.0,
        }


_TURN_PLAN = {
    "mission_type": "AREA_GRID",
    "mode": "AUTO",
    "status": "VALID",
    "radius_m": 12.6,
    "turn_count": 1,
    "turns": [
        {
            "mode": "AUTO",
            "status": "VALID",
            "radius_m": 12.6,
            "safe_radius_m": 12.6,
            "available_radius_m": 15.0,
            "turn_angle_deg": 180.0,
            "turn_speed_ms": 6.8,
            "turn_distance_m": 39.6,
            "turn_duration_s": 5.8,
            "photo_capture_recommended_during_turn": False,
            "warnings": [],
            "geometry": {"type": "FeatureCollection", "features": []},
        }
    ],
    "per_waypoint_curve_size": {2: 12.6},
    "warnings": [],
    "geometry": {"type": "FeatureCollection", "features": []},
    "epsg": 32630,
}


class _FakeResult:
    waypoints = [
        WaypointSchema(latitude=37.10, longitude=-3.60, altitude=100.0, heading=90.0, action_type=1),
        WaypointSchema(latitude=37.10, longitude=-3.55, altitude=100.0, heading=90.0, action_type=1),
        WaypointSchema(latitude=37.10, longitude=-3.50, altitude=100.0, heading=90.0, action_type=-1),
        WaypointSchema(latitude=37.12, longitude=-3.50, altitude=100.0, heading=270.0, action_type=1),
        WaypointSchema(latitude=37.12, longitude=-3.55, altitude=100.0, heading=270.0, action_type=1),
    ]
    total_distance = 1000.0
    estimated_time_sec = 150.0
    photo_count = 4
    battery_count = 2
    gsd = 2.74
    footprint_width = 120.0
    footprint_height = 80.0
    line_spacing = 40.0
    photo_spacing = 20.0
    recommended_speed_ms = 6.8
    num_lines = 2
    waypoint_mode = "photo"
    warnings = []
    capture_interval = _FakeCaptureBlock()
    turn_radius_result = _TURN_PLAN
    turn_radius_warnings = []
    flight_lines_geojson = {"type": "FeatureCollection", "features": []}
    photo_points = []
    geometry = None
    sweep_deg = 45.0
    mission_id = None


class _FakeReq:
    altitude = 100.0
    overlap_frontal = 75.0
    overlap_lateral = 65.0
    altitude_mode = "takeoff"
    drone_id = "dji-m3e"
    camera_id = "cam-43-20mp"
    dem_resolution_m = None
    turn_radius = {"mode": "AUTO", "mission_type": "AREA_GRID"}


def test_adapter_preserves_waypoints_speed_curve_and_capture():
    mission = build_universal_mission("grid", _FakeReq(), _FakeResult())
    data = from_universal_mission(mission)

    assert len(data.waypoints) == 5
    assert data.speed_ms == pytest.approx(6.8)
    assert data.capture_interval_s == 5
    assert data.photo_count == 4

    assert data.options["path_mode"] == "CURVED_TURNS"
    assert data.options["heading_mode"] == "FOLLOW_PATH"
    capture = data.options["photo_capture"]
    assert capture["mode"] == "TIME"
    assert capture["time_interval_s"] == 5

    assert data.waypoints[0].curve_size == pytest.approx(12.6)
    assert data.waypoints[0].speed == pytest.approx(6.8)
    assert data.waypoints[0].action_type == 1
    assert data.waypoints[2].curve_size == pytest.approx(12.6)


def test_adapter_no_turn_no_capture():
    result = _FakeResult()
    result.turn_radius_result = None
    result.capture_interval = None
    mission = build_universal_mission("grid", _FakeReq(), result)
    data = from_universal_mission(mission)
    assert data.options["path_mode"] == "STRAIGHT"
    assert data.options.get("photo_capture") is None
    assert data.capture_interval_s is None
    assert all(wp.curve_size == 0 for wp in data.waypoints)


def test_lchm_export_from_umm_preserves_waypoints_speed_and_curve():
    mission = build_universal_mission("grid", _FakeReq(), _FakeResult())
    data = from_universal_mission(mission)
    exporter = get_exporter("litchi_lchm")
    result = exporter.export(data)
    parsed = parse_lchm(result.data)

    assert parsed.waypoint_count == 5
    assert parsed.path_mode == LchmPathMode.CURVED_TURNS
    assert parsed.waypoints[0].speed == pytest.approx(6.8, abs=0.01)
    assert parsed.waypoints[1].curve_radius_m == pytest.approx(12.6, abs=0.01)
    # LCHM forces the first/last waypoint radius to zero (documented behaviour)
    assert parsed.waypoints[0].curve_radius_m == 0.0
    assert parsed.waypoints[4].curve_radius_m == 0.0


def test_real_grid_umm_preserves_every_engine_value():
    """A real grid mission must survive the UMM round-trip with equal values.

    The Universal Mission preserves all engine values (count, speed, interval,
    radius). Note: the LCHM binary is capped at 99 waypoints (u8 header + Litchi
    limit); a 352-waypoint grid cannot be byte-represented by the format, so the
    equivalence is asserted at the adapter level (UMM → MissionExportData).
    """
    from fastapi.testclient import TestClient

    from app.main import app
    from app.schemas.schemas import GridRequest, GridResponse

    client = TestClient(app)
    req_json = {
        "polygon": {
            "type": "Polygon",
            "coordinates": [[[-3.60, 37.10], [-3.50, 37.10], [-3.50, 37.20], [-3.60, 37.20], [-3.60, 37.10]]],
        },
        "altitude": 100,
        "overlap_frontal": 75,
        "overlap_lateral": 65,
        "camera_id": "cam-43-20mp",
        "drone_id": "dji-m3e",
        "altitude_mode": "takeoff",
        "turn_radius": {"mode": "AUTO", "mission_type": "AREA_GRID"},
    }
    resp = client.post("/api/v1/planning/grid", json=req_json)
    assert resp.status_code == 200, resp.text
    grid = resp.json()

    result = GridResponse(**grid)
    mission = build_universal_mission("grid", GridRequest(**req_json), result)
    data = from_universal_mission(mission)

    assert len(mission.waypoints) == len(grid["waypoints"])
    assert len(data.waypoints) == len(grid["waypoints"])
    assert data.speed_ms == pytest.approx(grid["recommended_speed_ms"], abs=0.01)
    assert data.options["path_mode"] == "CURVED_TURNS"
    assert data.capture_interval_s == grid["capture_interval"]["recommended_interval_s"]
    assert data.options["photo_capture"]["time_interval_s"] == grid["capture_interval"]["recommended_interval_s"]
    tr = grid["turn_radius_result"]
    assert tr is not None
    assert mission.turn_plan.radius_m == pytest.approx(tr["radius_m"], abs=0.01)
    assert data.options["turn_radius_result"]["radius_m"] == pytest.approx(tr["radius_m"], abs=0.01)
