"""Fase 10E — continuous preference scoring tests.

Covers the redesigned score (points 1–10 of 10E): continuity (no binary 0→1
flags), monotonicity toward the target, target resolution (preferred → band
midpoint → single bound → mission baseline → UNKNOWN/DATA_REQUIRED), real
time/turn/battery data, weight sensitivity, determinism and the scoring
breakdown. The corpus run verifies every corpus mission stays scoreable with a
full breakdown.
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
from app.modules.optimizer import explain, score_mission
from app.modules.optimizer.models import (
    OptimizationConstraints,
    OptimizationWeights,
    ScoreComponentStatus,
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
        max_battery_count=4,
        max_flight_time=400.0,
        max_photo_count=50,
    )


def _detail(score, component):
    return next(d for d in score.details if d.component == component)


# ── Continuity & monotonicity (10E point 3) ──────────────────────────────────


def test_gsd_utility_is_continuous_and_peaks_at_target():
    mission = _mission()
    for gsd, expected in [(2.0, 0.0), (2.5, 0.5), (3.0, 1.0), (3.5, 0.5), (4.0, 0.0)]:
        m = mission.model_copy(update={"metrics": mission.metrics.model_copy(update={"gsd_cm": gsd})})
        score = score_mission(m, constraints=_constraints(), weights=OptimizationWeights())
        assert score.gsd_score == pytest.approx(expected, abs=0.002)
    # strictly monotonic toward the target: no flat 1.0 plateau, no 0→1 jump
    mids = [
        score_mission(
            mission.model_copy(update={"metrics": mission.metrics.model_copy(update={"gsd_cm": g})}),
            constraints=_constraints(),
        ).gsd_score
        for g in (2.2, 2.5, 2.8)
    ]
    assert mids[0] < mids[1] < mids[2]


def test_overlap_utility_min_of_front_and_side():
    mission = _mission()
    score = score_mission(mission, constraints=_constraints(), weights=OptimizationWeights())
    # front 75/80 (hw 10) -> 0.5 ; side 65/70 (hw 10) -> 1.0 ; min = 0.5
    assert score.overlap_score == pytest.approx(0.5)
    d = _detail(score, "overlap")
    assert d.status is ScoreComponentStatus.SCORED
    assert d.target == pytest.approx(80.0)  # front is the binding axis


def test_time_battery_photo_are_linear_continuous():
    mission = _mission()
    score = score_mission(mission, constraints=_constraints(), weights=OptimizationWeights())
    assert score.time_score == pytest.approx(1 - 150 / 400)
    assert score.battery_score == pytest.approx(1 - 1 / 4)
    assert score.photo_count_score == pytest.approx(1 - 10 / 50)
    # a longer flight scores lower, strictly
    longer = mission.model_copy(update={"metrics": mission.metrics.model_copy(update={"flight_time_s": 300})})
    assert score_mission(longer, constraints=_constraints()).time_score < score.time_score


# ── Target resolution (10E point 4) ──────────────────────────────────────────


def test_gsd_target_resolution_chain():
    mission = _mission()  # gsd 2.74
    # 1) preferred beats the band midpoint
    s = score_mission(mission, constraints=OptimizationConstraints(min_gsd=2.0, max_gsd=4.0, preferred_gsd=3.5))
    assert _detail(s, "gsd").target == pytest.approx(3.5)
    # 2) band midpoint
    s = score_mission(mission, constraints=OptimizationConstraints(min_gsd=2.0, max_gsd=4.0))
    assert _detail(s, "gsd").target == pytest.approx(3.0)
    assert s.gsd_score == pytest.approx(1 - 0.26 / 1.0)
    # 3) single bound -> one-sided decay, flat on the compliant side
    s = score_mission(mission, constraints=OptimizationConstraints(max_gsd=3.0))
    assert _detail(s, "gsd").target == pytest.approx(3.0)
    assert s.gsd_score == 1.0  # 2.74 <= 3.0
    bad = _mission()
    bad.metrics.gsd_cm = 3.5
    assert score_mission(bad, constraints=OptimizationConstraints(max_gsd=3.0)).gsd_score == pytest.approx(
        1 - 0.5 / 3.0, abs=0.001
    )
    # 4) no target -> UNKNOWN, not scored
    s = score_mission(mission, weights=OptimizationWeights())
    d = _detail(s, "gsd")
    assert d.status is ScoreComponentStatus.UNKNOWN
    assert d.normalized_value is None
    assert d.message


def test_overlap_target_resolution_chain():
    mission = _mission()  # front 75 / side 65
    # 1) preferred
    s = score_mission(mission, constraints=OptimizationConstraints(preferred_overlap_front=80.0))
    assert _detail(s, "overlap").target == pytest.approx(80.0)
    assert _detail(s, "overlap").raw_value == pytest.approx(75.0)
    # 2) band midpoint (front is the binding axis)
    s = score_mission(mission, constraints=OptimizationConstraints(min_overlap_front=70.0, max_overlap_front=90.0))
    assert _detail(s, "overlap").target == pytest.approx(80.0)
    assert s.overlap_score == pytest.approx(0.5)
    # 3) single bound -> one-sided, compliant side flat (side is the binding axis)
    s = score_mission(mission, constraints=OptimizationConstraints(min_overlap_side=80.0))
    assert _detail(s, "overlap").target == pytest.approx(80.0)
    assert _detail(s, "overlap").raw_value == pytest.approx(65.0)
    assert s.overlap_score == pytest.approx(1 - (80 - 65) / 80, abs=0.001)
    # 4) nothing -> the mission's own baseline overlap is the target (always SCORED)
    s = score_mission(mission, weights=OptimizationWeights())
    d = _detail(s, "overlap")
    assert d.status is ScoreComponentStatus.SCORED
    assert d.target == pytest.approx(75.0)  # both axes at 1.0; front wins the tie
    assert s.overlap_score == pytest.approx(1.0)


def test_time_battery_photo_unknown_without_budget():
    score = score_mission(_mission(), weights=OptimizationWeights())
    for component in ("time", "battery", "photo_count"):
        d = _detail(score, component)
        assert d.status is ScoreComponentStatus.UNKNOWN
        assert d.normalized_value is None
        assert d.message


# ── Turn uses the real TurnRadius engine data (10E point 7) ──────────────────


def test_turn_score_uses_radius_fullness():
    base = _mission()
    for radius, available, status, expected in [
        (20.0, 20.0, "VALID", 1.0),  # uses all available space -> 1.0
        (10.0, 20.0, "VALID", 0.75),  # 0.5 + 0.5*0.5
        (20.0, 20.0, "CONSTRAINED", 0.75),  # base 0.75 * 1.0
        (5.0, 20.0, "CONSTRAINED", 0.469),  # 0.75 * (0.5 + 0.5*0.25)
    ]:
        m = base.model_copy(
            update={"turn_plan": TurnPlan(mode="AUTO", status=status, radius_m=radius, available_radius_m=available)}
        )
        score = score_mission(m, weights=OptimizationWeights())
        assert score.turn_score == pytest.approx(expected, abs=0.002)
        d = _detail(score, "turn")
        assert d.raw_value == pytest.approx(radius)
        assert d.target == pytest.approx(available)


def test_turn_unknown_when_no_turn_plan_and_none_mode():
    m = _mission()
    m.turn_plan = None
    m.parameters.turn_mode = "NONE"
    score = score_mission(m, weights=OptimizationWeights())
    d = _detail(score, "turn")
    assert d.status is ScoreComponentStatus.UNKNOWN
    assert score.turn_score is None
    # AUTO mode without a turn plan falls back to the NONE base (0.5)
    m.parameters.turn_mode = "AUTO"
    assert score_mission(m, weights=OptimizationWeights()).turn_score == pytest.approx(0.5)


# ── Coverage is never invented (10E point 8) ─────────────────────────────────


def test_coverage_is_data_required():
    score = score_mission(_mission(), weights=OptimizationWeights())
    d = _detail(score, "coverage")
    assert d.status is ScoreComponentStatus.DATA_REQUIRED
    assert d.normalized_value is None
    assert score.coverage_score is None
    assert "projected survey area" in d.message


# ── Breakdown & total (10E points 9, 11) ─────────────────────────────────────


def test_contributions_sum_to_total_and_weights_reported():
    score = score_mission(_mission(), constraints=_constraints(), weights=OptimizationWeights())
    scored = [d for d in score.details if d.status is ScoreComponentStatus.SCORED]
    assert len(scored) == 7  # all but coverage
    assert pytest.approx(sum(d.contribution for d in scored), abs=1e-3) == score.total_score
    for d in scored:
        assert 0.0 <= d.normalized_value <= 1.0
        assert d.weight > 0
        assert d.contribution > 0
    # coverage appears in the breakdown, marked DATA_REQUIRED (never dropped)
    assert any(d.component == "coverage" for d in score.details)


def test_score_mission_is_deterministic():
    a = score_mission(_mission(), constraints=_constraints(), weights=OptimizationWeights())
    b = score_mission(_mission(), constraints=_constraints(), weights=OptimizationWeights())
    assert a.model_dump() == b.model_dump()


def test_weight_sensitivity_moves_only_the_target_component():
    mission = _mission()
    base = score_mission(mission, constraints=_constraints(), weights=OptimizationWeights())
    heavy = score_mission(mission, constraints=_constraints(), weights=OptimizationWeights(photo_count=10.0))
    base_parts = {d.component: d.normalized_value for d in base.details}
    heavy_parts = {d.component: d.normalized_value for d in heavy.details}
    # normalized utilities are untouched by weights; only the total/contributions move
    assert base_parts == heavy_parts
    assert heavy.total_score != base.total_score


def test_explanation_surfaces_breakdown_and_unknown_components():
    mission = _mission()
    score = score_mission(mission, constraints=_constraints(), weights=OptimizationWeights())
    from app.modules.optimizer.models import (
        CandidateConfig,
        CandidateEvaluation,
        CandidateEvaluationResult,
        CandidateMission,
        CandidateSelection,
    )

    eval_result = CandidateEvaluationResult(
        total=1,
        evaluated=1,
        valid=1,
        candidates=[
            CandidateEvaluation(
                candidate=CandidateConfig(index=0, label="base", values={}),
                evaluated=True,
                valid=True,
                status="VALID",
                evaluation=None,
            )
        ],
    )
    # exercise the details-driven breakdown rendering directly
    text = explain(
        CandidateSelection(best=CandidateMission(mission=mission, label="base"), best_score=score),
        eval_result,
        constraints=_constraints(),
    )
    assert any("coverage" in r and "DATA_REQUIRED" in r for r in text.reasons)
    assert any("gsd" in r for r in text.reasons)


# ── Corpus: every mission stays scoreable with a full breakdown (10E point 8) ─


def test_all_corpus_missions_scoreable_with_full_breakdown(db):
    from .corpus import build_corpus

    for case in build_corpus(db):
        score = score_mission(case.mission, constraints=_constraints(), weights=OptimizationWeights())
        assert len(score.details) == 8
        assert score.total_score is not None
        assert all(d.label for d in score.details)
        scored = [d for d in score.details if d.status is ScoreComponentStatus.SCORED]
        assert pytest.approx(sum(d.contribution for d in scored), abs=1e-3) == score.total_score
