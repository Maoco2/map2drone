from __future__ import annotations
from typing import Any

from .base import MissionExporter, ExportResult, ValidationResult
from .models import MissionExportData


def _compute_checksum(lines: list[str]) -> int:
    ck = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        for ch in stripped:
            ck ^= ord(ch)
    return ck


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


def _build_waypoints(mission: MissionExportData) -> str:
    lines: list[str] = []
    lines.append("QGC WPL 110")
    is_interval_mode = mission.altitude_mode in ("takeoff", "ground")
    scan_lines = _detect_scan_lines(mission.waypoints) if is_interval_mode else []

    trig_start_indices: set[int] = set()
    trig_stop_indices: set[int] = set()
    for start, end in scan_lines:
        trig_start_indices.add(start)
        trig_stop_indices.add(end)

    seq = 0
    if mission.home:
        lat = mission.home.latitude
        lng = mission.home.longitude
        lines.append(
            f"{seq}\t1\t0\t16\t0\t0\t0\t0\t{mission.altitude:.1f}\t{lat:.7f}\t{lng:.7f}\t1"
        )
        seq += 1

    # Takeoff
    if mission.home:
        lines.append(
            f"{seq}\t0\t3\t22\t0\t0\t0\t0\t{mission.altitude:.1f}\t{mission.home.latitude:.7f}\t{mission.home.longitude:.7f}\t1"
        )
        seq += 1

    for i, wp in enumerate(mission.waypoints):
        # DO_SET_CAM_TRIGG_DIST before scan line entry
        if i in trig_start_indices and mission.photo_spacing > 0:
            lines.append(
                f"{seq}\t0\t3\t206\t{mission.photo_spacing:.1f}\t0\t0\t0\t{wp.altitude:.1f}\t{wp.latitude:.7f}\t{wp.longitude:.7f}\t1"
            )
            seq += 1
        lines.append(
            f"{seq}\t0\t3\t16\t{wp.curve_size:.1f}\t{wp.speed or mission.speed_ms:.1f}\t0\t0\t{wp.altitude:.1f}\t{wp.latitude:.7f}\t{wp.longitude:.7f}\t1"
        )
        seq += 1
        # DO_SET_CAM_TRIGG_DIST=0 after scan line exit
        if i in trig_stop_indices:
            lines.append(
                f"{seq}\t0\t3\t206\t0\t0\t0\t0\t{wp.altitude:.1f}\t{wp.latitude:.7f}\t{wp.longitude:.7f}\t1"
            )
            seq += 1

    # Land
    if mission.waypoints:
        last = mission.waypoints[-1]
        lines.append(
            f"{seq}\t0\t3\t21\t0\t0\t0\t0\t{last.altitude:.1f}\t{last.latitude:.7f}\t{last.longitude:.7f}\t1"
        )
        seq += 1

    raw = "\n".join(lines)
    checksum = _compute_checksum(lines)
    return f"{raw}\n--\n{checksum}\n"


class MissionPlannerExporter(MissionExporter):
    name = "Mission Planner (ArduPilot)"
    extension = ".waypoints"
    version = "1.0"
    description = "Formato waypoints compatible con Mission Planner / ArduPilot"

    def export(self, mission: MissionExportData) -> ExportResult:
        content = _build_waypoints(mission)
        return ExportResult(
            data=content,
            filename=f"{mission.project_name}.waypoints",
            mime_type="text/plain",
        )
