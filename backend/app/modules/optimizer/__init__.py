"""Photogrammetry Mission Optimizer — normative base (Fase 10B).

Only the architecture is provided: models, constraints, objective scoring and
the single-candidate evaluation pipeline. Automatic search is Fase 10C.
"""

from .candidate_builder import CandidateBuilder, mission_to_request
from .constraints import evaluate_constraints
from .evaluator import evaluate, evaluate_candidate, evaluate_candidates
from .explanation import explain
from .generator import DEFAULT_MAX_CANDIDATES, CandidateGenerator
from .models import (
    CandidateConfig,
    CandidateEvaluation,
    CandidateEvaluationResult,
    CandidateGenerationResult,
    CandidateMission,
    CandidateSelection,
    ConstraintReport,
    ConstraintStatus,
    EvaluationResult,
    MissionScore,
    OptimizationConstraints,
    OptimizationResult,
    OptimizationWeights,
    OptimizerInput,
)
from .objective import score_mission
from .optimizer import Optimizer
from .selection import select_best
from .variables import (
    OPTIMIZABLE_VARIABLES,
    OptimizationVariable,
    OptimizationVariables,
    VariableMode,
    expand_variable,
    expand_variables,
)

__all__ = [
    "OPTIMIZABLE_VARIABLES",
    "CandidateBuilder",
    "CandidateConfig",
    "CandidateEvaluation",
    "CandidateEvaluationResult",
    "CandidateGenerationResult",
    "CandidateGenerator",
    "CandidateMission",
    "CandidateSelection",
    "ConstraintReport",
    "ConstraintStatus",
    "DEFAULT_MAX_CANDIDATES",
    "EvaluationResult",
    "MissionScore",
    "OptimizationConstraints",
    "OptimizationExplanation",
    "OptimizationResult",
    "OptimizationVariable",
    "OptimizationVariables",
    "OptimizationWeights",
    "Optimizer",
    "OptimizerInput",
    "VariableMode",
    "evaluate",
    "evaluate_candidate",
    "evaluate_candidates",
    "evaluate_constraints",
    "expand_variable",
    "expand_variables",
    "explain",
    "mission_to_request",
    "score_mission",
    "select_best",
]
