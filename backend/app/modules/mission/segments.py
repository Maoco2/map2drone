"""Flight segmentation for the Universal Mission Model (Fase 10B).

Builds :class:`FlightSegment` lists from the mission waypoints and the
turn-radius plan. No physics/formula is duplicated here:

* straight-segment distances reuse the Planning Core UTM distance helpers;
* turn distances / durations are copied from the Turn Radius plan output.

Segments are a structural view (time, distance, photos, turns and energy per
segment) and are never authoritative for the mission totals — the
authoritative values stay in ``MissionMetrics``.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

from app.modules.mission.models import FlightSegment, UniversalWaypoint
from app.modules.planning.core.distance import make_transformer, utm_epsg_for


def _turn_indices(turn_radius_result: Optional[dict]) -> list[int]:
    """Global waypoint indices where a curve radius is applied."""
    if not turn_radius_result:
        return []
    pcs = turn_radius_result.get("per_waypoint_curve_size") or {}
    try:
        return sorted(int(k) for k in pcs.keys())
    except (TypeError, ValueError):
        return []


def _pairwise_distance(waypoints: Sequence[UniversalWaypoint], lo: int, hi: int) -> float:
    """Metric (UTM) length of the polyline from waypoint ``lo`` to ``hi``."""
    if hi <= lo:
        return 0.0
    pts = waypoints[lo : hi + 1]
    valid = [p for p in pts if p.longitude is not None and p.latitude is not None]
    if len(valid) < 2:
        return 0.0
    lons = [p.longitude for p in valid]
    lats = [p.latitude for p in valid]
    epsg = utm_epsg_for((min(lons) + max(lons)) / 2.0, (min(lats) + max(lats)) / 2.0)
    transformer = make_transformer(4326, epsg)
    projected = [transformer.transform(p.longitude, p.latitude) for p in valid]
    total = 0.0
    for i in range(1, len(projected)):
        total += math.hypot(projected[i][0] - projected[i - 1][0], projected[i][1] - projected[i - 1][1])
    return total


def _any_capture(waypoints: Sequence[UniversalWaypoint], lo: int, hi: int) -> bool:
    return any(wp.capture_enabled or wp.action_type == 1 for wp in waypoints[lo : hi + 1])


def build_segments(
    waypoints: Sequence[UniversalWaypoint],
    turn_radius_result: Optional[dict] = None,
    speed_ms: Optional[float] = None,
) -> list[FlightSegment]:
    """Build ordered straight + turn segments from a mission.

    When a turn plan is available, the waypoints with an applied curve radius
    are the turn boundaries; the remaining runs form the straight segments.
    Without a turn plan the whole mission is one straight segment.
    """
    wps = list(waypoints)
    if not wps:
        return []
    speed = speed_ms if speed_ms and speed_ms > 0 else (wps[0].speed_mps if wps[0].speed_mps else 0.0)

    turns = []
    if turn_radius_result:
        turns = turn_radius_result.get("turns") or []
    turn_idx = _turn_indices(turn_radius_result)

    segments: list[FlightSegment] = []
    n = len(wps)
    seg_index = 0
    line_index = 0

    def add_straight(lo: int, hi: int) -> None:
        nonlocal seg_index, line_index
        if hi < lo:
            return
        distance = _pairwise_distance(wps, lo, hi)
        duration = (distance / speed) if speed > 0 else 0.0
        segments.append(
            FlightSegment(
                segment_index=seg_index,
                start_waypoint=lo,
                end_waypoint=hi,
                distance_m=round(distance, 2),
                heading_deg=wps[lo].heading_deg,
                speed_mps=speed,
                duration_s=round(duration, 1),
                line_index=line_index,
                is_photo_segment=_any_capture(wps, lo, hi),
                is_turn_segment=False,
            )
        )
        line_index += 1
        seg_index += 1

    def add_turn(idx: int, turn: Optional[dict]) -> None:
        nonlocal seg_index
        segments.append(
            FlightSegment(
                segment_index=seg_index,
                start_waypoint=idx,
                end_waypoint=idx,
                distance_m=round(float(turn.get("turn_distance_m", 0.0)) if turn else 0.0, 2),
                heading_deg=wps[idx].heading_deg if idx < n else None,
                speed_mps=float(turn.get("turn_speed_ms", 0.0)) if turn and turn.get("turn_speed_ms") else speed,
                duration_s=round(float(turn.get("turn_duration_s", 0.0)) if turn else 0.0, 1),
                line_index=None,
                is_photo_segment=bool(turn and turn.get("photo_capture_recommended_during_turn", False)),
                is_turn_segment=True,
                turn_angle_deg=(
                    float(turn["turn_angle_deg"]) if turn and turn.get("turn_angle_deg") is not None else None
                ),
            )
        )
        seg_index += 1

    if not turn_idx:
        add_straight(0, n - 1)
    else:
        start = 0
        for i, idx in enumerate(turn_idx):
            if idx >= n:
                continue
            if idx > start:
                add_straight(start, idx - 1)
            turn = turns[i] if i < len(turns) else None
            add_turn(idx, turn)
            start = idx + 1
        if start < n:
            add_straight(start, n - 1)

    _annotate_waypoints(wps, segments)
    return segments


def _annotate_waypoints(wps: list[UniversalWaypoint], segments: list[FlightSegment]) -> None:
    """Fill ``line_index`` / ``segment_index`` / ``photo_index`` on waypoints."""
    for seg in segments:
        if seg.is_turn_segment:
            if seg.start_waypoint < len(wps):
                wps[seg.start_waypoint].segment_index = seg.segment_index
            continue
        for idx in range(seg.start_waypoint, seg.end_waypoint + 1):
            if idx < len(wps):
                wps[idx].line_index = seg.line_index
                wps[idx].segment_index = seg.segment_index
    photo = 0
    for wp in wps:
        if wp.capture_enabled or wp.action_type == 1:
            wp.photo_index = photo
            photo += 1
