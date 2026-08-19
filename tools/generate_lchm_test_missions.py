"""Generates the three validation missions and exports them as LCHM.

Produces:
    tools/lchm_exports/test_area_grid_litchi.lchm
    tools/lchm_exports/test_linear_corridor_litchi.lchm
    tools/lchm_exports/test_small_litchi.lchm

Run from the backend directory so the SQLite path resolves:
    python ../tools/generate_lchm_test_missions.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, ".")

from app.core.database import SessionLocal
from app.modules.corridor.engine import compute_corridor
from app.modules.export import get_exporter
from app.modules.export.litchi_lchm import parse_lchm
from app.modules.export.models import ExportWaypoint, MissionExportData
from app.modules.planning.engine import compute_grid
from app.schemas.schemas import CorridorRequest, GridRequest

OUT_DIR = Path(__file__).resolve().parent / "lchm_exports"

CAMERA_ID = "cam-43-20mp"
DRONE_ID = "dji-m3e"


def to_export_wps(waypoints):
    return [
        ExportWaypoint(
            latitude=w.latitude,
            longitude=w.longitude,
            altitude=w.altitude,
            heading=w.heading,
            speed=w.speed or 0,
        )
        for w in waypoints
    ]


def export_lchm(mission: MissionExportData, out_path: Path) -> None:
    exporter = get_exporter("litchi_lchm")
    result = exporter.export(mission)
    out_path.write_bytes(result.data)
    parsed = parse_lchm(result.data)
    print(f"  -> {out_path.name}  {len(result.data)} bytes, {parsed.waypoint_count} waypoints, "
          f"path={parsed.path_mode.name} heading={parsed.heading_mode.name}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()

    # ── TEST A — AREA GRID ────────────────────────────────────────────────
    print("TEST A — Area Grid (>=4 lines, >=20 waypoints)")
    poly = {
        "type": "Polygon",
        "coordinates": [[
            [-76.4950, 3.5750],
            [-76.4780, 3.5750],
            [-76.4780, 3.5920],
            [-76.4950, 3.5920],
            [-76.4950, 3.5750],
        ]],
    }
    grid = compute_grid(GridRequest(
        polygon=poly, altitude=100, overlap_frontal=75, overlap_lateral=65,
        drone_id=DRONE_ID, camera_id=CAMERA_ID,
    ), db)
    n_wps = len(grid.waypoints)
    assert n_wps >= 20, f"grid produced only {n_wps} waypoints"
    assert grid.num_lines >= 4, f"grid produced only {grid.num_lines} lines"
    mission_a = MissionExportData(
        project_name="test_area_grid",
        waypoints=to_export_wps(grid.waypoints),
        speed_ms=grid.recommended_speed_ms,
        options={"path_mode": "STRAIGHT", "heading_mode": "FOLLOW_PATH"},
    )
    export_lchm(mission_a, OUT_DIR / "test_area_grid_litchi.lchm")
    print(f"  {n_wps} waypoints, {grid.num_lines} lines")

    # ── TEST B — LINEAR CORRIDOR ──────────────────────────────────────────
    print("TEST B — Linear Corridor (>=3 lines, out-and-back)")
    centerline = {
        "type": "LineString",
        "coordinates": [[-76.4950, 3.5750], [-76.4800, 3.5820], [-76.4620, 3.5900]],
    }
    corr = compute_corridor(CorridorRequest(
        centerline=centerline, width_left=120, width_right=120, altitude=100,
        overlap_frontal=75, overlap_lateral=65,
        drone_id=DRONE_ID, camera_id=CAMERA_ID,
    ), db)
    n_wps = len(corr.waypoints)
    mission_b = MissionExportData(
        project_name="test_linear_corridor",
        waypoints=to_export_wps(corr.waypoints),
        speed_ms=corr.recommended_speed_ms,
        options={"path_mode": "STRAIGHT", "heading_mode": "FOLLOW_PATH"},
    )
    export_lchm(mission_b, OUT_DIR / "test_linear_corridor_litchi.lchm")
    print(f"  {n_wps} waypoints")

    # ── TEST C — SMALL ────────────────────────────────────────────────────
    print("TEST C — Small (3-5 waypoints, manual inspection)")
    small = [
        ExportWaypoint(latitude=3.5871270, longitude=-76.4855905, altitude=60.0, heading=0.0, speed=4.1),
        ExportWaypoint(latitude=3.5876250, longitude=-76.4855437, altitude=60.0, heading=90.0, speed=4.1),
        ExportWaypoint(latitude=3.5882288, longitude=-76.4854664, altitude=60.0, heading=180.0, speed=4.1),
        ExportWaypoint(latitude=3.5889532, longitude=-76.4853263, altitude=60.0, heading=270.0, speed=4.1),
        ExportWaypoint(latitude=3.5901015, longitude=-76.4851629, altitude=60.0, heading=0.0, speed=4.1),
    ]
    mission_c = MissionExportData(
        project_name="test_small",
        waypoints=small,
        speed_ms=4.1,
        options={"path_mode": "STRAIGHT", "heading_mode": "FOLLOW_PATH"},
    )
    export_lchm(mission_c, OUT_DIR / "test_small_litchi.lchm")
    print(f"  {len(small)} waypoints")

    db.close()


if __name__ == "__main__":
    main()