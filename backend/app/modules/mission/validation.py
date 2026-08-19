"""Universal Mission Model — validation and backward-compatible reading.

``parse_mission_blob`` reads either the new typed payload (with nested
``parameters`` / ``metrics`` / ``segments`` / plans / profiles) or a legacy
flat blob (the historical ``result.model_dump()`` shape, which has every
metric at the top level), and normalises both into a validated
:class:`UniversalMission`. Old missions persisted before Fase 10A therefore
load without breaking (risk R6), and the Fase 10B rich blocks are read when
present or left at explicit defaults when absent — nothing is reconstructed
by guesswork.
"""

from __future__ import annotations

import json
from typing import Optional, Union

from app.modules.mission.models import (
    SCHEMA_VERSION,
    CameraProfile,
    CapturePlan,
    DroneProfile,
    FlightSegment,
    MissionGeometry,
    MissionMetrics,
    MissionParameters,
    TurnPlan,
    UniversalMission,
    UniversalWaypoint,
    normalize_schema_version,
)


def _as_dict(raw: Union[str, dict]) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Mission payload must be a JSON object")
        return parsed
    raise TypeError("Mission payload must be a string or dict")


def _waypoint_from_any(d: dict, index: int) -> UniversalWaypoint:
    """Build a universal waypoint from a new-format or legacy waypoint dict."""
    action_type = d.get("action_type")
    capture = d.get("capture_enabled")
    if capture is None:
        capture = action_type == 1
    return UniversalWaypoint(
        index=d.get("index", index),
        latitude=d.get("latitude"),
        longitude=d.get("longitude"),
        altitude_m=d.get("altitude_m", d.get("altitude")),
        heading_deg=d.get("heading_deg", d.get("heading")),
        speed_mps=d.get("speed_mps", d.get("speed")),
        action_type=action_type,
        action=d.get("action", d.get("action_param")),
        gimbal_mode=d.get("gimbal_mode"),
        gimbal_pitch_deg=d.get("gimbal_pitch_deg"),
        curve_size_m=d.get("curve_size_m", d.get("curve_size", 0.0)) or 0.0,
        capture_enabled=bool(capture),
        capture_time_interval_s=d.get("capture_time_interval_s"),
        capture_distance_interval_m=d.get("capture_distance_interval_m"),
        photo_index=d.get("photo_index"),
        line_index=d.get("line_index"),
        segment_index=d.get("segment_index"),
        terrain_elevation_m=d.get("terrain_elevation_m", d.get("elevation_msnm")),
        agl_m=d.get("agl_m", d.get("agl")),
    )


def _opt_model(model_cls, data) -> Optional[object]:
    if isinstance(data, dict):
        try:
            return model_cls(**data)
        except (TypeError, ValueError):
            return None
    if isinstance(data, list):
        return None
    return data if isinstance(data, model_cls) else None


def _waypoints_from_any(waypoint_data: list) -> list[UniversalWaypoint]:
    return [_waypoint_from_any(w, i) if isinstance(w, dict) else w for i, w in enumerate(waypoint_data or [])]


def _segments_from_any(seg_data: list) -> list[FlightSegment]:
    segments: list[FlightSegment] = []
    for s in seg_data or []:
        if isinstance(s, FlightSegment):
            segments.append(s)
        elif isinstance(s, dict):
            try:
                segments.append(FlightSegment(**s))
            except (TypeError, ValueError):
                continue
    return segments


def parse_mission_blob(raw: Union[str, dict]) -> UniversalMission:
    """Parse and validate a mission payload (new or legacy) into a UMM."""
    data = _as_dict(raw)

    # --- version guard -----------------------------------------------------
    version = normalize_schema_version(data.get("schema_version", SCHEMA_VERSION))

    # --- parameters ---------------------------------------------------------
    if isinstance(data.get("parameters"), dict):
        params_data = data["parameters"]
    else:
        params_data = {
            "altitude_m": data.get("altitude", 0),
            "overlap_frontal": data.get("overlap_frontal", 0),
            "overlap_lateral": data.get("overlap_lateral", 0),
            "altitude_mode": data.get("waypoint_mode") or data.get("altitude_mode", "takeoff"),
            "speed_ms": data.get("recommended_speed_ms", 0),
            "drone_id": data.get("drone_id"),
            "camera_id": data.get("camera_id"),
            "capture_interval_s": _extract_interval(data.get("capture_interval")),
            "sweep_deg": data.get("sweep_deg"),
            "width_left_m": data.get("width_left"),
            "width_right_m": data.get("width_right"),
            "dem_resolution_m": data.get("dem_resolution_m"),
        }
    parameters = MissionParameters(**params_data)

    # --- metrics ------------------------------------------------------------
    if isinstance(data.get("metrics"), dict):
        metrics_data = {
            **data["metrics"],
            **{
                "total_distance_m": data["metrics"].get("total_distance_m", data.get("total_distance", 0)),
                "estimated_time_sec": data["metrics"].get("estimated_time_sec", data.get("estimated_time_sec", 0)),
                "battery_count": data["metrics"].get("battery_count", data.get("battery_count", 1)),
                "gsd_cm": data["metrics"].get("gsd_cm", data.get("gsd", 0)),
                "footprint_width_m": data["metrics"].get("footprint_width_m", data.get("footprint_width", 0)),
                "footprint_height_m": data["metrics"].get("footprint_height_m", data.get("footprint_height", 0)),
                "line_spacing_m": data["metrics"].get("line_spacing_m", data.get("line_spacing", 0)),
                "photo_spacing_m": data["metrics"].get("photo_spacing_m", data.get("photo_spacing", 0)),
                "num_lines": data["metrics"].get("num_lines", data.get("num_lines", 0)),
                "photo_count": data["metrics"].get("photo_count", data.get("photo_count", 0)),
            },
        }
    else:
        metrics_data = {
            "total_distance_m": data.get("total_distance", 0),
            "estimated_time_sec": data.get("estimated_time_sec", 0),
            "battery_count": data.get("battery_count", 1),
            "gsd_cm": data.get("gsd", 0),
            "footprint_width_m": data.get("footprint_width", 0),
            "footprint_height_m": data.get("footprint_height", 0),
            "line_spacing_m": data.get("line_spacing", 0),
            "photo_spacing_m": data.get("photo_spacing", 0),
            "num_lines": data.get("num_lines", 0),
            "photo_count": data.get("photo_count", 0),
        }
    metrics = MissionMetrics(**metrics_data)

    # --- geometry -----------------------------------------------------------
    geometry = None
    g = data.get("geometry")
    if isinstance(g, dict) and (g.get("polygon_geojson") or g.get("flight_lines_geojson")):
        geometry = MissionGeometry(
            polygon_geojson=g.get("polygon_geojson"),
            flight_lines_geojson=g.get("flight_lines_geojson"),
            centerline_geojson=g.get("centerline_geojson"),
            epsg_out=g.get("epsg_out", 4326),
            crs_name=g.get("crs_name", "WGS84"),
            transformation=g.get("transformation", ""),
            turn_geometry=g.get("turn_geometry"),
            photo_points=g.get("photo_points", []) or [],
        )

    mission_type = data.get("mission_type")
    if mission_type not in ("grid", "linear_corridor"):
        mission_type = "linear_corridor" if geometry else "grid"

    return UniversalMission(
        schema_version=version,
        mission_type=mission_type,
        created_at=data.get("created_at", ""),
        mission_id=data.get("mission_id"),
        name=data.get("name"),
        coordinate_reference=data.get("coordinate_reference", "EPSG:4326 (WGS84)"),
        parameters=parameters,
        waypoints=_waypoints_from_any(data.get("waypoints", [])),
        segments=_segments_from_any(data.get("segments", [])),
        flight_lines_geojson=data.get("flight_lines_geojson") or (geometry.flight_lines_geojson if geometry else None),
        geometry=geometry,
        photo_points=data.get("photo_points", []) or [],
        metrics=metrics,
        capture_interval=data.get("capture_interval"),
        capture_plan=_opt_model(CapturePlan, data.get("capture_plan")),
        turn_radius_result=data.get("turn_radius_result"),
        turn_plan=_opt_model(TurnPlan, data.get("turn_plan")),
        turn_radius_warnings=data.get("turn_radius_warnings", []) or [],
        drone_profile=_opt_model(DroneProfile, data.get("drone_profile")),
        camera_profile=_opt_model(CameraProfile, data.get("camera_profile")),
        warnings=data.get("warnings", []) or [],
    )


def _extract_interval(ci) -> None | int | float:
    if isinstance(ci, dict):
        return ci.get("recommended_interval_s")
    return ci
