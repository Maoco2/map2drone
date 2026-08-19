"""LCHM binary inspector / reverse-engineering tool.

Usage:
    python tools/lchm_inspector.py inspect <file.lchm> [--hex]

Shows structural info (magic, sizes, modes, waypoint records, trailer)
and optionally a grouped hex dump (HEADER / WAYPOINTS / TRAILER).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.modules.export.litchi_lchm import (
    LCHM_HEADER_SIZE,
    LCHM_WAYPOINT_RECORD_SIZE,
    parse_lchm,
)


def hex_dump(data: bytes, base_offset: int = 0, width: int = 16) -> list[str]:
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        hex_part = hex_part.ljust(width * 3 - 1)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"  {base_offset + i:04x}  {hex_part}  |{ascii_part}|")
    return lines


def inspect_file(path: Path, show_hex: bool) -> None:
    data = path.read_bytes()
    mission = parse_lchm(data)
    n_wps = mission.waypoint_count
    records_len = n_wps * LCHM_WAYPOINT_RECORD_SIZE
    trailer_offset = LCHM_HEADER_SIZE + records_len
    trailer_size = len(data) - trailer_offset

    print(f"File:         {path.name}")
    print(f"Magic:        {data[0:4].decode('latin1')}")
    print(f"File size:    {len(data)}")
    print(f"Header:       {LCHM_HEADER_SIZE}")
    print(f"Waypoints:    {n_wps}")
    print(f"Record size:  {LCHM_WAYPOINT_RECORD_SIZE}")
    print(f"Path Mode:    {mission.path_mode.name}")
    print(f"Heading Mode: {mission.heading_mode.name}")
    print(f"Trailer offset: {trailer_offset}")
    print(f"Trailer size:   {trailer_size}")
    print()

    print("Waypoint offsets:")
    for i in range(n_wps):
        print(f"  wp{i:03d}  offset {LCHM_HEADER_SIZE + i * LCHM_WAYPOINT_RECORD_SIZE}")
    print()

    print("Waypoint decoded values:")
    for i, wp in enumerate(mission.waypoints):
        print(
            f"  wp{i:03d}  lat={wp.latitude:+.7f} lon={wp.longitude:+.7f} "
            f"alt={wp.altitude:7.1f} hdg={wp.heading:7.1f} spd={wp.speed:5.1f} "
            f"gimbal={wp.gimbal_pitch:4d} flag={wp.flag} radius={wp.curve_radius_m:8.3f}"
        )
    print()

    if show_hex:
        print("=== HEADER ===")
        for line in hex_dump(data[:LCHM_HEADER_SIZE]):
            print(line)
        print()
        print("=== WAYPOINTS ===")
        for i in range(n_wps):
            start = LCHM_HEADER_SIZE + i * LCHM_WAYPOINT_RECORD_SIZE
            end = start + LCHM_WAYPOINT_RECORD_SIZE
            print(f"wp{i:03d}:")
            for line in hex_dump(data[start:end], base_offset=start):
                print(line)
            print()
        if trailer_size > 0:
            print("=== TRAILER ===")
            for line in hex_dump(data[trailer_offset:], base_offset=trailer_offset):
                print(line)
        else:
            print("=== TRAILER === (none)")


def main() -> None:
    parser = argparse.ArgumentParser(description="LCHM binary inspector")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("inspect", help="inspect a .lchm file")
    cmd.add_argument("file", help="path to .lchm file")
    cmd.add_argument("--hex", action="store_true", help="show grouped hex dump")
    args = parser.parse_args()

    if args.command == "inspect":
        inspect_file(Path(args.file), args.hex)


if __name__ == "__main__":
    main()
