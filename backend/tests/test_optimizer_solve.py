"""Tests for Optimizer.solve orchestration (Fase 10C-9)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.schemas import Camera, Drone
from app.modules.optimizer import (
    CandidateBuilder,
    Optimizer,
)
from app.modules.optimizer.models import (
    OptimizationConstraints,
    OptimizerInput,
)
from app.modules.optimizer.variables import (
    OptimizationVariable,
    OptimizationVariables,
    VariableMode,
)
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


def _grid_request() -> GridRequest:
    return GridRequest(
        polygon=_POLYGON,
        altitude=100.0,
        overlap_frontal=75.0,
        overlap_lateral=65.0,
        camera_id="cam-1-20mp",
        drone_id="dji-p4rtk",
        altitude_mode="takeoff",
    )


def _base_mission(db):
    return CandidateBuilder("grid", _grid_request(), db).build({"altitude_m": 100.0})


def _altitude_variables(altitudes):
    return OptimizationVariables(
        variables=[
            OptimizationVariable(name="altitude_m", mode=VariableMode.CANDIDATE_VALUES, values=altitudes),
        ]
    )


# ── Search over declared variables ───────────────────────────────────────────


def test_solve_search_optimal(db):
    inp = OptimizerInput(
        mission=_base_mission(db),
        request=_grid_request(),
        variables=_altitude_variables([80, 100, 120]),
    )
    result = Optimizer().solve(inp, db_session=db)
    assert result.status == "OPTIMAL"
    assert result.best_candidate is not None
    assert result.best_score is not None
    assert len(result.alternatives) == 2
    assert len(result.evaluations) == 3
    assert result.explanation is not None
    assert result.explanation.stats["valid"] == 3
    # the returned best is the highest-scoring valid evaluation
    totals = [e.score.total_score for e in result.evaluations if e.score is not None]
    assert result.best_score.total_score == max(totals)
    # provenance preserved
    assert all(e.variable_values is not None for e in result.evaluations)


def test_solve_search_status_constrained_by_max_candidates(db):
    inp = OptimizerInput(
        mission=_base_mission(db),
        request=_grid_request(),
        variables=_altitude_variables([60, 80, 100, 120, 140]),
        max_candidates=2,
    )
    result = Optimizer().solve(inp, db_session=db)
    assert result.status == "CONSTRAINED"
    assert "max_candidates=2" in result.message
    assert len(result.evaluations) == 2


def test_solve_search_no_solution(db):
    inp = OptimizerInput(
        mission=_base_mission(db),
        request=_grid_request(),
        variables=_altitude_variables([100, 140]),
        constraints=OptimizationConstraints(max_altitude=10.0),
    )
    result = Optimizer().solve(inp, db_session=db)
    assert result.status == "NO_SOLUTION"
    assert result.best_candidate is None
    assert result.best_score is None
    assert result.alternatives == []
    assert len(result.evaluations) == 2
    assert "No feasible mission found" in result.explanation.summary


def test_solve_search_explicit_builder_equals_rebuilt(db):
    builder = CandidateBuilder("grid", _grid_request(), db)
    inp = OptimizerInput(
        mission=_base_mission(db),
        request=_grid_request(),
        variables=_altitude_variables([80, 100, 120]),
    )
    with_builder = Optimizer().solve(inp, builder=builder)
    from_session = Optimizer().solve(inp, db_session=db)
    assert with_builder.status == from_session.status
    assert with_builder.best_score.total_score == from_session.best_score.total_score
    assert [a.variable_values for a in with_builder.alternatives] == [
        a.variable_values for a in from_session.alternatives
    ]


def test_solve_search_requires_db_session_without_builder(db):
    inp = OptimizerInput(
        mission=_base_mission(db),
        request=_grid_request(),
        variables=_altitude_variables([80, 100, 120]),
    )
    with pytest.raises(ValueError, match="db_session"):
        Optimizer().solve(inp)


def test_solve_search_deterministic(db):
    inp = OptimizerInput(
        mission=_base_mission(db),
        request=_grid_request(),
        variables=_altitude_variables([80, 100, 120]),
    )
    first = Optimizer().solve(inp, db_session=db)
    second = Optimizer().solve(inp, db_session=db)
    # rebuilt missions carry fresh created_at timestamps, so compare the
    # deterministic surface: status, ranking, values, scores and explanation
    assert first.status == second.status == "OPTIMAL"
    assert first.best_score.total_score == second.best_score.total_score
    assert first.best_candidate.variable_values == second.best_candidate.variable_values
    assert [a.variable_values for a in first.alternatives] == [a.variable_values for a in second.alternatives]
    assert [e.score.total_score for e in first.evaluations] == [e.score.total_score for e in second.evaluations]
    assert first.explanation.summary == second.explanation.summary
    assert first.explanation.reasons == second.explanation.reasons


# ── Single-candidate path (no variables) ─────────────────────────────────────


def test_solve_single_optimal(db):
    mission = _base_mission(db)
    inp = OptimizerInput(mission=mission)
    result = Optimizer().solve(inp)
    assert result.status == "OPTIMAL"
    assert result.best_candidate is not None
    assert result.best_candidate.mission == mission
    assert result.best_score is not None
    assert len(result.evaluations) == 1
    assert result.alternatives == []


def test_solve_single_feasible_with_warnings(db):
    mission = _base_mission(db)
    inp = OptimizerInput(
        mission=mission,
        constraints=OptimizationConstraints(preferred_turn_radius=1.0),
    )
    result = Optimizer().solve(inp)
    assert result.status == "FEASIBLE"
    assert result.best_candidate is not None
    assert result.explanation.warnings  # best carries warnings


def test_solve_single_no_solution(db):
    mission = _base_mission(db)
    inp = OptimizerInput(
        mission=mission,
        constraints=OptimizationConstraints(max_altitude=10.0),
    )
    result = Optimizer().solve(inp)
    assert result.status == "NO_SOLUTION"
    assert result.best_candidate is None
    assert result.best_score is None
