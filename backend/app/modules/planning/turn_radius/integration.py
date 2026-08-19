"""Export integration adapter for the turn-radius engine.

The LCHM exporter is NOT modified: it already serialises ``wp.curve_size``
into the record curve-radius field. This adapter computes the mission turn
radius with the engine/planners and writes it into every waypoint's
``curve_size`` before the exporter runs, mirroring the observed behaviour of
the reference mission (Area Grid: uniform radius on all interior waypoints,
exporter forces the first/last waypoints to zero; Linear Corridor: one radius
per interior waypoint where the path turns — waypoints can differ).

Configuration lives in ``options["turn_radius"]``:

.. code-block:: python

    {
        "mode": "AUTO" | "MANUAL" | "NONE",       # default AUTO
        "mission_type": "AREA_GRID" | "LINEAR_CORRIDOR",  # default AREA_GRID
        "speed_ms": 6.8,                          # survey speed (AUTO)
        "line_spacing_m": 51.1,                   # optional; derived from waypoints
        "safety_factor": 1.25,
        "max_lateral_acceleration_ms2": 4.5,
        "min_turn_radius_m": 2.0,
        "max_turn_radius_m": 50.0,
        "turn_clearance_m": 4.0,
        "turn_extension_m": None,
        "manual_radius_m": 12.0,                  # used when mode == MANUAL
        "drone_dynamics": {...},                  # optional DroneFlightDynamics override
    }

``apply_turn_radii`` mutates ``waypoints`` (setting ``curve_size``) and
returns ``(waypoints, plan, warnings)``. With ``NONE`` every waypoint's
``curve_size`` is cleared.

``compute_turn_radius_plan`` is the non-mutating equivalent used by the
planning endpoints: it returns ``(plan, warnings)`` without touching the
waypoints. Both share the same planner logic, so the radius shown in the
planner and the radius serialised into the export always match.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

from app.modules.planning.turn_radius.engine import TurnRadiusEngine
from app.modules.planning.turn_radius.models import (
    DroneFlightDynamics,
    TurnPlanResult,
    TurnRadiusInput,
    TurnRadiusMode,
)
from app.modules.planning.turn_radius.planners import CorridorTurnPlanner, GridTurnPlanner

_TURN_RADIUS_KEY = "turn_radius"


def _build_input(cfg: dict, default_speed: float) -> TurnRadiusInput:
    dynamics = None
    if cfg.get("drone_dynamics"):
        dynamics = DroneFlightDynamics(**cfg["drone_dynamics"])
    return TurnRadiusInput(
        mission_type=cfg.get("mission_type", "AREA_GRID"),
        mode=cfg.get("mode", "AUTO"),
        speed_ms=float(cfg.get("speed_ms") or default_speed),
        turn_speed_ms=cfg.get("turn_speed_ms"),
        line_spacing_m=float(cfg.get("line_spacing_m", 0) or 0),
        safety_factor=float(cfg.get("safety_factor", 1.25)),
        max_lateral_acceleration_ms2=cfg.get("max_lateral_acceleration_ms2"),
        min_turn_radius_m=cfg.get("min_turn_radius_m"),
        max_turn_radius_m=cfg.get("max_turn_radius_m"),
        turn_clearance_m=float(cfg.get("turn_clearance_m", 4.0)),
        turn_extension_m=cfg.get("turn_extension_m"),
        manual_radius_m=cfg.get("manual_radius_m"),
        drone_dynamics=dynamics,
    )


def compute_turn_radius_plan(
    waypoints: list,
    cfg: Optional[dict],
    *,
    mission_type: str = "AREA_GRID",
    line_spacing: float = 0.0,
    recommended_speed: float = 6.8,
    flight_lines_geojson: Optional[dict] = None,
) -> tuple[Optional[TurnPlanResult], list[str]]:
    """Compute a turn-radius plan without mutating ``waypoints``.

    ``cfg`` is the ``options["turn_radius"]`` config dict. With ``NONE`` or an
    empty config the plan is ``None`` (no turns). Linear Corridor is planned
    per waypoint (each interior waypoint where the path changes direction gets
    its own turn/radius); Area Grid plans serpentine U-turns between flight
    lines.
    """
    if not cfg:
        return None, []

    mode = TurnRadiusMode(cfg.get("mode", "AUTO"))
    if mode == TurnRadiusMode.NONE:
        return None, []

    inp = _build_input(cfg, recommended_speed)
    engine = TurnRadiusEngine(dynamics=inp.drone_dynamics)

    if mission_type == "LINEAR_CORRIDOR":
        corridor = SimpleNamespace(
            waypoints=waypoints,
            line_spacing=float(line_spacing or 0),
            recommended_speed_ms=float(recommended_speed or 6.8),
        )
        plan = CorridorTurnPlanner(engine).plan(corridor, inp)
    else:
        plan = GridTurnPlanner(engine).plan_from_waypoints(
            waypoints,
            inp,
            line_spacing=float(line_spacing or 0),
            recommended_speed=recommended_speed or 6.8,
        )
    return plan, plan.warnings


def apply_turn_radii(
    waypoints: list,
    options: Optional[dict] = None,
    default_speed: float = 6.8,
) -> tuple[list, Optional[TurnPlanResult], list[str]]:
    """Apply turn radii to ``waypoints`` (ExportWaypoint objects)."""
    cfg = (options or {}).get(_TURN_RADIUS_KEY) or {}
    if not cfg:
        return waypoints, None, []

    mode = TurnRadiusMode(cfg.get("mode", "AUTO"))
    if mode == TurnRadiusMode.NONE:
        for wp in waypoints:
            wp.curve_size = 0.0
        return waypoints, None, []

    mission_type = cfg.get("mission_type", "AREA_GRID")
    plan, warnings = compute_turn_radius_plan(
        waypoints,
        cfg,
        mission_type=mission_type,
        line_spacing=float(cfg.get("line_spacing_m", 0) or 0),
        recommended_speed=default_speed,
        flight_lines_geojson=cfg.get("flight_lines_geojson"),
    )

    if mission_type == "LINEAR_CORRIDOR" and plan is not None and plan.per_waypoint_curve_size:
        # Per-waypoint radii: each interior waypoint where the path turns gets
        # its own radius; straight-through waypoints are cleared.
        per_wp = plan.per_waypoint_curve_size
        for idx, wp in enumerate(waypoints):
            wp.curve_size = per_wp.get(idx, 0.0)
    else:
        radius_used = plan.radius_m if plan is not None else 0.0
        for wp in waypoints:
            wp.curve_size = radius_used

    return waypoints, plan, warnings
