"""Tests for the Fase 10F export-readiness diagnostic (READY / WARNING / BLOCKED).

The diagnostic must mirror the real exporters: LCHM over 99 waypoints is
BLOCKED with ``split_required`` (never a corrupt file), an INVALID turn-radius
plan is BLOCKED, and a constrained plan is only a WARNING.
"""

from app.core.database import get_db
from app.models.schemas import Camera, Drone
from app.modules.export.readiness import check_mission_readiness
from app.modules.mission import build_universal_mission
from app.modules.mission.models import TurnPlan
from app.modules.planning.engine import compute_grid
from app.schemas.schemas import GridRequest

_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [-5.99, 37.35],
            [-5.94, 37.35],
            [-5.94, 37.39],
            [-5.99, 37.39],
            [-5.99, 37.35],
        ]
    ],
}

_GRID = {
    "polygon": _POLYGON,
    "altitude": 250.0,
    "overlap_frontal": 80.0,
    "overlap_lateral": 75.0,
    "camera_id": "cam-1-20mp",
    "drone_id": "dji-p4rtk",
    "altitude_mode": "takeoff",
}


def _winner_mission():
    """Build a Universal Mission through the planning engine (same path the
    planner endpoint uses) so the readiness diagnostic runs on a real mission."""
    db = next(get_db())
    try:
        req = GridRequest(**_GRID)
        result = compute_grid(req, db)
        camera = db.query(Camera).filter(Camera.id == req.camera_id).first()
        drone = db.query(Drone).filter(Drone.id == req.drone_id).first()
        return build_universal_mission("grid", req, result, camera=camera, drone=drone)
    finally:
        db.close()


def test_readiness_small_grid_lchm_ready():
    item = check_mission_readiness(_winner_mission(), "litchi_lchm")
    assert item["status"] == "READY"
    assert item["id"] == "litchi_lchm"
    assert "split_required" not in item["codes"]


def test_readiness_over_99_waypoints_blocked_split_required():
    mission = _winner_mission()
    first = mission.waypoints[0]
    mission.waypoints = [first] * 100
    mission.metrics.waypoint_count = 100
    item = check_mission_readiness(mission, "litchi_lchm")
    assert item["status"] == "BLOCKED"
    assert "split_required" in item["codes"]
    assert any("99" in r for r in item["reasons"])


def test_readiness_invalid_turn_plan_blocked():
    mission = _winner_mission()
    mission.turn_plan = TurnPlan(mode="AUTO", status="INVALID", radius_m=None, turn_count=0)
    item = check_mission_readiness(mission, "litchi_lchm")
    assert item["status"] == "BLOCKED"
    assert "turn_radius_invalid" in item["codes"]


def test_readiness_constrained_turn_warning():
    mission = _winner_mission()
    mission.turn_plan = TurnPlan(mode="AUTO", status="CONSTRAINED", radius_m=5.0, turn_count=4)
    mission.turn_radius_warnings = ["Turn radius constrained by available space"]
    item = check_mission_readiness(mission, "litchi_lchm")
    assert item["status"] == "WARNING"
    assert "turn_radius_warning" in item["codes"]


def test_readiness_unknown_format_raises():
    import pytest

    with pytest.raises(ValueError):
        check_mission_readiness(_winner_mission(), "nope")


def test_readiness_gis_format_is_gis_only_warning():
    item = check_mission_readiness(_winner_mission(), "geojson")
    assert item["status"] in ("READY", "WARNING")
    assert item["compatibility"]["category"] in ("gis_only", "official", "importable_limited")
