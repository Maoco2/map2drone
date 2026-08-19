"""Optimizer — data models (Fase 10B + 10C).

Only the normative base is defined here: inputs, constraints, weights, scores,
candidates and results. Automatic search is Fase 10C; the candidate-generation
types (:class:`CandidateConfig`, :class:`CandidateGenerationResult`) are the
deterministic bridge between the optimization variables and the evaluation
pipeline. No optimization formula lives in this file.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from app.modules.mission.models import CameraProfile, DroneProfile, UniversalMission
from app.modules.optimizer.variables import OptimizationVariables

#: Default limit for the number of candidates evaluated per search run.
DEFAULT_MAX_CANDIDATES = 1000


class OptimizationConstraints(BaseModel):
    """Constraint box for a candidate mission (Fase 10C-3).

    ``allowed_capture_intervals`` is exporter/platform specific (e.g.
    ``[1, 2, 3, 4, 5, 6]`` for Litchi) and is NOT assumed to apply to every
    platform — when ``None`` no interval restriction is enforced.
    ``preferred_turn_radius`` is a soft target (WARNING when not met); the
    ``min/max`` turn radius fields are hard bounds (FAIL when out of range).
    """

    min_gsd: Optional[float] = None
    max_gsd: Optional[float] = None

    min_overlap_front: Optional[float] = None
    max_overlap_front: Optional[float] = None
    min_overlap_side: Optional[float] = None
    max_overlap_side: Optional[float] = None

    min_altitude: Optional[float] = None
    max_altitude: Optional[float] = None

    min_speed: Optional[float] = None
    max_speed: Optional[float] = None

    max_battery_count: Optional[int] = None
    min_flight_time: Optional[float] = None
    max_flight_time: Optional[float] = None

    min_mission_distance_m: Optional[float] = None
    max_mission_distance_m: Optional[float] = None

    min_photo_interval_s: Optional[float] = None
    max_photo_interval_s: Optional[float] = None

    # Soft preference targets (Fase 10E): when set they become the desired
    # value the continuous scoring is centered on, instead of the band midpoint
    # or the mission's own baseline. None defers to the resolution chain.
    preferred_gsd: Optional[float] = None
    preferred_overlap_front: Optional[float] = None
    preferred_overlap_side: Optional[float] = None

    preferred_turn_radius: Optional[float] = None
    min_turn_radius_m: Optional[float] = None
    max_turn_radius_m: Optional[float] = None
    max_turn_extension_m: Optional[float] = None

    max_photo_count: Optional[int] = None

    allowed_capture_intervals: Optional[list[int]] = None


class ConstraintStatus(str, Enum):
    """Outcome of a single constraint evaluation."""

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class ConstraintReport(BaseModel):
    """Structured constraint evaluation (Fase 10C-3).

    One report per configured constraint: ``limit`` is a dict of the enforced
    bounds (``{"min": ...}`` / ``{"max": ...}`` / both, or a soft ``preferred`` /
    platform ``allowed`` value). A violated constraint is never hidden — it is
    reported with ``status`` ``FAIL`` (hard bound) or ``WARNING`` (soft target
    or not evaluable from the available data).
    """

    constraint: str
    value: Optional[float] = None
    limit: dict = Field(default_factory=dict)
    status: ConstraintStatus
    reason: str


class OptimizationWeights(BaseModel):
    """Scoring weights for :func:`score_mission` (Fase 10C-12).

    Defaults are calibrated deterministically for a photogrammetric survey:
    data quality (gsd, overlap, coverage) and mission safety dominate, then
    operational cost (time, battery), then flight smoothness (turn) and
    processing load (photo_count). Every weight must be ``>= 0`` and at least
    one must be positive (a fully zero weight vector would make
    ``total_score`` undefined). Weights remain overridable per request.
    """

    coverage: float = 1.0
    gsd: float = 1.0
    overlap: float = 1.0
    time: float = 0.8
    battery: float = 0.8
    photo_count: float = 0.5
    turn: float = 0.6
    safety: float = 1.0

    @model_validator(mode="after")
    def _validate_weights(self) -> "OptimizationWeights":
        values = (
            self.coverage,
            self.gsd,
            self.overlap,
            self.time,
            self.battery,
            self.photo_count,
            self.turn,
            self.safety,
        )
        if any(v < 0 for v in values):
            raise ValueError("Optimization weights must be non-negative")
        if all(v == 0 for v in values):
            raise ValueError("At least one optimization weight must be positive")
        return self


class ScoreComponentStatus(str, Enum):
    """Measurement status of a single score component (Fase 10E).

    ``SCORED`` — the component was normalized in ``[0, 1]`` and contributes to
    the weighted total. ``UNKNOWN`` — no preference target/bound is configured
    for it (e.g. no GSD band), so it is excluded from the total until a target
    is provided. ``DATA_REQUIRED`` — the metric cannot be measured from the
    mission data (e.g. coverage needs the projected survey area, which is not
    part of the UMM 1.0 schema), so it is excluded until the data exists.
    """

    SCORED = "SCORED"
    UNKNOWN = "UNKNOWN"
    DATA_REQUIRED = "DATA_REQUIRED"


class ScoreComponentDetail(BaseModel):
    """One row of the scoring breakdown (Fase 10E).

    ``raw_value`` is the measured metric (e.g. GSD in cm/px, flight time in s),
    ``target`` the resolved preference it is compared against, and
    ``normalized_value`` the utility in ``[0, 1]`` (higher is closer to the
    target). ``contribution`` is ``normalized_value * weight`` normalized so
    that the contributions of all SCORED components sum to ``total_score``;
    it is ``None`` for UNKNOWN / DATA_REQUIRED components. ``message`` explains
    why a component is not scored.
    """

    component: str
    label: str
    raw_value: Optional[float] = None
    target: Optional[float] = None
    normalized_value: Optional[float] = None
    weight: float = 0.0
    contribution: Optional[float] = None
    status: ScoreComponentStatus = ScoreComponentStatus.SCORED
    message: Optional[str] = None


class MissionScore(BaseModel):
    """Per-criterion score block for a candidate mission (Fase 10E).

    Each score is in ``[0, 1]`` (higher is better) or ``None`` when it cannot
    be computed from the available data. ``details`` carries the full scoring
    breakdown (raw value, target, normalized value, weight, contribution and
    status per component); the per-criterion fields are the normalized values
    for backwards compatibility, and ``total_score`` is the weighted sum of the
    SCORED components' contributions.
    """

    coverage_score: Optional[float] = None
    gsd_score: Optional[float] = None
    overlap_score: Optional[float] = None
    time_score: Optional[float] = None
    battery_score: Optional[float] = None
    photo_count_score: Optional[float] = None
    turn_score: Optional[float] = None
    safety_score: Optional[float] = None
    total_score: Optional[float] = None
    details: list[ScoreComponentDetail] = Field(default_factory=list)


class OptimizerInput(BaseModel):
    """Everything the optimizer needs to evaluate a mission.

    ``variables`` (Fase 10C-2) declares the optimizable variables; when set,
    ``solve`` searches over their cartesian product. ``max_candidates`` caps
    the search deterministically (see :class:`CandidateGenerator`).
    ``request`` (Fase 10C-9) is the original planning request used to rebuild
    candidate missions — required for grid missions (their polygon is not part
    of the universal mission payload); the API layer always provides it.
    """

    mission: UniversalMission
    request: Optional[Any] = None
    drone_profile: Optional[DroneProfile] = None
    camera_profile: Optional[CameraProfile] = None
    constraints: Optional[OptimizationConstraints] = None
    weights: Optional[OptimizationWeights] = None
    variables: Optional[OptimizationVariables] = None
    max_candidates: int = DEFAULT_MAX_CANDIDATES


class CandidateMission(BaseModel):
    """A candidate mission to be evaluated.

    ``variable_values`` records the deterministic variable assignment that
    produced the mission (Fase 10C-4), so evaluations carry full provenance.
    """

    mission: UniversalMission
    label: str = "candidate"
    variable_values: Optional[dict[str, Any]] = None


class EvaluationResult(BaseModel):
    """Result of evaluating a single candidate (no search)."""

    valid: bool
    status: str = "VALID"
    metrics: dict = Field(default_factory=dict)
    score: Optional[MissionScore] = None
    warnings: list[str] = Field(default_factory=list)
    validation: Optional[dict] = None
    variable_values: Optional[dict[str, Any]] = None


class OptimizationResult(BaseModel):
    """Result of a full optimization run (automatic search is Fase 10C).

    ``best_candidate`` is the highest-scoring valid candidate mission;
    ``alternatives`` are the next best valid candidates (Fase 10C-6/7);
    ``explanation`` (Fase 10C-8) carries the human-readable rationale;
    ``status`` is ``OPTIMAL`` / ``FEASIBLE`` / ``CONSTRAINED`` / ``NO_SOLUTION``.
    """

    status: str = "NOT_IMPLEMENTED"
    message: str = ""
    best_candidate: Optional[CandidateMission] = None
    best_score: Optional[MissionScore] = None
    alternatives: list[CandidateMission] = Field(default_factory=list)
    evaluations: list[EvaluationResult] = Field(default_factory=list)
    explanation: Optional[OptimizationExplanation] = None


class OptimizationExplanation(BaseModel):
    """Human-readable rationale for a selection (Fase 10C-8).

    Everything is derived from the real evaluation data — no hardcoded
    thresholds: ``summary`` condenses why the best was chosen, ``reasons``
    explains the ranking/score/constraints, ``warnings`` carries the best
    mission's warnings, aggregated constraint outcomes and performance/camera
    advisories, and ``stats`` mirrors the batch counts.
    """

    summary: str = ""
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    stats: dict = Field(default_factory=dict)


class CandidateSelection(BaseModel):
    """Best-candidate selection from a batch evaluation (Fase 10C-6/10C-7).

    Only *valid* (evaluated + constraints passed + scoreable) candidates are
    eligible. Ranking is deterministic: score descending, ties broken by
    candidate index (insertion order). ``alternatives`` holds the next best
    candidates after ``best``; a variability criterion (Fase 10C-7) prefers
    alternatives whose variable values differ meaningfully from the best one,
    falling back to top-scoring near-duplicates only to fill the count.
    ``diverse_count`` reports how many alternatives were genuinely different.
    """

    best: Optional[CandidateMission] = None
    best_score: Optional[MissionScore] = None
    alternatives: list[CandidateMission] = Field(default_factory=list)
    diverse_count: int = 0


class CandidateEvaluation(BaseModel):
    """Outcome of evaluating a single candidate configuration (Fase 10C-5).

    A candidate is ``REJECTED`` when it could not be built/evaluated (planning
    or evaluation error); otherwise it is ``evaluated`` and its ``valid`` flag
    reports whether validation + constraints passed. ``reason`` documents
    rejection/errors; valid candidates carry the full ``evaluation``.
    """

    candidate: CandidateConfig
    evaluated: bool = False
    valid: bool = False
    rejected: bool = False
    status: str = "PENDING"  # VALID | INVALID | REJECTED | PENDING
    reason: str = ""
    evaluation: Optional[EvaluationResult] = None


class CandidateEvaluationResult(BaseModel):
    """Batch evaluation report (Fase 10C-5).

    ``evaluated`` counts the candidates that were built and run through the
    evaluation pipeline; ``valid`` / ``invalid`` split that set by the outcome;
    ``rejected`` counts the candidates that could not be built or evaluated
    (planning errors) — they are reported, never silently dropped.
    """

    total: int = 0
    evaluated: int = 0
    valid: int = 0
    invalid: int = 0
    rejected: int = 0
    candidates: list[CandidateEvaluation] = Field(default_factory=list)


# ── Candidate generation (Fase 10C-1) ───────────────────────────────────────


class CandidateConfig(BaseModel):
    """A single candidate configuration (deterministic variable assignment).

    ``values`` maps each optimizable variable to one concrete value. The order
    of ``values`` mirrors the insertion order of the variables at generation
    time (deterministic). ``index`` is the ordinal produced by the generator.
    """

    index: int
    label: str
    values: dict[str, Any] = Field(default_factory=dict)


class CandidateGenerationResult(BaseModel):
    """Deterministic candidate-set report from :class:`CandidateGenerator`.

    ``total_possible`` is the full cartesian product size; ``generated`` is the
    number of candidates actually produced (equal when not truncated).
    ``strategy`` documents the deterministic limiting strategy used when
    ``truncated`` is ``True`` — candidates are never dropped silently.
    """

    variables: list[str] = Field(default_factory=list)
    total_possible: int = 0
    generated: int = 0
    truncated: bool = False
    strategy: str = "full_cartesian"
    candidates: list[CandidateConfig] = Field(default_factory=list)


__all__ = [
    "DEFAULT_MAX_CANDIDATES",
    "CandidateConfig",
    "CandidateEvaluation",
    "CandidateEvaluationResult",
    "CandidateGenerationResult",
    "CandidateMission",
    "CandidateSelection",
    "ConstraintReport",
    "ConstraintStatus",
    "EvaluationResult",
    "MissionScore",
    "OptimizationConstraints",
    "OptimizationExplanation",
    "OptimizationResult",
    "OptimizationWeights",
    "OptimizerInput",
    "ScoreComponentDetail",
    "ScoreComponentStatus",
]
