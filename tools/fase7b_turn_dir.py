"""Fase 7b: determine if the alternating +7 flag correlates with turn direction."""
from __future__ import annotations

import pathlib
import struct

CURVE = pathlib.Path(r"C:\Users\usuario\Downloads\area_grid_74_time5_curve.lchm")

def rec(d: bytes, i: int) -> bytes:
    return d[44 + i * 56: 100 + i * 56]

def main() -> None:
    d = CURVE.read_bytes()
    n = d[43]
    lats, lons = [], []
    for i in range(n):
        r = rec(d, i)
        lats.append(struct.unpack(">d", r[20:28])[0])
        lons.append(struct.unpack(">d", r[28:36])[0])

    print("wp | flag | +36    | bearing_in | bearing_out | turn_delta | turn_dir | 90deg-ish | 180deg turn")
    print("-" * 110)

    import math
    def bearing(a, b):
        dy = lats[b] - lats[a]
        dx = lons[b] - lons[a]
        return math.degrees(math.atan2(dx, dy)) % 360

    for i in range(n):
        r = rec(d, i)
        flag = struct.unpack(">i", r[4:8])[0]
        r36 = struct.unpack(">f", r[36:40])[0]
        b_in = bearing(i - 1, i) if i > 0 else float("nan")
        b_out = bearing(i, i + 1) if i < n - 1 else float("nan")
        delta = (b_out - b_in + 540) % 360 - 180 if i > 0 and i < n - 1 else float("nan")
        is_90 = abs(abs(delta) - 90) < 2 if not math.isnan(delta) else False
        is_180 = abs(abs(delta) - 180) < 2 if not math.isnan(delta) else False
        turn_dir = "R" if (not math.isnan(delta) and delta > 0) else (
            "L" if not math.isnan(delta) else "-")
        print(f"{i:2d} | 0x{flag:08x} | {r36:7.3f} | {b_in:9.1f} | {b_out:9.1f} | "
              f"{delta:8.1f} | {turn_dir} | {is_90} | {is_180}")

if __name__ == "__main__":
    main()
