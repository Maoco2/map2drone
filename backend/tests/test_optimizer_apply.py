"""Module-level tests for the Fase 10F apply flow (persistence, comparison, gate).

These run ``apply_winner`` against a real in-memory database so the persistence
path (winner mission row + baseline/comparison blobs) is exercised without
auth.
"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.schemas import Camera, Drone, Mission, Project
from app.modules.optimizer import Optimizer
from app.modules.optimizer.apply import WinnerMismatchError, apply_winner, build_base_mission
from app.modules.optimizer.models import OptimizerInput
from app.modules.optimizer.variables import OptimizationVariable, OptimizationVariables, VariableMode
from app.schemas.schemas import (
    GridRequest,
    OptimizerSolveRequest,
    OptimizerVariableDeclaration,
    OptimizerVariablesRequest,
)

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
    session.add(Project(id="proj-1", name="Test project"))
    session.commit()
    return session


def _solve_request() -> OptimizerSolveRequest:
    return OptimizerSolveRequest(
        grid=GridRequest(
            polygon=_POLYGON,
            altitude=100.0,
            overlap_frontal=75.0,
            overlap_lateral=65.0,
            camera_id="cam-1-20mp",
            drone_id="dji-p4rtk",
            altitude_mode="takeoff",
        ),
        variables=OptimizerVariablesRequest(
            variables=[
                OptimizerVariableDeclaration(
                    name="altitude_m",
                    mode="candidate_values",
                    values=[80.0, 100.0, 120.0],
                )
            ]
        ),
    )


def _solve_winner(db):
    """Run the real optimizer and return (solve_request, winner_mission, values)."""
    solve_request = _solve_request()
    base_req = solve_request.grid.model_copy(deep=True)

    base_mission = build_base_mission(base_req, db)
    variables = OptimizationVariables(
        variables=[
            OptimizationVariable(
                name="altitude_m",
                mode=VariableMode.CANDIDATE_VALUES,
                values=[80.0, 100.0, 120.0],
            )
        ]
    )
    inp = OptimizerInput(
        mission=base_mission,
        request=base_req,
        variables=variables,
        max_candidates=200,
    )
    result = Optimizer().solve(inp, db_session=db)
    assert result.best_candidate is not None
    return solve_request, result.best_candidate.mission, result.best_candidate.variable_values


def test_apply_winner_persists_winner_and_preserves_original(db):
    solve_request, winner, values = _solve_winner(db)
    assert db.query(Mission).count() == 0

    result = apply_winner(
        solve_request,
        winner.model_dump(mode="json"),
        values,
        constraints=None,
        weights=None,
        db_session=db,
        project_id="proj-1",
        name="Winner grid",
    )

    assert result.mission_id is not None
    assert result.verification["matches"] is True
    assert result.verification["method"] == "candidate_builder"

    row = db.query(Mission).filter(Mission.id == result.mission_id).first()
    assert row is not None
    assert row.project_id == "proj-1"
    assert row.name == "Winner grid"
    assert row.mission_type == "grid"

    # grid_result_json carries the full winner Universal Mission.
    blob = json.loads(row.grid_result_json)
    assert blob["mission_type"] == "grid"
    assert blob["metrics"]["total_distance_m"] == winner.metrics.total_distance_m

    # parameters_json carries the apply metadata (baseline + comparison).
    params = json.loads(row.parameters_json)
    assert params["altitude"] == winner.parameters.altitude_m
    apply_block = params["optimizer_apply"]
    assert apply_block["modified_variables"] == ["altitude_m"]
    assert "altitude_m" in [c["metric"] for c in apply_block["comparison"]]
    assert apply_block["baseline_mission"]["parameters"]["altitude_m"] == 100.0
    assert apply_block["baseline_score"]["total_score"] is not None
    assert apply_block["winner_score"]["total_score"] is not None


def test_apply_winner_deterministic_no_project(db):
    solve_request, winner, values = _solve_winner(db)
    a = apply_winner(solve_request, winner.model_dump(mode="json"), values, None, None, db)
    b = apply_winner(solve_request, winner.model_dump(mode="json"), values, None, None, db)
    assert a.verification["matches"] is True and b.verification["matches"] is True
    assert a.applied_winner.metrics.total_distance_m == b.applied_winner.metrics.total_distance_m
    assert [r.model_dump() for r in a.comparison] == [r.model_dump() for r in b.comparison]


def test_apply_winner_tampered_mission_raises(db):
    solve_request, winner, values = _solve_winner(db)
    payload = winner.model_dump(mode="json")
    payload["metrics"] = {**payload["metrics"], "total_distance_m": payload["metrics"]["total_distance_m"] + 5000}
    with pytest.raises(WinnerMismatchError):
        apply_winner(solve_request, payload, values, None, None, db)


def test_apply_winner_baseline_score_beats_winner_or_equal(db):
    """The optimizer's best candidate must not score below the baseline."""
    solve_request, winner, values = _solve_winner(db)
    result = apply_winner(solve_request, winner.model_dump(mode="json"), values, None, None, db)
    assert result.baseline_score.total_score is not None
    assert result.winner_score.total_score is not None
    assert result.winner_score.total_score >= result.baseline_score.total_score - 1e-9
