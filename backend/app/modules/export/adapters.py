"""Export adapter: Universal Mission Model → MissionExportData (Fase 10B).

The exporters do NOT interpret or recalculate a mission: this adapter only
*transforms* a :class:`UniversalMission` into the existing
:class:`MissionExportData` consumed by the exporters (LCHM, CSV, DJI WPML/KMZ,
QGC, MAVLink, KMZ, ...). Every value is read from the Universal Mission —
nothing is recomputed here.

The Litchi-specific ``floor(scientific_interval_s)`` conversion lives here (in
the exporter adapter), NOT in the universal engine.
"""

from __future__ import annotations

import math
from typing import Optional

from app.modules.export.models import CameraInfo, DroneInfo, ExportWaypoint, MissionExportData
from app.modules.mission.models import CaptureMode, UniversalMission


def _commercial_interval(mission: UniversalMission) -> Optional[int]:
    """Operational capture interval for Litchi-class exporters.

    Prefers the engine-produced commercial interval; when only the scientific
    value exists the Litchi adapter applies ``floor(scientific)`` (the
    documented Litchi conversion — the universal engine policy is untouched).
    """
    plan = mission.capture_plan
    if plan is None or plan.mode != CaptureMode.TIME:
        return None
    if plan.commercial_interval_s is not None:
        return plan.commercial_interval_s
    if plan.scientific_interval_s is not None and plan.scientific_interval_s > 0:
        return max(1, int(math.floor(plan.scientific_interval_s)))
    return None


def _photo_capture_options(mission: UniversalMission) -> Optional[dict]:
    plan = mission.capture_plan
    if plan is None:
        return None
    if plan.mode == CaptureMode.TIME:
        interval = _commercial_interval(mission)
        if interval is None:
            return None
        return {"mode": "TIME", "time_interval_s": interval}
    if plan.mode == CaptureMode.DISTANCE:
        if plan.photo_spacing_m is None or plan.photo_spacing_m <= 0:
            return None
        return {"mode": "DISTANCE", "distance_interval_m": plan.photo_spacing_m}
    return None


def from_universal_mission(mission: UniversalMission) -> MissionExportData:
    """Transform a Universal Mission into exporter-ready ``MissionExportData``.

    No GSD / footprint / spacing / speed / interval / radius / distance /
    time / battery / geometry recalculation happens here — the values are
    copied from the Universal Mission only.
    """
    speed = float(mission.parameters.speed_ms or 0) or float(mission.parameters.recommended_speed_mps or 0) or 0.0

    waypoints = [
        ExportWaypoint(
            latitude=wp.latitude,
            longitude=wp.longitude,
            altitude=wp.altitude_m if wp.altitude_m is not None else 0.0,
            heading=wp.heading_deg if wp.heading_deg is not None else 0.0,
            speed=wp.speed_mps if (wp.speed_mps is not None and wp.speed_mps > 0) else (speed or None),
            curve_size=wp.curve_size_m if wp.curve_size_m else 0.0,
            rotation_dir=0,
            gimbal_pitch=wp.gimbal_pitch_deg if wp.gimbal_pitch_deg is not None else -90,
            gimbal_mode=wp.gimbal_mode if wp.gimbal_mode is not None else 2,
            action_type=wp.action_type if wp.action_type is not None else -1,
            action_param=wp.action if wp.action is not None else 0,
            elevation_msnm=wp.terrain_elevation_m,
            agl=wp.agl_m,
        )
        for wp in mission.waypoints
    ]

    drone = None
    dp = mission.drone_profile
    if dp is not None:
        drone = DroneInfo(
            id=dp.id or "",
            name=dp.name or "",
            manufacturer=dp.manufacturer or "",
            max_speed_ms=dp.max_speed_ms or 10.0,
            flight_time_min=dp.flight_time_min or 25.0,
            max_altitude_m=dp.max_altitude_m or 500.0,
        )

    camera = None
    cp = mission.camera_profile
    if cp is not None:
        camera = CameraInfo(
            id=cp.id or "",
            name=cp.name or "",
            focal_length_mm=cp.focal_length_mm or 0.0,
            pixel_size_um=cp.pixel_size_um or 0.0,
            image_width_px=cp.resolution_width_px or 0,
            image_height_px=cp.resolution_height_px or 0,
        )

    options: dict = {}
    if mission.turn_radius_result:
        options["turn_radius_result"] = mission.turn_radius_result
        if mission.turn_radius_warnings:
            options["turn_radius_warnings"] = list(mission.turn_radius_warnings)
    capture = _photo_capture_options(mission)
    if capture is not None:
        options["photo_capture"] = capture
    if any(wp.curve_size_m > 0 for wp in mission.waypoints):
        options["path_mode"] = "CURVED_TURNS"
    else:
        options["path_mode"] = "STRAIGHT"
    options["heading_mode"] = "FOLLOW_PATH"

    altitude_mode = mission.parameters.altitude_mode
    waypoint_mode = {"takeoff": "vertex", "ground": "terrain"}.get(altitude_mode, "photo")

    return MissionExportData(
        project_name=mission.name or "Universal Mission",
        waypoints=waypoints,
        drone=drone,
        camera=camera,
        speed_ms=speed,
        altitude=mission.parameters.altitude_m,
        altitude_mode=altitude_mode,
        waypoint_mode=waypoint_mode,
        total_distance_m=mission.metrics.total_distance_m,
        estimated_time_s=mission.metrics.estimated_time_sec,
        photo_count=mission.metrics.photo_count,
        gsd_cm=mission.metrics.gsd_cm,
        sweep_deg=mission.parameters.sweep_deg or 0.0,
        line_spacing=mission.metrics.line_spacing_m,
        photo_spacing=mission.metrics.photo_spacing_m,
        overlap_frontal=mission.parameters.overlap_frontal,
        overlap_lateral=mission.parameters.overlap_lateral,
        battery_count=mission.metrics.battery_count,
        capture_interval_s=_commercial_interval(mission),
        options=options,
    )


__all__ = ["from_universal_mission"]
