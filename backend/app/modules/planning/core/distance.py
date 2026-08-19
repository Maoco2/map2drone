"""Metric distance helpers (single source of truth).

Mission distances are computed in a projected metric CRS (UTM zone chosen from
the mission centroid) via pyproj — the same methodology used by the Turn
Radius engine and the Corridor engine, so every subsystem agrees on metric
measurements. Original mission coordinates (EPSG:4326) are never modified.
"""

import math
from typing import Optional, Sequence, Tuple

from pyproj import CRS, Transformer


def utm_epsg_for(lon: float, lat: float) -> int:
    """Best UTM zone EPSG code for the given lon/lat (meters everywhere)."""
    zone = int((lon + 180.0) // 6) + 1
    zone = max(1, min(60, zone))
    return 32600 + zone if lat >= 0 else 32700 + zone


def make_transformer(src_epsg: int, dst_epsg: int) -> Transformer:
    return Transformer.from_crs(CRS.from_epsg(src_epsg), CRS.from_epsg(dst_epsg), always_xy=True)


def _centroid(lon: float, lat: float) -> Tuple[float, float]:
    return lon, lat


def calculate_path_distance(
    waypoints_geo: Sequence[Sequence[float]],
    center_lon: Optional[float] = None,
    center_lat: Optional[float] = None,
) -> float:
    """Total metric distance (m) along a sequence of ``(lon, lat)`` points.

    The UTM zone is derived from the given centroid, or from the bounding box
    centre of the points when not provided. Euclidean distances between
    consecutive projected points are summed.
    """
    pts = [(float(p[0]), float(p[1])) for p in waypoints_geo]
    if len(pts) < 2:
        return 0.0
    if center_lon is None or center_lat is None:
        lons = [p[0] for p in pts]
        lats = [p[1] for p in pts]
        center_lon = (min(lons) + max(lons)) / 2.0
        center_lat = (min(lats) + max(lats)) / 2.0
    epsg = utm_epsg_for(center_lon, center_lat)
    transformer = make_transformer(4326, epsg)
    projected = [transformer.transform(p[0], p[1]) for p in pts]
    total = 0.0
    for i in range(1, len(projected)):
        dx = projected[i][0] - projected[i - 1][0]
        dy = projected[i][1] - projected[i - 1][1]
        total += math.hypot(dx, dy)
    return total


def distance_between_points(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
    center_lon: Optional[float] = None,
    center_lat: Optional[float] = None,
) -> float:
    """Metric distance (m) between two ``(lon, lat)`` points (UTM)."""
    return calculate_path_distance([(lon1, lat1), (lon2, lat2)], center_lon, center_lat)
