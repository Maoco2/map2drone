"""Tests for the Optimizer module (Fase 10B — normative base, no search)."""

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
from app.modules.optimizer import (
    CandidateMission,
    ConstraintStatus,
    Optimizer,
    OptimizerInput,
    evaluate,
    evaluate_candidate,
    evaluate_constraints,
    score_mission,
)
from app.modules.optimizer.models import OptimizationConstraints, OptimizationResult, OptimizationWeights


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
        allowed_capture_intervals=[1, 2, 3, 4, 5, 6],
    )


def test_candidate_creation():
    cand = CandidateMission(mission=_mission())
    assert cand.label == "candidate"
    assert cand.mission.mission_type == "grid"


def test_evaluate_valid_candidate():
    result = evaluate(_mission(), constraints=_constraints())
    assert result.valid is True
    assert result.status == "VALID"
    assert result.score is not None
    assert result.score.total_score is not None
    assert 0.0 <= result.score.total_score <= 1.0
    assert result.metrics["total_distance_m"] == pytest.approx(1000.0)
    assert result.validation is not None


def test_evaluate_invalid_candidate_has_no_score():
    mission = _mission()
    mission.metrics.gsd_cm = 0.0
    result = evaluate(mission)
    assert result.valid is False
    assert result.status == "INVALID"
    assert result.score is None


def test_evaluate_candidate_wrapper():
    result = evaluate_candidate(CandidateMission(mission=_mission()))
    assert result.valid is True


def test_evaluate_constraint_violation_blocks_photo_count():
    mission = _mission()
    result = evaluate(mission, constraints=OptimizationConstraints(max_photo_count=5))
    assert result.valid is False
    assert any(w.startswith("constraint:") for w in result.warnings)


def test_evaluate_allowed_capture_intervals():
    mission = _mission()
    result = evaluate(mission, constraints=OptimizationConstraints(allowed_capture_intervals=[1, 2, 3]))
    assert result.valid is False  # commercial interval 5 not allowed
    assert any("capture interval" in w for w in result.warnings)


def test_score_mission_returns_per_criterion_scores():
    mission = _mission()
    score = score_mission(mission, constraints=_constraints(), weights=OptimizationWeights())
    # Fase 10E: coverage is DATA_REQUIRED (no projected area in UMM 1.0) and the
    # constraint-driven components are continuous utilities, not binary flags.
    assert score.coverage_score is None
    # gsd band [2,4] -> target 3.0, half-width 1.0; gsd 2.74 -> 1 - 0.26 = 0.74
    assert score.gsd_score == pytest.approx(0.74)
    # overlap bands [70,90]/[60,80] -> targets 80/70; 75/65 -> 0.5 on both axes
    assert score.overlap_score == pytest.approx(0.5)
    # time 150/3600, battery 1/4, photos 10/50
    assert score.time_score == pytest.approx(0.958)
    assert score.battery_score == pytest.approx(0.75)
    assert score.photo_count_score == pytest.approx(0.8)
    assert score.turn_score == pytest.approx(1.0)
    assert score.safety_score == pytest.approx(1.0)
    assert score.total_score is not None
    assert len(score.details) == 8
    scored = [d for d in score.details if d.status.value == "SCORED"]
    assert len(scored) == 7
    assert pytest.approx(sum(d.contribution for d in scored), abs=1e-3) == score.total_score


def test_score_without_constraints_yields_total_from_available():
    mission = _mission()
    score = score_mission(mission)
    # without constraint targets the data-driven components (gsd/time/battery/
    # photos) are UNKNOWN; turn + safety keep the total scoreable
    assert score.gsd_score is None
    assert score.time_score is None
    assert score.coverage_score is None
    assert score.total_score is not None
    assert any(d.status.value == "UNKNOWN" for d in score.details)


def test_optimizer_solve_single_candidate():
    opt = Optimizer()
    result = opt.solve(OptimizerInput(mission=_mission()))
    assert isinstance(result, OptimizationResult)
    assert result.status in ("OPTIMAL", "FEASIBLE", "NO_SOLUTION")
    assert result.explanation is not None


def test_optimizer_evaluate_input():
    opt = Optimizer()
    result = opt.evaluate_input(OptimizerInput(mission=_mission(), constraints=_constraints()))
    assert result.valid is True
    assert result.score is not None


def test_evaluate_constraints_detects_gsd_outside_range():
    mission = _mission()
    reports = evaluate_constraints(OptimizationConstraints(min_gsd=1.0, max_gsd=1.5), mission)
    gsd = [r for r in reports if r.constraint == "gsd_cm"]
    assert gsd and gsd[0].status == ConstraintStatus.FAIL


# ── Weight calibration (Fase 10C-12) ─────────────────────────────────────────


def test_weights_defaults_are_calibrated():
    w = OptimizationWeights()
    # data quality + safety dominate; operational cost secondary; smoothness/load last
    assert w.safety == 1.0
    assert w.gsd == 1.0
    assert w.overlap == 1.0
    assert w.coverage == 1.0
    assert w.time == 0.8
    assert w.battery == 0.8
    assert w.turn == 0.6
    assert w.photo_count == 0.5


def test_weights_reject_negative():
    with pytest.raises(ValueError, match="non-negative"):
        OptimizationWeights(time=-1.0)


def test_weights_reject_all_zero():
    with pytest.raises(ValueError, match="positive"):
        OptimizationWeights(
            coverage=0,
            gsd=0,
            overlap=0,
            time=0,
            battery=0,
            photo_count=0,
            turn=0,
            safety=0,
        )


def test_calibrated_defaults_change_total_score():
    mission = _mission()
    constraints = OptimizationConstraints(max_gsd=1.0)  # gsd 2.74 fails -> 0.5
    calibrated = score_mission(mission, constraints=constraints)
    uniform = score_mission(
        mission,
        constraints=constraints,
        weights=OptimizationWeights(
            coverage=1,
            gsd=1,
            overlap=1,
            time=1,
            battery=1,
            photo_count=1,
            turn=1,
            safety=1,
        ),
    )
    # gsd (failing, 0.5) has equal weight in both, but turn (passing, 1.0) is
    # weighted lower in the calibrated set -> lower total than the uniform one
    assert calibrated.total_score is not None
    assert uniform.total_score is not None
    assert calibrated.total_score < uniform.total_score


def test_weights_override_affects_ranking_deterministically():
    mission = _mission()
    constraints = OptimizationConstraints(max_gsd=1.0)
    heavy_gsd = OptimizationWeights(gsd=5.0)
    default = score_mission(mission, constraints=constraints)
    heavy = score_mission(mission, constraints=constraints, weights=heavy_gsd)
    assert heavy.total_score is not None
    assert default.total_score is not None
    assert heavy.total_score < default.total_score  # failing gsd penalized harder
