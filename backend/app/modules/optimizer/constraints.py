"""Optimizer — constraint evaluation (Fase 10C-3).

Evaluates a candidate :class:`UniversalMission` against an
:class:`OptimizationConstraints` box and produces one structured report per
*configured* constraint:

    constraint | value | limit | status (PASS/WARNING/FAIL) | reason

Every configured constraint appears in the report — a violated constraint is
never hidden. ``FAIL`` means the hard bound is violated (the candidate must be
rejected); ``WARNING`` surfaces soft targets (``preferred_turn_radius``) or
constraints that cannot be evaluated from the available data (reported as not
evaluable instead of silently passing). Constraints are used for scoring AND as
the guard rails the search (Fase 10C) must honour.
"""

from __future__ import annotations

from typing import Optional

from app.modules.mission.models import CaptureMode, UniversalMission
from app.modules.optimizer.models import (
    ConstraintReport,
    ConstraintStatus,
    OptimizationConstraints,
)


def evaluate_constraints(
    constraints: Optional[OptimizationConstraints],
    mission: UniversalMission,
) -> list[ConstraintReport]:
    """Evaluate every configured constraint, returning its structured report."""
    if constraints is None:
        return []
    reports: list[ConstraintReport] = []
    p = mission.parameters
    m = mission.metrics

    _maybe_bound(reports, "altitude_m", p.altitude_m, constraints.min_altitude, constraints.max_altitude, " m")
    _maybe_bound(reports, "gsd_cm", m.gsd_cm, constraints.min_gsd, constraints.max_gsd, " cm")
    _maybe_bound(
        reports, "overlap_frontal", p.overlap_frontal, constraints.min_overlap_front, constraints.max_overlap_front, "%"
    )
    _maybe_bound(
        reports, "overlap_lateral", p.overlap_lateral, constraints.min_overlap_side, constraints.max_overlap_side, "%"
    )
    _maybe_bound(reports, "speed_ms", p.speed_ms, constraints.min_speed, constraints.max_speed, " m/s")

    if constraints.min_photo_interval_s is not None or constraints.max_photo_interval_s is not None:
        _maybe_bound(
            reports,
            "photo_interval_s",
            _photo_interval(mission),
            constraints.min_photo_interval_s,
            constraints.max_photo_interval_s,
            " s",
        )

    if constraints.min_flight_time is not None or constraints.max_flight_time is not None:
        _maybe_bound(
            reports,
            "flight_time_s",
            m.flight_time_s,
            constraints.min_flight_time,
            constraints.max_flight_time,
            " s",
        )

    if constraints.min_mission_distance_m is not None or constraints.max_mission_distance_m is not None:
        _maybe_bound(
            reports,
            "flight_distance_m",
            m.flight_distance_m,
            constraints.min_mission_distance_m,
            constraints.max_mission_distance_m,
            " m",
        )

    if constraints.max_battery_count is not None:
        reports.append(
            _limit_report(
                "battery_count",
                float(m.battery_count),
                constraints.max_battery_count,
                "exceeds the maximum",
                " batteries",
            )
        )
    if constraints.max_photo_count is not None:
        reports.append(
            _limit_report(
                "photo_count",
                float(m.photo_count),
                constraints.max_photo_count,
                "exceeds the maximum",
                " photos",
            )
        )

    radius = m_radius(mission)
    if constraints.min_turn_radius_m is not None or constraints.max_turn_radius_m is not None:
        _maybe_bound(
            reports,
            "turn_radius_m",
            radius,
            constraints.min_turn_radius_m,
            constraints.max_turn_radius_m,
            " m",
        )
    if constraints.preferred_turn_radius is not None:
        if radius is None:
            reports.append(_not_evaluable("turn_radius_m", "no turn radius data available"))
        elif abs(radius - constraints.preferred_turn_radius) <= 1e-6:
            reports.append(
                ConstraintReport(
                    constraint="turn_radius_m",
                    value=radius,
                    limit={"preferred": constraints.preferred_turn_radius},
                    status=ConstraintStatus.PASS,
                    reason="turn radius matches the preferred value.",
                )
            )
        else:
            reports.append(
                ConstraintReport(
                    constraint="turn_radius_m",
                    value=radius,
                    limit={"preferred": constraints.preferred_turn_radius},
                    status=ConstraintStatus.WARNING,
                    reason=f"turn radius {_num(radius)} m differs from the preferred "
                    f"{_num(constraints.preferred_turn_radius)} m.",
                )
            )

    if constraints.max_turn_extension_m is not None:
        ext = mission.turn_plan.extension_m if mission.turn_plan is not None else None
        if ext is None:
            reports.append(_not_evaluable("turn_extension_m", "no turn plan extension data available"))
        else:
            reports.append(
                _limit_report(
                    "turn_extension_m",
                    ext,
                    constraints.max_turn_extension_m,
                    "exceeds the maximum",
                    " m",
                )
            )

    if constraints.allowed_capture_intervals is not None and mission.capture_plan is not None:
        if mission.capture_plan.mode == CaptureMode.TIME:
            commercial = mission.capture_plan.commercial_interval_s
            allowed = sorted(constraints.allowed_capture_intervals)
            if commercial is None:
                reports.append(
                    _not_evaluable(
                        "capture_plan.commercial_interval_s",
                        "no commercial interval available",
                    )
                )
            elif commercial in constraints.allowed_capture_intervals:
                reports.append(
                    ConstraintReport(
                        constraint="capture_plan.commercial_interval_s",
                        value=float(commercial),
                        limit={"allowed": allowed},
                        status=ConstraintStatus.PASS,
                        reason="capture interval is allowed by this platform.",
                    )
                )
            else:
                reports.append(
                    ConstraintReport(
                        constraint="capture_plan.commercial_interval_s",
                        value=float(commercial),
                        limit={"allowed": allowed},
                        status=ConstraintStatus.FAIL,
                        reason=f"capture interval {commercial} s is not allowed by this platform (allowed {allowed}).",
                    )
                )

    return reports


def m_radius(mission: UniversalMission) -> Optional[float]:
    """Uniform mission turn radius (from plan or parameters)."""
    if mission.turn_plan is not None and mission.turn_plan.radius_m is not None:
        return mission.turn_plan.radius_m
    return mission.parameters.turn_radius_m


def _photo_interval(mission: UniversalMission) -> Optional[float]:
    """Scientific capture interval when available, else the configured one."""
    if mission.capture_plan is not None and mission.capture_plan.scientific_interval_s is not None:
        return mission.capture_plan.scientific_interval_s
    return mission.parameters.capture_interval_s


def _maybe_bound(
    reports: list[ConstraintReport],
    constraint: str,
    value: Optional[float],
    lo: Optional[float],
    hi: Optional[float],
    unit: str,
) -> None:
    if lo is None and hi is None:
        return
    if value is None:
        reports.append(_not_evaluable(constraint, f"no {constraint} data available"))
        return
    limit: dict = {}
    if lo is not None:
        limit["min"] = lo
    if hi is not None:
        limit["max"] = hi
    status = ConstraintStatus.PASS
    reason = f"{constraint} {_num(value)}{unit} is within bounds."
    if lo is not None and value < lo:
        status = ConstraintStatus.FAIL
        reason = f"{constraint} {_num(value)}{unit} is below the minimum {_num(lo)}{unit}."
    elif hi is not None and value > hi:
        status = ConstraintStatus.FAIL
        reason = f"{constraint} {_num(value)}{unit} exceeds the maximum {_num(hi)}{unit}."
    reports.append(
        ConstraintReport(
            constraint=constraint,
            value=value,
            limit=limit,
            status=status,
            reason=reason,
        )
    )


def _limit_report(
    constraint: str,
    value: float,
    max_value: float,
    verb: str,
    unit: str,
) -> ConstraintReport:
    if value <= max_value:
        return ConstraintReport(
            constraint=constraint,
            value=value,
            limit={"max": max_value},
            status=ConstraintStatus.PASS,
            reason=f"{constraint} {_num(value)}{unit} is within the maximum {_num(max_value)}{unit}.",
        )
    return ConstraintReport(
        constraint=constraint,
        value=value,
        limit={"max": max_value},
        status=ConstraintStatus.FAIL,
        reason=f"{constraint} {_num(value)}{unit} {verb} {_num(max_value)}{unit}.",
    )


def _not_evaluable(constraint: str, detail: str) -> ConstraintReport:
    return ConstraintReport(
        constraint=constraint,
        value=None,
        limit={},
        status=ConstraintStatus.WARNING,
        reason=f"{constraint} — {detail}.",
    )


def _num(value: float) -> str:
    return f"{value:g}"


__all__ = ["ConstraintReport", "ConstraintStatus", "evaluate_constraints", "m_radius"]
