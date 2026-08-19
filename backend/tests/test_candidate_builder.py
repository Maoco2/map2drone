"""Tests for the candidate mission builder (Fase 10C-4)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.schemas import Camera, Drone
from app.modules.optimizer.candidate_builder import CandidateBuilder
from app.schemas.schemas import CorridorRequest, GridRequest

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

_CENTERLINE = {
    "type": "LineString",
    "coordinates": [[-5.99, 37.35], [-5.94, 37.35]],
}


@pytest.fixture(scope="module")
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        Camera(
            id="cam-1-20mp",
            name='1" CMOS 20 MP',
            sensor_width_mm=13.2,
            sensor_height_mm=8.8,
            image_width_px=5472,
            image_height_px=3648,
            focal_length_mm=8.8,
            pixel_size_um=2.41,
            shutter_speed_s=0.001,
            shutter_type="electronic",
        )
    )
    session.add(
        Drone(
            id="dji-p4rtk",
            name="Phantom 4 RTK",
            manufacturer="DJI",
            weight_kg=1.391,
            max_speed_ms=20,
            flight_time_min=30,
            max_altitude_m=5000,
            camera_id="cam-1-20mp",
        )
    )
    session.commit()
    return session


def _grid_request(**overrides) -> GridRequest:
    req = GridRequest(
        polygon=_POLYGON,
        altitude=100.0,
        overlap_frontal=75.0,
        overlap_lateral=65.0,
        camera_id="cam-1-20mp",
        drone_id="dji-p4rtk",
        altitude_mode="takeoff",
    )
    return req.model_copy(update=overrides)


def _corridor_request(**overrides) -> CorridorRequest:
    req = CorridorRequest(
        centerline=_CENTERLINE,
        width_left=30.0,
        width_right=30.0,
        altitude=100.0,
        overlap_frontal=75.0,
        overlap_lateral=65.0,
        camera_id="cam-1-20mp",
        drone_id="dji-p4rtk",
        altitude_mode="takeoff",
    )
    return req.model_copy(update=overrides)


# ── Request variable application ─────────────────────────────────────────────


def test_request_for_applies_altitude_and_overlaps(db):
    builder = CandidateBuilder("grid", _grid_request(), db)
    req = builder.request_for({"altitude_m": 120.0, "front_overlap": 80.0, "side_overlap": 70.0})
    assert req.altitude == 120.0
    assert req.overlap_frontal == 80.0
    assert req.overlap_lateral == 70.0


def test_request_for_preserves_base_when_variable_absent(db):
    builder = CandidateBuilder("grid", _grid_request(), db)
    req = builder.request_for({"altitude_m": 120.0})
    assert req.overlap_frontal == 75.0
    assert req.overlap_lateral == 65.0
    # the base request is never mutated
    assert builder.base_request.altitude == 100.0


def test_request_for_turn_radius_auto(db):
    builder = CandidateBuilder("grid", _grid_request(), db)
    req = builder.request_for({"turn_radius_m": "AUTO"})
    assert req.turn_radius["mode"] == "AUTO"
    assert "manual_radius_m" not in req.turn_radius


def test_request_for_turn_radius_numeric(db):
    builder = CandidateBuilder("grid", _grid_request(), db)
    req = builder.request_for({"turn_radius_m": 12.0})
    assert req.turn_radius["mode"] == "MANUAL"
    assert req.turn_radius["manual_radius_m"] == 12.0


def test_request_for_resolves_camera_from_drone(db):
    builder = CandidateBuilder("grid", _grid_request(camera_id=None), db)
    req = builder.request_for({"altitude_m": 100.0})
    assert req.camera_id == "cam-1-20mp"


def test_request_for_unknown_variable_raises(db):
    builder = CandidateBuilder("grid", _grid_request(), db)
    with pytest.raises(ValueError):
        builder.request_for({"hacienda_m": 100})


# ── Grid build ───────────────────────────────────────────────────────────────


def test_build_grid_produces_mission_with_applied_values(db):
    builder = CandidateBuilder("grid", _grid_request(), db)
    mission = builder.build({"altitude_m": 120.0, "front_overlap": 80.0, "side_overlap": 70.0})
    assert mission.mission_type == "grid"
    assert mission.parameters.altitude_m == 120.0
    assert mission.parameters.overlap_frontal == 80.0
    assert mission.parameters.overlap_side == 70.0
    assert mission.metrics.gsd_cm > 0
    assert mission.parameters.speed_ms > 0
    assert len(mission.waypoints) >= 2
    # camera/drone profiles populated from the DB
    assert mission.camera_profile is not None
    assert mission.camera_profile.id == "cam-1-20mp"
    assert mission.drone_profile is not None
    assert mission.drone_profile.id == "dji-p4rtk"


def test_build_grid_altitude_changes_gsd(db):
    low = CandidateBuilder("grid", _grid_request(), db).build({"altitude_m": 100.0})
    high = CandidateBuilder("grid", _grid_request(), db).build({"altitude_m": 200.0})
    assert high.metrics.gsd_cm > low.metrics.gsd_cm


def test_build_grid_overlap_changes_photo_spacing(db):
    dense = CandidateBuilder("grid", _grid_request(), db).build(
        {"altitude_m": 100.0, "front_overlap": 85.0, "side_overlap": 75.0}
    )
    sparse = CandidateBuilder("grid", _grid_request(), db).build(
        {"altitude_m": 100.0, "front_overlap": 60.0, "side_overlap": 50.0}
    )
    assert dense.metrics.photo_spacing_m < sparse.metrics.photo_spacing_m
    assert dense.metrics.line_spacing_m < sparse.metrics.line_spacing_m


# ── Speed-dependent recomputation ────────────────────────────────────────────


def test_build_speed_recomputes_metrics(db):
    slow = CandidateBuilder("grid", _grid_request(), db).build({"altitude_m": 100.0, "speed_mps": 4.0})
    fast = CandidateBuilder("grid", _grid_request(), db).build({"altitude_m": 100.0, "speed_mps": 8.0})
    assert fast.parameters.speed_ms == 8.0
    assert slow.parameters.speed_ms == 4.0
    assert fast.metrics.flight_time_s < slow.metrics.flight_time_s
    assert fast.metrics.total_distance_m == pytest.approx(slow.metrics.total_distance_m, rel=1e-6)


def test_build_speed_recomputes_capture_interval(db):
    slow = CandidateBuilder("grid", _grid_request(), db).build({"altitude_m": 100.0, "speed_mps": 4.0})
    fast = CandidateBuilder("grid", _grid_request(), db).build({"altitude_m": 100.0, "speed_mps": 8.0})
    assert slow.capture_plan is not None
    assert fast.capture_plan is not None
    assert fast.capture_plan.scientific_interval_s < slow.capture_plan.scientific_interval_s


def test_build_photo_interval_override_scientific(db):
    mission = CandidateBuilder("grid", _grid_request(), db).build({"altitude_m": 100.0, "photo_interval_s": 4.2})
    assert mission.capture_plan is not None
    assert mission.capture_plan.scientific_interval_s == 4.2
    assert mission.parameters.capture_interval_s == 4.2


def test_build_turn_radius_config_produces_turn_plan(db):
    mission = CandidateBuilder("grid", _grid_request(), db).build({"altitude_m": 100.0, "turn_radius_m": "AUTO"})
    assert mission.turn_plan is not None
    assert mission.turn_plan.mode == "AUTO"
    assert mission.turn_plan.radius_m is not None


def test_build_speed_with_turn_plan_keeps_turn_data(db):
    mission = CandidateBuilder("grid", _grid_request(), db).build(
        {"altitude_m": 100.0, "speed_mps": 6.0, "turn_radius_m": "AUTO"}
    )
    assert mission.turn_plan is not None
    assert mission.metrics.turn_time_s >= 0
    assert mission.metrics.turn_source in ("turn_plan", "overhead_fallback")


# ── Corridor build ───────────────────────────────────────────────────────────


def test_build_corridor_produces_mission(db):
    builder = CandidateBuilder("linear_corridor", _corridor_request(), db)
    mission = builder.build({"altitude_m": 100.0, "speed_mps": 5.0})
    assert mission.mission_type == "linear_corridor"
    assert mission.parameters.altitude_m == 100.0
    assert mission.parameters.speed_ms == 5.0
    assert len(mission.waypoints) >= 2
    assert mission.geometry is not None


def test_builder_rejects_unknown_mission_type(db):
    with pytest.raises(ValueError):
        CandidateBuilder("hologram", _grid_request(), db)


# ── Evaluator provenance ─────────────────────────────────────────────────────


def test_evaluate_candidate_records_variable_values(db):
    from app.modules.optimizer import CandidateMission, evaluate_candidate

    mission = CandidateBuilder("grid", _grid_request(), db).build({"altitude_m": 100.0})
    result = evaluate_candidate(CandidateMission(mission=mission, variable_values={"altitude_m": 100.0}))
    assert result.valid is True
    assert result.variable_values == {"altitude_m": 100.0}
