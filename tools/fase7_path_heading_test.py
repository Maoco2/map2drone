"""Fase 7: generate controlled path/heading byte test files.

All four files share an IDENTICAL mission (same coords, altitude, speed,
heading, gimbal, capture). The ONLY bytes that differ across the set are
offset 7 (heading mode) and offset 15 (path mode).

Files (named by the actual byte values written):
    lchm_byte_00_00.lchm   heading=0x00 path=0x00
    lchm_byte_00_01.lchm   heading=0x00 path=0x01
    lchm_byte_03_00.lchm   heading=0x03 path=0x00
    lchm_byte_03_01.lchm   heading=0x03 path=0x01

Confirmed by physical Litchi test (Fase 7):
    byte[7]  = heading mode: 0x00=FOLLOW_PATH (seguir camino), 0x03=CUSTOM_POI (personalizado)
    byte[15] = path mode:    0x00=STRAIGHT (recto),           0x01=CURVED_TURNS (giros curvos)

Run from backend dir:
    python ../tools/fase7_path_heading_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, ".")

from app.modules.export import get_exporter
from app.modules.export.litchi_lchm import parse_lchm
from app.schemas.schemas import ExportRequest

OUT_DIR = Path(__file__).resolve().parent / "lchm_exports" / "fase7"

WAYPOINTS = [
    {"latitude": 3.5871270, "longitude": -76.4855905, "altitude": 60.0, "heading": 0.0, "speed": 4.1},
    {"latitude": 3.5876250, "longitude": -76.4855437, "altitude": 60.0, "heading": 90.0, "speed": 4.1},
    {"latitude": 3.5882288, "longitude": -76.4854664, "altitude": 60.0, "heading": 180.0, "speed": 4.1},
    {"latitude": 3.5889532, "longitude": -76.4853263, "altitude": 60.0, "heading": 270.0, "speed": 4.1},
    {"latitude": 3.5901015, "longitude": -76.4851629, "altitude": 60.0, "heading": 0.0, "speed": 4.1},
]


def export(project_name: str, path_mode: str, heading_mode: str, out_path: Path) -> None:
    from app.api.v1.endpoints import _build_mission
    req = ExportRequest(
        project_name=project_name,
        waypoints=WAYPOINTS,
        speed=4.1,
        altitude=60.0,
        options={
            "path_mode": path_mode,
            "heading_mode": heading_mode,
            "photo_capture": {"mode": "TIME", "time_interval_s": 5},
        },
    )
    exporter = get_exporter("litchi_lchm")
    built = _build_mission(req)
    result = exporter.export(built)
    out_path.write_bytes(result.data)
    parsed = parse_lchm(result.data)
    print(f"  -> {out_path.name}  path={path_mode:8s} heading={heading_mode:10s} "
          f"bytes[7]={result.data[7]:02x} bytes[15]={result.data[15]:02x} "
          f"parsed_path={parsed.path_mode.name} parsed_heading={parsed.heading_mode.name}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Generating path/heading byte matrix (identical mission)...")

    # byte[7]=heading (FOLLOW_PATH=0x00, CUSTOM_POI=0x03), byte[15]=path (STRAIGHT=0x00, CURVED_TURNS=0x01)
    # Filenames reflect the RAW bytes written at offset 7 and 15.
    export("byte_00_00", "STRAIGHT", "FOLLOW_PATH", OUT_DIR / "lchm_byte_00_00.lchm")
    export("byte_00_01", "CURVED_TURNS", "FOLLOW_PATH", OUT_DIR / "lchm_byte_00_01.lchm")
    export("byte_03_00", "STRAIGHT", "CUSTOM_POI", OUT_DIR / "lchm_byte_03_00.lchm")
    export("byte_03_01", "CURVED_TURNS", "CUSTOM_POI", OUT_DIR / "lchm_byte_03_01.lchm")

    print("\nDone. Verify byte diffs with:")
    print("  python tools/lchm_byte_diff.py tools/lchm_exports/fase7/lchm_byte_00_01.lchm"
          " tools/lchm_exports/fase7/lchm_byte_03_01.lchm")


if __name__ == "__main__":
    main()
