"""Fase 10D — integrated constraint validation (point 5).

Runs the full evaluation/search pipeline against real missions with a complete
constraint box and verifies the guard-rail semantics: WARNING never eliminates,
FAIL eliminates, partial boxes restrict, no feasible candidate yields
NO_SOLUTION, and rejected candidates are reported (never dropped).
"""

from app.modules.optimizer import evaluate, evaluate_candidates
from app.modules.optimizer.models import CandidateConfig, OptimizationConstraints, OptimizerInput
from app.modules.optimizer.optimizer import Optimizer
from app.modules.optimizer.variables import OptimizationVariable, OptimizationVariables, VariableMode

from .corpus import build_corpus, get_case


def _altitude_variables(values):
    return OptimizationVariables(
        variables=[OptimizationVariable(name="altitude_m", mode=VariableMode.CANDIDATE_VALUES, values=values)]
    )


def _full_box() -> OptimizationConstraints:
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
        min_flight_time=30.0,
        max_flight_time=400.0,
        min_mission_distance_m=100.0,
        max_mission_distance_m=20000.0,
        min_photo_interval_s=1.0,
        max_photo_interval_s=10.0,
        max_photo_count=100,
        allowed_capture_intervals=[1, 2, 3, 4, 5, 6],
    )


def _grid_case(db):
    return get_case(build_corpus(db), "grid_small_time")


# ── Full box: everything PASS → OPTIMAL ──────────────────────────────────────


def test_full_constraint_box_passes(db):
    case = _grid_case(db)
    result = Optimizer().solve(
        OptimizerInput(
            mission=case.mission,
            request=case.request,
            variables=_altitude_variables([80, 100, 120]),
            constraints=_full_box(),
        ),
        db_session=db,
    )
    assert result.status == "OPTIMAL"
    assert result.best_candidate is not None
    assert result.explanation.stats["total"] == 3
    assert result.explanation.stats["evaluated"] == 3
    assert result.explanation.stats["valid"] == 3
    assert result.explanation.stats["invalid"] == 0
    assert result.explanation.stats["rejected"] == 0
    assert all(e.valid for e in result.evaluations)


# ── WARNING never eliminates ─────────────────────────────────────────────────


def test_warning_does_not_eliminate_candidate(db):
    case = _grid_case(db)
    result = Optimizer().solve(
        OptimizerInput(
            mission=case.mission,
            request=case.request,
            constraints=OptimizationConstraints(preferred_turn_radius=1.0),
        ),
        db_session=db,
    )
    assert result.status == "FEASIBLE"  # valid but warned
    assert result.best_candidate is not None
    assert result.explanation.warnings  # the preferred-radius mismatch is surfaced
    # the underlying evaluation is still VALID (no FAIL)
    assert result.evaluations[0].valid is True


def test_warning_on_mismatched_preferred_radius(db):
    from app.modules.mission.models import TurnPlan

    case = _grid_case(db)
    mission = case.mission.model_copy(deep=True)
    mission.turn_plan = TurnPlan(mode="AUTO", status="VALID", radius_m=10.0)
    evaluation = evaluate(mission, constraints=OptimizationConstraints(preferred_turn_radius=5.0))
    assert evaluation.valid is True
    assert any("differs from the preferred" in w for w in evaluation.warnings)

    matched = evaluate(mission, constraints=OptimizationConstraints(preferred_turn_radius=10.0))
    assert matched.valid is True
    assert not any("differs from the preferred" in w for w in matched.warnings)


def test_non_evaluable_constraint_is_warning_not_fail(db):
    # no turn plan -> the extension cannot be evaluated; WARNING, never FAIL
    case = _grid_case(db)
    evaluation = evaluate(case.mission, constraints=OptimizationConstraints(max_turn_extension_m=50.0))
    assert evaluation.valid is True
    assert any("turn_extension_m" in w for w in evaluation.warnings)


# ── FAIL eliminates the candidate ────────────────────────────────────────────


def test_hard_constraint_fail_marks_candidate_invalid(db):
    case = _grid_case(db)
    evaluation = evaluate(case.mission, constraints=OptimizationConstraints(max_photo_count=20))
    assert evaluation.valid is False
    assert evaluation.status == "INVALID"


def test_fail_eliminates_only_the_violating_candidates(db):
    case = _grid_case(db)
    result = Optimizer().solve(
        OptimizerInput(
            mission=case.mission,
            request=case.request,
            variables=_altitude_variables([80, 100, 120, 140]),
            constraints=OptimizationConstraints(max_photo_count=20, min_gsd=2.0, max_gsd=4.0),
        ),
        db_session=db,
    )
    assert result.status == "OPTIMAL"
    # 80 m (36 photos) and 100 m (21 photos) exceed the budget -> invalid
    invalid = {e.variable_values["altitude_m"] for e in result.evaluations if not e.valid}
    assert invalid == {80.0, 100.0}
    valid = {e.variable_values["altitude_m"] for e in result.evaluations if e.valid}
    assert valid == {120.0, 140.0}
    # the optimizer genuinely found the cheapest valid candidate
    assert result.best_candidate.variable_values["altitude_m"] == 120.0
    assert result.explanation.stats["invalid"] == 2


# ── Partial box: only the configurations inside stay valid ───────────────────


def test_partial_box_only_high_altitude_candidates_valid(db):
    case = _grid_case(db)
    result = Optimizer().solve(
        OptimizerInput(
            mission=case.mission,
            request=case.request,
            variables=_altitude_variables([80, 100, 120, 140]),
            constraints=OptimizationConstraints(min_gsd=3.0),
        ),
        db_session=db,
    )
    assert result.status == "OPTIMAL"
    invalid = {e.variable_values["altitude_m"] for e in result.evaluations if not e.valid}
    assert invalid == {80.0, 100.0}  # GSD below the 3.0 cm floor
    valid = {e.variable_values["altitude_m"] for e in result.evaluations if e.valid}
    assert valid == {120.0, 140.0}
    assert result.best_candidate.variable_values["altitude_m"] == 120.0


# ── No feasible candidate → NO_SOLUTION ──────────────────────────────────────


def test_all_invalid_yields_no_solution(db):
    case = _grid_case(db)
    result = Optimizer().solve(
        OptimizerInput(
            mission=case.mission,
            request=case.request,
            variables=_altitude_variables([80, 100, 120, 140]),
            constraints=OptimizationConstraints(max_altitude=10.0),
        ),
        db_session=db,
    )
    assert result.status == "NO_SOLUTION"
    assert result.best_candidate is None
    assert result.best_score is None
    assert result.alternatives == []
    assert result.explanation.stats["invalid"] == 4
    assert result.explanation.stats["rejected"] == 0


# ── Rejected candidates are reported, never dropped ──────────────────────────


def test_rejected_candidates_reported_in_stats(db):
    case = _grid_case(db)

    class FlakyBuilder:
        """Builder whose build() fails for a specific altitude."""

        def build(self, values):
            if values.get("altitude_m") == 999:
                raise ValueError("planning failed")
            return case.mission.model_copy(deep=True)

    cfgs = [
        CandidateConfig(index=0, label="ok", values={"altitude_m": 100}),
        CandidateConfig(index=1, label="bad", values={"altitude_m": 999}),
    ]
    report = evaluate_candidates(cfgs, FlakyBuilder())
    assert report.total == 2
    assert report.evaluated == 1
    assert report.valid == 1
    assert report.invalid == 0
    assert report.rejected == 1
    assert [c.status for c in report.candidates] == ["VALID", "REJECTED"]
    assert report.candidates[1].reason  # the failure reason is surfaced


# ── No constraints ⇒ no constraint-driven scores, still scoreable ────────────


def test_no_constraints_leaves_constraint_scores_none(db):
    case = _grid_case(db)
    evaluation = evaluate(case.mission)
    assert evaluation.valid is True
    assert evaluation.score is not None
    assert evaluation.score.gsd_score is None
    assert evaluation.score.time_score is None
    assert evaluation.score.battery_score is None
    assert evaluation.score.photo_count_score is None
    # overlap always has a target (the mission's own baseline overlap), so it is
    # SCORED even without explicit constraints
    assert evaluation.score.overlap_score is not None
    # Fase 10E: coverage is DATA_REQUIRED (no projected area in UMM 1.0), so it
    # is never reported as a fake 1.0; overlap + safety keep the total scoreable
    assert evaluation.score.coverage_score is None
    coverage = [d for d in evaluation.score.details if d.component == "coverage"][0]
    assert coverage.status.value == "DATA_REQUIRED"
    assert coverage.message
    assert evaluation.score.total_score is not None
