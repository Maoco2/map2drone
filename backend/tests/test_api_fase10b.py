"""API tests for the /missions/validate endpoint."""

from fastapi.testclient import TestClient

from app.main import app
from app.modules.mission import mission_to_dict
from app.modules.mission.models import (
    CaptureMode,
    CapturePlan,
    MissionMetrics,
    MissionParameters,
    TurnPlan,
    UniversalMission,
    UniversalWaypoint,
)

client = TestClient(app)


def _mission_dict(**overrides) -> dict:
    params = MissionParameters(
        altitude_m=100.0,
        overlap_frontal=75.0,
        overlap_lateral=65.0,
        speed_ms=6.8,
        altitude_mode="takeoff",
        capture_mode="TIME",
        turn_mode="AUTO",
        turn_radius_m=12.0,
    )
    metrics = MissionMetrics(
        total_distance_m=1000.0,
        estimated_time_sec=150.0,
        line_spacing_m=40.0,
        photo_spacing_m=20.0,
        gsd_cm=2.74,
        footprint_width_m=120.0,
        footprint_height_m=80.0,
        num_lines=2,
        photo_count=10,
        battery_count=1,
        waypoint_count=3,
        flight_time_s=150.0,
        flight_distance_m=1000.0,
        line_count=2,
    )
    waypoints = [
        UniversalWaypoint(
            index=0, latitude=37.10, longitude=-3.60, altitude_m=100.0, heading_deg=90.0, capture_enabled=True
        ),
        UniversalWaypoint(
            index=1, latitude=37.10, longitude=-3.55, altitude_m=100.0, heading_deg=90.0, capture_enabled=True
        ),
        UniversalWaypoint(
            index=2, latitude=37.10, longitude=-3.50, altitude_m=100.0, heading_deg=90.0, capture_enabled=True
        ),
    ]
    flight_lines = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[-3.60, 37.10], [-3.50, 37.10]]},
                "properties": {},
            },
        ],
    }
    mission = UniversalMission(
        mission_type="grid",
        parameters=params,
        waypoints=waypoints,
        metrics=metrics,
        flight_lines_geojson=flight_lines,
        capture_plan=CapturePlan(
            mode=CaptureMode.TIME,
            scientific_interval_s=5.3,
            commercial_interval_s=5,
            status="VALID",
        ),
        turn_plan=TurnPlan(mode="AUTO", status="VALID", radius_m=12.0),
    )
    if overrides:
        mission = mission.model_copy(update=overrides)
    return mission_to_dict(mission)


def test_api_missions_validate_valid_mission():
    resp = client.post("/api/v1/missions/validate", json={"payload": _mission_dict()})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["valid"] is True
    assert body["status"] == "VALID"
    assert body["errors"] == []


def test_api_missions_validate_legacy_blob():
    legacy = {
        "waypoints": [
            {"latitude": 37.1, "longitude": -3.6, "altitude": 100.0, "heading": 90.0, "action_type": 1},
            {"latitude": 37.1, "longitude": -3.55, "altitude": 100.0, "heading": 90.0},
        ],
        "altitude": 100.0,
        "total_distance": 1000.0,
        "estimated_time_sec": 150.0,
        "photo_count": 2,
        "battery_count": 1,
        "gsd": 2.74,
        "footprint_width": 120.0,
        "footprint_height": 80.0,
        "line_spacing": 40.0,
        "photo_spacing": 20.0,
        "recommended_speed_ms": 6.8,
        "num_lines": 2,
        "overlap_frontal": 75.0,
        "overlap_lateral": 65.0,
    }
    resp = client.post("/api/v1/missions/validate", json={"payload": legacy})
    assert resp.status_code == 200, resp.text
    assert resp.json()["valid"] is True


def test_api_missions_validate_invalid_mission():
    bad = _mission_dict()
    bad["metrics"]["gsd_cm"] = 0.0
    resp = client.post("/api/v1/missions/validate", json={"payload": bad})
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert body["status"] == "INVALID"
    codes = [e["code"] for e in body["errors"]]
    assert "gsd_invalid" in codes


def test_api_missions_validate_bad_payload_returns_400():
    resp = client.post("/api/v1/missions/validate", json={"payload": "not json"})
    assert resp.status_code == 400
