"""Tests for best-candidate selection (Fase 10C-6)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.schemas import Camera, Drone
from app.modules.mission.models import MissionMetrics, MissionParameters, UniversalMission
from app.modules.optimizer import (
    CandidateBuilder,
    CandidateGenerator,
    evaluate_candidates,
    expand_variables,
    select_best,
)
from app.modules.optimizer.models import (
    CandidateConfig,
    CandidateEvaluation,
    CandidateEvaluationResult,
    EvaluationResult,
    MissionScore,
    OptimizationConstraints,
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


def _builder(db) -> CandidateBuilder:
    return CandidateBuilder("grid", _grid_request(), db)


def _altitude_candidates(altitudes, speed=5.0):
    varset = OptimizationVariables(
        variables=[
            OptimizationVariable(name="altitude_m", mode=VariableMode.CANDIDATE_VALUES, values=altitudes),
            OptimizationVariable(name="speed_mps", mode=VariableMode.FIXED, value=speed),
        ]
    )
    return CandidateGenerator(expand_variables(varset)).generate().candidates


# ── Fakes for unit-level selection ───────────────────────────────────────────


def _mission(values):
    return UniversalMission(
        mission_type="grid",
        parameters=MissionParameters(
            altitude_m=values["altitude_m"],
            overlap_frontal=75.0,
            overlap_lateral=65.0,
            speed_ms=6.8,
        ),
        metrics=MissionMetrics(),
    )


class _StubBuilder:
    def build(self, values):
        return _mission(values)


def _ce(index, score, values=None, evaluated=True, valid=True, rejected=False):
    cfg = CandidateConfig(index=index, label=f"c{index}", values=values or {"altitude_m": float(index)})
    eval_res = None
    if evaluated:
        eval_res = EvaluationResult(
            valid=valid,
            status="VALID" if valid else "INVALID",
            score=MissionScore(total_score=score),
        )
    return CandidateEvaluation(
        candidate=cfg,
        evaluated=evaluated,
        valid=valid,
        rejected=rejected,
        status="REJECTED" if rejected else ("VALID" if valid else "INVALID"),
        evaluation=eval_res,
    )


def test_select_best_ranks_by_score():
    result = CandidateEvaluationResult(
        total=3,
        evaluated=3,
        valid=3,
        candidates=[
            _ce(0, 0.7),
            _ce(1, 0.9),
            _ce(2, 0.5),
        ],
    )
    sel = select_best(result, _StubBuilder())
    assert sel.best.variable_values["altitude_m"] == 1
    assert sel.best_score.total_score == 0.9
    assert [a.variable_values["altitude_m"] for a in sel.alternatives] == [0, 2]


def test_select_best_ties_break_by_index():
    result = CandidateEvaluationResult(
        total=2,
        evaluated=2,
        valid=2,
        candidates=[
            _ce(0, 0.9),
            _ce(1, 0.9),
        ],
    )
    sel = select_best(result, _StubBuilder())
    assert sel.best.variable_values["altitude_m"] == 0
    assert len(sel.alternatives) == 1


def test_select_best_ignores_invalid_and_rejected():
    result = CandidateEvaluationResult(
        total=3,
        evaluated=1,
        valid=1,
        invalid=1,
        rejected=1,
        candidates=[
            _ce(0, 0.9),  # valid
            _ce(1, 0.99, valid=False, evaluated=True),  # invalid (higher score, excluded)
            _ce(2, 0.95, evaluated=False, rejected=True),  # rejected
        ],
    )
    sel = select_best(result, _StubBuilder())
    assert sel.best.variable_values["altitude_m"] == 0
    assert sel.best_score.total_score == 0.9
    assert sel.alternatives == []


def test_select_best_no_eligible():
    result = CandidateEvaluationResult(
        total=2,
        evaluated=2,
        valid=0,
        invalid=2,
        candidates=[
            _ce(0, 0.9, valid=False),
            _ce(1, 0.8, valid=False),
        ],
    )
    sel = select_best(result, _StubBuilder())
    assert sel.best is None
    assert sel.best_score is None
    assert sel.alternatives == []


def test_select_best_alternatives_count():
    result = CandidateEvaluationResult(
        total=4,
        evaluated=4,
        valid=4,
        candidates=[
            _ce(0, 0.9),
            _ce(1, 0.8),
            _ce(2, 0.7),
            _ce(3, 0.6),
        ],
    )
    assert len(select_best(result, _StubBuilder(), alternatives_count=1).alternatives) == 1
    assert len(select_best(result, _StubBuilder(), alternatives_count=3).alternatives) == 3
    # more requested than available → capped
    assert len(select_best(result, _StubBuilder(), alternatives_count=10).alternatives) == 3


def test_select_best_rebuilds_mission_from_values():
    result = CandidateEvaluationResult(
        total=1,
        evaluated=1,
        valid=1,
        candidates=[
            _ce(0, 0.9, values={"altitude_m": 120.0}),
        ],
    )
    sel = select_best(result, _StubBuilder())
    assert sel.best.mission.parameters.altitude_m == 120.0
    assert sel.best.variable_values == {"altitude_m": 120.0}
    assert sel.best.label == "c0"


# ── Integration over the real engines ────────────────────────────────────────


def test_select_best_from_real_run(db):
    candidates = _altitude_candidates([80, 100, 120, 140])
    eval_result = evaluate_candidates(candidates, _builder(db))
    sel = select_best(eval_result, _builder(db))
    assert sel.best is not None
    scores = [c.evaluation.score.total_score for c in eval_result.candidates]
    assert sel.best_score.total_score == max(scores)
    assert len(sel.alternatives) == 3
    assert sel.best.mission.parameters.altitude_m == sel.best.variable_values["altitude_m"]
    # alternatives are the other valid candidates, ordered by score
    assert sel.best.variable_values["altitude_m"] not in [a.variable_values["altitude_m"] for a in sel.alternatives]


def test_select_best_excludes_constraint_invalid(db):
    candidates = _altitude_candidates([100, 140])
    eval_result = evaluate_candidates(
        candidates,
        _builder(db),
        constraints=OptimizationConstraints(max_altitude=110.0),
    )
    sel = select_best(eval_result, _builder(db))
    assert sel.best.variable_values["altitude_m"] == 100.0
    assert all(a.variable_values["altitude_m"] != 140.0 for a in sel.alternatives)


def test_select_best_all_invalid_returns_empty(db):
    candidates = _altitude_candidates([100, 140])
    eval_result = evaluate_candidates(
        candidates,
        _builder(db),
        constraints=OptimizationConstraints(max_altitude=10.0),
    )
    sel = select_best(eval_result, _builder(db))
    assert sel.best is None
    assert sel.best_score is None
    assert sel.alternatives == []


# ── 10C-7: variability criterion for alternatives ────────────────────────────


def _altitude_ce(index, score, altitude):
    """Candidate with a single variable value, for the variability tests."""
    cfg = CandidateConfig(index=index, label=f"c{index}", values={"altitude_m": altitude})
    eval_res = EvaluationResult(valid=True, status="VALID", score=MissionScore(total_score=score))
    return CandidateEvaluation(
        candidate=cfg,
        evaluated=True,
        valid=True,
        rejected=False,
        status="VALID",
        evaluation=eval_res,
    )


def test_alternatives_prefer_diverse_values_over_near_duplicates():
    result = CandidateEvaluationResult(
        total=4,
        evaluated=4,
        valid=4,
        candidates=[
            _altitude_ce(0, 0.99, 100.0),  # best
            _altitude_ce(1, 0.98, 100.5),  # near-duplicate of best (<5%)
            _altitude_ce(2, 0.95, 120.0),  # meaningfully different
            _altitude_ce(3, 0.93, 90.0),  # meaningfully different
        ],
    )
    sel = select_best(result, _StubBuilder(), alternatives_count=2)
    assert sel.best.variable_values["altitude_m"] == 100.0
    assert [a.variable_values["altitude_m"] for a in sel.alternatives] == [120.0, 90.0]
    assert sel.diverse_count == 2


def test_alternatives_fallback_fills_with_near_duplicates():
    result = CandidateEvaluationResult(
        total=3,
        evaluated=3,
        valid=3,
        candidates=[
            _altitude_ce(0, 0.99, 100.0),  # best
            _altitude_ce(1, 0.98, 100.5),  # near-duplicate
            _altitude_ce(2, 0.97, 101.0),  # near-duplicate
        ],
    )
    sel = select_best(result, _StubBuilder(), alternatives_count=2)
    # only one truly diverse alternative exists → the second slot is filled by
    # the top-scoring remaining candidate (fallback), still deterministic
    assert [a.variable_values["altitude_m"] for a in sel.alternatives] == [100.5, 101.0]
    assert sel.diverse_count == 0


def test_diversity_tolerance_is_configurable():
    result = CandidateEvaluationResult(
        total=3,
        evaluated=3,
        valid=3,
        candidates=[
            _altitude_ce(0, 0.99, 100.0),
            _altitude_ce(1, 0.98, 101.0),  # 1% → similar under default, different under 0.5%
            _altitude_ce(2, 0.97, 130.0),
        ],
    )
    default = select_best(result, _StubBuilder(), alternatives_count=2)
    assert [a.variable_values["altitude_m"] for a in default.alternatives] == [130.0, 101.0]
    assert default.diverse_count == 1
    strict = select_best(result, _StubBuilder(), alternatives_count=2, diversity_tolerance=0.005)
    assert [a.variable_values["altitude_m"] for a in strict.alternatives] == [101.0, 130.0]
    assert strict.diverse_count == 2


def test_alternatives_differ_from_each_other_too():
    result = CandidateEvaluationResult(
        total=4,
        evaluated=4,
        valid=4,
        candidates=[
            _altitude_ce(0, 0.99, 100.0),  # best
            _altitude_ce(1, 0.98, 104.0),  # similar to best (4%)
            _altitude_ce(2, 0.97, 102.0),  # similar to best AND to c1 (2%)
            _altitude_ce(3, 0.90, 120.0),  # diverse
        ],
    )
    sel = select_best(result, _StubBuilder(), alternatives_count=1)
    assert [a.variable_values["altitude_m"] for a in sel.alternatives] == [120.0]
    assert sel.diverse_count == 1


def test_alternatives_variability_is_deterministic(db):
    candidates = _altitude_candidates([100, 101, 102, 103, 120])
    first = select_best(evaluate_candidates(candidates, _builder(db)), _builder(db))
    second = select_best(evaluate_candidates(candidates, _builder(db)), _builder(db))
    assert [a.variable_values["altitude_m"] for a in first.alternatives] == [
        a.variable_values["altitude_m"] for a in second.alternatives
    ]
    assert first.diverse_count == second.diverse_count
