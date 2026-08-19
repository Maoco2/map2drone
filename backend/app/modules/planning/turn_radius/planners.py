"""Turn-radius planners for Area Grid and Linear Corridor.

The Area Grid planner reconstructs the flight lines and calls
``TurnRadiusEngine.plan_turn`` once per transition between consecutive lines
(serpentine U-turns).

The Linear Corridor planner works per waypoint: every interior waypoint where
the path changes direction (the incoming and outgoing segment headings differ
by more than ``HEADING_TOLERANCE_DEG``) gets its own turn with its own angle
and radius. A corridor with a single winding line therefore produces one turn
per vertex, and each waypoint's radius can differ.

Geometry is always projected (UTM, chosen from the centroid) so line
separation, radii and turn points are metric.
"""

from __future__ import annotations

from typing import Optional, Sequence

from shapely.geometry import LineString

from app.modules.planning.turn_radius.engine import TurnRadiusEngine
from app.modules.planning.turn_radius.geometry import (
    heading_degrees,
    make_transformer,
    right_normal,
    signed_turn_angle,
    turn_direction_for,
    utm_epsg_for,
)
from app.modules.planning.turn_radius.models import (
    MissionType,
    TurnGeometryResult,
    TurnPlanResult,
    TurnRadiusInput,
    TurnRadiusMode,
    TurnStatus,
)

HEADING_TOLERANCE_DEG = 1.5


def _cyclic_heading_diff(a: float, b: float) -> float:
    return (b - a + 540.0) % 360.0 - 180.0


def _resolved_input(
    user_inp: Optional[TurnRadiusInput],
    *,
    mission_type: MissionType,
    speed_default: float,
    spacing: float,
    turn_angle: float,
) -> TurnRadiusInput:
    """Build a working input, filling AUTO values the planner can derive."""
    if user_inp is None:
        base = TurnRadiusInput(speed_ms=max(speed_default, 0.01))
    else:
        base = user_inp
    updates: dict = {"mission_type": mission_type}
    if base.line_spacing_m <= 0 and spacing > 0:
        updates["line_spacing_m"] = spacing
    if base.turn_angle_deg is None and turn_angle > 0:
        updates["turn_angle_deg"] = turn_angle
    return base.model_copy(update=updates)


def reconstruct_lines_from_waypoints(waypoints: Sequence) -> tuple[list[LineString], list[float], int, str, dict]:
    """Reconstruct straight flight lines from a waypoint sequence.

    Consecutive waypoints whose heading differs by less than
    ``HEADING_TOLERANCE_DEG`` belong to the same flight line. Returns
    ``(lines_projected, traversal_headings, epsg, crs_name, group_indices)``
    where ``group_indices[i]`` lists the global waypoint indices of line ``i``.

    Works with any objects exposing ``longitude``, ``latitude`` and
    ``heading`` attributes (``WaypointSchema``, ``ExportWaypoint``, ...).
    """
    if not waypoints:
        return [], [], 4326, "WGS84", {}

    epsg = utm_epsg_for(waypoints[0].longitude, waypoints[0].latitude)
    transformer = make_transformer(4326, epsg)
    zone = epsg - 32600 if epsg < 32700 else epsg - 32700
    crs_name = f"WGS 84 / UTM zone {zone}"

    groups: list[list[int]] = []
    for idx, wp in enumerate(waypoints):
        h = wp.heading % 360.0
        if groups:
            last_idx = groups[-1][-1]
            last_h = waypoints[last_idx].heading % 360.0
            if abs(_cyclic_heading_diff(last_h, h)) < HEADING_TOLERANCE_DEG:
                groups[-1].append(idx)
                continue
        groups.append([idx])

    lines: list[LineString] = []
    headings: list[float] = []
    for group in groups:
        first = waypoints[group[0]]
        last = waypoints[group[-1]]
        p0 = transformer.transform(first.longitude, first.latitude)
        p1 = transformer.transform(last.longitude, last.latitude)
        lines.append(LineString([p0, p1]))
        headings.append(sum(waypoints[i].heading for i in group) / len(group))

    group_indices: dict = {i: g for i, g in enumerate(groups)}
    return lines, headings, epsg, crs_name, group_indices


def _line_spacing_from(lines: list[LineString]) -> float:
    """Tightest consecutive spacing — the conservative constraint for turns."""
    if len(lines) < 2:
        return 0.0
    return min(lines[i].distance(lines[i + 1]) for i in range(len(lines) - 1))


def _mission_geometry(turns: list[TurnGeometryResult]) -> dict:
    """Merge every turn's GeoJSON into one mission-level FeatureCollection.

    Each feature is tagged with ``properties.turn`` (0-based turn index) and
    carries ``kind`` (turn_arc / turn_center / clearance_buffer) already set
    by the engine, so the frontend can style the mission geometry directly
    without re-computing anything.
    """
    features: list[dict] = []
    for i, t in enumerate(turns):
        fc = t.geometry or {}
        for feat in fc.get("features", []):
            f = dict(feat)
            props = dict(f.get("properties", {}))
            props["turn"] = i
            f["properties"] = props
            features.append(f)
    return {"type": "FeatureCollection", "features": features}


def _plan_transitions(
    engine: TurnRadiusEngine,
    lines: list[LineString],
    headings: list[float],
    inp: TurnRadiusInput,
    epsg: int,
    crs_name: str,
) -> list[TurnGeometryResult]:
    turns: list[TurnGeometryResult] = []
    for i in range(len(lines) - 1):
        exit_pt = lines[i].coords[-1]
        entry_pt = lines[i + 1].coords[0]
        h_in = headings[i] % 360.0
        h_out = headings[i + 1] % 360.0
        angle = abs(signed_turn_angle(h_in, h_out))
        angle = angle if angle > 1e-6 else 180.0
        vx = entry_pt[0] - exit_pt[0]
        vy = entry_pt[1] - exit_pt[1]
        rx, ry = right_normal(h_in)
        direction = "RIGHT" if (vx * rx + vy * ry) >= 0 else "LEFT"
        turns.append(engine.plan_turn(exit_pt, h_in, h_out, angle, direction, inp, epsg=epsg, crs_name=crs_name))
    return turns


class GridTurnPlanner:
    """Plans turn radii for an Area Grid mission (serpentine U-turns)."""

    def __init__(self, engine: Optional[TurnRadiusEngine] = None) -> None:
        self.engine = engine or TurnRadiusEngine()

    def plan(self, grid, inp: Optional[TurnRadiusInput] = None) -> TurnPlanResult:
        return self.plan_from_waypoints(
            grid.waypoints,
            inp,
            line_spacing=float(getattr(grid, "line_spacing", 0) or 0),
            recommended_speed=float(getattr(grid, "recommended_speed_ms", 0) or 0),
        )

    def plan_from_waypoints(
        self,
        waypoints: Sequence,
        inp: Optional[TurnRadiusInput] = None,
        line_spacing: float = 0.0,
        recommended_speed: float = 0.0,
    ) -> TurnPlanResult:
        lines, headings, epsg, crs_name, group_indices = reconstruct_lines_from_waypoints(waypoints)
        spacing = line_spacing if line_spacing > 0 else _line_spacing_from(lines)
        work = _resolved_input(
            inp,
            mission_type=MissionType.AREA_GRID,
            speed_default=recommended_speed or 6.8,
            spacing=spacing,
            turn_angle=180.0,
        )
        turns = _plan_transitions(self.engine, lines, headings, work, epsg, crs_name)

        per_wp: dict[int, float] = {}
        for i in range(len(turns)):
            last_idx = group_indices.get(i, [])[-1] if group_indices.get(i) else None
            if last_idx is not None:
                per_wp[last_idx] = turns[i].radius_m

        return self._assemble(work, MissionType.AREA_GRID, turns, per_wp, epsg, crs_name)

    @staticmethod
    def _assemble(
        inp: TurnRadiusInput,
        mission_type: MissionType,
        turns: list[TurnGeometryResult],
        per_wp: dict,
        epsg: int,
        crs_name: str,
    ) -> TurnPlanResult:
        if not turns:
            return TurnPlanResult(
                mission_type=mission_type.value,
                mode=inp.mode.value,
                status=TurnStatus.NONE.value,
                radius_m=0.0,
                epsg=epsg,
                crs_name=crs_name,
                geometry=_mission_geometry(turns),
                explanation="No turns to plan: the path has no direction changes.",
            )

        radius = 0.0
        valid_radii = [t.radius_m for t in turns if t.status != TurnStatus.INVALID.value and t.radius_m > 0]
        if valid_radii:
            radius = min(valid_radii)
        statuses = {t.status for t in turns}
        if TurnStatus.CONSTRAINED.value in statuses:
            status = TurnStatus.CONSTRAINED.value
        elif TurnStatus.INVALID.value in statuses:
            status = TurnStatus.INVALID.value
        else:
            status = TurnStatus.VALID.value

        warnings: list[str] = []
        seen: set[str] = set()
        for t in turns:
            for w in t.warnings:
                if w not in seen:
                    seen.add(w)
                    warnings.append(w)

        return TurnPlanResult(
            mission_type=mission_type.value,
            mode=inp.mode.value,
            status=status,
            radius_m=radius,
            turn_count=len(turns),
            turns=turns,
            per_waypoint_curve_size=per_wp,
            warnings=warnings,
            explanation=(f"Mission turn radius {radius:.2f} m (minimum across {len(turns)} turns)."),
            geometry=_mission_geometry(turns),
            epsg=epsg,
            crs_name=crs_name,
        )


class CorridorTurnPlanner:
    """Plans turn radii for a Linear Corridor mission.

    Works directly from the corridor waypoints: for every interior waypoint the
    incoming heading (segment i-1→i) is compared with the outgoing heading
    (segment i→i+1). Where the path changes direction a turn is planned at that
    waypoint, so a single-line corridor with bends produces one turn per
    vertex, each with its own angle (and therefore its own radius).
    """

    def __init__(self, engine: Optional[TurnRadiusEngine] = None) -> None:
        self.engine = engine or TurnRadiusEngine()

    def plan(self, corridor, inp: Optional[TurnRadiusInput] = None) -> TurnPlanResult:
        waypoints = corridor.waypoints
        if not waypoints:
            return self._empty(corridor, inp, "Corridor response has no waypoints.")

        epsg = utm_epsg_for(waypoints[0].longitude, waypoints[0].latitude)
        transformer = make_transformer(4326, epsg)
        zone = epsg - 32600 if epsg < 32700 else epsg - 32700
        crs_name = f"WGS 84 / UTM zone {zone}"

        spacing = float(getattr(corridor, "line_spacing", 0) or 0)
        work = _resolved_input(
            inp,
            mission_type=MissionType.LINEAR_CORRIDOR,
            speed_default=float(getattr(corridor, "recommended_speed_ms", 0) or 6.8),
            spacing=spacing,
            turn_angle=180.0,
        )

        turns: list[TurnGeometryResult] = []
        per_wp: dict[int, float] = {}
        pts = [transformer.transform(w.longitude, w.latitude) for w in waypoints]
        for i in range(1, len(pts) - 1):
            h_in = heading_degrees(pts[i - 1], pts[i])
            h_out = heading_degrees(pts[i], pts[i + 1])
            angle = abs(signed_turn_angle(h_in, h_out))
            if angle <= HEADING_TOLERANCE_DEG:
                continue
            direction = turn_direction_for(h_in, h_out)
            turn = self.engine.plan_turn(
                pts[i], h_in, h_out, angle, direction, work, epsg=epsg, crs_name=crs_name
            )
            turns.append(turn)
            per_wp[i] = turn.radius_m

        return GridTurnPlanner._assemble(work, MissionType.LINEAR_CORRIDOR, turns, per_wp, epsg, crs_name)

    @staticmethod
    def _empty(corridor, inp: Optional[TurnRadiusInput], reason: str) -> TurnPlanResult:
        mode = inp.mode.value if inp is not None else TurnRadiusMode.AUTO.value
        return TurnPlanResult(
            mission_type=MissionType.LINEAR_CORRIDOR.value,
            mode=mode,
            status=TurnStatus.NONE.value,
            radius_m=0.0,
            warnings=[reason],
            explanation=reason,
        )
