"""Turn radius engine — pure geometry helpers.

All geometry lives in a projected CRS (UTM, chosen from the centroid) so
distances and radii are metric. Headings are angles (degrees clockwise from
north) — angles, not distances, and are never used for metric math.

Circle convention
-----------------
For a turn of radius ``R`` starting at point ``P`` with entry heading
``h_in``:

* ``dir_sign = +1`` for RIGHT turns (heading increases, clockwise), ``-1`` for
  LEFT turns (heading decreases, counter-clockwise).
* ``C = P + dir_sign * R * right_normal(h_in)``            (turn center)
* ``P(t) = C + dir_sign * R * left_normal(h(t))``          (arc point)
* ``h(t) = h_in + dir_sign * turn_angle * t``              (t in [0, 1])

with ``right_normal = (cos h, -sin h)`` and ``left_normal = (-cos h, sin h)``
in (x=east, y=north). This yields clockwise (RIGHT) and counter-clockwise
(LEFT) arcs that start at ``P`` tangent to ``h_in`` and end tangent to
``h_out``.
"""

from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence, Tuple

from pyproj import CRS, Transformer
from shapely.geometry import LineString, Point

UTM_TEMPLATE = "EPSG:{code}"


def utm_epsg_for(lon: float, lat: float) -> int:
    """Best UTM zone EPSG code for the given lon/lat (meters everywhere)."""
    zone = int((lon + 180.0) // 6) + 1
    zone = max(1, min(60, zone))
    return 32600 + zone if lat >= 0 else 32700 + zone


def make_transformer(src_epsg: int, dst_epsg: int) -> Transformer:
    return Transformer.from_crs(CRS.from_epsg(src_epsg), CRS.from_epsg(dst_epsg), always_xy=True)


def heading_degrees(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Heading clockwise from north for segment p1→p2, in [0, 360)."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0


def heading_unit(heading_deg: float) -> Tuple[float, float]:
    """Unit vector (x=east, y=north) along a heading."""
    r = math.radians(heading_deg % 360.0)
    return (math.sin(r), math.cos(r))


def left_normal(heading_deg: float) -> Tuple[float, float]:
    x, y = heading_unit(heading_deg)
    return (-y, x)


def right_normal(heading_deg: float) -> Tuple[float, float]:
    x, y = heading_unit(heading_deg)
    return (y, -x)


def signed_turn_angle(heading_in: float, heading_out: float) -> float:
    """Signed smallest turn from heading_in to heading_out in [-180, 180].

    Positive = turn to the RIGHT (heading increases, clockwise). A 180-degree
    reversal is reported as +180 by convention (its sign is geometrically
    ambiguous from the headings alone; the planners resolve it from the
    position of the next flight line).
    """
    d = (heading_out - heading_in) % 360.0
    if d > 180.0:
        d -= 360.0
    return d


def turn_direction_for(heading_in: float, heading_out: float) -> str:
    """'RIGHT' when heading increases, 'LEFT' when it decreases."""
    return "RIGHT" if signed_turn_angle(heading_in, heading_out) >= 0 else "LEFT"


def turn_angle_degrees(heading_in: float, heading_out: float) -> float:
    """Absolute turn angle in [0, 180] between the two headings."""
    return abs(signed_turn_angle(heading_in, heading_out))


def generate_circular_arc(
    start: Tuple[float, float],
    heading_in: float,
    heading_out: float,
    radius: float,
    turn_direction: str,
    turn_angle_deg: Optional[float] = None,
    samples: int = 64,
) -> Tuple[LineString, Point]:
    """Build a circular arc between ``start`` (heading_in) and heading_out.

    Returns ``(arc, center)`` in projected meters. With ``radius == 0`` the
    arc degenerates to a point. ``turn_angle_deg`` defaults to the signed
    angle implied by the two headings; when both are given it takes
    precedence (used for exactly-180 U-turns).
    """
    direction_sign = 1 if turn_direction == "RIGHT" else -1
    angle = abs(turn_angle_deg) if turn_angle_deg is not None else abs(signed_turn_angle(heading_in, heading_out))
    angle = max(0.0, min(180.0, angle)) * direction_sign

    rad = max(0.0, radius)
    if rad <= 0.0 or angle == 0.0:
        pt = Point(start)
        return LineString([start, start]), pt

    nx, ny = right_normal(heading_in)
    cx = start[0] + direction_sign * rad * nx
    cy = start[1] + direction_sign * rad * ny
    center = Point(cx, cy)

    pts: list[Tuple[float, float]] = []
    for k in range(samples + 1):
        h = heading_in + angle * (k / samples)
        lx, ly = left_normal(h)
        pts.append((cx + direction_sign * rad * lx, cy + direction_sign * rad * ly))
    return LineString(pts), center


def arc_endpoint(
    start: Tuple[float, float],
    heading_in: float,
    heading_out: float,
    radius: float,
    turn_direction: str,
    turn_angle_deg: Optional[float] = None,
) -> Tuple[float, float]:
    """Final point of the arc (tangent to ``heading_out``), without building it."""
    direction_sign = 1 if turn_direction == "RIGHT" else -1
    angle = abs(turn_angle_deg) if turn_angle_deg is not None else abs(signed_turn_angle(heading_in, heading_out))
    angle = max(0.0, min(180.0, angle)) * direction_sign
    rad = max(0.0, radius)
    nx, ny = right_normal(heading_in)
    cx = start[0] + direction_sign * rad * nx
    cy = start[1] + direction_sign * rad * ny
    h_out = heading_in + angle
    lx, ly = left_normal(h_out)
    return (cx + direction_sign * rad * lx, cy + direction_sign * rad * ly)


def arc_length(radius: float, turn_angle_deg: float) -> float:
    """Arc length in meters: radius * |angle| (radians)."""
    return radius * math.radians(min(180.0, abs(turn_angle_deg)))


def project_linestring(line: LineString, transformer: Transformer) -> LineString:
    return LineString(transformer.itransform(line.coords))


def project_point(point: Tuple[float, float], transformer: Transformer) -> Tuple[float, float]:
    return transformer.transform(point[0], point[1])


def unproject_linestring(line: LineString, transformer: Transformer) -> LineString:
    return LineString(transformer.itransform(line.coords))


def to_geojson_line(line: LineString, transformer: Transformer) -> dict:
    coords = [[round(x, 9), round(y, 9)] for x, y in transformer.itransform(line.coords)]
    return {"type": "LineString", "coordinates": coords}


def to_geojson_point(point: Point, transformer: Transformer) -> dict:
    x, y = transformer.transform(point.x, point.y)
    return {"type": "Point", "coordinates": [round(x, 9), round(y, 9)]}


def to_geojson_geometry(
    arc: LineString,
    center: Point,
    swept: Optional["object"] = None,
    transformer: Optional[Transformer] = None,
) -> dict:
    """GeoJSON FeatureCollection with the arc, center and clearance buffer."""
    if transformer is None:
        return {"type": "FeatureCollection", "features": []}
    features: list[dict] = [
        {
            "type": "Feature",
            "properties": {"kind": "turn_arc"},
            "geometry": to_geojson_line(arc, transformer),
        },
        {
            "type": "Feature",
            "properties": {"kind": "turn_center"},
            "geometry": to_geojson_point(center, transformer),
        },
    ]
    if swept is not None and not swept.is_empty:
        from shapely.geometry import mapping
        from shapely.ops import transform as shp_transform

        def _round_geom(g):
            if g.is_empty:
                return g

            def _round(x, y, z=None):
                return round(x, 9), round(y, 9)

            return shp_transform(_round, g)

        geojson = mapping(shp_transform(lambda x, y: transformer.transform(x, y), _round_geom(swept)))
        features.append(
            {
                "type": "Feature",
                "properties": {"kind": "clearance_buffer"},
                "geometry": geojson,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def perpendicular_distance(line: LineString, point: Tuple[float, float]) -> float:
    """Minimum distance from ``point`` to ``line`` (projected meters)."""
    return line.distance(Point(point))


def lines_spacing(lines: Sequence[LineString]) -> float:
    """Median perpendicular distance between consecutive parallel lines."""
    if len(lines) < 2:
        return 0.0
    dists: list[float] = []
    for a, b in zip(lines[:-1], lines[1:]):
        d1 = a.distance(b)
        mid_a = a.interpolate(0.5, normalized=True)
        d2 = b.distance(mid_a)
        dists.append(min(d1, d2))
    dists.sort()
    return dists[len(dists) // 2] if dists else 0.0


def median_distance(values: Iterable[float]) -> float:
    vals = sorted(values)
    if not vals:
        return 0.0
    n = len(vals)
    mid = n // 2
    if n % 2 == 1:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2.0
