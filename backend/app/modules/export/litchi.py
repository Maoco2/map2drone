from __future__ import annotations
from typing import Sequence

from .base import MissionExporter, ExportResult, ValidationResult, ValidationError
from .models import MissionExportData, ExportWaypoint

CSV_HEADER = (
    "latitude,longitude,altitude(m),heading(deg),curvesize(m),rotationdir,"
    "gimbalmode,gimbalpitchangle,"
    "actiontype1,actionparam1,actiontype2,actionparam2,"
    "actiontype3,actionparam3,actiontype4,actionparam4,"
    "actiontype5,actionparam5,actiontype6,actionparam6,"
    "actiontype7,actionparam7,actiontype8,actionparam8,"
    "actiontype9,actionparam9,actiontype10,actionparam10,"
    "actiontype11,actionparam11,actiontype12,actionparam12,"
    "actiontype13,actionparam13,actiontype14,actionparam14,"
    "actiontype15,actionparam15,"
    "altitudemode,speed(m/s),"
    "poi_latitude,poi_longitude,poi_altitude(m),poi_altitudemode,"
    "photo_timeinterval,photo_distinterval"
)


def _action_pairs(wp: ExportWaypoint) -> list[str]:
    pairs: list[str] = []
    for i in range(1, 16):
        if i == 1:
            pairs.append(str(wp.action_type if wp.action_type is not None else -1))
            pairs.append(str(wp.action_param if wp.action_param is not None else 0))
        else:
            matched = None
            for a in wp.actions:
                idx = wp.actions.index(a) + 2
                if idx == i:
                    matched = a
                    break
            if matched:
                pairs.append(str(matched.action_type))
                pairs.append(str(matched.action_param))
            else:
                pairs.extend(["-1", "0"])
    return pairs


def generate_litchi_csv(
    waypoints: Sequence[ExportWaypoint],
    speed_ms: float = 10.0,
    photo_spacing: float = 0,
    altitude_mode: str = "photo",
) -> str:
    rows = [CSV_HEADER]
    is_interval_mode = altitude_mode in ("takeoff", "ground")
    for i, wp in enumerate(waypoints):
        actions = _action_pairs(wp)
        # Determine photo interval for vertex/terrain mode
        if is_interval_mode and photo_spacing > 0 and i < len(waypoints) - 1:
            nxt = waypoints[i + 1]
            hdg_diff = abs(wp.heading - nxt.heading) % 360
            if hdg_diff > 180:
                hdg_diff = 360 - hdg_diff
            same_line = hdg_diff <= 45
            if same_line:
                dist_interval = round(photo_spacing, 1)
                time_interval = round(photo_spacing / speed_ms, 1) if speed_ms > 0 else -1.0
            else:
                dist_interval = -1.0
                time_interval = -1.0
        else:
            dist_interval = -1.0
            time_interval = -1.0
        row = (
            f"{wp.latitude:.7f},{wp.longitude:.7f},{wp.altitude:.1f},{wp.heading:.1f},"
            f"{wp.curve_size:.1f},{wp.rotation_dir},"
            f"{wp.gimbal_mode},{wp.gimbal_pitch:.0f},"
            f"{','.join(actions)},"
            f"0,{speed_ms:.1f},"
            f"0,0,0,0,"
            f"{time_interval},{dist_interval}"
        )
        rows.append(row)
    return "\n".join(rows)


class LitchiExporter(MissionExporter):
    name = "Litchi CSV"
    extension = ".csv"
    version = "1.0"
    description = "CSV compatible con Litchi Mission Hub"

    def validate(self, mission: MissionExportData) -> ValidationResult:
        errors: list[ValidationError] = []
        is_vertex_mode = mission.altitude_mode in ("takeoff", "ground")
        limit = 240 if is_vertex_mode else 99
        if len(mission.waypoints) > limit:
            errors.append(ValidationError(
                field="waypoints",
                message=f"Litchi soporta máximo {limit} waypoints por misión (se tienen {len(mission.waypoints)})"
            ))
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def export(self, mission: MissionExportData) -> ExportResult:
        csv = generate_litchi_csv(
            mission.waypoints, mission.speed_ms,
            mission.photo_spacing, mission.altitude_mode,
        )
        return ExportResult(
            data=csv,
            filename=f"{mission.project_name}.litchi.csv",
            mime_type="text/csv",
        )
