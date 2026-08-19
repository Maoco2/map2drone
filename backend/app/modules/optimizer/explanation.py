"""Optimizer — selection explanation (Fase 10C-8).

Turns a :class:`CandidateSelection` + its :class:`CandidateEvaluationResult`
into a human-readable :class:`OptimizationExplanation` derived exclusively from
the real evaluation data:

* ``summary`` — why the best mission was chosen (label, values, score, ranking).
* ``reasons`` — score comparison vs the closest competitor, diversity of the
  alternatives, the best mission's score breakdown and hard-constraint
  compliance (PASS reports re-derived from the best mission's own data).
* ``warnings`` — the best mission's evaluation warnings, aggregated constraint
  FAIL/WARNING outcomes across the batch, and performance/camera-height
  advisories computed from the best mission's metrics.

No hardcoded numeric thresholds are used: bounds always come from the
configured constraints; advisories are driven by metric flags (e.g. battery
count, turn-plan fallback).
"""

from __future__ import annotations

from typing import Optional

from app.modules.optimizer.constraints import evaluate_constraints
from app.modules.optimizer.models import (
    CandidateEvaluationResult,
    CandidateMission,
    ConstraintStatus,
    OptimizationConstraints,
    OptimizationExplanation,
)

_SCORE_LABELS = {
    "coverage_score": "coverage",
    "gsd_score": "gsd",
    "overlap_score": "overlap",
    "time_score": "time",
    "battery_score": "battery",
    "photo_count_score": "photos",
    "turn_score": "turns",
    "safety_score": "safety",
}

_CRITICAL_TURN_SOURCES = ("overhead_fallback",)


def explain(
    selection,
    evaluation_result: CandidateEvaluationResult,
    constraints: Optional[OptimizationConstraints] = None,
) -> OptimizationExplanation:
    """Build the explanation for a selection from real evaluation data."""
    stats = {
        "total": evaluation_result.total,
        "evaluated": evaluation_result.evaluated,
        "valid": evaluation_result.valid,
        "invalid": evaluation_result.invalid,
        "rejected": evaluation_result.rejected,
    }

    best = selection.best
    if best is None or selection.best_score is None:
        return OptimizationExplanation(
            summary=_no_solution_summary(evaluation_result),
            reasons=_no_solution_reasons(evaluation_result),
            warnings=_aggregated_constraint_warnings(evaluation_result),
            stats=stats,
        )

    reasons = _best_reasons(selection, evaluation_result, constraints)
    warnings = _best_warnings(best, evaluation_result)
    warnings += _performance_warnings(best, constraints)
    warnings += _aggregated_constraint_warnings(evaluation_result)

    return OptimizationExplanation(
        summary=_summary(best, selection.best_score, evaluation_result),
        reasons=reasons,
        warnings=warnings,
        stats=stats,
    )


# ── Summary ──────────────────────────────────────────────────────────────────


def _summary(best: CandidateMission, best_score, evaluation_result) -> str:
    return (
        f"Selected mission {best.label} ({_fmt_values(best.variable_values)}) "
        f"with total score {best_score.total_score:.3f} — best of "
        f"{evaluation_result.valid} valid candidate(s) out of "
        f"{evaluation_result.evaluated} evaluated."
    )


def _no_solution_summary(evaluation_result) -> str:
    return (
        "No feasible mission found: "
        f"{evaluation_result.valid} valid of {evaluation_result.evaluated} "
        f"evaluated candidate(s), {evaluation_result.invalid} invalid, "
        f"{evaluation_result.rejected} rejected."
    )


# ── Reasons ──────────────────────────────────────────────────────────────────


def _best_reasons(selection, evaluation_result, constraints) -> list[str]:
    reasons = [
        f"Highest score ({selection.best_score.total_score:.3f}) among "
        f"{evaluation_result.valid} valid candidate(s) out of "
        f"{evaluation_result.evaluated} evaluated."
    ]

    competitor = _closest_competitor(evaluation_result, selection.best_score.total_score)
    if competitor is not None:
        reasons.append(
            f"Closest competitor scored {competitor:.3f} "
            f"(difference {selection.best_score.total_score - competitor:.3f})."
        )

    reasons.append(_diversity_reason(selection))

    breakdown = _score_breakdown(selection.best_score)
    if breakdown:
        reasons.append(f"Score breakdown: {breakdown}.")

    compliance = _constraint_compliance(best_mission, constraints) if (best_mission := _best_mission(selection)) else []
    if compliance:
        reasons.append(f"Best mission satisfies the configured hard bounds: {', '.join(compliance)}.")
    return reasons


def _closest_competitor(evaluation_result, best_total: Optional[float]) -> Optional[float]:
    totals = sorted(
        {
            c.evaluation.score.total_score
            for c in evaluation_result.candidates
            if c.evaluation is not None
            and c.evaluation.score is not None
            and c.evaluation.score.total_score is not None
        },
        reverse=True,
    )
    if best_total is None or len(totals) < 2:
        return None
    return totals[1]


def _diversity_reason(selection) -> str:
    if not selection.alternatives:
        return "No alternative mission retained."
    n = len(selection.alternatives)
    if selection.diverse_count == n:
        return f"All {n} alternative(s) chosen for meaningful variation in variable values (diversity criterion)."
    return (
        f"{selection.diverse_count} of {n} alternative(s) differ meaningfully in "
        "variable values; the rest share near-identical settings (fallback fill)."
    )


def _score_breakdown(score) -> str:
    """Render the scoring breakdown, preferring the Fase 10E detail rows.

    ``details`` carries raw value, resolved target, normalized value and
    status per component; UNKNOWN / DATA_REQUIRED components are shown with a
    short reason instead of a fake number. Falls back to the flat score fields
    for legacy ``MissionScore`` objects built without ``details``.
    """
    details = getattr(score, "details", None)
    if details:
        parts = []
        for d in details:
            if d.normalized_value is not None:
                parts.append(f"{d.label} {d.normalized_value:.3f}")
            elif d.message:
                parts.append(f"{d.label} ({d.status.value}: {d.message})")
            else:
                parts.append(f"{d.label} ({d.status.value})")
        return ", ".join(parts)
    parts = []
    for key, label in _SCORE_LABELS.items():
        value = getattr(score, key)
        if value is not None:
            parts.append(f"{label} {value:.3f}")
    return ", ".join(parts)


def _constraint_compliance(best_mission, constraints) -> list[str]:
    if constraints is None:
        return []
    names = []
    for report in evaluate_constraints(constraints, best_mission):
        if report.status is ConstraintStatus.PASS:
            names.append(report.constraint)
    return names


# ── Warnings ─────────────────────────────────────────────────────────────────


def _best_warnings(best: CandidateMission, evaluation_result) -> list[str]:
    evaluation = _best_evaluation(evaluation_result, best)
    if evaluation is None:
        return []
    return [f"best: {w}" for w in evaluation.warnings]


def _best_evaluation(evaluation_result, best: CandidateMission):
    for ce in evaluation_result.candidates:
        if ce.evaluation is not None and ce.evaluation.variable_values == best.variable_values:
            return ce.evaluation
    return None


def _performance_warnings(best: CandidateMission, constraints) -> list[str]:
    warnings = []
    metrics = best.mission.metrics
    if metrics.battery_count > 1:
        warnings.append(
            f"advisory: mission requires {metrics.battery_count} battery change(s) "
            f"(flight time {metrics.flight_time_s:.0f} s)."
        )
    if metrics.turn_source in _CRITICAL_TURN_SOURCES:
        warnings.append(
            "advisory: turn times use the overhead fallback estimate (no turn "
            "plan) — flight time may differ from a real turn plan."
        )
    if constraints is not None and constraints.min_gsd is not None and constraints.max_gsd is not None:
        lo, hi, gsd = constraints.min_gsd, constraints.max_gsd, metrics.gsd_cm
        if lo <= gsd <= hi:
            warnings.append(
                f"advisory: camera height {best.mission.parameters.altitude_m:g} m "
                f"yields GSD {gsd:.2f} cm, inside the configured band [{lo:g}, {hi:g}] cm."
            )
        else:
            warnings.append(f"advisory: GSD {gsd:.2f} cm is outside the configured band [{lo:g}, {hi:g}] cm.")
    return warnings


def _aggregated_constraint_warnings(evaluation_result) -> list[str]:
    invalid_counts: dict[str, int] = {}
    valid_counts: dict[str, int] = {}
    for ce in evaluation_result.candidates:
        if ce.evaluation is None or not ce.evaluation.warnings:
            continue
        target = valid_counts if ce.valid else invalid_counts
        for w in ce.evaluation.warnings:
            if not w.startswith("constraint:"):
                continue
            reason = w.split(":", 1)[1].strip()
            target[reason] = target.get(reason, 0) + 1

    warnings = []
    for reason, count in sorted(invalid_counts.items()):
        warnings.append(f"{count} candidate(s) rejected by constraint: {reason}.")
    for reason, count in sorted(valid_counts.items()):
        warnings.append(f"{count} other valid candidate(s) carry the warning: {reason}.")
    return warnings


# ── No-solution branch ───────────────────────────────────────────────────────


def _no_solution_reasons(evaluation_result) -> list[str]:
    reasons = []
    if evaluation_result.rejected and evaluation_result.evaluated == 0:
        reasons.append("All candidates failed to build/plan — review the polygon, drone and camera settings.")
    if evaluation_result.invalid:
        reasons.append(
            f"{evaluation_result.invalid} candidate(s) failed validation or constraints; see warnings below."
        )
    if evaluation_result.valid == 0 and not reasons:
        reasons.append("No candidate passed validation + constraints.")
    return reasons


def _best_mission(selection) -> Optional:
    return selection.best.mission if selection.best is not None else None


def _fmt_values(values) -> str:
    if not values:
        return "defaults"
    return ", ".join(f"{k}={_fmt(v)}" for k, v in values.items())


def _fmt(value) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return f"{value:g}"
    return str(value)


__all__ = ["explain"]
