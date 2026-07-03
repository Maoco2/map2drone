"""
Map2Drone Planning Engine
Polygon-aware lawnmower algorithm with optimal sweep angle.
Flight lines are clipped to the polygon boundary and the sweep
angle is optimized to minimize total flight time.
Supports terrain-follow (AGL) altitude mode via SRTM DEM.
"""

import math
from typing import Sequence, Optional
from app.schemas.schemas import GridRequest, GridResponse, WaypointSchema, GSDRequest, GSDResponse
from app.models.schemas import Camera, Drone
from app.modules.planning.elevation import ElevationProvider, create_provider


# ---------------------------------------------------------------------------
# Camera helpers
# ---------------------------------------------------------------------------

def _get_camera(db_session, camera_id: str) -> Camera | None:
    return db_session.query(Camera).filter(Camera.id == camera_id).first()


def calc_gsd(altitude_m: float, focal_length_mm: float, pixel_size_um: float) -> float:
    return (altitude_m * pixel_size_um) / (focal_length_mm * 10)


def calc_footprint(gsd: float, image_width_px: int, image_height_px: int) -> tuple[float, float]:
    return gsd * image_width_px / 100, gsd * image_height_px / 100


def compute_gsd(req: GSDRequest, db_session) -> GSDResponse:
    camera = _get_camera(db_session, req.camera_id)
    if not camera:
        raise ValueError("Camera not found")
    gsd = calc_gsd(req.altitude, camera.focal_length_mm, camera.pixel_size_um)
    fw, fh = calc_footprint(gsd, camera.image_width_px, camera.image_height_px)
    return GSDResponse(gsd=round(gsd, 4), footprint_width=round(fw, 2), footprint_height=round(fh, 2))


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def _extract_polygon_coords(polygon: dict) -> list[list[float]]:
    raw = polygon.get("coordinates", [[]])[0]
    if not isinstance(raw, list):
        raise ValueError("Invalid polygon coordinates format")
    coords: list[list[float]] = []
    for p in raw:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            coords.append([float(p[0]), float(p[1])])
    if len(coords) < 3:
        raise ValueError("Polygon must have at least 3 valid coordinate pairs")
    return coords


def _lnglat_to_meters(coords: Sequence[Sequence[float]], center_lat: float, center_lon: float) -> list[list[float]]:
    deg_to_m = 111320.0
    cos_clat = math.cos(math.radians(center_lat))
    result = []
    for lng, lat in coords:
        dx = (lng - center_lon) * deg_to_m * cos_clat
        dy = (lat - center_lat) * deg_to_m
        result.append([dx, dy])
    return result


def _meters_to_lnglat(coords_m: Sequence[Sequence[float]], center_lat: float, center_lon: float) -> list[list[float]]:
    deg_to_m = 111320.0
    cos_clat = math.cos(math.radians(center_lat))
    result = []
    for x, y in coords_m:
        lng = x / (deg_to_m * cos_clat) + center_lon
        lat = y / deg_to_m + center_lat
        result.append([lng, lat])
    return result


def _rotate_points(points: Sequence[Sequence[float]], angle_deg: float) -> list[list[float]]:
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return [[x * c - y * s, x * s + y * c] for x, y in points]


# ---------------------------------------------------------------------------
# Line-polygon intersection (horizontal scan lines in local frame)
# ---------------------------------------------------------------------------

def _horizontal_segments_inside(polygon_m: Sequence[Sequence[float]], y: float) -> list[tuple[float, float]]:
    """Return (x_start, x_end) pairs where a horizontal line at *y* is inside *polygon_m*."""
    xs: list[float] = []
    n = len(polygon_m)
    for i in range(n):
        x1, y1 = polygon_m[i]
        x2, y2 = polygon_m[(i + 1) % n]

        if abs(y2 - y1) < 1e-12:
            if abs(y - y1) < 1e-9:
                xs.append(x1)
                xs.append(x2)
            continue

        if (y1 <= y <= y2) or (y2 <= y <= y1):
            t = (y - y1) / (y2 - y1)
            x = x1 + t * (x2 - x1)
            xs.append(x)

    if len(xs) < 2:
        return []

    xs.sort()
    unique = [xs[0]]
    for x in xs[1:]:
        if abs(x - unique[-1]) > 1e-9:
            unique.append(x)
    return [(unique[i], unique[i + 1]) for i in range(0, len(unique) - 1, 2)]


# ---------------------------------------------------------------------------
# Optimal sweep angle
# ---------------------------------------------------------------------------

def _estimate_total_distance(
    polygon_m: Sequence[Sequence[float]],
    angle_deg: float,
    line_spacing_m: float,
    photo_spacing_m: float,
) -> float:
    """Quick distance estimate for a given sweep angle (used during optimisation)."""
    rot = _rotate_points(polygon_m, -angle_deg)
    ys = [p[1] for p in rot]
    min_y, max_y = min(ys), max(ys)
    range_y = max_y - min_y
    if range_y < 1e-6:
        return 0.0

    num_lines = max(2, int(range_y / line_spacing_m))
    total = 0.0
    prev_end: tuple[float, float] | None = None

    for i in range(num_lines):
        y = min_y + (i + 0.5) / num_lines * range_y
        segs = _horizontal_segments_inside(rot, y)
        if not segs:
            continue

        seg = segs[0]
        seg_len = seg[1] - seg[0]
        if seg_len < photo_spacing_m:
            continue

        if i % 2 == 0:
            sx, ex = seg[0], seg[1]
        else:
            sx, ex = seg[1], seg[0]

        total += abs(ex - sx)
        if prev_end is not None:
            dx = sx - prev_end[0]
            dy = y - prev_end[1]
            total += math.sqrt(dx * dx + dy * dy)
        prev_end = (ex, y)

    return total


def _find_optimal_angle(
    polygon_m: Sequence[Sequence[float]],
    line_spacing_m: float,
    photo_spacing_m: float,
) -> float:
    """Brute-force search for sweep angle that minimises flight distance."""
    candidates = list(range(0, 180, 10))  # coarse
    best_angle = 0.0
    best_dist = float("inf")
    for a in candidates:
        d = _estimate_total_distance(polygon_m, a, line_spacing_m, photo_spacing_m)
        if d < best_dist:
            best_dist = d
            best_angle = float(a)

    return best_angle


# ---------------------------------------------------------------------------
# Main grid algorithm
# ---------------------------------------------------------------------------

def _point_inside_polygon(x: float, y: float, polygon: Sequence[Sequence[float]]) -> bool:
    """Ray casting test."""
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


# ---------------------------------------------------------------------------
# Scan line segment computation
# ---------------------------------------------------------------------------

def _compute_line_segments(
    poly_m: list[list[float]], sweep_deg: float,
    line_spacing_m: float, photo_spacing_m: float,
    center_lat: float, center_lon: float,
) -> tuple[list[dict], int]:
    """Compute scan line segments (entry/exit) for a given sweep angle.

    Returns (segments, num_lines) where each segment dict contains:
      entry_lat, entry_lng, exit_lat, exit_lng, heading, seg_len,
      num_photos, y_rot, entry_x_rot, exit_x_rot.
    """
    poly_rot = _rotate_points(poly_m, -sweep_deg)
    ys = [p[1] for p in poly_rot]
    min_y, max_y = min(ys), max(ys)
    range_y = max_y - min_y
    num_lines = max(2, int(range_y / line_spacing_m))
    segments: list[dict] = []

    for i in range(num_lines):
        y = min_y + (i + 0.5) / num_lines * range_y
        segs = _horizontal_segments_inside(poly_rot, y)
        if not segs:
            continue
        seg = segs[0]
        seg_len = abs(seg[1] - seg[0])
        num_photos = max(1, int(seg_len / photo_spacing_m)) if seg_len >= photo_spacing_m else 0
        if seg_len < 1:
            continue

        if i % 2 == 0:
            entry_x, exit_x = seg[0], seg[1]
        else:
            entry_x, exit_x = seg[1], seg[0]

        entry_x_m, entry_y_m = _rotate_points([[entry_x, y]], sweep_deg)[0]
        entry_lng, entry_lat = _meters_to_lnglat([[entry_x_m, entry_y_m]], center_lat, center_lon)[0]
        exit_x_m, exit_y_m = _rotate_points([[exit_x, y]], sweep_deg)[0]
        exit_lng, exit_lat = _meters_to_lnglat([[exit_x_m, exit_y_m]], center_lat, center_lon)[0]

        heading = (90 - sweep_deg) % 360 if i % 2 == 0 else (90 - sweep_deg + 180) % 360

        segments.append({
            "i": i,
            "entry_lat": entry_lat, "entry_lng": entry_lng,
            "exit_lat": exit_lat, "exit_lng": exit_lng,
            "heading": heading,
            "seg_len": seg_len,
            "num_photos": num_photos,
            "y_rot": y,
            "entry_x_rot": entry_x,
            "exit_x_rot": exit_x,
        })

    return segments, num_lines


# ---------------------------------------------------------------------------
# Waypoint generation strategies
# ---------------------------------------------------------------------------

def _photo_waypoints_from_segments(
    segments: list[dict], sweep_deg: float, altitude: float,
    center_lat: float, center_lon: float,
    min_spacing_m: float = 0,
) -> list[WaypointSchema]:
    """Legacy mode: one waypoint per photo position."""
    wps: list[WaypointSchema] = []
    for seg in segments:
        n = seg["num_photos"]
        if n < 1:
            continue
        for j in range(n):
            frac = (j + 0.5) / n
            x_rot = seg["entry_x_rot"] + frac * (seg["exit_x_rot"] - seg["entry_x_rot"])
            x_m, y_m = _rotate_points([[x_rot, seg["y_rot"]]], sweep_deg)[0]
            lng, lat = _meters_to_lnglat([[x_m, y_m]], center_lat, center_lon)[0]
            if min_spacing_m > 0 and wps:
                dx = (lng - wps[-1].longitude) * 111320 * math.cos(math.radians(lat))
                dy = (lat - wps[-1].latitude) * 111320
                if math.sqrt(dx * dx + dy * dy) < min_spacing_m:
                    continue
            wps.append(WaypointSchema(
                latitude=lat, longitude=lng,
                altitude=altitude, heading=seg["heading"],
                action_type=1,
            ))
    return wps


def _vertex_waypoints_from_segments(
    segments: list[dict], altitude: float,
) -> list[WaypointSchema]:
    """Takeoff mode: two waypoints per scan line (entry + exit). No photo actions."""
    wps: list[WaypointSchema] = []
    for seg in segments:
        wps.append(WaypointSchema(
            latitude=seg["entry_lat"], longitude=seg["entry_lng"],
            altitude=altitude, heading=seg["heading"],
            action_type=-1,
        ))
        wps.append(WaypointSchema(
            latitude=seg["exit_lat"], longitude=seg["exit_lng"],
            altitude=altitude, heading=seg["heading"],
            action_type=-1,
        ))
    return wps


def _terrain_waypoints_from_segments(
    segments: list[dict], sweep_deg: float, altitude: float,
    center_lat: float, center_lon: float,
    elevation_provider: Optional[ElevationProvider] = None,
    sample_interval_m: float = 10,
    elevation_threshold: float = 5,
    min_spacing_m: float = 0,
    ref_ground: Optional[float] = None,
) -> tuple[list[WaypointSchema], float]:
    """Ground mode: vertex waypoints + additional waypoints at DEM break points.

    Returns (waypoints, ref_ground) where ref_ground is the elevation used
    as the terrain reference for altitude calculation.
    """
    if not segments:
        return [], ref_ground or 0.0

    dem_samples: list[tuple[float, float, float]] = []

    for seg in segments:
        n = max(2, int(seg["seg_len"] / sample_interval_m))
        for j in range(n):
            frac = j / (n - 1)
            x_rot = seg["entry_x_rot"] + frac * (seg["exit_x_rot"] - seg["entry_x_rot"])
            x_m, y_m = _rotate_points([[x_rot, seg["y_rot"]]], sweep_deg)[0]
            lng, lat = _meters_to_lnglat([[x_m, y_m]], center_lat, center_lon)[0]
            dem_samples.append((lat, lng, seg["heading"]))

    pts = [(lat, lng) for lat, lng, _ in dem_samples]
    elevations = elevation_provider.get_elevations(pts) if elevation_provider else [0.0] * len(pts)

    if not elevations or max(elevations) <= 0:
        return _vertex_waypoints_from_segments(segments, altitude), ref_ground or 0.0

    if ref_ground is None:
        ref_ground = elevations[0]

    wps: list[WaypointSchema] = []
    sample_idx = 0

    for seg_idx, seg in enumerate(segments):
        n = max(2, int(seg["seg_len"] / sample_interval_m))
        last_break_elev = elevations[sample_idx]

        for j in range(n):
            lat, lng, hdg = dem_samples[sample_idx]
            elev = elevations[sample_idx]
            adj_alt = max(10, altitude + (elev - ref_ground))
            sample_idx += 1

            should_add = (j == 0 or j == n - 1 or abs(elev - last_break_elev) > elevation_threshold)
            if not should_add:
                continue

            if min_spacing_m > 0 and wps:
                dx = (lng - wps[-1].longitude) * 111320 * math.cos(math.radians(lat))
                dy = (lat - wps[-1].latitude) * 111320
                if math.sqrt(dx * dx + dy * dy) < min_spacing_m:
                    if j != 0 and j != n - 1:
                        last_break_elev = elev
                    continue

            wps.append(WaypointSchema(
                latitude=lat, longitude=lng,
                altitude=adj_alt, heading=hdg,
                action_type=-1,
            ))
            if j != n - 1:
                last_break_elev = elev

    return wps, ref_ground


# ---------------------------------------------------------------------------
# Main grid entry point
# ---------------------------------------------------------------------------

def compute_grid(req: GridRequest, db_session) -> GridResponse:
    camera = _get_camera(db_session, req.camera_id)
    if not camera:
        raise ValueError("Camera not found")

    drone = None
    recommended_speed_ms = 10.0
    if req.drone_id:
        drone = db_session.query(Drone).filter(Drone.id == req.drone_id).first()

    # Shutter-limited speed
    gsd_m = calc_gsd(req.altitude, camera.focal_length_mm, camera.pixel_size_um) / 100
    shutter_factor = 1.0 if camera.shutter_type == "mechanical" else 0.5
    v_shutter = gsd_m / (2.0 * camera.shutter_speed_s) * shutter_factor
    recommended_speed_ms = v_shutter
    if drone and drone.max_speed_ms:
        recommended_speed_ms = min(v_shutter, drone.max_speed_ms)

    # 1. Polygon in geographic coords
    poly_geo = _extract_polygon_coords(req.polygon)

    gsd = calc_gsd(req.altitude, camera.focal_length_mm, camera.pixel_size_um)
    fw, fh = calc_footprint(gsd, camera.image_width_px, camera.image_height_px)

    overlap_lat = req.overlap_lateral / 100
    overlap_frt = req.overlap_frontal / 100

    line_spacing_m = fw * (1 - overlap_lat)
    photo_spacing_m = fh * (1 - overlap_frt)

    # 2. Convert to local metres
    lats = [p[1] for p in poly_geo]
    lons = [p[0] for p in poly_geo]
    center_lat = (min(lats) + max(lats)) / 2
    center_lon = (min(lons) + max(lons)) / 2
    poly_m = _lnglat_to_meters(poly_geo, center_lat, center_lon)

    # 3. Find sweep angle
    sweep_deg = req.rotation_deg if req.rotation_deg is not None else _find_optimal_angle(poly_m, line_spacing_m, photo_spacing_m)

    # 3b. For cross grid, generate both angles
    angle_a = sweep_deg
    angle_b = sweep_deg + 90 if req.grid_type == "cross" else None

    segments_a, lines_a = _compute_line_segments(
        poly_m, angle_a, line_spacing_m, photo_spacing_m, center_lat, center_lon,
    )
    all_segments = list(segments_a)
    total_lines = lines_a

    if angle_b is not None:
        segments_b, lines_b = _compute_line_segments(
            poly_m, angle_b, line_spacing_m, photo_spacing_m, center_lat, center_lon,
        )
        all_segments.extend(segments_b)
        total_lines += lines_b

    # 4. Determine waypoint mode from altitude_mode
    wp_mode = {"takeoff": "vertex", "ground": "terrain"}.get(req.altitude_mode, "photo")

    # 4b. Create elevation provider for terrain mode
    elevation_provider: Optional[ElevationProvider] = None
    dem_sample_interval = 10.0
    dem_elevation_threshold = 5.0
    if wp_mode == "terrain":
        elevation_provider = create_provider()
        # SRTM ~30m: sample every 20m, threshold 5m
        res = req.dem_resolution_m or 30.0
        dem_sample_interval = max(2.0, min(20.0, res * 0.67))
        dem_elevation_threshold = max(1.0, min(5.0, res * 0.17))

    # 5. Generate waypoints
    min_wp_spacing = line_spacing_m
    if wp_mode == "photo":
        waypoints = _photo_waypoints_from_segments(segments_a, angle_a, req.altitude, center_lat, center_lon,
                                                     min_spacing_m=min_wp_spacing)
        if angle_b is not None:
            waypoints_b = _photo_waypoints_from_segments(segments_b, angle_b, req.altitude, center_lat, center_lon,
                                                          min_spacing_m=min_wp_spacing)
            waypoints.extend(waypoints_b)
        photo_count = len(waypoints)
    elif wp_mode == "vertex":
        waypoints = _vertex_waypoints_from_segments(segments_a, req.altitude)
        if angle_b is not None:
            waypoints_b = _vertex_waypoints_from_segments(segments_b, req.altitude)
            waypoints.extend(waypoints_b)
        photo_count = sum(s["num_photos"] for s in all_segments)
    else:  # "terrain"
        waypoints, ref_ground = _terrain_waypoints_from_segments(segments_a, angle_a, req.altitude, center_lat, center_lon,
                                                                   elevation_provider=elevation_provider,
                                                                   sample_interval_m=dem_sample_interval,
                                                                   elevation_threshold=dem_elevation_threshold,
                                                                   min_spacing_m=min_wp_spacing)
        if angle_b is not None:
            waypoints_b, _ = _terrain_waypoints_from_segments(segments_b, angle_b, req.altitude, center_lat, center_lon,
                                                               elevation_provider=elevation_provider,
                                                               sample_interval_m=dem_sample_interval,
                                                               elevation_threshold=dem_elevation_threshold,
                                                               min_spacing_m=min_wp_spacing,
                                                               ref_ground=ref_ground)
            waypoints.extend(waypoints_b)
        photo_count = sum(s["num_photos"] for s in all_segments)

    # Validate
    approx_wp = len(waypoints)
    if approx_wp > 200000:
        raise ValueError(
            f"Area too large: ~{approx_wp} waypoints estimated. "
            f"Increase altitude ({req.altitude}m) or reduce overlap "
            f"({req.overlap_frontal}%/{req.overlap_lateral}%)."
        )
    if len(waypoints) < 2:
        raise ValueError("Polygon too small for the selected parameters")

    # 6. Compute metrics
    total_distance = 0.0
    for k in range(1, len(waypoints)):
        dx = (waypoints[k].longitude - waypoints[k - 1].longitude) * 111320 * math.cos(math.radians(waypoints[k].latitude))
        dy = (waypoints[k].latitude - waypoints[k - 1].latitude) * 111320
        total_distance += math.sqrt(dx * dx + dy * dy)

    estimated_time_sec = total_distance / recommended_speed_ms + total_lines * 5
    battery_minutes = 25
    battery_count = max(1, math.ceil(estimated_time_sec / 60 / battery_minutes))

    return GridResponse(
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
        sweep_deg=round(sweep_deg, 1),
        num_lines=total_lines,
        waypoint_mode=wp_mode,
    )
