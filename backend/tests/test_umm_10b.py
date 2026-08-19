"""Tests for the Fase 10B Universal Mission Model extensions.

Covers the rich blocks: typed waypoints, segments, capture plan, turn plan,
drone/camera profiles, normalized metrics, serialization round-trips,
versioning and backward compatibility.
"""

import pytest

from app.modules.mission import (
    build_universal_mission,
    is_supported_version,
    mission_from_dict,
    mission_to_dict,
    normalize_schema_version,
    parse_mission_blob,
    to_legacy_dict,
)
from app.modules.mission.models import (
    CaptureMode,
    CapturePlan,
    FlightSegment,
    TurnPlan,
    UniversalMission,
    UniversalWaypoint,
)
from app.schemas.schemas import WaypointSchema

# ── Fakes ────────────────────────────────────────────────────────────────────


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


def _waypoints():
    return [
        WaypointSchema(latitude=37.10, longitude=-3.60, altitude=100.0, heading=90.0, action_type=1),
        WaypointSchema(latitude=37.10, longitude=-3.55, altitude=100.0, heading=90.0, action_type=1),
        WaypointSchema(latitude=37.10, longitude=-3.50, altitude=100.0, heading=90.0, action_type=-1),
        WaypointSchema(latitude=37.12, longitude=-3.50, altitude=100.0, heading=270.0, action_type=1),
        WaypointSchema(latitude=37.12, longitude=-3.55, altitude=100.0, heading=270.0, action_type=1),
    ]


class _FakeResult:
    waypoints = _waypoints()
    total_distance = 1000.0
    estimated_time_sec = 150.0
    photo_count = 10
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
    photo_points = [{"index": 0, "latitude": 37.1, "longitude": -3.6, "capture": True}]
    geometry = None
    sweep_deg = 45.0
    mission_id = "m-1"


class _FakeReq:
    altitude = 100.0
    overlap_frontal = 75.0
    overlap_lateral = 65.0
    altitude_mode = "takeoff"
    drone_id = "dji-m3e"
    camera_id = "cam-43-20mp"
    dem_resolution_m = None
    turn_radius = {"mode": "AUTO", "mission_type": "AREA_GRID"}


# ── Rich block construction ──────────────────────────────────────────────────


def test_build_fills_parameters_and_metrics_blocks():
    mission = build_universal_mission("grid", _FakeReq(), _FakeResult())
    p = mission.parameters
    assert p.recommended_speed_mps == pytest.approx(6.8)
    assert p.gsd_cm == pytest.approx(2.74)
    assert p.footprint_width_m == pytest.approx(120.0)
    assert p.footprint_length_m == pytest.approx(80.0)
    assert p.overlap_front == pytest.approx(75.0)
    assert p.overlap_side == pytest.approx(65.0)
    assert p.line_spacing_m == pytest.approx(40.0)
    assert p.photo_spacing_m == pytest.approx(20.0)
    assert p.capture_mode == "TIME"
    assert p.turn_mode == "AUTO"
    assert p.turn_radius_m == pytest.approx(12.6)
    assert p.battery_count == 2
    assert p.estimated_time_s == pytest.approx(150.0)
    assert p.total_distance_m == pytest.approx(1000.0)
    assert p.photo_count == 10

    m = mission.metrics
    assert m.flight_distance_m == pytest.approx(1000.0)
    assert m.flight_time_s == pytest.approx(150.0)
    assert m.straight_flight_time_s == pytest.approx(150.0 - 5.8, abs=0.1)
    assert m.line_count == 2
    assert m.waypoint_count == 5
    assert m.estimated_energy is None


def test_build_typed_waypoints():
    mission = build_universal_mission("grid", _FakeReq(), _FakeResult())
    wps = mission.waypoints
    assert all(isinstance(w, UniversalWaypoint) for w in wps)
    assert wps[0].latitude == pytest.approx(37.10)
    assert wps[0].longitude == pytest.approx(-3.60)
    assert wps[0].altitude_m == pytest.approx(100.0)
    assert wps[0].heading_deg == pytest.approx(90.0)
    assert wps[0].action_type == 1
    assert wps[0].capture_enabled is True
    assert wps[0].curve_size_m == pytest.approx(12.6)
    assert wps[2].curve_size_m == pytest.approx(12.6)


def test_build_segments_with_turn_plan():
    mission = build_universal_mission("grid", _FakeReq(), _FakeResult())
    segs = mission.segments
    assert all(isinstance(s, FlightSegment) for s in segs)
    assert len(segs) == 3
    assert segs[0].is_turn_segment is False
    assert segs[0].start_waypoint == 0
    assert segs[0].end_waypoint == 1
    assert segs[0].line_index == 0
    assert segs[0].distance_m > 0
    assert segs[1].is_turn_segment is True
    assert segs[1].start_waypoint == 2
    assert segs[1].distance_m == pytest.approx(39.6)
    assert segs[1].duration_s == pytest.approx(5.8)
    assert segs[1].turn_angle_deg == pytest.approx(180.0)
    assert segs[2].is_turn_segment is False
    assert segs[2].line_index == 1
    # waypoint annotations
    assert mission.waypoints[0].line_index == 0
    assert mission.waypoints[3].line_index == 1
    assert mission.waypoints[2].segment_index == 1
    assert mission.waypoints[0].photo_index == 0


def test_build_capture_plan_preserves_scientific_and_commercial():
    mission = build_universal_mission("grid", _FakeReq(), _FakeResult())
    cp = mission.capture_plan
    assert cp is not None
    assert cp.mode == CaptureMode.TIME
    assert cp.scientific_interval_s == pytest.approx(5.3)
    assert cp.commercial_interval_s == 5
    assert cp.photo_spacing_m == pytest.approx(36.4)


def test_build_turn_plan_adapted():
    mission = build_universal_mission("grid", _FakeReq(), _FakeResult())
    tp = mission.turn_plan
    assert isinstance(tp, TurnPlan)
    assert tp.mode == "AUTO"
    assert tp.status == "VALID"
    assert tp.radius_m == pytest.approx(12.6)
    assert tp.safe_radius_m == pytest.approx(12.6)
    assert tp.available_radius_m == pytest.approx(15.0)
    assert tp.turn_count == 1
    assert tp.turn_duration_s == pytest.approx(5.8)
    assert tp.turn_distance_m == pytest.approx(39.6)


def test_build_no_turn_and_no_capture():
    result = _FakeResult()
    result.turn_radius_result = None
    result.capture_interval = None
    result.turn_radius_warnings = []
    mission = build_universal_mission("grid", _FakeReq(), result)
    assert mission.turn_plan is None
    assert mission.capture_plan is None
    assert mission.parameters.turn_mode == "NONE"
    assert mission.parameters.capture_mode == "NONE"
    assert len(mission.segments) == 1  # single straight run


def test_build_profiles_when_provided():
    class _Cam:
        id = "cam-43-20mp"
        name = "4/3 CMOS 20 MP"
        sensor_width_mm = 17.3
        sensor_height_mm = 13.0
        image_width_px = 5280
        image_height_px = 3956
        focal_length_mm = 12.0
        pixel_size_um = 3.27
        shutter_speed_s = 0.001
        shutter_type = "electronic"

    class _Dron:
        id = "dji-m3e"
        name = "Mavic 3 Enterprise (M3E)"
        manufacturer = "DJI"
        weight_kg = 0.915
        max_speed_ms = 21.0
        flight_time_min = 45.0
        max_altitude_m = 5000.0

    mission = build_universal_mission("grid", _FakeReq(), _FakeResult(), camera=_Cam(), drone=_Dron())
    cp = mission.camera_profile
    assert cp is not None
    assert cp.focal_length_mm == pytest.approx(12.0)
    assert cp.resolution_width_px == 5280
    dp = mission.drone_profile
    assert dp is not None
    assert dp.flight_time_min == pytest.approx(45.0)
    assert dp.dynamics.provenance.value == "DEFAULT"
    assert mission.parameters.flight_time_min == pytest.approx(45.0)


# ── Serialization / deserialization ─────────────────────────────────────────


def test_serialization_round_trip_preserves_blocks():
    mission = build_universal_mission("grid", _FakeReq(), _FakeResult())
    data = mission_to_dict(mission)
    reparsed = mission_from_dict(data)
    assert isinstance(reparsed, UniversalMission)
    assert reparsed.schema_version == mission.schema_version
    assert len(reparsed.waypoints) == len(mission.waypoints)
    assert isinstance(reparsed.waypoints[0], UniversalWaypoint)
    assert reparsed.waypoints[0].latitude == pytest.approx(37.10)
    assert len(reparsed.segments) == len(mission.segments)
    assert reparsed.capture_plan is not None
    assert reparsed.capture_plan.commercial_interval_s == 5
    assert reparsed.turn_plan is not None
    assert reparsed.turn_plan.radius_m == pytest.approx(12.6)
    assert reparsed.metrics.flight_time_s == pytest.approx(150.0)


def test_serialization_json_round_trip():
    import json

    mission = build_universal_mission("grid", _FakeReq(), _FakeResult())
    raw = json.dumps(mission_to_dict(mission))
    reparsed = parse_mission_blob(raw)
    assert reparsed.metrics.total_distance_m == pytest.approx(1000.0)


def test_legacy_serializer_maps_waypoints_back():
    mission = build_universal_mission("grid", _FakeReq(), _FakeResult())
    legacy = to_legacy_dict(mission)
    wp = legacy["waypoints"][0]
    assert wp["latitude"] == pytest.approx(37.10)
    assert wp["longitude"] == pytest.approx(-3.60)
    assert wp["altitude"] == pytest.approx(100.0)
    assert wp["heading"] == pytest.approx(90.0)
    assert wp["action_type"] == 1
    assert wp["action_param"] == 0
    assert "segments" in legacy
    assert "capture_plan" in legacy
    assert "turn_plan" in legacy


def test_legacy_round_trip_still_stable():
    mission = build_universal_mission("grid", _FakeReq(), _FakeResult())
    legacy = to_legacy_dict(mission)
    reparsed = parse_mission_blob(legacy)
    assert reparsed.metrics.total_distance_m == pytest.approx(1000.0)
    assert reparsed.parameters.speed_ms == pytest.approx(6.8)
    assert len(reparsed.photo_points) == 1
    assert len(reparsed.segments) == 3
    assert reparsed.capture_plan is not None


def test_legacy_waypoint_coercion_keeps_values():
    blob = {
        "mission_type": "grid",
        "waypoints": [
            {
                "latitude": 37.1,
                "longitude": -3.6,
                "altitude": 100.0,
                "heading": 12.0,
                "speed": 6.8,
                "action_type": 1,
                "action_param": 0,
                "elevation_msnm": 600.0,
                "agl": 100.0,
            }
        ],
        "total_distance": 10.0,
        "estimated_time_sec": 2.0,
        "photo_count": 1,
        "battery_count": 1,
        "gsd": 2.0,
        "footprint_width": 10.0,
        "footprint_height": 8.0,
        "line_spacing": 4.0,
        "photo_spacing": 2.0,
        "recommended_speed_ms": 6.8,
    }
    mission = parse_mission_blob(blob)
    wp = mission.waypoints[0]
    assert wp.altitude_m == pytest.approx(100.0)
    assert wp.heading_deg == pytest.approx(12.0)
    assert wp.speed_mps == pytest.approx(6.8)
    assert wp.terrain_elevation_m == pytest.approx(600.0)
    assert wp.agl_m == pytest.approx(100.0)
    assert wp.capture_enabled is True


# ── Versioning ───────────────────────────────────────────────────────────────


def test_version_normalization_and_support():
    assert normalize_schema_version("1.0.0") == "1.0"
    assert normalize_schema_version(None) == "1.0"
    assert is_supported_version("1.0") is True
    assert is_supported_version("2.0") is False
    assert is_supported_version("1.1") is False


def test_unknown_version_is_preserved_and_flagged():
    blob = {
        "schema_version": "2.0",
        "mission_type": "grid",
        "waypoints": [{"latitude": 37.1, "longitude": -3.6}],
        "total_distance": 10.0,
        "estimated_time_sec": 2.0,
        "photo_count": 1,
        "battery_count": 1,
        "gsd": 2.0,
        "footprint_width": 10.0,
        "footprint_height": 8.0,
        "line_spacing": 4.0,
        "photo_spacing": 2.0,
        "recommended_speed_ms": 6.8,
    }
    mission = parse_mission_blob(blob)
    assert mission.schema_version == "2.0"
    from app.modules.mission import UniversalMissionValidator

    result = UniversalMissionValidator().validate(mission)
    codes = {w.code for w in result.warnings}
    assert "unsupported_version" in codes


# ── Capture plan variants ────────────────────────────────────────────────────


def test_capture_plan_distance_mode():
    plan = CapturePlan(mode="DISTANCE", photo_spacing_m=12.5)
    assert plan.mode == CaptureMode.DISTANCE
    assert plan.photo_spacing_m == pytest.approx(12.5)


def test_capture_plan_none_mode():
    plan = CapturePlan(mode="NONE")
    assert plan.mode == CaptureMode.NONE
    assert plan.commercial_interval_s is None
