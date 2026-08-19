"""Fase 7b: detailed trailer diff curve vs straight."""
from __future__ import annotations

import pathlib
import struct

CURVE = pathlib.Path(r"C:\Users\usuario\Downloads\area_grid_74_time5_curve.lchm")
STRAIGHT = pathlib.Path(r"C:\Users\usuario\Downloads\map2drone\tools\lchm_exports\fase6\area_grid_74_time5.lchm")

def main() -> None:
    d = CURVE.read_bytes()
    e = STRAIGHT.read_bytes()
    n = d[43]
    trailer_off = 44 + n * 56
    dt, et = d[trailer_off:], e[trailer_off:]

    # show diff regions (runs of differing bytes)
    diffs = []
    i = 0
    while i < len(dt):
        if dt[i] != et[i]:
            start = i
            while i < len(dt) and dt[i] != et[i]:
                i += 1
            diffs.append((start, i - 1))
        else:
            i += 1
    print(f"trailer diff regions ({len(diffs)}):")
    for (a, b) in diffs:
        print(f"  rel {a}..{b} (len {b-a+1})  curve={dt[a:b+1].hex()}  straight={et[a:b+1].hex()}")

    # interpret region around 852 rel
    print("\n== around first diff (rel 830..900) ==")
    print("rel | curve hex (8B) | straight hex (8B) | curve f32s | straight f32s")
    for rel in range(830, 905, 8):
        cd = dt[rel:rel+8]
        ed = et[rel:rel+8]
        cf = [struct.unpack(">f", cd[x:x+4])[0] for x in (0, 4)]
        ef = [struct.unpack(">f", ed[x:x+4])[0] for x in (0, 4)]
        print(f"{rel:4d} | {cd.hex()} | {ed.hex()} | {cf[0]:10.4f} {cf[1]:10.4f} | {ef[0]:10.4f} {ef[1]:10.4f}")

if __name__ == "__main__":
    main()
