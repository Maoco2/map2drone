"""Shared core data models (pure dataclasses, no DB)."""

from dataclasses import dataclass


@dataclass
class PhotoPoint:
    """A photo capture position along a flight line.

    ``distance_along_line_m`` is measured from the start of the containing
    flight line (in mission traversal order). ``capture`` is ``True`` for
    actual photo triggers; photo-mode missions also emit vertex waypoints
    with ``capture=False`` so the line outline renders.
    """

    index: int
    latitude: float
    longitude: float
    altitude_m: float
    distance_along_line_m: float
    speed_ms: float
    heading_deg: float
    capture: bool = True


@dataclass
class FlightLine:
    """A flight line in EPSG:4326, with planning metadata.

    ``order`` is the mission traversal order (0-based). ``reverse`` marks
    boustrophedon return lines. ``distance_m`` is the metric length.
    """

    order: int
    coordinates: list  # [[lon, lat], ...] EPSG:4326
    heading_deg: float
    line_index: int
    distance_m: float
    reverse: bool = False


@dataclass
class MissionMetrics:
    """Consolidated mission metrics (distance / time / battery).

    Accounting model (documented):

    * ``straight_distance_m``: along-track legs where heading does not change
      (flight lines).
    * ``transition_distance_m``: connector legs between flight lines.
    * ``turn_distance_m``: circular-arc length from the Turn Radius plan when
      available, else ``0``.
    * ``total_distance_m``: waypoint path length (metric, UTM) — equals
      ``straight + transition``.
    * ``straight_time_s``: ``straight / speed``.
    * ``transition_time_s``: ``transition / speed``.
    * ``turn_time_s``: real turn durations from the plan when available, else
      the documented per-line overhead fallback.
    * ``total_time_s``: ``straight + transition + turn`` time.

    When no turn plan is available ``turn_time_s`` equals
    ``num_lines * DEFAULT_TURN_OVERHEAD_S_PER_LINE`` which reproduces the
    historical ``estimated_time_sec = total_distance / speed + num_lines * 5``.
    """

    straight_distance_m: float = 0.0
    transition_distance_m: float = 0.0
    turn_distance_m: float = 0.0
    total_distance_m: float = 0.0
    straight_time_s: float = 0.0
    transition_time_s: float = 0.0
    turn_time_s: float = 0.0
    total_time_s: float = 0.0
    flight_time_available_min: float = 0.0
    usable_flight_time_min: float = 0.0
    required_minutes: float = 0.0
    battery_count: int = 1
    battery_margin_min: float = 0.0
    turn_source: str = "overhead_fallback"

    def to_dict(self) -> dict:
        return {
            "straight_distance_m": round(self.straight_distance_m, 2),
            "transition_distance_m": round(self.transition_distance_m, 2),
            "turn_distance_m": round(self.turn_distance_m, 2),
            "total_distance_m": round(self.total_distance_m, 2),
            "straight_time_s": round(self.straight_time_s, 1),
            "transition_time_s": round(self.transition_time_s, 1),
            "turn_time_s": round(self.turn_time_s, 1),
            "total_time_s": round(self.total_time_s, 1),
            "flight_time_available_min": self.flight_time_available_min,
            "usable_flight_time_min": self.usable_flight_time_min,
            "required_minutes": self.required_minutes,
            "battery_count": self.battery_count,
            "battery_margin_min": self.battery_margin_min,
            "turn_source": self.turn_source,
        }
