"""Fase 6: geometric round-trip validation.

Compares the mission as planned by the engine vs. the LCHM file as parsed back,
waypoint by waypoint: count, lat/lon, altitude, heading, speed, gimbal, order.
Reports the original planning metadata and the LCHM-decoded values.

Run from backend dir:
    python ../tools/fase6_validate.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, ".")

from app.core.database import SessionLocal
from app.modules.corridor.engine import compute_corridor
from app.modules.export.litchi_lchm import parse_lchm
from app.modules.planning.engine import compute_grid
from app.schemas.schemas import CorridorRequest, GridRequest

OUT = Path(__file__).resolve().parent / "lchm_exports" / "fase6"
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

def compare(plan_wps, lchm_path, label, mission_speed=None):
    print(f"\n=== {label} ===")
    data = lchm_path.read_bytes()
    parsed = parse_lchm(data)
    ok = True
    if parsed.waypoint_count != len(plan_wps):
        print(f"  COUNT: planned={len(plan_wps)} parsed={parsed.waypoint_count}  ** MISMATCH **")
        return
    print(f"  COUNT: {parsed.waypoint_count}  OK")
    print(f"  PATH MODE: {parsed.path_mode.name}   HEADING MODE: {parsed.heading_mode.name}")
    max_lat = max_alt = max_hdg = max_spd = 0.0
    for i, (p, w) in enumerate(zip(plan_wps, parsed.waypoints)):
        dlat = abs(p["latitude"] - w.latitude)
        dlon = abs(p["longitude"] - w.longitude)
        dalt = abs(p["altitude"] - w.altitude)
        dhdg = abs((p["heading"] - w.heading + 180) % 360 - 180)
        expected_spd = mission_speed if mission_speed is not None else (p.get("speed") or 0)
        dspd = abs(expected_spd - w.speed)
        max_lat = max(max_lat, dlat)
        max_alt = max(max_alt, dalt)
        max_hdg = max(max_hdg, dhdg)
        max_spd = max(max_spd, dspd)
        if dlat > 1e-6 or dlon > 1e-6 or dalt > 0.01 or dhdg > 0.01 or dspd > 0.01:
            ok = False
            print(f"  wp{i}: dlat={dlat:.2e} dlon={dlon:.2e} dalt={dalt:.3f} dhdg={dhdg:.3f} dspd={dspd:.3f}  ** MISMATCH **")
    print(f"  MAX DELTA lat={max_lat:.2e} alt={max_alt:.4f} hdg={max_hdg:.4f} spd={max_spd:.4f}")
    print(f"  GIMBAL (wp0): pitch={parsed.waypoints[0].gimbal_pitch} flag={parsed.waypoints[0].flag}")
    print(f"  RESULT: {'PASS' if ok else 'FAIL'}")
    return ok

def main() -> None:
    db = SessionLocal()
    grid = compute_grid(GridRequest(**GRID_PARAMS), db)
    corr = compute_corridor(CorridorRequest(**CORRIDOR_PARAMS), db)
    db.close()

    grid_wps = to_export_wps(grid.waypoints)
    corr_wps = to_export_wps(corr.waypoints)

    compare(grid_wps, OUT / "area_grid_74_time5.lchm", "A. Area Grid TIME=5 (74 wps)", grid.recommended_speed_ms)
    compare(corr_wps, OUT / "linear_corridor_15_time5.lchm", "B. Linear Corridor TIME=5 (15 wps)", corr.recommended_speed_ms)
    compare(grid_wps, OUT / "area_grid_dist_20_5.lchm", "C. Area Grid DISTANCE=20.5 (74 wps)", grid.recommended_speed_ms)
    compare(grid_wps, OUT / "area_grid_none.lchm", "D. Area Grid NONE (74 wps)", grid.recommended_speed_ms)

if __name__ == "__main__":
    main()
