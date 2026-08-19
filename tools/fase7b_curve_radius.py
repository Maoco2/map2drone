"""Fase 7b: correlate flag/+36 with headings in both files."""
from __future__ import annotations

import pathlib
import struct

CURVE = pathlib.Path(r"C:\Users\usuario\Downloads\area_grid_74_time5_curve.lchm")
STRAIGHT = pathlib.Path(r"C:\Users\usuario\Downloads\map2drone\tools\lchm_exports\fase6\area_grid_74_time5.lchm")

def rec(d: bytes, i: int) -> bytes:
    return d[44 + i * 56: 100 + i * 56]

def main() -> None:
    d = CURVE.read_bytes()
    e = STRAIGHT.read_bytes()
    print("wp | curve flag/+36 | straight flag/+36 | hdg curve | spd")
    print("-" * 70)
    for i in range(d[43]):
        r, q = rec(d, i), rec(e, i)
        f = struct.unpack(">i", r[4:8])[0]
        fq = struct.unpack(">i", q[4:8])[0]
        r36 = struct.unpack(">f", r[36:40])[0]
        q36 = struct.unpack(">f", q[36:40])[0]
        hdg = struct.unpack(">f", r[8:12])[0]
        spd = struct.unpack(">f", r[12:16])[0]
        print(f"{i:2d} | {f:08x} {r36:8.3f}      | {fq:08x} {q36:8.3f}       | {hdg:7.1f} | {spd:.2f}")

if __name__ == "__main__":
    main()
