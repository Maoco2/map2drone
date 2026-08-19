"""Tests for the candidate evaluation batch loop (Fase 10C-5)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.schemas import Camera, Drone
from app.modules.optimizer import (
    CandidateBuilder,
    CandidateGenerator,
    evaluate_candidates,
    expand_variables,
)
from app.modules.optimizer.models import OptimizationConstraints
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


def _builder(db) -> CandidateBuilder:
    return CandidateBuilder("grid", _grid_request(), db)


def _speed_candidates(max_candidates: int = 10):
    varset = OptimizationVariables(
        variables=[
            OptimizationVariable(name="altitude_m", mode=VariableMode.FIXED, value=100),
            OptimizationVariable(name="speed_mps", mode=VariableMode.RANGE, min_value=4.0, max_value=8.0, step=2.0),
        ]
    )
    return CandidateGenerator(expand_variables(varset), max_candidates=max_candidates).generate().candidates


# ── Batch loop over the real engines ─────────────────────────────────────────


def test_evaluate_candidates_counts_and_order(db):
    result = evaluate_candidates(_speed_candidates(), _builder(db))
    assert result.total == 3
    assert result.evaluated == 3
    assert result.valid == 3
    assert result.invalid == 0
    assert result.rejected == 0
    # deterministic order preserved
    assert [c.candidate.index for c in result.candidates] == [0, 1, 2]
    assert all(c.status == "VALID" for c in result.candidates)
    # provenance recorded per evaluation
    assert result.candidates[0].evaluation.variable_values == {
        "altitude_m": 100.0,
        "speed_mps": 4.0,
    }


def test_evaluate_candidates_split_valid_invalid_by_constraints(db):
    variables = OptimizationVariables(
        variables=[
            OptimizationVariable(name="altitude_m", mode=VariableMode.CANDIDATE_VALUES, values=[100, 120]),
        ]
    )
    candidates = CandidateGenerator(expand_variables(variables)).generate().candidates
    constraints = OptimizationConstraints(max_altitude=110.0)
    result = evaluate_candidates(candidates, _builder(db), constraints=constraints)
    assert result.evaluated == 2
    assert result.valid == 1
    assert result.invalid == 1
    statuses = {c.candidate.values["altitude_m"]: c.status for c in result.candidates}
    assert statuses[100.0] == "VALID"
    assert statuses[120.0] == "INVALID"


def test_evaluate_candidates_is_deterministic(db):
    first = evaluate_candidates(_speed_candidates(), _builder(db))
    second = evaluate_candidates(_speed_candidates(), _builder(db))
    assert first == second
    assert [c.evaluation.score.total_score for c in first.candidates] == [
        c.evaluation.score.total_score for c in second.candidates
    ]


# ── Rejection handling ───────────────────────────────────────────────────────


class _FailingBuilder:
    def __init__(self, real: CandidateBuilder):
        self.real = real

    def build(self, values):
        if values.get("altitude_m") == 120:
            raise ValueError("Polygon too small for the selected parameters")
        return self.real.build(values)


def test_rejected_candidates_are_reported_not_dropped(db):
    variables = OptimizationVariables(
        variables=[
            OptimizationVariable(name="altitude_m", mode=VariableMode.CANDIDATE_VALUES, values=[100, 120]),
        ]
    )
    candidates = CandidateGenerator(expand_variables(variables)).generate().candidates
    result = evaluate_candidates(candidates, _FailingBuilder(_builder(db)))
    assert result.total == 2
    assert result.evaluated == 1
    assert result.valid == 1
    assert result.rejected == 1
    rejected = [c for c in result.candidates if c.rejected]
    assert len(rejected) == 1
    assert rejected[0].status == "REJECTED"
    assert rejected[0].evaluated is False
    assert rejected[0].candidate.values["altitude_m"] == 120
    assert "Polygon too small" in rejected[0].reason
    assert rejected[0].evaluation is None


def test_empty_candidate_list_is_empty_result(db):
    result = evaluate_candidates([], _builder(db))
    assert result.total == 0
    assert result.evaluated == 0
    assert result.valid == 0
    assert result.rejected == 0
    assert result.candidates == []
