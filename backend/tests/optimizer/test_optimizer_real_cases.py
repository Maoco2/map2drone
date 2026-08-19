"""Fase 10D — real-mission validation (corpus, determinism, improvement, LCHM).

Runs the Photogrammetry Mission Optimizer against the real planning engines and
validates behaviour the unit tests cannot: the corpus matrix, run-to-run
determinism (candidates / variable values / scores / winner / alternatives /
status / UMM), genuine improvement over the baseline, coherent winner metrics
and the explicit LCHM waypoint-capacity state.
"""

import pytest

from app.modules.export.adapters import from_universal_mission
from app.modules.export.litchi_lchm import LchmExporter, LchmValidationError
from app.modules.optimizer import evaluate
from app.modules.optimizer.models import OptimizationConstraints, OptimizerInput
from app.modules.optimizer.optimizer import Optimizer
from app.modules.optimizer.variables import OptimizationVariable, OptimizationVariables, VariableMode

from .corpus import build_corpus, get_case, lchm_export_status

LCHM_MAX_WAYPOINTS = 99


def _candidate_values_variables(name, values):
    return OptimizationVariables(
        variables=[OptimizationVariable(name=name, mode=VariableMode.CANDIDATE_VALUES, values=values)]
    )


# ── Corpus matrix ────────────────────────────────────────────────────────────


def test_corpus_covers_validation_matrix(db):
    corpus = build_corpus(db)
    ids = {c.case_id for c in corpus}
    required = {
        "grid_small_time",  # grid < 99 waypoints
        "grid_large_over_99",  # grid > 99 waypoints
        "corridor_vertex",  # corridor
        "grid_small_low_alt",  # different altitude
        "grid_small_high_alt",  # different altitude
        "grid_small_fast",  # different speed
        "grid_small_slow",  # different speed
        "grid_small_overlap_high",  # different overlaps
        "grid_small_time",  # TIME capture
        "grid_small_capture_distance",  # DISTANCE capture
        "grid_small_capture_none",  # NONE capture
        "grid_small_turn_manual_small",  # small turn radius
        "grid_small_turn_manual_large",  # large turn radius
    }
    assert required.issubset(ids)
    # every case keeps the original request and the built UMM
    for case in corpus:
        assert case.request is not None
        assert case.mission is not None
        assert case.mission.mission_type == case.mission_type


def test_each_case_keeps_original_request_and_umm(db):
    for case in build_corpus(db):
        assert case.request is not None
        assert case.mission is not None
        assert case.mission.mission_type == case.mission_type
        # request and mission are coherent (altitude matches parameters)
        assert case.mission.parameters.altitude_m == pytest.approx(case.request.altitude, abs=1e-6)


def test_grid_small_stays_below_lchm_limit(db):
    case = get_case(build_corpus(db), "grid_small_time")
    assert len(case.mission.waypoints) < LCHM_MAX_WAYPOINTS
    assert lchm_export_status(case.mission) == "LCHM_OK"


def test_grid_large_exceeds_lchm_limit(db):
    case = get_case(build_corpus(db), "grid_large_over_99")
    assert len(case.mission.waypoints) > LCHM_MAX_WAYPOINTS
    assert lchm_export_status(case.mission) == "LCHM_UNSUPPORTED_WAYPOINT_COUNT"


def test_corpus_case_waypoint_counts_match_metrics(db):
    for case in build_corpus(db):
        assert case.mission.metrics.waypoint_count == len(case.mission.waypoints)


# ── Search over real missions ────────────────────────────────────────────────


def test_solve_grid_small_optimal(db):
    case = get_case(build_corpus(db), "grid_small_time")
    result = Optimizer().solve(
        OptimizerInput(
            mission=case.mission,
            request=case.request,
            variables=_candidate_values_variables("altitude_m", [80, 100, 120]),
        ),
        db_session=db,
    )
    assert result.status == "OPTIMAL"
    assert result.best_candidate is not None
    assert result.best_score is not None
    assert len(result.alternatives) == 2
    assert result.explanation.stats["evaluated"] == 3
    assert result.explanation.stats["valid"] == 3
    assert all(e.variable_values is not None for e in result.evaluations)


def test_solve_corridor_optimal(db):
    case = get_case(build_corpus(db), "corridor_vertex")
    result = Optimizer().solve(
        OptimizerInput(
            mission=case.mission,
            request=case.request,
            variables=_candidate_values_variables("altitude_m", [90, 100, 110]),
        ),
        db_session=db,
    )
    assert result.status == "OPTIMAL"
    assert result.best_candidate.mission.mission_type == "linear_corridor"
    assert result.explanation.stats["evaluated"] == 3


# ── Determinism (Fase 10D point 2) ───────────────────────────────────────────


def _result_surface(result):
    """Deterministic surface of a solve (created_at is excluded)."""
    return (
        result.status,
        result.best_candidate.variable_values if result.best_candidate else None,
        result.best_score.total_score if result.best_score else None,
        tuple(a.variable_values for a in result.alternatives),
        tuple((e.variable_values, e.status, e.score.total_score if e.score else None) for e in result.evaluations),
        result.explanation.summary,
        tuple(result.explanation.reasons),
        result.explanation.stats,
        (
            result.best_candidate.mission.model_dump(mode="json", exclude={"created_at"})
            if result.best_candidate is not None
            else None
        ),
    )


def test_determinism_across_repeated_runs(db):
    case = get_case(build_corpus(db), "grid_small_time")
    surfaces = []
    for _ in range(3):
        result = Optimizer().solve(
            OptimizerInput(
                mission=case.mission,
                request=case.request,
                variables=_candidate_values_variables("altitude_m", [80, 100, 120]),
            ),
            db_session=db,
        )
        surfaces.append(_result_surface(result))
    for other in surfaces[1:]:
        assert other == surfaces[0]


def test_determinism_with_constraints_and_weights(db):
    case = get_case(build_corpus(db), "grid_small_time")
    constraints = OptimizationConstraints(min_gsd=2.0, max_gsd=4.0, max_photo_count=100)
    first = Optimizer().solve(
        OptimizerInput(
            mission=case.mission,
            request=case.request,
            variables=_candidate_values_variables("altitude_m", [80, 100, 120, 140]),
            constraints=constraints,
        ),
        db_session=db,
    )
    second = Optimizer().solve(
        OptimizerInput(
            mission=case.mission,
            request=case.request,
            variables=_candidate_values_variables("altitude_m", [80, 100, 120, 140]),
            constraints=constraints,
        ),
        db_session=db,
    )
    assert _result_surface(first) == _result_surface(second)


# ── The optimizer actually improves (Fase 10D point 3) ───────────────────────


def test_optimizer_improves_over_baseline(db):
    corpus = build_corpus(db)
    case = get_case(corpus, "grid_small_time")
    baseline = case.mission
    limit = baseline.metrics.photo_count - 1

    # baseline violates the photo budget; the search must find a valid winner
    baseline_eval = evaluate(
        baseline,
        constraints=OptimizationConstraints(max_photo_count=limit, min_gsd=2.0, max_gsd=4.0),
    )
    assert baseline_eval.valid is False

    result = Optimizer().solve(
        OptimizerInput(
            mission=baseline,
            request=case.request,
            variables=_candidate_values_variables("altitude_m", [80, 100, 120, 140]),
            constraints=OptimizationConstraints(max_photo_count=limit, min_gsd=2.0, max_gsd=4.0),
        ),
        db_session=db,
    )
    assert result.status == "OPTIMAL"
    assert result.best_candidate is not None
    winner = result.best_candidate.mission
    assert winner.metrics.photo_count <= limit  # satisfies the budget
    assert winner.metrics.photo_count < baseline.metrics.photo_count  # real improvement
    assert 2.0 <= winner.metrics.gsd_cm <= 4.0  # GSD in the requested band
    assert winner.metrics.photo_count > 0  # not a degenerate zero-photo mission


def test_winner_metrics_are_coherent(db):
    corpus = build_corpus(db)
    case = get_case(corpus, "grid_small_time")
    result = Optimizer().solve(
        OptimizerInput(
            mission=case.mission,
            request=case.request,
            variables=_candidate_values_variables("altitude_m", [80, 100, 120, 140]),
            constraints=OptimizationConstraints(min_gsd=2.0, max_gsd=4.0, max_photo_count=50),
        ),
        db_session=db,
    )
    assert result.best_candidate is not None
    winner = result.best_candidate.mission
    m = winner.metrics
    p = winner.parameters
    assert m.gsd_cm > 0
    assert m.line_spacing_m > 0
    assert m.photo_spacing_m > 0
    assert m.footprint_width_m > 0
    assert m.footprint_height_m > 0
    assert m.photo_count > 0
    assert m.battery_count >= 1
    assert p.speed_ms > 0
    assert 0.0 < p.overlap_frontal < 100.0
    assert 0.0 < p.overlap_lateral < 100.0
    assert winner.capture_plan is not None
    assert winner.capture_plan.mode.value in ("TIME", "DISTANCE", "NONE")
    assert winner.capture_plan.commercial_interval_s is not None
    # capture plan matches the capture interval block (optimizer consumed it)
    block = winner.capture_interval
    assert block["recommended_interval_s"] == winner.capture_plan.commercial_interval_s
    assert winner.metrics.total_distance_m > 0
    assert winner.metrics.flight_time_s > 0


# ── LCHM capacity (Fase 10D point 8) ─────────────────────────────────────────


def test_large_mission_lchm_unsupported_no_auto_split(db):
    corpus = build_corpus(db)
    case = get_case(corpus, "grid_large_over_99")
    mission = case.mission
    assert len(mission.waypoints) > LCHM_MAX_WAYPOINTS

    # explicit state: no auto-split exists yet
    assert lchm_export_status(mission) == "LCHM_UNSUPPORTED_WAYPOINT_COUNT"

    # the exporter refuses (hard guard, Fase 10C-13) and never wraps the count
    export_data = from_universal_mission(mission)
    with pytest.raises(LchmValidationError, match="at most 99 waypoints"):
        LchmExporter().export(export_data)

    # the mission itself is untouched: no splitting was applied
    assert len(mission.waypoints) > LCHM_MAX_WAYPOINTS
    assert mission.metrics.waypoint_count == len(mission.waypoints)
