"""Tests for the selection explanation (Fase 10C-8)."""

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
    explain,
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


# ── Integration over the real engines ────────────────────────────────────────


def test_explain_real_run_counts_and_summary(db):
    candidates = _altitude_candidates([80, 100, 120, 140])
    eval_result = evaluate_candidates(candidates, _builder(db))
    selection = select_best(eval_result, _builder(db))
    explanation = explain(selection, eval_result)
    assert explanation.stats == {
        "total": 4,
        "evaluated": 4,
        "valid": 4,
        "invalid": 0,
        "rejected": 0,
    }
    assert "Selected mission" in explanation.summary
    assert selection.best.label in explanation.summary
    assert explanation.reasons and explanation.reasons[0].startswith("Highest score")
    assert any(r.startswith("Score breakdown:") for r in explanation.reasons)


def test_explain_constraint_compliance_reason(db):
    candidates = _altitude_candidates([80, 100, 120])
    constraints = OptimizationConstraints(min_altitude=90.0, max_altitude=110.0)
    eval_result = evaluate_candidates(candidates, _builder(db), constraints=constraints)
    selection = select_best(eval_result, _builder(db))
    explanation = explain(selection, eval_result, constraints=constraints)
    compliance = [r for r in explanation.reasons if "satisfies the configured hard bounds" in r]
    assert len(compliance) == 1
    assert "altitude_m" in compliance[0]


def test_explain_aggregates_invalid_constraint_rejections(db):
    candidates = _altitude_candidates([100, 140])
    constraints = OptimizationConstraints(max_altitude=110.0)
    eval_result = evaluate_candidates(candidates, _builder(db), constraints=constraints)
    selection = select_best(eval_result, _builder(db))
    explanation = explain(selection, eval_result, constraints=constraints)
    assert any(
        w.startswith("1 candidate(s) rejected by constraint:") and "altitude_m" in w for w in explanation.warnings
    )
    assert explanation.stats["invalid"] == 1


def test_explain_no_solution(db):
    candidates = _altitude_candidates([100, 140])
    constraints = OptimizationConstraints(max_altitude=10.0)
    eval_result = evaluate_candidates(candidates, _builder(db), constraints=constraints)
    selection = select_best(eval_result, _builder(db))
    explanation = explain(selection, eval_result, constraints=constraints)
    assert "No feasible mission found" in explanation.summary
    assert explanation.stats["valid"] == 0
    assert any("failed validation or constraints" in r for r in explanation.reasons)


def test_explain_is_deterministic(db):
    candidates = _altitude_candidates([80, 100, 120, 140])
    first = explain(
        select_best(evaluate_candidates(candidates, _builder(db)), _builder(db)),
        evaluate_candidates(candidates, _builder(db)),
    )
    second = explain(
        select_best(evaluate_candidates(candidates, _builder(db)), _builder(db)),
        evaluate_candidates(candidates, _builder(db)),
    )
    assert first == second


# ── Advisories (performance / camera height) ─────────────────────────────────


def _mission(values, gsd=3.0, battery=1, turn_source="turn_plan", altitude=100.0):
    return UniversalMission(
        mission_type="grid",
        parameters=MissionParameters(
            altitude_m=altitude,
            overlap_frontal=75.0,
            overlap_lateral=65.0,
            speed_ms=6.8,
        ),
        metrics=MissionMetrics(
            gsd_cm=gsd,
            battery_count=battery,
            turn_source=turn_source,
            flight_time_s=1800.0,
            photo_count=80,
            waypoint_count=60,
        ),
    )


class _StubBuilder:
    def __init__(self, mission):
        self.mission = mission

    def build(self, values):
        return self.mission


def _result_for(values, mission, constraints=None):
    cfg = CandidateConfig(index=0, label="c0", values=values)
    eval_res = EvaluationResult(valid=True, status="VALID", score=MissionScore(total_score=0.9))
    eval_res.variable_values = values
    return CandidateEvaluationResult(
        total=1,
        evaluated=1,
        valid=1,
        candidates=[
            CandidateEvaluation(candidate=cfg, evaluated=True, valid=True, status="VALID", evaluation=eval_res),
        ],
    )


def _multi_result(score_pairs):
    """CandidateEvaluationResult from [(values, score), ...] with distinct scores."""
    candidates = []
    for i, (values, score) in enumerate(score_pairs):
        cfg = CandidateConfig(index=i, label=f"c{i}", values=values)
        eval_res = EvaluationResult(valid=True, status="VALID", score=MissionScore(total_score=score))
        eval_res.variable_values = values
        candidates.append(
            CandidateEvaluation(
                candidate=cfg,
                evaluated=True,
                valid=True,
                status="VALID",
                evaluation=eval_res,
            )
        )
    return CandidateEvaluationResult(
        total=len(candidates), evaluated=len(candidates), valid=len(candidates), candidates=candidates
    )


def test_explain_closest_competitor_reason():
    values = {"altitude_m": 100.0}
    mission = _mission(values)
    result = _multi_result([(values, 0.90), ({"altitude_m": 120.0}, 0.70)])
    selection = select_best(result, _StubBuilder(mission))
    explanation = explain(selection, result)
    competitor = [r for r in explanation.reasons if r.startswith("Closest competitor scored")]
    assert len(competitor) == 1
    assert "0.700" in competitor[0]
    assert "0.200" in competitor[0]


def test_explain_battery_advisory():
    values = {"altitude_m": 100.0}
    mission = _mission(values, battery=3, turn_source="turn_plan")
    result = _result_for(values, mission)
    selection = select_best(result, _StubBuilder(mission))
    explanation = explain(selection, result)
    assert any("requires 3 battery change(s)" in w for w in explanation.warnings)


def test_explain_turn_fallback_advisory():
    values = {"altitude_m": 100.0}
    mission = _mission(values, battery=1, turn_source="overhead_fallback")
    result = _result_for(values, mission)
    selection = select_best(result, _StubBuilder(mission))
    explanation = explain(selection, result)
    assert any("overhead fallback estimate" in w for w in explanation.warnings)


def test_explain_camera_height_gsd_advisory_inside_band():
    values = {"altitude_m": 100.0}
    mission = _mission(values, gsd=3.0)
    constraints = OptimizationConstraints(min_gsd=1.0, max_gsd=5.0)
    result = _result_for(values, mission)
    selection = select_best(result, _StubBuilder(mission))
    explanation = explain(selection, result, constraints=constraints)
    assert any(
        w.startswith("advisory: camera height 100 m") and "inside the configured band" in w
        for w in explanation.warnings
    )


def test_explain_camera_height_gsd_advisory_outside_band():
    values = {"altitude_m": 100.0}
    mission = _mission(values, gsd=8.0)
    constraints = OptimizationConstraints(min_gsd=1.0, max_gsd=5.0)
    result = _result_for(values, mission)
    selection = select_best(result, _StubBuilder(mission))
    explanation = explain(selection, result, constraints=constraints)
    assert any("GSD 8.00 cm is outside the configured band" in w for w in explanation.warnings)


def test_explain_best_evaluation_warnings_carried_over():
    values = {"altitude_m": 100.0}
    mission = _mission(values)
    result = _result_for(values, mission)
    result.candidates[0].evaluation.warnings = ["constraint:turn_radius_m — no turn radius data available"]
    selection = select_best(result, _StubBuilder(mission))
    explanation = explain(selection, result)
    assert any(w.startswith("best:") and "turn_radius_m" in w for w in explanation.warnings)
