from __future__ import annotations
import json
from typing import Any

from .base import (
    MissionExporter, ExportResult, ValidationResult,
    CompatibilityInfo, CompatibilityCategory, ExportWarning,
    has_multiple_actions, has_gimbal, has_terrain_following, has_heading_per_wp,
)
from .models import MissionExportData


def _detect_scan_lines(waypoints: list) -> list[tuple[int, int]]:
    """Return list of (start_idx, end_idx) for scan line segments in vertex/terrain mode."""
    if len(waypoints) < 2:
        return []
    lines: list[tuple[int, int]] = []
    start = None
    for i in range(len(waypoints) - 1):
        hdg_diff = abs(waypoints[i].heading - waypoints[i + 1].heading) % 360
        if hdg_diff > 180:
            hdg_diff = 360 - hdg_diff
        same_line = hdg_diff <= 45
        if same_line and start is None:
            start = i
        elif not same_line and start is not None:
            lines.append((start, i))
            start = None
    if start is not None:
        lines.append((start, len(waypoints) - 1))
    return lines


def _build_plan(mission: MissionExportData) -> str:
    items: list[dict[str, Any]] = []
    is_interval_mode = mission.altitude_mode in ("takeoff", "ground")
    scan_lines = _detect_scan_lines(mission.waypoints) if is_interval_mode else []

    # Build set of indices where camera trigger should be set
    trig_start_indices: set[int] = set()
    trig_stop_indices: set[int] = set()
    for start, end in scan_lines:
        trig_start_indices.add(start)
        trig_stop_indices.add(end)

    # Takeoff
    if mission.home:
        items.append({
            "autoContinue": True,
            "command": 22,
            "coordinate": [mission.home.longitude, mission.home.latitude, mission.altitude],
            "frame": 3,
            "params": [0, 0, 0, 0, mission.altitude, 0, 0],
            "type": "MissionItem",
        })

    for i, wp in enumerate(mission.waypoints):
        # Insert DO_SET_CAM_TRIGG_DIST before scan line entry
        if i in trig_start_indices and mission.photo_spacing > 0:
            items.append({
                "autoContinue": True,
                "command": 206,
                "coordinate": [wp.longitude, wp.latitude, wp.altitude],
                "frame": 3,
                "params": [mission.photo_spacing, 0, 0, 0, 0, 0, 0],
                "type": "MissionItem",
            })
        items.append({
            "autoContinue": True,
            "command": 16,
            "coordinate": [wp.longitude, wp.latitude, wp.altitude],
            "frame": 3,
            "params": [
                wp.curve_size or 0,
                wp.speed or mission.speed_ms,
                0, 0, wp.heading or 0,
                wp.action_type if wp.action_type > 0 else -1,
                wp.action_param or 0,
            ],
            "type": "MissionItem",
        })
        # Insert DO_SET_CAM_TRIGG_DIST=0 after scan line exit
        if i in trig_stop_indices:
            items.append({
                "autoContinue": True,
                "command": 206,
                "coordinate": [wp.longitude, wp.latitude, wp.altitude],
                "frame": 3,
                "params": [0, 0, 0, 0, 0, 0, 0],
                "type": "MissionItem",
            })

    # Land
    if mission.waypoints:
        last = mission.waypoints[-1]
        items.append({
            "autoContinue": True,
            "command": 21,
            "coordinate": [last.longitude, last.latitude, last.altitude],
            "frame": 3,
            "params": [0, 0, 0, 0, 0, 0, 0],
            "type": "MissionItem",
        })

    plan: dict[str, Any] = {
        "fileType": "Plan",
        "groundStation": "QGroundControl",
        "version": 1,
        "mission": {
            "cruiseSpeed": mission.speed_ms,
            "firmwareType": 12,
            "globalPlanAltitudeMode": 1,
            "hoverSpeed": 5.0,
            "items": items,
            "plannedHomePosition": [
                mission.home.longitude if mission.home else 0,
                mission.home.latitude if mission.home else 0,
                mission.altitude,
            ],
            "vehicleType": 1,
            "version": 2,
        },
        "geoFence": {
            "circles": [],
            "polygons": [],
            "version": 2,
        },
        "rallyPoints": {
            "points": [],
            "version": 2,
        },
    }

    return json.dumps(plan, indent=2)


class QgcExporter(MissionExporter):
    name = "QGroundControl Plan"
    extension = ".plan"
    version = "2.0"
    description = "Plan JSON compatible con QGroundControl"
    compatibility = CompatibilityInfo(
        category=CompatibilityCategory.OFFICIAL,
        description=(
            "El formato .plan está documentado oficialmente por QGroundControl "
            "(proyecto open source). Se importa directamente en QGroundControl. "
            "El comportamiento real depende del firmware del autopiloto (ArduPilot/PX4)."
        ),
    )

    def get_warnings(self, mission: MissionExportData) -> list[ExportWarning]:
        warnings: list[ExportWarning] = []
        if has_gimbal(mission):
            warnings.append(ExportWarning(
                code="gimbal_lost",
                message="El plan QGC no representa pitch/modo de gimbal por waypoint.",
                fields=["gimbal_pitch", "gimbal_mode"],
            ))
        if has_multiple_actions(mission):
            warnings.append(ExportWarning(
                code="actions_approximated",
                message=(
                    "El disparo de cámara se aproxima con DO_SET_CAM_TRIGG_DIST "
                    "al inicio/fin de cada scanline; las acciones exactas por waypoint "
                    "no se transfieren."
                ),
                fields=["actions", "action_type", "action_param"],
            ))
        if has_terrain_following(mission):
            warnings.append(ExportWarning(
                code="terrain_following_lost",
                message="El plan no activa seguimiento de terreno; se exportan alturas fijas.",
                fields=["terrain_following"],
            ))
        if not has_heading_per_wp(mission):
            pass
        return warnings

    def export(self, mission: MissionExportData) -> ExportResult:
        plan = _build_plan(mission)
        return ExportResult(
            data=plan,
            filename=f"{mission.project_name}.plan",
            mime_type="application/json",
        )
