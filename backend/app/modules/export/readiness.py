"""Export readiness diagnostic for a Universal Mission (Fase 10F-8).

The readiness check uses the real exporters: it transforms the Universal
Mission through :func:`from_universal_mission` (the same adapter the export
path uses) and runs the exporter's ``validate`` / ``get_warnings`` — nothing is
recomputed or invented here.

Status semantics:

* ``READY``   — the exporter can serialize the mission with no warnings.
* ``WARNING`` — serializable, but carries caveats (exporter warnings or a
  constrained turn-radius plan that still produces a file).
* ``BLOCKED`` — the exporter refuses to serialize (validation errors, e.g.
  LCHM over its 99-waypoint capacity) or the mission has an INVALID
  turn-radius plan (flying it with the configured turns is not possible).

Structured codes include ``split_required`` (waypoint capacity),
``turn_radius_invalid`` (plan INVALID) and ``turn_radius_warning`` (plan
CONSTRAINED / mission turn warnings). The exporter remains the authority for
the final validation — this diagnostic mirrors it, it never relaxes it.
"""

from __future__ import annotations

import re

from app.modules.export.adapters import from_universal_mission
from app.modules.export.factory import get_exporter

_STATUS_READY = "READY"
_STATUS_WARNING = "WARNING"
_STATUS_BLOCKED = "BLOCKED"

_WAYPOINT_LIMIT_RE = re.compile(r"99\s*waypoints", re.IGNORECASE)


def _validation_code(message: str) -> str:
    if _WAYPOINT_LIMIT_RE.search(message):
        return "split_required"
    return "validation"


def check_mission_readiness(mission, fmt: str) -> dict:
    """Return the readiness diagnostic for one exporter as a JSON-ready dict."""
    exporter = get_exporter(fmt)
    export_data = from_universal_mission(mission)
    validation = exporter.validate(export_data)
    warnings = exporter.get_warnings(export_data)

    reasons: list[str] = []
    codes: list[str] = []

    status = _STATUS_READY
    if not validation.valid:
        for err in validation.errors:
            reasons.append(err.message)
            code = _validation_code(err.message)
            if code not in codes:
                codes.append(code)
        status = _STATUS_BLOCKED

    for w in warnings:
        reasons.append(w.message)
        if w.code not in codes:
            codes.append(w.code)
        if status == _STATUS_READY:
            status = _STATUS_WARNING

    turn_plan = mission.turn_plan
    if turn_plan is not None and turn_plan.status == "INVALID":
        status = _STATUS_BLOCKED
        if "turn_radius_invalid" not in codes:
            codes.append("turn_radius_invalid")
            reasons.append("Turn-radius plan is INVALID — the mission cannot be flown with the configured turns.")

    turn_warnings = mission.turn_radius_warnings or []
    if turn_warnings:
        for tw in turn_warnings:
            if tw not in reasons:
                reasons.append(f"Turn radius: {tw}")
            if "turn_radius_warning" not in codes:
                codes.append("turn_radius_warning")
            if status == _STATUS_READY:
                status = _STATUS_WARNING

    return {
        "id": fmt,
        "name": exporter.name,
        "extension": exporter.extension,
        "status": status,
        "reasons": reasons,
        "codes": codes,
        "compatibility": exporter.compatibility.model_dump(mode="json") if exporter.compatibility is not None else None,
        "warnings": [w.model_dump(mode="json") for w in warnings],
    }


__all__ = ["check_mission_readiness"]
