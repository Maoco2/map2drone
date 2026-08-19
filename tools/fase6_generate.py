"""Fase 6: generate LCHM files through the real Map2Drone pipeline.

Uses the actual planning engine (compute_grid / compute_corridor) and the
actual LCHM exporter (get_exporter("litchi_lchm")) — the same code paths the
API uses. No fixture reuse, no manual byte edits.

Produces (in tools/lchm_exports/fase6/):
    A  area_grid_74_time5.lchm        Area Grid, 74 wps,  TIME = 5
    B  linear_corridor_15_time5.lchm  Linear Corridor, 15 wps, TIME = 5
    C  area_grid_dist_20_5.lchm       Area Grid,        DISTANCE = 20.5 m
    D  area_grid_none.lchm            Area Grid,        NONE
    T1..T6  area_grid_time{1..6}.lchm  Area Grid, TIME = 1..6

Run from the backend directory so the SQLite path resolves:
    python ../tools/fase6_generate.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, ".")

from app.core.database import SessionLocal
from app.modules.corridor.engine import compute_corridor
from app.modules.export import get_exporter
from app.modules.export.litchi_lchm import parse_lchm
from app.modules.planning.engine import compute_grid
from app.schemas.schemas import CorridorRequest, GridRequest

OUT_DIR = Path(__file__).resolve().parent / "lchm_exports" / "fase6"

CAMERA_ID = "cam-43-20mp"
DRONE_ID = "dji-m3e"

GRID_PARAMS = dict(
    polygon={"type": "Polygon", "coordinates": [[
        [-76.4950, 3.5750], [-76.4780, 3.5750], [-76.4780, 3.5920],
        [-76.4950, 3.5920], [-76.4950, 3.5750]]]},
    altitude=100, overlap_frontal=75, overlap_lateral=65,
    drone_id=DRONE_ID, camera_id=CAMERA_ID,
)

CORRIDOR_PARAMS = dict(
    centerline={"type": "LineString", "coordinates": [
        [-76.4950, 3.5750],
        [-76.4850, 3.5750],
        [-76.4750 + 0.01 * math.cos(math.radians(30)), 3.5750 + 0.01 * math.sin(math.radians(30))],
    ]},
    width_left=120, width_right=120, altitude=100,
    overlap_frontal=75, overlap_lateral=65,
    drone_id=DRONE_ID, camera_id=CAMERA_ID,
)


def to_export_wps(waypoints):
    return [
        {
            "latitude": w.latitude,
            "longitude": w.longitude,
            "altitude": w.altitude,
            "heading": w.heading,
            "speed": w.speed or 0,
        }
        for w in waypoints
    ]


def export_lchm(project_name: str, waypoints: list[dict], speed_ms: float,
                photo_capture: dict, out_path: Path) -> int:
    exporter = get_exporter("litchi_lchm")
    mission = {
        "project_name": project_name,
        "waypoints": waypoints,
        "speed": speed_ms,
        "altitude": 100,
        "options": {
            "path_mode": "STRAIGHT",
            "heading_mode": "FOLLOW_PATH",
            "photo_capture": photo_capture,
        },
    }
    # Build via the real exporter through the same MissionExportData the API builds.
    from app.api.v1.endpoints import _build_mission
    from app.schemas.schemas import ExportRequest
    req = ExportRequest(**mission)
    built = _build_mission(req)
    result = exporter.export(built)
    out_path.write_bytes(result.data)
    parsed = parse_lchm(result.data)
    print(f"  -> {out_path.name}  {len(result.data)} bytes, {parsed.waypoint_count} waypoints, "
          f"path={parsed.path_mode.name} heading={parsed.heading_mode.name}")
    return len(result.data)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()

    print("Planning Area Grid (74 wps)...")
    grid = compute_grid(GridRequest(**GRID_PARAMS), db)
    grid_wps = to_export_wps(grid.waypoints)
    print(f"  {len(grid_wps)} waypoints, {grid.num_lines} lines, speed={grid.recommended_speed_ms:.2f}")
    if len(grid_wps) != 74:
        print(f"  WARNING: expected 74, got {len(grid_wps)}")

    print("Planning Linear Corridor (15 wps)...")
    corr = compute_corridor(CorridorRequest(**CORRIDOR_PARAMS), db)
    corr_wps = to_export_wps(corr.waypoints)
    print(f"  {len(corr_wps)} waypoints, {corr.num_lines} lines, speed={corr.recommended_speed_ms:.2f}")
    if len(corr_wps) != 15:
        print(f"  WARNING: expected 15, got {len(corr_wps)}")

    print("\n=== A: Area Grid TIME=5 ===")
    export_lchm("area_grid_74_time5", grid_wps, grid.recommended_speed_ms,
                {"mode": "TIME", "time_interval_s": 5}, OUT_DIR / "area_grid_74_time5.lchm")

    print("\n=== B: Linear Corridor TIME=5 ===")
    export_lchm("linear_corridor_15_time5", corr_wps, corr.recommended_speed_ms,
                {"mode": "TIME", "time_interval_s": 5}, OUT_DIR / "linear_corridor_15_time5.lchm")

    print("\n=== C: Area Grid DISTANCE=20.5 ===")
    export_lchm("area_grid_dist_20_5", grid_wps, grid.recommended_speed_ms,
                {"mode": "DISTANCE", "distance_interval_m": 20.5}, OUT_DIR / "area_grid_dist_20_5.lchm")

    print("\n=== D: Area Grid NONE ===")
    export_lchm("area_grid_none", grid_wps, grid.recommended_speed_ms,
                {"mode": "NONE"}, OUT_DIR / "area_grid_none.lchm")

    print("\n=== T1..T6: Area Grid TIME=1..6 ===")
    for t in range(1, 7):
        export_lchm(f"area_grid_time{t}", grid_wps, grid.recommended_speed_ms,
                    {"mode": "TIME", "time_interval_s": t}, OUT_DIR / f"area_grid_time{t}.lchm")

    db.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
