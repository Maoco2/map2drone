"""Optimizer — continuous preference scoring (Fase 10E).

Separates *feasibility* (the PASS / WARNING / FAIL constraint reports in
``constraints.py``, untouched) from *preference*: each score component is a
continuous utility in ``[0, 1]`` measuring how close the candidate is to the
resolved target, never a binary satisfied/unsatisfied flag.

Resolution chain per component (first match wins):

* GSD:        ``preferred_gsd`` → band midpoint (min+max) → single bound
              (one-sided decay) → UNKNOWN (no target configured).
* Overlap:    per-axis ``preferred_overlap_*`` → band midpoint → single bound
              → the mission's own baseline overlap (the original request) as
              the target. Overlap is therefore always scoreable.
* time/battery/photo_count: require ``max_flight_time`` / ``max_battery_count``
              / ``max_photo_count``; otherwise UNKNOWN.
* turn:       real TurnPlan data (status base × radius-fullness), no physics
              re-run.
* safety:     validator outcome (unchanged).
* coverage:   DATA_REQUIRED — the projected survey area is not part of the UMM
              1.0 schema, so coverage cannot be measured (never invented).

No component is silently dropped: every one appears in ``score.details`` with
its status and a human-readable ``message``.
"""

from __future__ import annotations

from typing import Optional

from app.modules.mission.models import UniversalMission
from app.modules.mission.validator import MissionValidationResult, UniversalMissionValidator
from app.modules.optimizer.models import (
    MissionScore,
    OptimizationConstraints,
    OptimizationWeights,
    ScoreComponentDetail,
    ScoreComponentStatus,
)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _round3(v: Optional[float]) -> Optional[float]:
    return round(v, 3) if v is not None else None


def _score_from_validation(result: MissionValidationResult) -> float:
    n_issues = len(result.errors) + len(result.warnings)
    if n_issues == 0:
        return 1.0
    if result.valid:
        return max(0.0, 1.0 - 0.2 * len(result.warnings))
    return 0.0


def _tent(value: float, target: float, scale: float) -> float:
    """Peak at ``target`` decaying linearly to 0 at ``target ± scale``."""
    return _clamp01(1.0 - abs(value - target) / max(scale, 1e-6))


def _one_sided_high(value: float, limit: float, _scale: Optional[float] = None) -> float:
    """1.0 at/below ``limit``, linear decay beyond it (scale = limit)."""
    if value <= limit:
        return 1.0
    return _clamp01(1.0 - (value - limit) / max(limit, 1e-6))


def _one_sided_low(value: float, limit: float, _scale: Optional[float] = None) -> float:
    """1.0 at/above ``limit``, linear decay below it (scale = limit)."""
    if value >= limit:
        return 1.0
    return _clamp01(1.0 - (limit - value) / max(limit, 1e-6))


def _band_mid(lo: Optional[float], hi: Optional[float]) -> Optional[float]:
    if lo is None or hi is None:
        return None
    return (lo + hi) / 2.0


def _gsd_plan(c: Optional[OptimizationConstraints]) -> Optional[tuple[str, float, float]]:
    """(shape, target, scale) for the GSD utility, or None (no target)."""
    if c is None:
        return None
    band = c.min_gsd is not None and c.max_gsd is not None
    if c.preferred_gsd is not None:
        scale = (c.max_gsd - c.min_gsd) / 2.0 if band else c.preferred_gsd
        return ("tent", c.preferred_gsd, max(scale, 1e-6))
    if band:
        mid = (c.min_gsd + c.max_gsd) / 2.0
        return ("tent", mid, max((c.max_gsd - c.min_gsd) / 2.0, 1e-6))
    if c.max_gsd is not None:
        return ("one_sided_high", c.max_gsd, c.max_gsd)
    if c.min_gsd is not None:
        return ("one_sided_low", c.min_gsd, c.min_gsd)
    return None


def _overlap_axis_plan(c: Optional[OptimizationConstraints], axis: str, baseline: float) -> tuple[str, float, float]:
    """(shape, target, scale) for one overlap axis (front/side)."""
    if c is None:
        return ("tent", baseline, max(baseline, 1e-6))
    pref = c.preferred_overlap_front if axis == "front" else c.preferred_overlap_side
    lo = c.min_overlap_front if axis == "front" else c.min_overlap_side
    hi = c.max_overlap_front if axis == "front" else c.max_overlap_side
    band = lo is not None and hi is not None
    if pref is not None:
        scale = (hi - lo) / 2.0 if band else pref
        return ("tent", pref, max(scale, 1e-6))
    if band:
        return ("tent", (lo + hi) / 2.0, max((hi - lo) / 2.0, 1e-6))
    if hi is not None:
        return ("one_sided_high", hi, hi)
    if lo is not None:
        return ("one_sided_low", lo, lo)
    return ("tent", baseline, max(baseline, 1e-6))


def score_mission(
    mission: UniversalMission,
    constraints: Optional[OptimizationConstraints] = None,
    weights: Optional[OptimizationWeights] = None,
    validation: Optional[MissionValidationResult] = None,
) -> MissionScore:
    """Score a mission in ``[0, 1]`` per component (higher is closer to target).

    Feasibility is out of scope here (see ``evaluator.evaluate`` for the
    constraint fold); this function only expresses preferences.
    """
    w = weights if weights is not None else OptimizationWeights()
    p = mission.parameters
    m = mission.metrics
    c = constraints

    components: list[ScoreComponentDetail] = []

    # ── coverage ────────────────────────────────────────────────────────────
    components.append(
        ScoreComponentDetail(
            component="coverage",
            label="coverage",
            status=ScoreComponentStatus.DATA_REQUIRED,
            weight=w.coverage,
            message=(
                "coverage cannot be measured from the UMM 1.0 mission data — "
                "requires the projected survey area and camera footprint."
            ),
        )
    )

    # ── gsd ─────────────────────────────────────────────────────────────────
    gsd_plan = _gsd_plan(c)
    if gsd_plan is None:
        gsd_score = None
        components.append(
            ScoreComponentDetail(
                component="gsd",
                label="gsd",
                raw_value=_round3(m.gsd_cm),
                status=ScoreComponentStatus.UNKNOWN,
                weight=w.gsd,
                message="no preferred_gsd nor gsd band configured — set a target to score GSD.",
            )
        )
    else:
        shape, target, scale = gsd_plan
        fn = {"tent": _tent, "one_sided_high": _one_sided_high, "one_sided_low": _one_sided_low}[shape]
        gsd_score = fn(m.gsd_cm, target, scale)
        components.append(
            ScoreComponentDetail(
                component="gsd",
                label="gsd",
                raw_value=_round3(m.gsd_cm),
                target=_round3(target),
                normalized_value=_round3(gsd_score),
                weight=w.gsd,
                status=ScoreComponentStatus.SCORED,
            )
        )

    # ── overlap ─────────────────────────────────────────────────────────────
    front_plan = _overlap_axis_plan(c, "front", p.overlap_frontal)
    side_plan = _overlap_axis_plan(c, "side", p.overlap_lateral)
    front_score = _overlap_utility(p.overlap_frontal, front_plan)
    side_score = _overlap_utility(p.overlap_lateral, side_plan)
    overlap_score = min(front_score, side_score)
    # the breakdown reflects the binding axis (the one with the lower utility)
    if front_score <= side_score:
        overlap_raw, overlap_target = p.overlap_frontal, front_plan[1]
    else:
        overlap_raw, overlap_target = p.overlap_lateral, side_plan[1]
    components.append(
        ScoreComponentDetail(
            component="overlap",
            label="overlap",
            raw_value=_round3(overlap_raw),
            target=_round3(overlap_target),
            normalized_value=_round3(overlap_score),
            weight=w.overlap,
            status=ScoreComponentStatus.SCORED,
        )
    )

    # ── time ────────────────────────────────────────────────────────────────
    if c is not None and c.max_flight_time is not None:
        time_score = _clamp01(1.0 - m.flight_time_s / max(c.max_flight_time, 1e-6))
        components.append(
            ScoreComponentDetail(
                component="time",
                label="time",
                raw_value=_round3(m.flight_time_s),
                target=c.max_flight_time,
                normalized_value=_round3(time_score),
                weight=w.time,
                status=ScoreComponentStatus.SCORED,
            )
        )
    else:
        time_score = None
        components.append(
            ScoreComponentDetail(
                component="time",
                label="time",
                raw_value=_round3(m.flight_time_s),
                status=ScoreComponentStatus.UNKNOWN,
                weight=w.time,
                message="max_flight_time not configured — set a flight-time budget to score it.",
            )
        )

    # ── battery ─────────────────────────────────────────────────────────────
    if c is not None and c.max_battery_count is not None:
        battery_score = _clamp01(1.0 - m.battery_count / max(c.max_battery_count, 1e-6))
        components.append(
            ScoreComponentDetail(
                component="battery",
                label="battery",
                raw_value=float(m.battery_count),
                target=float(c.max_battery_count),
                normalized_value=_round3(battery_score),
                weight=w.battery,
                status=ScoreComponentStatus.SCORED,
            )
        )
    else:
        battery_score = None
        components.append(
            ScoreComponentDetail(
                component="battery",
                label="battery",
                raw_value=float(m.battery_count),
                status=ScoreComponentStatus.UNKNOWN,
                weight=w.battery,
                message="max_battery_count not configured — set a battery budget to score it.",
            )
        )

    # ── photo count ─────────────────────────────────────────────────────────
    if c is not None and c.max_photo_count is not None:
        photo_score = _clamp01(1.0 - m.photo_count / max(c.max_photo_count, 1e-6))
        components.append(
            ScoreComponentDetail(
                component="photo_count",
                label="photos",
                raw_value=float(m.photo_count),
                target=float(c.max_photo_count),
                normalized_value=_round3(photo_score),
                weight=w.photo_count,
                status=ScoreComponentStatus.SCORED,
            )
        )
    else:
        photo_score = None
        components.append(
            ScoreComponentDetail(
                component="photo_count",
                label="photos",
                raw_value=float(m.photo_count),
                status=ScoreComponentStatus.UNKNOWN,
                weight=w.photo_count,
                message="max_photo_count not configured — set a photo budget to score it.",
            )
        )

    # ── turn ────────────────────────────────────────────────────────────────
    tp = mission.turn_plan
    if tp is not None:
        base = {"VALID": 1.0, "CONSTRAINED": 0.75, "NONE": 0.5, "INVALID": 0.0}.get(tp.status, 0.5)
        fullness = 1.0
        if tp.radius_m is not None and tp.available_radius_m not in (None, 0.0):
            fullness = min(1.0, tp.radius_m / tp.available_radius_m)
        turn_score = base * (0.5 + 0.5 * fullness)
        components.append(
            ScoreComponentDetail(
                component="turn",
                label="turns",
                raw_value=_round3(tp.radius_m),
                target=_round3(tp.available_radius_m),
                normalized_value=_round3(turn_score),
                weight=w.turn,
                status=ScoreComponentStatus.SCORED,
            )
        )
    elif p.turn_mode != "NONE":
        turn_score = 0.5
        components.append(
            ScoreComponentDetail(
                component="turn",
                label="turns",
                normalized_value=turn_score,
                weight=w.turn,
                status=ScoreComponentStatus.SCORED,
                message="no turn plan — scored at the NONE base.",
            )
        )
    else:
        turn_score = None
        components.append(
            ScoreComponentDetail(
                component="turn",
                label="turns",
                status=ScoreComponentStatus.UNKNOWN,
                weight=w.turn,
                message="turn mode is NONE — no turn plan to score.",
            )
        )

    # ── safety ──────────────────────────────────────────────────────────────
    if validation is None:
        validation = UniversalMissionValidator().validate(mission)
    safety_score = _score_from_validation(validation)
    components.append(
        ScoreComponentDetail(
            component="safety",
            label="safety",
            raw_value=float(len(validation.warnings)),
            target=0.0,
            normalized_value=_round3(safety_score),
            weight=w.safety,
            status=ScoreComponentStatus.SCORED,
        )
    )

    # ── weighted total ──────────────────────────────────────────────────────
    scored = [
        c
        for c in components
        if c.status is ScoreComponentStatus.SCORED and c.normalized_value is not None and c.weight > 0
    ]
    denominator = sum(c.weight for c in scored)
    if denominator > 0:
        total = round(sum(c.normalized_value * c.weight for c in scored) / denominator, 4)
        for c in scored:
            c.contribution = round(c.normalized_value * c.weight / denominator, 4)
    else:
        total = None

    return MissionScore(
        coverage_score=_round3(_normalized(components, "coverage")),
        gsd_score=_round3(_normalized(components, "gsd")),
        overlap_score=_round3(_normalized(components, "overlap")),
        time_score=_round3(_normalized(components, "time")),
        battery_score=_round3(_normalized(components, "battery")),
        photo_count_score=_round3(_normalized(components, "photo_count")),
        turn_score=_round3(_normalized(components, "turn")),
        safety_score=_round3(_normalized(components, "safety")),
        total_score=total,
        details=components,
    )


def _overlap_utility(value: float, plan: tuple[str, float, float]) -> float:
    shape, target, scale = plan
    fn = {"tent": _tent, "one_sided_high": _one_sided_high, "one_sided_low": _one_sided_low}[shape]
    return fn(value, target, scale)


def _normalized(components: list[ScoreComponentDetail], component: str) -> Optional[float]:
    for c in components:
        if c.component == component:
            return c.normalized_value
    return None


__all__ = ["score_mission"]
