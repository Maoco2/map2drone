"""Optimizer — candidate mission builder (Fase 10C-4).

Builds a candidate :class:`UniversalMission` from a set of variable values by
orchestrating the existing engines — it never replaces them:

    request (variable values applied)  →  compute_grid / compute_corridor
                                       →  build_universal_mission
                                       →  speed-dependent recomputation
                                          (Planning Core / CaptureInterval /
                                          TurnRadius) for speed_mps

Variable mapping:

* ``altitude_m``      → request ``altitude``
* ``front_overlap``   → request ``overlap_frontal``
* ``side_overlap``    → request ``overlap_lateral``
* ``turn_radius_m``   → request ``turn_radius`` (``"AUTO"`` → AUTO mode,
                        numeric → MANUAL with ``manual_radius_m``)
* ``speed_mps``       → recomputed mission metrics / capture interval /
                        turn-radius plan at that speed (engine functions)
* ``photo_interval_s``→ the candidate's scientific capture interval (decimal,
                        no floor policy — the Litchi conversion stays in the
                        exporter adapter)

Both ``compute_grid`` / ``compute_corridor`` require a SQLAlchemy session
(they resolve the camera/drone from the DB); the builder resolves the camera
from the drone when the request only carries ``drone_id``.
"""

from __future__ import annotations

from typing import Any, Optional

from app.core.photogrammetry.capture_interval import (
    build_capture_interval_block,
    compute_capture_interval,
)
from app.models.schemas import Camera, Drone
from app.modules.corridor.engine import compute_corridor
from app.modules.mission.builder import (
    _apply_curve_sizes,
    _capture_plan_from_block,
    _turn_plan_from_result,
    build_universal_mission,
)
from app.modules.mission.models import MissionMetrics, UniversalMission
from app.modules.mission.segments import build_segments
from app.modules.optimizer.variables import OPTIMIZABLE_VARIABLES
from app.modules.planning.core.metrics import calculate_mission_metrics
from app.modules.planning.engine import compute_grid
from app.modules.planning.turn_radius.integration import compute_turn_radius_plan
from app.schemas.schemas import CorridorRequest, GridRequest


class CandidateBuilder:
    """Deterministic planner-backed builder for optimization candidates.

    Args:
        mission_type: ``"grid"`` or ``"linear_corridor"``.
        base_request: the original planning request (variables are applied on a
            deep copy, the original is never mutated).
        db_session: SQLAlchemy session used by the engines and profile lookups.
    """

    def __init__(self, mission_type: str, base_request: GridRequest | CorridorRequest, db_session) -> None:
        if mission_type not in ("grid", "linear_corridor"):
            raise ValueError(f"Unsupported mission_type {mission_type!r} (expected 'grid' or 'linear_corridor')")
        self.mission_type = mission_type
        self.base_request = base_request
        self.db_session = db_session

    # ── Public API ───────────────────────────────────────────────────────────

    def request_for(self, values: dict[str, Any]) -> GridRequest | CorridorRequest:
        """Copy the base request with the variable values applied."""
        _check_names(values)
        req = self.base_request.model_copy(deep=True)
        if "altitude_m" in values:
            req.altitude = float(values["altitude_m"])
        if "front_overlap" in values:
            req.overlap_frontal = float(values["front_overlap"])
        if "side_overlap" in values:
            req.overlap_lateral = float(values["side_overlap"])
        if "turn_radius_m" in values:
            req.turn_radius = _turn_radius_config(self.base_request.turn_radius, values["turn_radius_m"])
        if not getattr(req, "camera_id", None):
            resolved = _resolve_camera_id(req, self.db_session)
            if resolved is not None:
                req.camera_id = resolved
        return req

    def build(self, values: dict[str, Any]) -> UniversalMission:
        """Build the candidate mission for the given variable values."""
        req = self.request_for(values)
        camera, drone = _fetch_profiles(req, self.db_session)
        if self.mission_type == "linear_corridor":
            result = compute_corridor(req, self.db_session)
        else:
            result = compute_grid(req, self.db_session)
        mission = build_universal_mission(self.mission_type, req, result, camera=camera, drone=drone)
        speed = values.get("speed_mps")
        if speed is not None and float(speed) > 0:
            _apply_speed(mission, values, req, float(speed))
        if "photo_interval_s" in values:
            _override_photo_interval(mission, float(values["photo_interval_s"]))
        return mission


def mission_to_request(mission: UniversalMission) -> GridRequest | CorridorRequest:
    """Rebuild a planning request from a built mission (Fase 10C-9).

    The optimizer's ``solve`` only receives a :class:`UniversalMission` (the
    base mission), so the candidate search rebuilds the request from the
    mission's own authoritative parameters/geometry. The turn-radius config is
    reconstructed from ``turn_mode`` / ``turn_radius_m``.
    """
    p = mission.parameters
    geo = mission.geometry
    turn_radius = _turn_config_from_parameters(p)
    common = dict(
        altitude=p.altitude_m,
        overlap_frontal=p.overlap_frontal,
        overlap_lateral=p.overlap_lateral,
        camera_id=p.camera_id,
        drone_id=p.drone_id,
        altitude_mode=p.altitude_mode,
        dem_resolution_m=p.dem_resolution_m,
        turn_radius=turn_radius,
    )
    if mission.mission_type == "linear_corridor":
        if geo is None or geo.centerline_geojson is None:
            raise ValueError("linear_corridor mission has no centerline geometry; cannot rebuild the request")
        if not p.width_left_m or not p.width_right_m:
            raise ValueError(
                "linear_corridor mission is missing width_left_m/width_right_m; cannot rebuild the request"
            )
        return CorridorRequest(
            centerline=geo.centerline_geojson,
            width_left=p.width_left_m,
            width_right=p.width_right_m,
            **common,
        )
    if geo is None or geo.polygon_geojson is None:
        raise ValueError("grid mission has no polygon geometry; cannot rebuild the request")
    return GridRequest(
        polygon=geo.polygon_geojson,
        sweep_deg=p.sweep_deg,
        **common,
    )


def _turn_config_from_parameters(p) -> Optional[dict]:
    """Reconstruct a request turn-radius config from mission parameters."""
    if p.turn_mode in ("MANUAL", "AUTO"):
        cfg = {"mode": p.turn_mode}
        if p.turn_mode == "MANUAL" and p.turn_radius_m is not None:
            cfg["manual_radius_m"] = p.turn_radius_m
        return cfg
    return None


# ── Variable application ─────────────────────────────────────────────────────


def _check_names(values: dict[str, Any]) -> None:
    for name in values:
        if name not in OPTIMIZABLE_VARIABLES:
            raise ValueError(f"Unknown optimizable variable {name!r} (allowed: {', '.join(OPTIMIZABLE_VARIABLES)})")


def _turn_radius_config(base_cfg: Optional[dict], value: Any) -> dict:
    """Translate the turn_radius_m variable onto a turn-radius config dict."""
    base = dict(base_cfg) if base_cfg else {}
    if value == "AUTO":
        cfg = {k: v for k, v in base.items() if k != "manual_radius_m"}
        cfg["mode"] = "AUTO"
    else:
        cfg = dict(base)
        cfg["mode"] = "MANUAL"
        cfg["manual_radius_m"] = float(value)
    return cfg


def _resolve_camera_id(req, db_session) -> Optional[str]:
    if getattr(req, "camera_id", None):
        return req.camera_id
    if getattr(req, "drone_id", None):
        drone = db_session.query(Drone).filter(Drone.id == req.drone_id).first()
        if drone is not None and drone.camera_id:
            return drone.camera_id
    return None


def _fetch_profiles(req, db_session) -> tuple[Optional[Camera], Optional[Drone]]:
    camera = None
    if getattr(req, "camera_id", None):
        camera = db_session.query(Camera).filter(Camera.id == req.camera_id).first()
    drone = None
    if getattr(req, "drone_id", None):
        drone = db_session.query(Drone).filter(Drone.id == req.drone_id).first()
    return camera, drone


# ── Speed-dependent recomputation (engine orchestration) ────────────────────


def _apply_speed(mission: UniversalMission, values: dict[str, Any], req, speed: float) -> None:
    """Recompute the speed-dependent engine outputs at the chosen speed.

    Altitude / overlaps / turn radius are already applied through the request
    (geometry, GSD, spacing, waypoints, photo points all come from the engines).
    ``speed_mps`` cannot be injected into the planners (the request carries no
    speed field), so the candidate's speed is applied by recomputing the
    Planning Core metrics, the CaptureInterval recommendation and the TurnRadius
    plan at that speed — using the same engine functions the planners use.
    """
    turn_plan_result = _recompute_turn_plan(mission, req, speed)
    _recompute_metrics(mission, req, speed, turn_plan_result)
    _recompute_capture_interval(mission, req, speed)

    mission.parameters.speed_ms = speed
    mission.parameters.recommended_speed_mps = speed
    for wp in mission.waypoints:
        if wp.speed_mps is not None:
            wp.speed_mps = speed


def _recompute_turn_plan(mission: UniversalMission, req, speed: float):
    """Recompute the turn-radius plan at the chosen speed (engine function)."""
    turn_cfg = getattr(req, "turn_radius", None)
    if not turn_cfg or not mission.waypoints:
        return None
    planner_type = "LINEAR_CORRIDOR" if mission.mission_type == "linear_corridor" else "AREA_GRID"
    flight_lines_geojson = None
    if planner_type == "LINEAR_CORRIDOR" and mission.geometry is not None:
        flight_lines_geojson = mission.geometry.flight_lines_geojson
    plan, warnings = compute_turn_radius_plan(
        _engine_waypoints(mission.waypoints),
        turn_cfg,
        mission_type=planner_type,
        line_spacing=mission.metrics.line_spacing_m,
        recommended_speed=speed,
        flight_lines_geojson=flight_lines_geojson,
    )
    dynamics = mission.drone_profile.dynamics if mission.drone_profile is not None else None
    mission.turn_radius_result = plan.model_dump(mode="json") if plan is not None else None
    mission.turn_plan = _turn_plan_from_result(mission.turn_radius_result, dynamics)
    mission.turn_radius_warnings = warnings
    _apply_curve_sizes(mission.waypoints, mission.turn_radius_result)
    mission.segments = build_segments(mission.waypoints, mission.turn_radius_result, speed)
    return plan


def _engine_waypoints(waypoints):
    """Adapt universal waypoints to the engine WaypointSchema shape.

    The TurnRadius planners read ``longitude / latitude / heading``; the
    universal waypoint carries the same data under ``heading_deg``.
    """
    from app.schemas.schemas import WaypointSchema

    return [
        WaypointSchema(
            latitude=wp.latitude,
            longitude=wp.longitude,
            altitude=wp.altitude_m or 0.0,
            heading=wp.heading_deg or 0.0,
            action_type=wp.action_type,
            action_param=wp.action,
            elevation_msnm=wp.terrain_elevation_m,
            agl=wp.agl_m,
        )
        for wp in waypoints
    ]


def _recompute_metrics(mission: UniversalMission, req, speed: float, turn_plan_result) -> None:
    """Recompute Planning Core metrics at the chosen speed."""
    wps_geo_heading = [(wp.longitude, wp.latitude, wp.heading_deg or 0.0) for wp in mission.waypoints]
    if not wps_geo_heading:
        return
    drone_flight_time_min = mission.drone_profile.flight_time_min if mission.drone_profile is not None else None
    core = calculate_mission_metrics(
        wps_geo_heading,
        speed_mps=speed,
        num_lines=mission.metrics.line_count or mission.metrics.num_lines,
        turn_plan=turn_plan_result,
        drone_flight_time_min=drone_flight_time_min,
    )
    mission.metrics = MissionMetrics(
        total_distance_m=core.total_distance_m,
        estimated_time_sec=core.total_time_s,
        straight_distance_m=core.straight_distance_m,
        transition_distance_m=core.transition_distance_m,
        turn_distance_m=core.turn_distance_m,
        straight_time_s=core.straight_time_s,
        transition_time_s=core.transition_time_s,
        turn_time_s=core.turn_time_s,
        turn_source=core.turn_source,
        battery_count=core.battery_count,
        gsd_cm=mission.metrics.gsd_cm,
        footprint_width_m=mission.metrics.footprint_width_m,
        footprint_height_m=mission.metrics.footprint_height_m,
        line_spacing_m=mission.metrics.line_spacing_m,
        photo_spacing_m=mission.metrics.photo_spacing_m,
        num_lines=mission.metrics.num_lines,
        photo_count=mission.metrics.photo_count,
        flight_distance_m=core.total_distance_m,
        flight_time_s=core.total_time_s,
        straight_flight_time_s=round(core.straight_time_s + core.transition_time_s, 1),
        line_count=mission.metrics.line_count,
        waypoint_count=mission.metrics.waypoint_count,
        estimated_energy=mission.metrics.estimated_energy,
    )
    mission.parameters.estimated_time_s = mission.metrics.estimated_time_sec
    mission.parameters.total_distance_m = mission.metrics.total_distance_m
    mission.parameters.battery_count = mission.metrics.battery_count


def _recompute_capture_interval(mission: UniversalMission, req, speed: float) -> None:
    """Recompute the CaptureInterval recommendation at the chosen speed."""
    old_block = mission.capture_interval if isinstance(mission.capture_interval, dict) else {}
    assumed_footprint = old_block.get("assumed_footprint_length_m")
    footprint = float(assumed_footprint or mission.metrics.footprint_height_m or 0.0)
    if footprint <= 0:
        return
    ci = compute_capture_interval(
        footprint_length_m=footprint,
        front_overlap=req.overlap_frontal,
        flight_speed_mps=speed,
    )
    block = build_capture_interval_block(
        ci,
        planned_agl_m=old_block.get("planned_agl_m", req.altitude),
        terrain_follow=old_block.get("terrain_follow", False),
        assumed_agl_m=old_block.get("assumed_agl_m", req.altitude),
        assumed_footprint_length_m=old_block.get("assumed_footprint_length_m", footprint),
    )
    mission.capture_interval = block.model_dump(mode="json")
    mission.capture_plan = _capture_plan_from_block(mission.capture_interval)


def _override_photo_interval(mission: UniversalMission, interval: float) -> None:
    """Apply the candidate's scientific capture interval (no floor policy)."""
    if mission.capture_plan is not None:
        mission.capture_plan.scientific_interval_s = interval
    mission.parameters.capture_interval_s = interval
    ci = mission.capture_interval
    if isinstance(ci, dict) and ci.get("ideal_interval_s") is not None:
        ci["ideal_interval_s"] = round(interval, 3)


__all__ = ["CandidateBuilder", "mission_to_request"]
