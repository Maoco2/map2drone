"""Turn-radius planners for Area Grid and Linear Corridor.

The planners turn a plan (``GridResponse`` / ``CorridorResponse``) — or in the
export path, a plain list of waypoints — into a ``TurnPlanResult`` by
reconstructing the flight lines and calling ``TurnRadiusEngine.plan_turn``
once per transition between consecutive lines.

Geometry is always projected (UTM, chosen from the centroid) so line
separation, radii and turn points are metric.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

from shapely.geometry import LineString, Point

from app.modules.planning.turn_radius.engine import TurnRadiusEngine
from app.modules.planning.turn_radius.geometry import (
    make_transformer,
    right_normal,
    signed_turn_angle,
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
        return self._assemble(work, MissionType.AREA_GRID, turns, group_indices, epsg, crs_name)

    @staticmethod
    def _assemble(
        inp: TurnRadiusInput,
        mission_type: MissionType,
        turns: list[TurnGeometryResult],
        group_indices: dict,
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
                explanation="Fewer than two flight lines: no turns to plan.",
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

        per_wp: dict[int, float] = {}
        for i in range(len(turns)):
            last_idx = group_indices.get(i, [])[-1] if group_indices.get(i) else None
            if last_idx is not None:
                per_wp[last_idx] = turns[i].radius_m

        return TurnPlanResult(
            mission_type=mission_type.value,
            mode=inp.mode.value,
            status=status,
            radius_m=radius,
            turn_count=len(turns),
            turns=turns,
            per_waypoint_curve_size=per_wp,
            warnings=warnings,
            explanation=(f"Uniform mission turn radius {radius:.2f} m (minimum across {len(turns)} turns)."),
            geometry=_mission_geometry(turns),
            epsg=epsg,
            crs_name=crs_name,
        )


class CorridorTurnPlanner:
    """Plans turn radii for a Linear Corridor mission.

    Uses the real corridor geometry (``flight_lines_geojson``) so turn angles
    follow the corridor bends and line separation follows the actual offset
    spacing.
    """

    def __init__(self, engine: Optional[TurnRadiusEngine] = None) -> None:
        self.engine = engine or TurnRadiusEngine()

    def _segments_from_geojson(self, flight_lines_geojson: dict, epsg: int) -> list[LineString]:
        transformer = make_transformer(4326, epsg)
        segments: list[LineString] = []
        for feat in flight_lines_geojson.get("features", []):
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [])
            if not coords or geom.get("type") != "LineString":
                continue
            pts = [transformer.transform(c[0], c[1]) for c in coords]
            if len(pts) >= 2:
                segments.append(LineString(pts))
        return segments

    @staticmethod
    def _traversal(seg: LineString, reverse: bool) -> LineString:
        coords = list(seg.coords)
        if reverse:
            coords = coords[::-1]
        return LineString(coords)

    def plan(self, corridor, inp: Optional[TurnRadiusInput] = None) -> TurnPlanResult:
        geom = getattr(corridor, "geometry", None)
        if geom is None:
            return self._empty(corridor, inp, "Corridor response has no geometry.")

        waypoints = corridor.waypoints
        if waypoints:
            epsg = utm_epsg_for(waypoints[0].longitude, waypoints[0].latitude)
        else:
            epsg = int(getattr(geom, "epsg_out", 4326) or 4326)
        crs_name = str(getattr(geom, "crs_name", "WGS84"))

        raw = self._segments_from_geojson(getattr(geom, "flight_lines_geojson", {}) or {}, epsg)
        if len(raw) < 2:
            return self._empty(corridor, inp, "Fewer than two flight lines: no turns to plan.")

        # Serpentine traversal: odd segments are flown reversed.
        traversal = [self._traversal(seg, i % 2 == 1) for i, seg in enumerate(raw)]
        headings: list[float] = []
        for line in traversal:
            c0, c1 = line.coords[0], line.coords[1]
            dx = c1[0] - c0[0]
            dy = c1[1] - c0[1]
            headings.append((math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0)

        spacing = float(getattr(corridor, "line_spacing", 0) or 0)
        if spacing <= 0:
            spacing = _line_spacing_from(traversal)
        work = _resolved_input(
            inp,
            mission_type=MissionType.LINEAR_CORRIDOR,
            speed_default=float(getattr(corridor, "recommended_speed_ms", 0) or 6.8),
            spacing=spacing,
            turn_angle=180.0,
        )

        turns = _plan_transitions(self.engine, traversal, headings, work, epsg, crs_name)
        per_wp = self._per_waypoint_mapping(waypoints, traversal, turns, epsg)
        plan = GridTurnPlanner._assemble(work, MissionType.LINEAR_CORRIDOR, turns, {}, epsg, crs_name)
        plan.per_waypoint_curve_size = per_wp
        return plan

    @staticmethod
    def _per_waypoint_mapping(waypoints, traversal, turns, epsg) -> dict:
        if not waypoints or not turns:
            return {}
        transformer = make_transformer(4326, epsg)
        nearest: list[int] = []
        for wp in waypoints:
            pt = Point(transformer.transform(wp.longitude, wp.latitude))
            d = [(pt.distance(line), i) for i, line in enumerate(traversal)]
            nearest.append(min(d, key=lambda t: t[0])[1])
        mapping: dict = {}
        for i in range(len(nearest) - 1):
            if nearest[i] != nearest[i + 1] and nearest[i] < len(turns):
                mapping[i] = turns[nearest[i]].radius_m
        return mapping

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
