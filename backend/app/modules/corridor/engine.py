"""
Map2Drone Linear Corridor Engine.

Computes a corridor flight plan from a centerline (GeoJSON LineString).

All geometry operations run in an appropriate projected CRS (UTM zone,
chosen from the corridor centroid) via pyproj + shapely, so offsets,
buffers and distances are metric — never raw EPSG:4326 degrees.

Supports asymmetric corridors (width_left / width_right in meters) and the
same waypoint modes as the area grid: vertex (Takeoff), terrain (AGL) and
photo (one waypoint per photo trigger).
"""

import math
from typing import Optional

from pyproj import CRS, Transformer
from shapely.geometry import GeometryCollection, LineString, MultiLineString, Point, Polygon

from app.core.photogrammetry.capture_interval import (
    build_capture_interval_block,
    compute_capture_interval,
    compute_minimum_plausible_agl,
)
from app.models.schemas import Drone
from app.modules.planning.core.camera import get_camera_required
from app.modules.planning.core.distance import utm_epsg_for
from app.modules.planning.core.metrics import calculate_mission_metrics
from app.modules.planning.core.photo_points import annotate_photo_points, photo_points_to_dicts
from app.modules.planning.core.photogrammetry import calc_footprint, calc_gsd
from app.modules.planning.core.spacing import calculate_line_spacing, calculate_photo_spacing
from app.modules.planning.core.speed import calculate_recommended_speed
from app.modules.planning.elevation import ElevationProvider, create_provider
from app.modules.planning.turn_radius.integration import compute_turn_radius_plan
from app.schemas.schemas import CorridorGeometry, CorridorRequest, CorridorResponse, WaypointSchema


def _extract_centerline_coords(centerline: dict) -> list[list[float]]:
    coords = centerline.get("coordinates", [])
    if not isinstance(coords, list):
        raise ValueError("Centerline must be a GeoJSON LineString")
    cleaned: list[list[float]] = []
    for p in coords:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            cleaned.append([float(p[0]), float(p[1])])
    if len(cleaned) < 2:
        raise ValueError("Centerline must have at least 2 valid coordinate pairs")
    if len(cleaned) >= 3:
        first = cleaned[0]
        last = cleaned[-1]
        if abs(first[0] - last[0]) <= 1e-9 and abs(first[1] - last[1]) <= 1e-9:
            cleaned = cleaned[:-1]
    if len(cleaned) < 2:
        raise ValueError("Centerline must have at least 2 valid coordinate pairs")
    return cleaned


def _as_single_line(geom) -> Optional[LineString]:
    """Return the longest LineString inside a geometry result."""
    if isinstance(geom, LineString):
        return geom if geom.length > 1e-9 else None
    if isinstance(geom, MultiLineString):
        best = max(geom.geoms, key=lambda g: g.length, default=None)
        return best if best is not None and best.length > 1e-9 else None
    if isinstance(geom, GeometryCollection):
        lines = [g for g in geom.geoms if isinstance(g, LineString)]
        if lines:
            return max(lines, key=lambda g: g.length)
    return None


def _polyline_local_heading(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Heading in degrees clockwise from north for the local segment p1→p2."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0


def _path_vertices(line: LineString) -> list[tuple[float, float]]:
    """Return the vertices that represent a real direction change.

    Only consecutive duplicates and points exactly collinear with their
    neighbours are dropped; every other vertex — no matter how small the
    direction change — is kept, so flight-line corners always get a waypoint.
    """
    coords = list(line.coords)
    if len(coords) < 2:
        return coords
    cleaned: list[tuple[float, float]] = [coords[0]]
    for p in coords[1:]:
        if p != cleaned[-1]:
            cleaned.append(p)
    if len(cleaned) < 3:
        return cleaned
    out: list[tuple[float, float]] = [cleaned[0]]
    for i in range(1, len(cleaned) - 1):
        a, b, c = cleaned[i - 1], cleaned[i], cleaned[i + 1]
        h1 = _polyline_local_heading(a, b)
        h2 = _polyline_local_heading(b, c)
        delta = abs((h2 - h1 + 540.0) % 360.0 - 180.0)
        if delta <= 1e-6:
            continue
        out.append(cleaned[i])
    out.append(cleaned[-1])
    return out


def _build_corridor_polygon(left: LineString, right: LineString) -> Polygon:
    ring = list(left.coords) + list(right.coords)[::-1]
    poly = Polygon(ring)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly


def _build_flight_segments(
    center: LineString,
    poly: Polygon,
    width_left: float,
    width_right: float,
    line_spacing_m: float,
) -> list[LineString]:
    """Parallel flight lines along the corridor axis, clipped to the footprint."""
    corridor_width = width_left + width_right
    n = int(corridor_width / line_spacing_m)
    if n < 1:
        n = 1
    if n * line_spacing_m < corridor_width:
        n += 1
    step = corridor_width / n
    offsets = [-width_right + step * (i + 0.5) for i in range(n)]

    segments: list[LineString] = []
    for off in offsets:
        curve = _as_single_line(center.offset_curve(off, join_style="mitre", mitre_limit=2.0))
        if curve is None:
            continue
        inside = curve.intersection(poly)
        part = _as_single_line(inside)
        if part is None or part.length < max(1.0, line_spacing_m * 0.2):
            continue
        segments.append(part)
    return segments


# ---------------------------------------------------------------------------
# Waypoint generation strategies
# ---------------------------------------------------------------------------


def _photo_waypoints(
    segments: list[LineString],
    altitude: float,
    inverse: Transformer,
    photo_spacing_m: float,
) -> tuple[list[WaypointSchema], int]:
    """Photo waypoints plus one waypoint at every flight-line vertex.

    Adding the vertices makes the corridor outline (each flight line's shape)
    appear when the mission is exported to third-party software.
    """
    wps: list[WaypointSchema] = []
    photo_count = 0
    for idx, seg in enumerate(segments):
        reverse = idx % 2 == 1
        n = max(1, int(seg.length / photo_spacing_m))
        positions: dict[float, int] = {}
        for j in range(n):
            d = (j + 0.5) * seg.length / n
            positions[round(d, 3)] = 1
        for pt in _path_vertices(seg):
            key = round(seg.project(Point(pt)), 3)
            positions.setdefault(key, -1)
        for d in sorted(positions, reverse=reverse):
            action = positions[d]
            pt = seg.interpolate(d)
            if reverse:
                d2 = max(d - 1.0, 0.0)
            else:
                d2 = min(d + 1.0, seg.length)
            pt2 = seg.interpolate(d2)
            hdg = _polyline_local_heading((pt.x, pt.y), (pt2.x, pt2.y))
            lon, lat = inverse.transform(pt.x, pt.y)
            wps.append(WaypointSchema(latitude=lat, longitude=lon, altitude=altitude, heading=hdg, action_type=action))
            if action == 1:
                photo_count += 1
    return wps, photo_count


def _vertex_waypoints(
    segments: list[LineString],
    altitude: float,
    inverse: Transformer,
) -> list[WaypointSchema]:
    """Takeoff mode: a waypoint at every flight-line vertex (any direction change)."""
    wps: list[WaypointSchema] = []
    for idx, seg in enumerate(segments):
        coords = _path_vertices(seg)
        if idx % 2 == 1:
            coords = coords[::-1]
        n = len(coords)
        for i, (x, y) in enumerate(coords):
            hdg = _polyline_local_heading(coords[i], coords[min(i + 1, n - 1)])
            lon, lat = inverse.transform(x, y)
            wps.append(WaypointSchema(latitude=lat, longitude=lon, altitude=altitude, heading=hdg, action_type=-1))
    return wps


def _terrain_waypoints(
    segments: list[LineString],
    altitude: float,
    inverse: Transformer,
    elevation_provider: Optional[ElevationProvider],
    sample_interval_m: float,
    elevation_threshold: float,
    warnings: Optional[list[str]] = None,
) -> tuple[list[WaypointSchema], float, list[float]]:
    """Ground mode: vertex waypoints at DEM break points + flight-line vertices.

    Returns (waypoints, ref_ground, ground_elevations) where ref_ground is the
    terrain reference elevation and ground_elevations is the raw DEM sample
    list used for the conservative capture-interval footprint.
    """
    if not segments:
        return [], 0.0, []

    samples: list[tuple[float, float, float, bool]] = []  # (lat, lng, heading, forced)
    sample_pts: list[tuple[float, float]] = []
    seg_counts: list[int] = []

    for idx, seg in enumerate(segments):
        reverse = idx % 2 == 1
        n = max(2, int(seg.length / sample_interval_m))
        positions: dict[float, bool] = {}
        for j in range(n):
            d = j * seg.length / (n - 1)
            positions[round(d, 3)] = False
        for pt in _path_vertices(seg):
            key = round(seg.project(Point(pt)), 3)
            positions.setdefault(key, True)
        start = len(samples)
        for d in sorted(positions, reverse=reverse):
            forced = positions[d]
            pt = seg.interpolate(d)
            lon, lat = inverse.transform(pt.x, pt.y)
            if reverse:
                d2 = max(d - 1.0, 0.0)
            else:
                d2 = min(d + 1.0, seg.length)
            pt2 = seg.interpolate(d2)
            hdg = _polyline_local_heading((pt.x, pt.y), (pt2.x, pt2.y))
            samples.append((lat, lon, hdg, forced))
            sample_pts.append((lat, lon))
        seg_counts.append(len(samples) - start)

    elevations = elevation_provider.get_elevations(sample_pts) if elevation_provider else [0.0] * len(sample_pts)

    if not elevations or max(elevations) <= 0:
        if warnings is not None:
            warnings.append(
                "Elevation data unavailable — Ground (AGL) mode used vertex waypoints "
                "at flight-line corners instead of terrain-adjusted samples; the capture "
                "interval assumes the requested altitude since terrain relief could not "
                "be verified."
            )
        return _vertex_waypoints(segments, altitude, inverse), 0.0, elevations

    ref_ground = elevations[0]
    wps: list[WaypointSchema] = []
    base = 0
    for count in seg_counts:
        last_break_elev = elevations[base]
        for k in range(count):
            lat, lng, hdg, forced = samples[base]
            elev = elevations[base]
            adj_alt = altitude + (elev - ref_ground)
            if not forced and k != 0 and k != count - 1 and abs(elev - last_break_elev) <= elevation_threshold:
                base += 1
                continue
            wps.append(
                WaypointSchema(
                    latitude=lat,
                    longitude=lng,
                    altitude=adj_alt,
                    heading=hdg,
                    action_type=-1,
                    elevation_msnm=elev,
                    agl=altitude,
                )
            )
            base += 1
            if k != count - 1:
                last_break_elev = elev

    return wps, ref_ground, elevations


# ---------------------------------------------------------------------------
# GeoJSON output helpers
# ---------------------------------------------------------------------------


def _polygon_to_geojson(poly: Polygon, inverse: Transformer) -> dict:
    ring = [list(inverse.transform(x, y)) for x, y in poly.exterior.coords]
    return {"type": "Polygon", "coordinates": [ring]}


def _flight_lines_to_geojson(segments: list[LineString], inverse: Transformer) -> dict:
    features = []
    for i, seg in enumerate(segments):
        coords = [list(inverse.transform(x, y)) for x, y in seg.coords]
        features.append(
            {
                "type": "Feature",
                "id": f"cl_{i}",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {"type": "scan", "line": i},
            }
        )
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Main corridor entry point
# ---------------------------------------------------------------------------


def compute_corridor(req: CorridorRequest, db_session) -> CorridorResponse:
    camera = get_camera_required(db_session, req.camera_id)

    drone = None
    recommended_speed_ms = 10.0
    if req.drone_id:
        drone = db_session.query(Drone).filter(Drone.id == req.drone_id).first()

    # Shutter-limited speed (Planning Core, same rule as the area grid)
    gsd = calc_gsd(req.altitude, camera.focal_length_mm, camera.pixel_size_um)
    recommended_speed_ms = calculate_recommended_speed(
        gsd,
        camera.shutter_speed_s,
        camera.shutter_type,
        drone_max_speed_ms=drone.max_speed_ms if drone else None,
    )

    coords_geo = _extract_centerline_coords(req.centerline)
    lats = [p[1] for p in coords_geo]
    lons = [p[0] for p in coords_geo]
    center_lat = (min(lats) + max(lats)) / 2
    center_lon = (min(lons) + max(lons)) / 2

    epsg = utm_epsg_for(center_lon, center_lat)
    crs_name = CRS.from_epsg(epsg).name
    transformer = Transformer.from_crs(CRS.from_epsg(4326), CRS.from_epsg(epsg), always_xy=True)
    inverse = Transformer.from_crs(CRS.from_epsg(epsg), CRS.from_epsg(4326), always_xy=True)

    center = LineString([transformer.transform(lon, lat) for lon, lat in coords_geo])
    corridor_length = center.length
    if corridor_length < 2.0:
        raise ValueError("Centerline too short (must be at least 2 m)")

    warnings: list[str] = []

    left = _as_single_line(center.offset_curve(req.width_left, join_style="mitre", mitre_limit=2.0))
    right = _as_single_line(center.offset_curve(-req.width_right, join_style="mitre", mitre_limit=2.0))
    if left is None or right is None:
        raise ValueError("Unable to build corridor offsets (centerline self-intersects or is too tight)")

    poly = _build_corridor_polygon(left, right)
    if poly.is_empty or len(poly.exterior.coords) < 4:
        raise ValueError("Corridor footprint is invalid — use a smoother centerline or reduce widths")
    if not poly.is_valid:
        warnings.append(
            "Corridor footprint self-intersected and was repaired automatically; "
            "results may be approximate near sharp bends."
        )
    corridor_area = poly.area

    gsd = calc_gsd(req.altitude, camera.focal_length_mm, camera.pixel_size_um)
    fw, fh = calc_footprint(gsd, camera.image_width_px, camera.image_height_px)

    line_spacing_m = calculate_line_spacing(fw, req.overlap_lateral)
    photo_spacing_m = calculate_photo_spacing(fh, req.overlap_frontal)

    segments = _build_flight_segments(center, poly, req.width_left, req.width_right, line_spacing_m)
    num_lines = len(segments)
    if num_lines == 0:
        raise ValueError("Corridor is too narrow for the selected camera and overlap")

    wp_mode = {"takeoff": "vertex", "ground": "terrain"}.get(req.altitude_mode, "photo")

    elevation_provider: Optional[ElevationProvider] = None
    dem_sample_interval = 10.0
    dem_elevation_threshold = 5.0
    terrain_elevations: list[float] = []
    if wp_mode == "terrain":
        elevation_provider = create_provider()
        res = req.dem_resolution_m or 30.0
        dem_sample_interval = max(2.0, min(20.0, res * 0.67))
        dem_elevation_threshold = max(1.0, min(5.0, res * 0.17))

    if wp_mode == "photo":
        waypoints, photo_count = _photo_waypoints(segments, req.altitude, inverse, photo_spacing_m)
    elif wp_mode == "vertex":
        waypoints = _vertex_waypoints(segments, req.altitude, inverse)
        photo_count = sum(max(1, int(s.length / photo_spacing_m)) for s in segments)
    else:  # terrain
        waypoints, _, terrain_elevations = _terrain_waypoints(
            segments,
            req.altitude,
            inverse,
            elevation_provider,
            dem_sample_interval,
            dem_elevation_threshold,
            warnings,
        )
        photo_count = sum(max(1, int(s.length / photo_spacing_m)) for s in segments)

    if len(waypoints) > 200000:
        raise ValueError(
            f"Corridor too long: ~{len(waypoints)} waypoints estimated. "
            f"Increase altitude ({req.altitude}m) or reduce overlap "
            f"({req.overlap_frontal}%/{req.overlap_lateral}%)."
        )
    if len(waypoints) < 2:
        raise ValueError("Corridor too short for the selected parameters")

    # Metrics (Planning Core: UTM distance, real turn times when a turn-radius
    # plan is configured, otherwise the documented per-line overhead fallback,
    # unified battery requirements)
    turn_plan = None
    turn_radius_warnings: list[str] = []
    if getattr(req, "turn_radius", None):
        turn_plan, turn_radius_warnings = compute_turn_radius_plan(
            waypoints,
            req.turn_radius,
            mission_type="LINEAR_CORRIDOR",
            line_spacing=line_spacing_m,
            recommended_speed=recommended_speed_ms,
            flight_lines_geojson=_flight_lines_to_geojson(segments, inverse),
        )

    wps_geo_heading = [(w.longitude, w.latitude, w.heading) for w in waypoints]
    metrics = calculate_mission_metrics(
        wps_geo_heading,
        speed_mps=recommended_speed_ms,
        num_lines=num_lines,
        turn_plan=turn_plan,
        drone_flight_time_min=drone.flight_time_min if drone else None,
    )
    total_distance = metrics.total_distance_m
    estimated_time_sec = metrics.total_time_s
    battery_count = metrics.battery_count

    # Authoritative photo points (EPSG:4326)
    photo_points = photo_points_to_dicts(annotate_photo_points(waypoints, recommended_speed_ms))

    # Universal capture interval recommendation (front overlap -> photo interval)
    # Terrain-follow uses a conservative minimum footprint computed from the
    # lowest plausible AGL, so the requested front overlap is kept even where
    # the drone gets closer to the ground than the planned altitude.
    ci_agl = req.altitude
    if wp_mode == "terrain":
        ci_agl = compute_minimum_plausible_agl(
            requested_agl_m=req.altitude,
            ground_elevations=terrain_elevations if terrain_elevations else [],
        )
    gsd_ci = calc_gsd(ci_agl, camera.focal_length_mm, camera.pixel_size_um)
    _, fh_ci = calc_footprint(gsd_ci, camera.image_width_px, camera.image_height_px)

    ci = compute_capture_interval(
        footprint_length_m=fh_ci,
        front_overlap=req.overlap_frontal,
        flight_speed_mps=recommended_speed_ms,
    )

    return CorridorResponse(
        waypoints=waypoints,
        total_distance=round(total_distance, 2),
        estimated_time_sec=round(estimated_time_sec, 1),
        photo_count=photo_count,
        battery_count=battery_count,
        gsd=round(gsd, 4),
        footprint_width=round(fw, 2),
        footprint_height=round(fh, 2),
        line_spacing=round(line_spacing_m, 2),
        photo_spacing=round(photo_spacing_m, 2),
        recommended_speed_ms=round(recommended_speed_ms, 2),
        num_lines=num_lines,
        waypoint_mode=wp_mode,
        corridor_length_m=round(corridor_length, 2),
        corridor_area_m2=round(corridor_area, 2),
        geometry=CorridorGeometry(
            polygon_geojson=_polygon_to_geojson(poly, inverse),
            flight_lines_geojson=_flight_lines_to_geojson(segments, inverse),
            centerline_geojson={"type": "LineString", "coordinates": coords_geo},
            epsg_out=epsg,
            crs_name=crs_name,
            transformation=f"EPSG:4326 -> EPSG:{epsg} (pyproj/shapely projected geometry)",
        ),
        warnings=warnings,
        capture_interval=build_capture_interval_block(
            ci,
            planned_agl_m=req.altitude,
            terrain_follow=(wp_mode == "terrain"),
            assumed_agl_m=ci_agl,
            assumed_footprint_length_m=fh_ci,
        ),
        turn_radius_result=turn_plan.model_dump(mode="json") if turn_plan is not None else None,
        turn_radius_warnings=turn_radius_warnings,
        photo_points=photo_points,
    )
