"""Map2Drone Planning Core.

Shared, single-source-of-truth photogrammetry/planning primitives used by every
mission type (Area Grid, Linear Corridor and future modes):

* camera resolution
* GSD / footprint
* shutter-limited recommended speed
* line / photo spacing
* metric (UTM) distance
* battery requirements
* mission metrics (straight / turn / total distance and time, batteries)

The core is pure math + pyproj. It never queries the database itself (the
camera accessor takes the session as a parameter) and it never modifies the
Turn Radius or Capture Interval engines — it orchestrates them.
"""

from .battery import (
    DEFAULT_FLIGHT_TIME_MIN_FALLBACK,
    DEFAULT_USABLE_BATTERY_FRACTION,
    BatteryRequirements,
    calculate_battery_requirements,
)
from .camera import get_camera, get_camera_required
from .distance import calculate_path_distance, make_transformer, utm_epsg_for
from .metrics import (
    DEFAULT_TURN_OVERHEAD_S_PER_LINE,
    MissionMetrics,
    calculate_mission_metrics,
)
from .models import FlightLine, PhotoPoint
from .photo_points import (
    PHOTO_POINT_LINE_TOLERANCE_DEG,
    annotate_photo_points,
    photo_points_to_dicts,
)
from .photogrammetry import (
    calc_footprint,
    calc_gsd,
    calculate_gsd_and_footprint,
)
from .spacing import calculate_line_spacing, calculate_photo_spacing
from .speed import (
    ELECTRONIC_SHUTTER_FACTOR,
    MECHANICAL_SHUTTER_FACTOR,
    calculate_recommended_speed,
)

__all__ = [
    "BatteryRequirements",
    "ELECTRONIC_SHUTTER_FACTOR",
    "MECHANICAL_SHUTTER_FACTOR",
    "FlightLine",
    "MissionMetrics",
    "PhotoPoint",
    "PHOTO_POINT_LINE_TOLERANCE_DEG",
    "DEFAULT_FLIGHT_TIME_MIN_FALLBACK",
    "DEFAULT_TURN_OVERHEAD_S_PER_LINE",
    "DEFAULT_USABLE_BATTERY_FRACTION",
    "annotate_photo_points",
    "calc_footprint",
    "calc_gsd",
    "calculate_battery_requirements",
    "calculate_gsd_and_footprint",
    "calculate_line_spacing",
    "calculate_mission_metrics",
    "calculate_path_distance",
    "calculate_photo_spacing",
    "calculate_recommended_speed",
    "get_camera",
    "get_camera_required",
    "make_transformer",
    "photo_points_to_dicts",
    "utm_epsg_for",
]
