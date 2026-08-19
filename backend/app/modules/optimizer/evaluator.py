"""Optimizer — evaluation pipeline (Fase 10B).

``evaluate`` is the conceptual pipeline:

    candidate mission
        → UniversalMissionValidator
        → metrics
        → score

It is an orchestrator only: it reuses the mission's own CapturePlan / TurnPlan
/ metrics produced by the engines and never re-runs CaptureInterval,
TurnRadius or Planning Core formulas (they live in the Universal Mission
already).
"""

from __future__ import annotations

from typing import Optional

from app.modules.mission.validator import UniversalMissionValidator
from app.modules.optimizer.constraints import evaluate_constraints
from app.modules.optimizer.models import (
    CandidateConfig,
    CandidateEvaluation,
    CandidateEvaluationResult,
    CandidateMission,
    ConstraintStatus,
    EvaluationResult,
    MissionScore,
    OptimizationConstraints,
    OptimizationWeights,
)
from app.modules.optimizer.objective import score_mission


def evaluate(
    mission,
    constraints: Optional[OptimizationConstraints] = None,
    weights: Optional[OptimizationWeights] = None,
) -> EvaluationResult:
    """Validate + score a mission/candidate (no search, no mutation)."""
    validator = UniversalMissionValidator()
    validation = validator.validate(mission)

    reports = evaluate_constraints(constraints, mission)
    failures = [r for r in reports if r.status is ConstraintStatus.FAIL]
    warnings = [f"{w.code}: {w.message}" for w in validation.warnings]
    warnings += [f"constraint:{r.constraint} — {r.reason}" for r in reports if r.status is not ConstraintStatus.PASS]

    score: Optional[MissionScore] = None
    if validation.valid:
        score = score_mission(mission, constraints=constraints, weights=weights, validation=validation)
        score = _fold_constraints(score, bool(failures))

    valid = validation.valid and not failures
    status = "VALID"
    if not valid:
        status = "INVALID"
    elif warnings:
        status = "WARNING"

    return EvaluationResult(
        valid=valid,
        status=status,
        metrics=mission.metrics.model_dump(mode="json"),
        score=score,
        warnings=warnings,
        validation={
            "status": validation.status,
            "errors": [e.model_dump(mode="json") for e in validation.errors],
            "warnings": [w.model_dump(mode="json") for w in validation.warnings],
        },
    )


def evaluate_candidate(
    candidate: CandidateMission,
    constraints: Optional[OptimizationConstraints] = None,
    weights: Optional[OptimizationWeights] = None,
) -> EvaluationResult:
    """Evaluate a :class:`CandidateMission` (10B convenience wrapper).

    The candidate's ``variable_values`` are recorded in the result for
    provenance (Fase 10C-4).
    """
    result = evaluate(candidate.mission, constraints=constraints, weights=weights)
    result.variable_values = candidate.variable_values
    return result


def evaluate_candidates(
    candidates: list[CandidateConfig],
    builder,
    constraints: Optional[OptimizationConstraints] = None,
    weights: Optional[OptimizationWeights] = None,
) -> CandidateEvaluationResult:
    """Evaluate a batch of candidate configurations (Fase 10C-5).

    For each candidate the mission is built through ``builder.build(values)``
    and then run through the evaluation pipeline. Candidates that fail to build
    or to evaluate are marked ``REJECTED`` (never silently dropped) and the
    counts are reported. Deterministic: the report preserves candidate order.
    """
    out: list[CandidateEvaluation] = []
    evaluated = valid = invalid = rejected = 0
    for cfg in candidates:
        try:
            mission = builder.build(cfg.values)
            result = evaluate(mission, constraints=constraints, weights=weights)
            result.variable_values = cfg.values
        except Exception as exc:
            rejected += 1
            out.append(
                CandidateEvaluation(
                    candidate=cfg,
                    evaluated=False,
                    valid=False,
                    rejected=True,
                    status="REJECTED",
                    reason=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        evaluated += 1
        if result.valid:
            valid += 1
            status = "VALID"
        else:
            invalid += 1
            status = "INVALID"
        out.append(
            CandidateEvaluation(
                candidate=cfg,
                evaluated=True,
                valid=result.valid,
                rejected=False,
                status=status,
                evaluation=result,
            )
        )
    return CandidateEvaluationResult(
        total=len(candidates),
        evaluated=evaluated,
        valid=valid,
        invalid=invalid,
        rejected=rejected,
        candidates=out,
    )


def _fold_constraints(score: MissionScore, has_violations: bool) -> MissionScore:
    """Knock the total score down when constraints are violated."""
    if not has_violations:
        return score
    if score.total_score is None:
        return score
    score.total_score = round(score.total_score * 0.5, 4)
    return score


__all__ = ["evaluate", "evaluate_candidate", "evaluate_candidates"]
