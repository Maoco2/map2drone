"""Tests for the Universal Mission Model (Fase 10A)."""

import pytest

from app.modules.mission import (
    build_universal_mission,
    parse_mission_blob,
    to_legacy_dict,
)
from app.modules.mission.models import UniversalMission

# --- Legacy flat blob (historical `result.model_dump()` shape) ----------------


def _legacy_flat_blob() -> dict:
    return {
        "waypoints": [
            {
                "latitude": 37.1,
                "longitude": -3.6,
                "altitude": 100.0,
                "heading": 0.0,
                "action_type": 1,
            }
        ],
        "total_distance": 1234.56,
        "estimated_time_sec": 180.5,
        "photo_count": 1,
        "battery_count": 2,
        "gsd": 2.74,
        "footprint_width": 120.5,
        "footprint_height": 80.3,
        "line_spacing": 42.2,
        "photo_spacing": 20.1,
        "recommended_speed_ms": 6.8,
        "num_lines": 4,
        "waypoint_mode": "vertex",
        "warnings": ["Elevation data unavailable"],
        "capture_interval": {"status": "VALID", "recommended_interval_s": 3},
    }


def test_parse_legacy_flat_blob_builds_umm():
    mission = parse_mission_blob(_legacy_flat_blob())
    assert isinstance(mission, UniversalMission)
    assert mission.mission_type == "grid"
    assert mission.metrics.total_distance_m == pytest.approx(1234.56)
    assert mission.metrics.estimated_time_sec == pytest.approx(180.5)
    assert mission.metrics.battery_count == 2
    assert mission.metrics.gsd_cm == pytest.approx(2.74)
    assert mission.metrics.num_lines == 4
    assert mission.parameters.altitude_mode == "vertex"
    assert mission.parameters.speed_ms == pytest.approx(6.8)
    assert mission.capture_interval["recommended_interval_s"] == 3
    assert len(mission.waypoints) == 1


def test_parse_legacy_flat_blob_as_string():
    import json

    mission = parse_mission_blob(json.dumps(_legacy_flat_blob()))
    assert mission.metrics.total_distance_m == pytest.approx(1234.56)


def test_parse_legacy_blob_with_corridor_geometry():
    data = _legacy_flat_blob()
    data["geometry"] = {
        "polygon_geojson": {"type": "Polygon", "coordinates": [[]]},
        "flight_lines_geojson": {"type": "FeatureCollection", "features": []},
        "centerline_geojson": {"type": "LineString", "coordinates": []},
        "epsg_out": 32630,
        "crs_name": "WGS 84 / UTM zone 30N",
        "transformation": "EPSG:4326 -> EPSG:32630",
    }
    mission = parse_mission_blob(data)
    assert mission.mission_type == "linear_corridor"
    assert mission.geometry is not None
    assert mission.geometry.epsg_out == 32630


def test_parse_invalid_payload_raises():
    with pytest.raises(Exception):
        parse_mission_blob("not json")
    with pytest.raises(Exception):
        parse_mission_blob([])


# --- Builder ----------------------------------------------------------------


class _FakeCamera:
    def model_dump(self, **kw):
        return {"status": "VALID", "recommended_interval_s": 3}


class _FakeResult:
    waypoints = []
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
    num_lines = 3
    waypoint_mode = "photo"
    warnings = []
    capture_interval = _FakeCamera()
    turn_radius_result = None
    turn_radius_warnings = []
    flight_lines_geojson = {"type": "FeatureCollection", "features": []}
    photo_points = [{"index": 0, "capture": True}]
    geometry = None
    sweep_deg = 45.0


class _FakeReq:
    altitude = 100.0
    overlap_frontal = 75.0
    overlap_lateral = 65.0
    altitude_mode = "takeoff"
    drone_id = "dji-m3e"
    camera_id = "cam-43-20mp"
    dem_resolution_m = None


def test_build_universal_mission_grid():
    result = _FakeResult()
    result.sweep_deg = 45.0
    mission = build_universal_mission("grid", _FakeReq(), result)
    assert mission.mission_type == "grid"
    assert mission.metrics.photo_count == 10
    assert mission.parameters.speed_ms == pytest.approx(6.8)
    assert mission.parameters.drone_id == "dji-m3e"
    assert mission.capture_interval["recommended_interval_s"] == 3
    assert mission.flight_lines_geojson is not None


def test_build_universal_mission_corridor_geometry():
    class _G:
        polygon_geojson = {"type": "Polygon"}
        flight_lines_geojson = {"type": "FeatureCollection"}
        centerline_geojson = {"type": "LineString"}
        epsg_out = 32630
        crs_name = "WGS 84 / UTM 30N"
        transformation = "EPSG:4326 -> EPSG:32630"

    result = _FakeResult()
    result.geometry = _G()
    mission = build_universal_mission("linear_corridor", _FakeReq(), result)
    assert mission.geometry is not None
    assert mission.geometry.epsg_out == 32630
    assert mission.flight_lines_geojson is not None


# --- Legacy serializer -------------------------------------------------------


def test_to_legacy_dict_contains_required_flat_keys():
    result = _FakeResult()
    mission = build_universal_mission("grid", _FakeReq(), result)
    legacy = to_legacy_dict(mission)
    for key in (
        "waypoints",
        "total_distance",
        "estimated_time_sec",
        "photo_count",
        "battery_count",
        "gsd",
        "footprint_width",
        "footprint_height",
        "line_spacing",
        "photo_spacing",
        "recommended_speed_ms",
        "num_lines",
        "waypoint_mode",
        "warnings",
        "capture_interval",
        "flight_lines_geojson",
        "photo_points",
    ):
        assert key in legacy
    assert legacy["total_distance"] == pytest.approx(1000.0)
    assert legacy["estimated_time_sec"] == pytest.approx(150.0)


def test_legacy_round_trip_is_stable():
    result = _FakeResult()
    mission = build_universal_mission("grid", _FakeReq(), result)
    legacy = to_legacy_dict(mission)
    reparsed = parse_mission_blob(legacy)
    assert reparsed.metrics.total_distance_m == pytest.approx(mission.metrics.total_distance_m)
    assert reparsed.metrics.estimated_time_sec == pytest.approx(mission.metrics.estimated_time_sec)
    assert reparsed.parameters.speed_ms == pytest.approx(mission.parameters.speed_ms)
    assert len(reparsed.photo_points) == 1
