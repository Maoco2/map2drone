"""Build the Universal Mission Model from an engine result (Fase 10A + 10B).

The engine responses (``GridResponse`` / ``CorridorResponse``) already carry
the authoritative planning data; this builder copies them into the typed
``UniversalMission`` structure and produces the legacy flat serialization used
for ``Mission.grid_result_json`` (backward compatible with existing blobs).

Fase 10B additionally populates the rich blocks the exporters need: typed
waypoints, flight segments, capture plan, turn plan and the drone/camera
profiles. No formula is computed here — every value is copied from the
engines.
"""

from __future__ import annotations

from typing import Optional

from app.modules.mission.models import (
    CameraProfile,
    CaptureMode,
    CapturePlan,
    DroneDynamicsProvenance,
    DroneFlightDynamicsProfile,
    DroneProfile,
    MissionGeometry,
    MissionMetrics,
    MissionParameters,
    TurnPlan,
    UniversalMission,
    UniversalWaypoint,
)
from app.modules.mission.segments import build_segments
from app.schemas.schemas import CorridorRequest, CorridorResponse, GridRequest, GridResponse, WaypointSchema


def _capture_interval_s(result) -> Optional[float]:
    ci = getattr(result, "capture_interval", None)
    if ci is None:
        return None
    if hasattr(ci, "model_dump"):
        ci = ci.model_dump(mode="json")
    rec = getattr(ci, "recommended_interval_s", None)
    if rec is not None:
        return rec
    if isinstance(ci, dict):
        return ci.get("recommended_interval_s")
    return None


def _capture_mode(result) -> str:
    rec = _capture_interval_s(result)
    return "TIME" if rec is not None else "NONE"


def _turn_mode(req, result) -> str:
    tr = getattr(result, "turn_radius_result", None)
    if isinstance(tr, dict) and tr.get("mode"):
        return tr["mode"]
    return "NONE"


def _turn_radius_m(result) -> Optional[float]:
    tr = getattr(result, "turn_radius_result", None)
    if isinstance(tr, dict):
        return tr.get("radius_m")
    return None


def _capture_plan_from_block(ci) -> Optional[CapturePlan]:
    """Adapt the CaptureInterval block onto the universal CapturePlan."""
    if ci is None:
        return None
    if hasattr(ci, "model_dump"):
        ci = ci.model_dump(mode="json")
    if not isinstance(ci, dict):
        return None
    rec = ci.get("recommended_interval_s")
    ideal = ci.get("ideal_interval_s")
    scientific = ideal if ideal is not None else rec
    return CapturePlan(
        mode=CaptureMode.TIME if rec is not None else CaptureMode.NONE,
        scientific_interval_s=scientific,
        commercial_interval_s=rec,
        photo_spacing_m=ci.get("actual_photo_spacing_m") or ci.get("required_photo_spacing_m"),
        status=ci.get("status") or "NONE",
    )


def _turn_plan_from_result(tr: Optional[dict], dynamics: Optional[DroneFlightDynamicsProfile]) -> Optional[TurnPlan]:
    """Adapt the Turn Radius plan result onto the universal TurnPlan."""
    if not tr:
        return None
    turns = tr.get("turns") or []
    first = turns[0] if turns else {}
    safe_radius = first.get("safe_radius_m")
    available_radius = first.get("available_radius_m")
    ext = first.get("extension_before_m") or first.get("extension_after_m")
    return TurnPlan(
        mode=tr.get("mode") or "NONE",
        status=tr.get("status") or "NONE",
        radius_m=tr.get("radius_m"),
        safe_radius_m=safe_radius,
        available_radius_m=available_radius,
        extension_m=ext,
        a_lat_ms2=dynamics.max_lateral_acceleration_ms2 if dynamics else None,
        safety_factor=1.25,
        turn_duration_s=first.get("turn_duration_s") or None,
        turn_distance_m=first.get("turn_distance_m") or None,
        turn_count=tr.get("turn_count") or len(turns),
        turns=turns,
        warnings=tr.get("warnings") or [],
        geometry=tr.get("geometry"),
    )


def _waypoint_from_engine(wp: WaypointSchema, index: int, speed_ms: float) -> UniversalWaypoint:
    return UniversalWaypoint(
        index=index,
        latitude=wp.latitude,
        longitude=wp.longitude,
        altitude_m=wp.altitude,
        heading_deg=wp.heading,
        speed_mps=speed_ms,
        action_type=wp.action_type,
        action=wp.action_param,
        capture_enabled=(wp.action_type == 1),
        terrain_elevation_m=getattr(wp, "elevation_msnm", None),
        agl_m=getattr(wp, "agl", None),
    )


def _apply_curve_sizes(wps: list[UniversalWaypoint], turn_radius_result: Optional[dict]) -> None:
    if not turn_radius_result:
        return
    pcs = turn_radius_result.get("per_waypoint_curve_size") or {}
    radius = turn_radius_result.get("radius_m") or 0.0
    for wp in wps:
        wp.curve_size_m = radius
    for key in pcs:
        try:
            idx = int(key)
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(wps):
            wps[idx].curve_size_m = float(pcs[key])


def _drone_dynamics_profile(req) -> DroneFlightDynamicsProfile:
    cfg = getattr(req, "turn_radius", None) or {}
    dynamics = cfg.get("drone_dynamics") if isinstance(cfg, dict) else None
    if isinstance(dynamics, dict):
        return DroneFlightDynamicsProfile(
            max_lateral_acceleration_ms2=dynamics.get("max_lateral_acceleration_ms2"),
            preferred_turn_speed_mps=dynamics.get("preferred_turn_speed_ms") or dynamics.get("turn_speed_ms"),
            min_turn_radius_m=dynamics.get("min_turn_radius_m"),
            max_turn_radius_m=dynamics.get("max_turn_radius_m"),
            provenance=DroneDynamicsProvenance(dynamics.get("source", "USER")),
        )
    return DroneFlightDynamicsProfile()  # DEFAULT provenance, no invented data


def _camera_profile(camera) -> Optional[CameraProfile]:
    if camera is None:
        return None
    return CameraProfile(
        id=getattr(camera, "id", None),
        name=getattr(camera, "name", None),
        sensor_width_mm=getattr(camera, "sensor_width_mm", None),
        sensor_height_mm=getattr(camera, "sensor_height_mm", None),
        resolution_width_px=getattr(camera, "image_width_px", None),
        resolution_height_px=getattr(camera, "image_height_px", None),
        focal_length_mm=getattr(camera, "focal_length_mm", None),
        pixel_size_um=getattr(camera, "pixel_size_um", None),
        shutter_type=getattr(camera, "shutter_type", None),
        shutter_speed_s=getattr(camera, "shutter_speed_s", None),
    )


def _drone_profile(drone, req) -> Optional[DroneProfile]:
    if drone is None:
        return None
    return DroneProfile(
        id=getattr(drone, "id", None),
        name=getattr(drone, "name", None),
        manufacturer=getattr(drone, "manufacturer", None),
        weight_kg=getattr(drone, "weight_kg", None),
        max_speed_ms=getattr(drone, "max_speed_ms", None),
        flight_time_min=getattr(drone, "flight_time_min", None),
        max_altitude_m=getattr(drone, "max_altitude_m", None),
        dynamics=_drone_dynamics_profile(req),
    )


def build_universal_mission(
    mission_type: str,
    req: GridRequest | CorridorRequest,
    result: GridResponse | CorridorResponse,
    camera=None,
    drone=None,
) -> UniversalMission:
    """Build the typed mission from a planning request + engine result.

    ``camera`` / ``drone`` are the optional DB profile objects used to populate
    the universal camera/drone profiles; when omitted the profiles are left
    ``None`` and the dynamics provenance stays ``DEFAULT``.
    """
    geometry = None
    if mission_type == "linear_corridor":
        g = result.geometry  # CorridorGeometry
        geometry = MissionGeometry(
            polygon_geojson=g.polygon_geojson if g else None,
            flight_lines_geojson=g.flight_lines_geojson if g else None,
            centerline_geojson=g.centerline_geojson if g else None,
            epsg_out=g.epsg_out if g else 4326,
            crs_name=g.crs_name if g else "WGS84",
            transformation=g.transformation if g else "",
            turn_geometry=result.turn_radius_result.get("geometry") if result.turn_radius_result else None,
            photo_points=getattr(result, "photo_points", []) or [],
        )

    speed_ms = float(getattr(result, "recommended_speed_ms", 0) or 0)
    wps = [_waypoint_from_engine(wp, i, speed_ms) for i, wp in enumerate(result.waypoints)]
    _apply_curve_sizes(wps, result.turn_radius_result)

    ci = result.capture_interval
    capture_interval = ci.model_dump(mode="json") if hasattr(ci, "model_dump") else ci
    capture_plan = _capture_plan_from_block(ci)
    turn_plan = _turn_plan_from_result(result.turn_radius_result, _drone_dynamics_profile(req))

    metrics = MissionMetrics(
        total_distance_m=result.total_distance,
        estimated_time_sec=result.estimated_time_sec,
        battery_count=result.battery_count,
        gsd_cm=result.gsd,
        footprint_width_m=result.footprint_width,
        footprint_height_m=result.footprint_height,
        line_spacing_m=result.line_spacing,
        photo_spacing_m=result.photo_spacing,
        num_lines=result.num_lines,
        photo_count=result.photo_count,
        flight_distance_m=result.total_distance,
        flight_time_s=result.estimated_time_sec,
        straight_flight_time_s=_straight_flight_time(result, turn_plan),
        line_count=result.num_lines,
        waypoint_count=len(wps),
        estimated_energy=None,
    )

    epsg_out = geometry.epsg_out if geometry else 4326
    crs_name = geometry.crs_name if geometry else "WGS84"
    coordinate_reference = f"EPSG:{epsg_out} / {crs_name}" if mission_type == "linear_corridor" else "EPSG:4326 (WGS84)"

    mission = UniversalMission(
        mission_type=mission_type,
        mission_id=getattr(result, "mission_id", None),
        name=getattr(req, "name", None),
        coordinate_reference=coordinate_reference,
        parameters=MissionParameters(
            altitude_m=req.altitude,
            overlap_frontal=req.overlap_frontal,
            overlap_lateral=req.overlap_lateral,
            altitude_mode=req.altitude_mode,
            speed_ms=speed_ms,
            drone_id=req.drone_id,
            camera_id=getattr(req, "camera_id", None),
            capture_interval_s=_capture_interval_s(result),
            sweep_deg=getattr(result, "sweep_deg", None),
            width_left_m=getattr(req, "width_left", None),
            width_right_m=getattr(req, "width_right", None),
            dem_resolution_m=getattr(req, "dem_resolution_m", None),
            altitude_reference=req.altitude_mode,
            recommended_speed_mps=speed_ms,
            gsd_cm=result.gsd,
            footprint_width_m=result.footprint_width,
            footprint_length_m=result.footprint_height,
            overlap_front=req.overlap_frontal,
            overlap_side=req.overlap_lateral,
            line_spacing_m=result.line_spacing,
            photo_spacing_m=result.photo_spacing,
            capture_mode=_capture_mode(result),
            turn_mode=_turn_mode(req, result),
            turn_radius_m=_turn_radius_m(result),
            turn_radius_result=result.turn_radius_result,
            battery_count=result.battery_count,
            flight_time_min=drone.flight_time_min if drone else None,
            estimated_time_s=result.estimated_time_sec,
            total_distance_m=result.total_distance,
            photo_count=result.photo_count,
        ),
        waypoints=wps,
        segments=build_segments(wps, result.turn_radius_result, speed_ms),
        flight_lines_geojson=getattr(result, "flight_lines_geojson", None)
        or (geometry.flight_lines_geojson if geometry else None),
        geometry=geometry,
        photo_points=getattr(result, "photo_points", []) or [],
        metrics=metrics,
        capture_interval=capture_interval,
        capture_plan=capture_plan,
        turn_radius_result=result.turn_radius_result,
        turn_plan=turn_plan,
        turn_radius_warnings=result.turn_radius_warnings or [],
        drone_profile=_drone_profile(drone, req),
        camera_profile=_camera_profile(camera),
        warnings=result.warnings or [],
    )
    return mission


def _straight_flight_time(result, turn_plan: Optional[TurnPlan]) -> float:
    """Straight+transition flight time: total minus real turn time (engine data)."""
    total = float(result.estimated_time_sec or 0.0)
    if turn_plan is None:
        return round(total, 1)
    turn_time = sum(float(t.get("turn_duration_s", 0.0) or 0.0) for t in turn_plan.turns)
    return round(max(0.0, total - turn_time), 1)


def _waypoint_to_legacy(wp: UniversalWaypoint) -> dict:
    return {
        "latitude": wp.latitude,
        "longitude": wp.longitude,
        "altitude": wp.altitude_m,
        "heading": wp.heading_deg if wp.heading_deg is not None else 0,
        "speed": wp.speed_mps,
        "action_type": wp.action_type if wp.action_type is not None else -1,
        "action_param": wp.action if wp.action is not None else 0,
        "elevation_msnm": wp.terrain_elevation_m,
        "agl": wp.agl_m,
    }


def to_legacy_dict(mission: UniversalMission) -> dict:
    """Legacy flat serialization, compatible with ``Mission.grid_result_json``.

    Mirrors the previous ``result.model_dump()`` shape so old frontend loaders
    and old stored missions keep working; new fields (``flight_lines_geojson``,
    ``photo_points``) are simply included. The rich Fase 10B blocks
    (``segments``, ``capture_plan``, ``turn_plan``, profiles) are appended so
    stored missions carry the full universal payload, still readable by old
    loaders that ignore unknown keys.
    """
    m = mission.metrics
    g = mission.geometry
    geometry = None
    if mission.mission_type == "linear_corridor":
        geometry = {
            "polygon_geojson": g.polygon_geojson if g else {},
            "flight_lines_geojson": g.flight_lines_geojson if g else {},
            "centerline_geojson": g.centerline_geojson if g else {},
            "epsg_out": g.epsg_out if g else 4326,
            "crs_name": g.crs_name if g else "WGS84",
            "transformation": g.transformation if g else "",
            "turn_geometry": g.turn_geometry if g else None,
            "photo_points": g.photo_points if g else [],
        }
    return {
        "schema_version": mission.schema_version,
        "mission_type": mission.mission_type,
        "created_at": mission.created_at,
        "mission_id": mission.mission_id,
        "name": mission.name,
        "coordinate_reference": mission.coordinate_reference,
        "waypoints": [_waypoint_to_legacy(wp) for wp in mission.waypoints],
        "segments": [s.model_dump(mode="json") for s in mission.segments],
        "total_distance": m.total_distance_m,
        "estimated_time_sec": m.estimated_time_sec,
        "photo_count": m.photo_count,
        "battery_count": m.battery_count,
        "gsd": m.gsd_cm,
        "footprint_width": m.footprint_width_m,
        "footprint_height": m.footprint_height_m,
        "line_spacing": m.line_spacing_m,
        "photo_spacing": m.photo_spacing_m,
        "recommended_speed_ms": mission.parameters.speed_ms,
        "sweep_deg": mission.parameters.sweep_deg,
        "num_lines": m.num_lines,
        "waypoint_mode": mission.parameters.altitude_mode,
        "warnings": mission.warnings,
        "capture_interval": mission.capture_interval,
        "capture_plan": mission.capture_plan.model_dump(mode="json") if mission.capture_plan else None,
        "turn_radius_result": mission.turn_radius_result,
        "turn_plan": mission.turn_plan.model_dump(mode="json") if mission.turn_plan else None,
        "turn_radius_warnings": mission.turn_radius_warnings,
        "drone_profile": mission.drone_profile.model_dump(mode="json") if mission.drone_profile else None,
        "camera_profile": mission.camera_profile.model_dump(mode="json") if mission.camera_profile else None,
        "flight_lines_geojson": mission.flight_lines_geojson,
        "photo_points": mission.photo_points,
        "geometry": geometry,
        "corridor_length_m": getattr(mission, "corridor_length_m", None),
        "corridor_area_m2": getattr(mission, "corridor_area_m2", None),
        "parameters": mission.parameters.model_dump(mode="json"),
        "metrics": mission.metrics.model_dump(mode="json"),
    }
