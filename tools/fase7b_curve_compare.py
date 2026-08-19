"""Fase 7b: generate a CURVED_TURNS variant with turn radii and compare
against the user's Litchi-modified file (area_grid_74_time5_curve.lchm).

The exporter (after Fase 7 enum fix) writes:
    byte[7]=0x03  -> CUSTOM_POI     (personalizado, heading mode)
    byte[15]=0x01 -> CURVED_TURNS   (giros curvos, path mode)
    record +36 (f32) = curve_size in meters (turn radius)

Run from backend dir:
    python ../tools/fase7b_curve_compare.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, ".")

from app.core.database import SessionLocal
from app.modules.export import get_exporter
from app.modules.export.litchi_lchm import parse_lchm
from app.modules.planning.engine import compute_grid
from app.schemas.schemas import GridRequest

OUT_DIR = Path(__file__).resolve().parent / "lchm_exports" / "fase7b"
USER_CURVE = Path(r"C:\Users\usuario\Downloads\area_grid_74_time5_curve.lchm")

CAMERA_ID = "cam-43-20mp"
DRONE_ID = "dji-m3e"

GRID_PARAMS = dict(
    polygon={"type": "Polygon", "coordinates": [[
        [-76.4950, 3.5750], [-76.4780, 3.5750], [-76.4780, 3.5920],
        [-76.4950, 3.5920], [-76.4950, 3.5750]]]},
    altitude=100, overlap_frontal=75, overlap_lateral=65,
    drone_id=DRONE_ID, camera_id=CAMERA_ID,
)

RADIUS_M = 12.637


def to_export_wps(waypoints, radius_m: float):
    return [
        {
            "latitude": w.latitude,
            "longitude": w.longitude,
            "altitude": w.altitude,
            "heading": w.heading,
            "speed": w.speed or 0,
            "curve_size": radius_m,
        }
        for w in waypoints
    ]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    print("Planning Area Grid (74 wps)...")
    grid = compute_grid(GridRequest(**GRID_PARAMS), db)
    db.close()
    if len(grid.waypoints) != 74:
        print(f"WARNING: expected 74, got {len(grid.waypoints)}")
        return

    exporter = get_exporter("litchi_lchm")
    wps = to_export_wps(grid.waypoints, RADIUS_M)
    from app.api.v1.endpoints import _build_mission
    from app.schemas.schemas import ExportRequest
    req = ExportRequest(
        project_name="area_grid_74_time5_curve",
        waypoints=wps,
        speed=grid.recommended_speed_ms,
        altitude=100,
        options={
            "path_mode": "CURVED_TURNS",
            "heading_mode": "CUSTOM_POI",
            "photo_capture": {"mode": "TIME", "time_interval_s": 5},
        },
    )
    built = _build_mission(req)
    result = exporter.export(built)
    out = OUT_DIR / "area_grid_74_time5_curve.lchm"
    out.write_bytes(result.data)
    parsed = parse_lchm(result.data)
    print(f"  -> {out.name}  {len(result.data)} bytes, {parsed.waypoint_count} wps, "
          f"path={parsed.path_mode.name} heading={parsed.heading_mode.name}")

    user = USER_CURVE.read_bytes()
    print(f"\nUser file: {USER_CURVE}  {len(user)} bytes, {user[43]} wps")
    print(f"  byte[7]={user[7]:02x} byte[15]={user[15]:02x}")
    print(f"Ours    : byte[7]={result.data[7]:02x} byte[15]={result.data[15]:02x}")
    print("\nVerify with:")
    print("  python tools/lchm_byte_diff.py <user_curve> tools/lchm_exports/fase7b/area_grid_74_time5_curve.lchm")


if __name__ == "__main__":
    main()
