"""Authoritative photo-point annotation (single source of truth).

Produces the ``photo_points`` payload returned by the Grid and Corridor
engines so the frontend can render photo triggers and flight-line outlines
without reconstructing geometry. Consecutive waypoints whose heading stays
within ``PHOTO_POINT_LINE_TOLERANCE_DEG`` form one flight line; within each
line, ``distance_along_line_m`` is the metric (UTM) distance from the line
start. ``capture`` mirrors the waypoint action (``1`` → photo trigger).

A generous tolerance keeps curved corridor lines grouped while boustrophedon
reversals between lines (heading change ≥ 90°) always split the groups.
"""

from typing import Sequence

from .distance import make_transformer, utm_epsg_for
from .models import PhotoPoint

# Curved corridor lines can change heading gradually; 180° reversals are the
# only guaranteed line separators, so a wide tolerance is safe.
PHOTO_POINT_LINE_TOLERANCE_DEG = 15.0


def _cyclic_heading_diff(a: float, b: float) -> float:
    return (b - a + 540.0) % 360.0 - 180.0


def annotate_photo_points(
    waypoints: Sequence,
    speed_ms: float,
    heading_tolerance_deg: float = PHOTO_POINT_LINE_TOLERANCE_DEG,
) -> list[PhotoPoint]:
    """Return one :class:`PhotoPoint` per waypoint, grouped by flight line."""
    if not waypoints:
        return []
    pts: list[PhotoPoint] = []
    index = 0
    i = 0
    n = len(waypoints)
    while i < n:
        j = i + 1
        base_heading = float(waypoints[i].heading) % 360.0
        while (
            j < n
            and abs(_cyclic_heading_diff(base_heading, float(waypoints[j].heading) % 360.0)) <= heading_tolerance_deg
        ):
            j += 1
        group = waypoints[i:j]
        cum = 0.0
        transformer = None
        epsg = None
        for k, wp in enumerate(group):
            if k > 0:
                if transformer is None:
                    lats = [w.latitude for w in group]
                    lons = [w.longitude for w in group]
                    epsg = utm_epsg_for((min(lons) + max(lons)) / 2.0, (min(lats) + max(lats)) / 2.0)
                    transformer = make_transformer(4326, epsg)
                prev = transformer.transform(group[k - 1].longitude, group[k - 1].latitude)
                cur = transformer.transform(wp.longitude, wp.latitude)
                dx = cur[0] - prev[0]
                dy = cur[1] - prev[1]
                cum += (dx * dx + dy * dy) ** 0.5
            pts.append(
                PhotoPoint(
                    index=index,
                    latitude=wp.latitude,
                    longitude=wp.longitude,
                    altitude_m=wp.altitude,
                    distance_along_line_m=round(cum, 2),
                    speed_ms=float(speed_ms),
                    heading_deg=float(wp.heading),
                    capture=bool(getattr(wp, "action_type", -1) == 1),
                )
            )
            index += 1
        i = j
    return pts


def photo_points_to_dicts(photo_points: Sequence[PhotoPoint]) -> list[dict]:
    return [
        {
            "index": p.index,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "altitude_m": p.altitude_m,
            "distance_along_line_m": p.distance_along_line_m,
            "speed_ms": p.speed_ms,
            "heading_deg": p.heading_deg,
            "capture": p.capture,
        }
        for p in photo_points
    ]
