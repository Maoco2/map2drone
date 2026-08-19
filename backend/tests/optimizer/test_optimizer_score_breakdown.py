"""Fase 10E — preference-score calibration audit.

Verifies the continuous scoring redesign: per-component utilities in [0, 1],
target resolution (band midpoint / single bound / preferred / mission
baseline), the weighted total reproducing the formula, coherent weight
sensitivity, the scoring breakdown (details) and, using real candidates, that
valid candidates now differentiate continuously on every scored component
(no more binary 1.0 blocks). A constraint FAIL halves the total score.
"""

import pytest

from app.modules.mission.models import (
    CaptureMode,
    CapturePlan,
    MissionMetrics,
    MissionParameters,
    TurnPlan,
    UniversalMission,
    UniversalWaypoint,
)
from app.modules.optimizer import evaluate, score_mission
from app.modules.optimizer.models import OptimizationConstraints, OptimizationWeights, OptimizerInput
from app.modules.optimizer.optimizer import Optimizer
from app.modules.optimizer.variables import OptimizationVariable, OptimizationVariables, VariableMode

from .corpus import AUTO_TURN, SMALL_POLYGON, build_corpus, get_case, grid_request

_SCORE_KEYS = (
    "coverage_score",
    "gsd_score",
    "overlap_score",
    "time_score",
    "battery_score",
    "photo_count_score",
    "turn_score",
    "safety_score",
)


def _mission(**overrides) -> UniversalMission:
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
        UniversalWaypoint(index=0, latitude=37.10, longitude=-3.60, altitude_m=100.0, heading_deg=90.0),
        UniversalWaypoint(index=1, latitude=37.10, longitude=-3.55, altitude_m=100.0, heading_deg=90.0),
        UniversalWaypoint(index=2, latitude=37.10, longitude=-3.50, altitude_m=100.0, heading_deg=90.0),
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
    return mission


def _constraints() -> OptimizationConstraints:
    return OptimizationConstraints(
        min_gsd=2.0,
        max_gsd=4.0,
        min_overlap_front=70.0,
        max_overlap_front=90.0,
        min_overlap_side=60.0,
        max_overlap_side=80.0,
        min_altitude=60.0,
        max_altitude=200.0,
        min_speed=4.0,
        max_speed=12.0,
        max_battery_count=4,
        max_flight_time=3600.0,
        max_photo_count=50,
    )


def _weight_map(w: OptimizationWeights) -> dict:
    return {
        "coverage_score": w.coverage,
        "gsd_score": w.gsd,
        "overlap_score": w.overlap,
        "time_score": w.time,
        "battery_score": w.battery,
        "photo_count_score": w.photo_count,
        "turn_score": w.turn,
        "safety_score": w.safety,
    }


# ── Formula audit ─────────────────────────────────────────────────────────────


def test_weighted_formula_reproduces_total_score():
    mission = _mission()
    weights = OptimizationWeights()
    score = score_mission(mission, constraints=_constraints(), weights=weights)
    weights_map = _weight_map(weights)
    numerator = 0.0
    denominator = 0.0
    for key in _SCORE_KEYS:
        value = getattr(score, key)
        if value is None:
            continue
        numerator += value * weights_map[key]
        denominator += weights_map[key]
    assert denominator > 0
    assert score.total_score == pytest.approx(round(numerator / denominator, 4))


def test_scores_normalized_to_unit_interval():
    mission = _mission()
    score = score_mission(mission, constraints=_constraints(), weights=OptimizationWeights())
    for key in _SCORE_KEYS:
        value = getattr(score, key)
        assert value is None or 0.0 <= value <= 1.0
    assert score.total_score is None or 0.0 <= score.total_score <= 1.0


def test_weight_sensitivity_is_coherent():
    # gsd (2.74) is far above the [1.0, 1.5] band -> utility saturates at 0.0
    mission = _mission()
    constraints = OptimizationConstraints(min_gsd=1.0, max_gsd=1.5)
    default = score_mission(mission, constraints=constraints, weights=OptimizationWeights())
    assert default.gsd_score == 0.0
    heavy = score_mission(
        mission,
        constraints=constraints,
        weights=OptimizationWeights(gsd=10.0),
    )
    light = score_mission(
        mission,
        constraints=constraints,
        weights=OptimizationWeights(gsd=0.0),
    )
    assert default.total_score is not None
    assert heavy.total_score is not None
    assert light.total_score is not None
    # more gsd weight pulls the total towards the weak gsd score (0.0 < 1.0)
    assert heavy.total_score < default.total_score
    # zeroing the weak component pulls the total towards the strong ones
    assert light.total_score > default.total_score


def test_calibrated_weights_prioritize_quality_and_safety():
    w = OptimizationWeights()
    quality = (w.gsd, w.overlap, w.coverage, w.safety)
    assert all(q == 1.0 for q in quality)
    assert w.time == 0.8 and w.battery == 0.8
    assert w.turn == 0.6
    assert w.photo_count == 0.5
    assert min(quality) >= max(w.time, w.battery) > w.turn > w.photo_count


# ── Real-candidate audit (Fase 10E point 5) ──────────────────────────────────


def test_valid_real_candidates_have_continuous_constraint_scores(db):
    """Fase 10E: among VALID candidates the constraint-driven components now
    differentiate continuously (no more binary 1.0 blocks). Every component
    appears in ``details`` with a status; scored ones carry raw + target."""
    corpus = build_corpus(db)
    case = get_case(corpus, "grid_small_time")
    result = Optimizer().solve(
        OptimizerInput(
            mission=case.mission,
            request=case.request,
            variables=OptimizationVariables(
                variables=[
                    OptimizationVariable(name="altitude_m", mode=VariableMode.CANDIDATE_VALUES, values=[80, 100, 120])
                ]
            ),
            constraints=OptimizationConstraints(
                min_gsd=2.0,
                max_gsd=3.0,
                max_flight_time=400,
                max_photo_count=100,
                max_battery_count=4,
            ),
        ),
        db_session=db,
    )
    valid = [e for e in result.evaluations if e.valid and e.score is not None]
    assert valid  # the search found valid candidates
    assert len(valid) > 1
    # the continuous utilities must actually differ across valid altitudes
    gsd_values = {round(getattr(e.score, "gsd_score"), 3) for e in valid}
    assert len(gsd_values) > 1
    time_values = {round(getattr(e.score, "time_score"), 3) for e in valid}
    assert len(time_values) > 1
    # every score carries the full breakdown
    for e in valid:
        assert e.score.details
        assert len(e.score.details) == 8
        assert all(d.raw_value is not None or d.status.value != "SCORED" for d in e.score.details)
        scored = [d for d in e.score.details if d.status.value == "SCORED"]
        assert pytest.approx(sum(d.contribution for d in scored), abs=1e-3) == e.score.total_score


def test_turn_and_safety_scores_differentiate_real_candidates(db):
    from app.modules.optimizer.candidate_builder import CandidateBuilder

    builder_request = grid_request(SMALL_POLYGON, altitude=100.0, turn_radius=AUTO_TURN)
    valid_cand = CandidateBuilder("grid", builder_request, db).build({"altitude_m": 100.0, "speed_mps": 6.8})
    constrained_cand = CandidateBuilder("grid", builder_request, db).build({"altitude_m": 100.0, "speed_mps": 10.0})
    assert valid_cand.turn_plan.status == "VALID"
    assert constrained_cand.turn_plan.status == "CONSTRAINED"

    valid = evaluate(valid_cand)
    constrained = evaluate(constrained_cand)
    assert valid.valid is True
    assert constrained.valid is True  # CONSTRAINED turn plan is not INVALID
    # Fase 10E: continuous turn utility = status base × (0.5 + 0.5·fullness)
    # VALID 12.84 m / 22.225 m available -> 1.0 · (0.5 + 0.5·0.578) ≈ 0.789
    # CONSTRAINED 22.225 m / 22.225 m available -> 0.75 · 1.0 = 0.75
    assert valid.score.turn_score == pytest.approx(0.789, abs=0.01)
    assert constrained.score.turn_score == pytest.approx(0.75)
    assert valid.score.safety_score >= constrained.score.safety_score
    assert valid.score.total_score > constrained.score.total_score
    # the breakdown exposes the real turn-plan data
    turn = [d for d in valid.score.details if d.component == "turn"][0]
    assert turn.raw_value == pytest.approx(12.84, abs=0.01)
    assert turn.target == pytest.approx(22.225, abs=0.01)
    assert turn.status.value == "SCORED"


# ── Constraint FAIL folds the score (Fase 10D point 5) ───────────────────────


def test_constraint_fail_halves_total_score():
    """A hard constraint FAIL knocks the total down by 0.5 (fold in evaluate)."""
    mission = _mission()
    ok = evaluate(mission, constraints=_constraints())
    assert ok.valid is True
    assert ok.score.total_score is not None

    bad = _constraints().model_copy(update={"max_photo_count": 5})
    prefold = score_mission(mission, constraints=bad, weights=OptimizationWeights())
    assert prefold.total_score is not None
    # the violated constraint drops its own score below 1.0 and then the fold
    # halves the weighted total
    failed = evaluate(mission, constraints=bad)
    assert failed.valid is False
    assert failed.score is not None
    assert failed.score.total_score == pytest.approx(round(prefold.total_score * 0.5, 4), rel=1e-3)
    assert failed.score.total_score < ok.score.total_score
