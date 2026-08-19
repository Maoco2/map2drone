"""Optimizer — solve orchestration (Fase 10C-9).

:class:`Optimizer` orchestrates the deterministic search end to end:

    variables (if declared)  →  CandidateGenerator
    candidate values         →  CandidateBuilder   (existing planning engines)
    built missions           →  evaluate_candidates (validation + constraints)
                             →  select_best        (ranking + alternatives)
                             →  explain            (human-readable rationale)

``solve`` never replaces the engines: it only composes them, in the same order
and with the same functions a human operator would run. ``status`` reflects
the outcome: ``OPTIMAL`` (clean best, full search), ``FEASIBLE`` (best passes
but carries warnings), ``CONSTRAINED`` (search deterministically capped by
``max_candidates``), ``NO_SOLUTION`` (no valid candidate).
"""

from __future__ import annotations

from typing import Optional

from app.modules.optimizer.candidate_builder import CandidateBuilder, mission_to_request
from app.modules.optimizer.evaluator import evaluate, evaluate_candidates
from app.modules.optimizer.explanation import explain
from app.modules.optimizer.generator import CandidateGenerator
from app.modules.optimizer.models import (
    CandidateConfig,
    CandidateEvaluation,
    CandidateEvaluationResult,
    CandidateMission,
    CandidateSelection,
    OptimizationResult,
    OptimizerInput,
)
from app.modules.optimizer.selection import select_best
from app.modules.optimizer.variables import expand_variables


class Optimizer:
    """Orchestrator for the Photogrammetry Mission Optimizer (deterministic)."""

    def __init__(self) -> None:
        self._input: Optional[OptimizerInput] = None

    def evaluate_input(self, inp: OptimizerInput):
        """Validate + score a single candidate (no search)."""
        self._input = inp
        return evaluate(
            inp.mission,
            constraints=inp.constraints,
            weights=inp.weights,
        )

    def solve(
        self,
        inp: OptimizerInput,
        builder: Optional[CandidateBuilder] = None,
        db_session=None,
    ) -> OptimizationResult:
        """Automatic optimization search (Fase 10C-9).

        When ``inp.variables`` is declared the search evaluates the generated
        candidate set; otherwise the base mission itself is evaluated as the
        single candidate. ``builder`` may be supplied by the API layer (which
        has the original request + DB session); when omitted and a search is
        requested, it is rebuilt from the base mission via
        :func:`mission_to_request` — ``db_session`` is then required.
        """
        self._input = inp
        if inp.variables is None:
            return self._solve_single(inp)
        if builder is None:
            builder = self._resolve_builder(inp, db_session)
        return self._solve_search(inp, builder)

    @staticmethod
    def _resolve_builder(inp, db_session) -> CandidateBuilder:
        """Obtain the candidate builder: explicit request, or mission rebuild.

        Grid missions do not carry their polygon in the universal mission
        payload, so ``inp.request`` is the authoritative source for them; the
        mission rebuild (corridor only) is a convenience fallback.
        """
        request = None
        if inp.request is not None:
            request = inp.request
        elif db_session is not None:
            request = mission_to_request(inp.mission)
        if request is None:
            raise ValueError(
                "solve() requires OptimizerInput.request (or db_session with a "
                "rebuildable mission) when variables are declared — candidates "
                "must be planned."
            )
        if db_session is None:
            raise ValueError("solve() requires db_session when variables are declared")
        return CandidateBuilder(inp.mission.mission_type, request, db_session)

    # ── Search over declared variables ──────────────────────────────────────

    def _solve_search(self, inp: OptimizerInput, builder: CandidateBuilder) -> OptimizationResult:
        generation = CandidateGenerator(
            expand_variables(inp.variables),
            max_candidates=inp.max_candidates,
        ).generate()

        eval_result = evaluate_candidates(
            generation.candidates,
            builder,
            constraints=inp.constraints,
            weights=inp.weights,
        )
        selection = select_best(eval_result, builder)
        explanation = explain(selection, eval_result, constraints=inp.constraints)

        status, message = self._search_status(generation, selection, eval_result, inp)
        evaluations = [c.evaluation for c in eval_result.candidates if c.evaluation is not None]

        return OptimizationResult(
            status=status,
            message=message,
            best_candidate=selection.best,
            best_score=selection.best_score,
            alternatives=selection.alternatives,
            evaluations=evaluations,
            explanation=explanation,
        )

    @staticmethod
    def _search_status(generation, selection, eval_result, inp) -> tuple[str, str]:
        if eval_result.valid == 0:
            return "NO_SOLUTION", (
                f"No feasible candidate found: {eval_result.valid} valid of "
                f"{eval_result.evaluated} evaluated, {eval_result.invalid} invalid, "
                f"{eval_result.rejected} rejected."
            )
        if generation.truncated:
            return "CONSTRAINED", (
                f"Search limited to {generation.generated} of "
                f"{generation.total_possible} candidate(s) "
                f"(max_candidates={inp.max_candidates}); "
                "the result is constrained to the evaluated set."
            )
        best_eval = _best_evaluation(eval_result, selection.best)
        if best_eval is not None and best_eval.warnings:
            return "FEASIBLE", (
                "Best candidate passes validation and hard constraints but carries warnings; see explanation."
            )
        return "OPTIMAL", ("Best candidate found — deterministic full search, no warnings.")

    # ── Single-candidate path (no variables) ────────────────────────────────

    def _solve_single(self, inp: OptimizerInput) -> OptimizationResult:
        result = evaluate(inp.mission, constraints=inp.constraints, weights=inp.weights)

        eval_result = CandidateEvaluationResult(
            total=1,
            evaluated=1,
            valid=1 if result.valid else 0,
            invalid=0 if result.valid else 1,
            candidates=[
                CandidateEvaluation(
                    candidate=CandidateConfig(index=0, label="base", values={}),
                    evaluated=True,
                    valid=result.valid,
                    status="VALID" if result.valid else "INVALID",
                    evaluation=result,
                ),
            ],
        )
        selection = CandidateSelection(
            best=CandidateMission(mission=inp.mission, label="base", variable_values={}) if result.valid else None,
            best_score=result.score if result.valid else None,
            alternatives=[],
        )
        explanation = explain(selection, eval_result, constraints=inp.constraints)

        if not result.valid:
            status, message = "NO_SOLUTION", "The base mission is not feasible."
        elif result.warnings:
            status, message = (
                "FEASIBLE",
                ("The base mission passes validation and hard constraints but carries warnings; see explanation."),
            )
        else:
            status, message = "OPTIMAL", "The base mission is feasible with no warnings."

        return OptimizationResult(
            status=status,
            message=message,
            best_candidate=selection.best,
            best_score=selection.best_score,
            alternatives=[],
            evaluations=[result],
            explanation=explanation,
        )


def _best_evaluation(eval_result: CandidateEvaluationResult, best: Optional[CandidateMission]):
    if best is None:
        return None
    for ce in eval_result.candidates:
        if ce.evaluation is not None and ce.evaluation.variable_values == best.variable_values:
            return ce.evaluation
    return None


__all__ = ["Optimizer", "evaluate"]
