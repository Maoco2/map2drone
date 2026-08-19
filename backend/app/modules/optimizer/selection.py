"""Optimizer — best-candidate selection (Fase 10C-6/10C-7).

Ranks the valid candidates of a batch evaluation by score and returns the best
one (with its rebuilt Universal Mission) plus backup alternatives.

Only candidates that were evaluated, passed validation + constraints and carry
a scoreable ``total_score`` are eligible. Ranking is deterministic: score
descending, ties broken by candidate index (the generation/insertion order).

Alternatives (Fase 10C-7) follow a *variability* criterion: candidates whose
variable values are essentially the same as the best one (relative difference
below ``diversity_tolerance`` on every shared variable) are skipped in favour
of meaningfully different settings, so the returned backups are real fallbacks
rather than near-duplicates. If fewer diverse candidates exist than requested,
the remaining slots are filled with the top-scoring remaining candidates.

The best/alternative missions are rebuilt from their ``variable_values``
through the same :class:`~app.modules.optimizer.candidate_builder.CandidateBuilder`
the evaluation loop used — the loop itself keeps no mission payloads, so the
memory footprint stays bounded regardless of how many candidates were
evaluated.
"""

from __future__ import annotations

from typing import Optional

from app.modules.optimizer.models import (
    CandidateMission,
    CandidateSelection,
)

DEFAULT_DIVERSITY_TOLERANCE = 0.05


def select_best(
    evaluation_result,
    builder,
    alternatives_count: int = 3,
    diversity_tolerance: float = DEFAULT_DIVERSITY_TOLERANCE,
) -> CandidateSelection:
    """Select the best candidate and diverse backup alternatives.

    Args:
        evaluation_result: a :class:`CandidateEvaluationResult`.
        builder: the :class:`CandidateBuilder` used to rebuild the selected
            missions from their variable values.
        alternatives_count: number of alternatives after the best one.
        diversity_tolerance: relative difference (per variable) below which two
            candidates are considered equivalent when building alternatives.

    Returns:
        :class:`CandidateSelection` (``best`` / ``best_score`` may be ``None``
        when there is no eligible candidate).
    """
    eligible = [
        c
        for c in evaluation_result.candidates
        if c.evaluated
        and c.valid
        and c.evaluation is not None
        and c.evaluation.score is not None
        and c.evaluation.score.total_score is not None
    ]
    ranked = sorted(eligible, key=lambda c: c.evaluation.score.total_score, reverse=True)

    if not ranked:
        return CandidateSelection(best=None, best_score=None, alternatives=[])

    best = ranked[0]
    alternatives = _select_alternatives(
        ranked,
        best,
        alternatives_count=alternatives_count,
        diversity_tolerance=diversity_tolerance,
    )
    return CandidateSelection(
        best=_rebuild(best, builder),
        best_score=best.evaluation.score,
        alternatives=[_rebuild(c, builder) for c in alternatives],
        diverse_count=sum(
            1 for c in alternatives if not _similar(c.candidate.values, best.candidate.values, diversity_tolerance)
        ),
    )


def _select_alternatives(ranked, best, alternatives_count, diversity_tolerance):
    """Greedy score-ordered selection of diverse alternatives, with fallback."""
    chosen_values = [best.candidate.values]
    chosen_indices = {best.candidate.index}
    alternatives = []

    for c in ranked[1:]:
        if len(alternatives) == alternatives_count:
            break
        if c.candidate.index in chosen_indices:
            continue
        if any(_similar(c.candidate.values, s, diversity_tolerance) for s in chosen_values):
            continue
        alternatives.append(c)
        chosen_indices.add(c.candidate.index)
        chosen_values.append(c.candidate.values)

    # fallback: fill remaining slots with the top-scoring remaining candidates
    for c in ranked[1:]:
        if len(alternatives) == alternatives_count:
            break
        if c.candidate.index in chosen_indices:
            continue
        alternatives.append(c)
        chosen_indices.add(c.candidate.index)
    return alternatives


def _similar(a_values: dict, b_values: dict, tolerance: float) -> bool:
    """Two candidates are *similar* when every shared variable that differs
    stays below the relative tolerance (Fase 10C-7 variability criterion)."""
    for name in set(a_values) | set(b_values):
        if name not in a_values or name not in b_values:
            continue
        av, bv = a_values[name], b_values[name]
        if av == bv:
            continue
        denom = max(abs(av), abs(bv))
        if denom == 0:
            return False
        if abs(av - bv) / denom >= tolerance:
            return False
    return True


def _rebuild(candidate_eval, builder) -> Optional[CandidateMission]:
    """Rebuild the candidate mission from its variable values (deterministic)."""
    if builder is None:
        return None
    try:
        mission = builder.build(candidate_eval.candidate.values)
    except Exception:
        return None
    return CandidateMission(
        mission=mission,
        label=candidate_eval.candidate.label,
        variable_values=candidate_eval.candidate.values,
    )


__all__ = ["DEFAULT_DIVERSITY_TOLERANCE", "select_best"]
