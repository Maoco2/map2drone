"""Consolidated mission metrics (single source of truth).

Replaces the duplicated distance / time / battery computations that used to
live inside the Grid and Corridor engines, and removes the fixed
``num_lines * 5`` turn penalty in favour of the real turn times produced by the
Turn Radius plan when one is available.
"""

from typing import Optional, Sequence

from .battery import calculate_battery_requirements
from .distance import calculate_path_distance, make_transformer, utm_epsg_for
from .models import MissionMetrics

# Same tolerance the Turn Radius planners use to reconstruct flight lines.
HEADING_TOLERANCE_DEG = 1.5

# Historical fixed per-line turn overhead kept as the documented fallback when
# no Turn Radius plan is available (reproduces the old `num_lines * 5`).
DEFAULT_TURN_OVERHEAD_S_PER_LINE = 5.0


def _cyclic_heading_diff(a: float, b: float) -> float:
    return (b - a + 540.0) % 360.0 - 180.0


def split_straight_transition(
    waypoints_geo_heading: Sequence,
    tolerance_deg: float = HEADING_TOLERANCE_DEG,
) -> tuple[float, float]:
    """Partition the waypoint path into straight vs transition distances.

    ``waypoints_geo_heading`` is a sequence of ``(lon, lat, heading)``. Legs
    whose heading change stays within ``tolerance_deg`` are "straight" (along a
    flight line); the rest are turn transitions between lines.
    """
    pts = [(float(p[0]), float(p[1])) for p in waypoints_geo_heading]
    if len(pts) < 2:
        return 0.0, 0.0
    headings = [float(p[2]) % 360.0 for p in waypoints_geo_heading]
    straight = 0.0
    transition = 0.0
    epsg = _utm_for_points(pts)
    transformer = make_transformer(4326, epsg)
    projected = [transformer.transform(lon, lat) for lon, lat in pts]
    for i in range(1, len(projected)):
        dx = projected[i][0] - projected[i - 1][0]
        dy = projected[i][1] - projected[i - 1][1]
        d = (dx * dx + dy * dy) ** 0.5
        if abs(_cyclic_heading_diff(headings[i - 1], headings[i])) <= tolerance_deg:
            straight += d
        else:
            transition += d
    return straight, transition


def _utm_for_points(pts) -> int:

    lons = [p[0] for p in pts]
    lats = [p[1] for p in pts]
    return utm_epsg_for((min(lons) + max(lons)) / 2.0, (min(lats) + max(lats)) / 2.0)


def _turn_times(plan, num_lines: int, overhead_s_per_line: float) -> tuple[float, float, str]:
    """Return ``(turn_distance_m, turn_time_s, source)`` from a turn plan.

    Uses the real arc geometry when the plan has measurable turns, otherwise
    falls back to the documented per-line overhead.
    """
    if plan is not None:
        turns = getattr(plan, "turns", None) or []
        durations = [t.turn_duration_s for t in turns if t.turn_duration_s and t.turn_duration_s > 0]
        distances = [t.turn_distance_m for t in turns if t.turn_distance_m and t.turn_distance_m > 0]
        if durations:
            return sum(distances), sum(durations), "turn_plan"
    return 0.0, max(0.0, num_lines) * overhead_s_per_line, "overhead_fallback"


def calculate_mission_metrics(
    waypoints_geo_heading: Sequence,
    speed_mps: float,
    num_lines: int,
    turn_plan=None,
    drone_flight_time_min: Optional[float] = None,
    usable_battery_fraction: Optional[float] = None,
    turn_overhead_s_per_line: float = DEFAULT_TURN_OVERHEAD_S_PER_LINE,
) -> MissionMetrics:
    """Compute consolidated mission metrics.

    ``waypoints_geo_heading`` is a sequence of ``(lon, lat, heading)`` in
    mission order. ``turn_plan`` is a TurnRadius ``TurnPlanResult`` or ``None``.
    """
    pts = [(float(p[0]), float(p[1])) for p in waypoints_geo_heading]
    total_distance = calculate_path_distance(pts)
    straight_distance, transition_distance = split_straight_transition(waypoints_geo_heading)

    speed = speed_mps if speed_mps and speed_mps > 0 else 1.0
    straight_time = straight_distance / speed
    transition_time = transition_distance / speed
    turn_distance, turn_time, turn_source = _turn_times(turn_plan, num_lines, turn_overhead_s_per_line)
    total_time = straight_time + transition_time + turn_time

    battery_kwargs = {"drone_flight_time_min": drone_flight_time_min}
    if usable_battery_fraction is not None:
        battery_kwargs["usable_battery_fraction"] = usable_battery_fraction
    battery = calculate_battery_requirements(total_time, **battery_kwargs)

    return MissionMetrics(
        straight_distance_m=round(straight_distance, 2),
        transition_distance_m=round(transition_distance, 2),
        turn_distance_m=round(turn_distance, 2),
        total_distance_m=round(total_distance, 2),
        straight_time_s=round(straight_time, 1),
        transition_time_s=round(transition_time, 1),
        turn_time_s=round(turn_time, 1),
        total_time_s=round(total_time, 1),
        flight_time_available_min=battery.flight_time_available_min,
        usable_flight_time_min=battery.usable_flight_time_min,
        required_minutes=battery.required_minutes,
        battery_count=battery.battery_count,
        battery_margin_min=battery.battery_margin_min,
        turn_source=turn_source,
    )
