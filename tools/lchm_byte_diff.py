"""LCHM byte-diff tool: detailed differential analysis of two LCHM files.

Shows every changed byte with absolute offset, section (header / waypoint
record / trailer), trailer-relative offset, old byte, new byte and the
interpreted f32/f64 value when the 4/8-byte window aligns.

Usage:
    python tools/lchm_byte_diff.py <file_a> <file_b>
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.modules.export.litchi_lchm import (
    LCHM_HEADER_SIZE,
    LCHM_WAYPOINT_RECORD_SIZE,
    _trailer_start,
)

SECTION_HEADER = "header"
SECTION_WP = "waypoint"
SECTION_TRAILER = "trailer"


def _f32(data: bytes, off: int) -> str:
    if off < 0 or off + 4 > len(data):
        return ""
    v = struct.unpack(">f", data[off:off + 4])[0]
    return f"{v:.4f}"


def _f64(data: bytes, off: int) -> str:
    if off < 0 or off + 8 > len(data):
        return ""
    v = struct.unpack(">d", data[off:off + 8])[0]
    return f"{v:.6f}"


def _section_label(data: bytes, off: int, trailer_start: int, n_wp: int) -> str:
    if off < LCHM_HEADER_SIZE:
        return SECTION_HEADER
    if off < trailer_start:
        rel = off - LCHM_HEADER_SIZE
        idx = rel // LCHM_WAYPOINT_RECORD_SIZE
        field = rel % LCHM_WAYPOINT_RECORD_SIZE
        return f"{SECTION_WP}{idx}+{field}"
    return SECTION_TRAILER


def byte_diff(file_a: bytes, file_b: bytes) -> str:
    trailer_a = _trailer_start(file_a)
    trailer_b = _trailer_start(file_b)
    n_a = (trailer_a - LCHM_HEADER_SIZE) // LCHM_WAYPOINT_RECORD_SIZE
    n_b = (trailer_b - LCHM_HEADER_SIZE) // LCHM_WAYPOINT_RECORD_SIZE
    length = max(len(file_a), len(file_b))

    lines: list[str] = []
    lines.append(f"A: {len(file_a)}B, {n_a} waypoints, trailer@{trailer_a} ({len(file_a) - trailer_a}B)")
    lines.append(f"B: {len(file_b)}B, {n_b} waypoints, trailer@{trailer_b} ({len(file_b) - trailer_b}B)")
    lines.append("")

    changes: list[tuple[int, int | None, int | None]] = []
    for i in range(length):
        old_b = file_a[i] if i < len(file_a) else None
        new_b = file_b[i] if i < len(file_b) else None
        if old_b != new_b:
            changes.append((i, old_b, new_b))

    if not changes:
        return "No differences."

    lines.append("OFFSET   SECTION         TRAILER-REL  OLD→NEW   f32(old)  f32(new)  f64(old)  f64(new)")
    lines.append("-" * 100)

    # Group consecutive runs but still annotate each change with float context.
    run: list[tuple[int, int | None, int | None]] = []
    for change in changes:
        if run and change[0] != run[-1][0] + 1:
            lines.extend(_emit_run(run, file_a, file_b, trailer_a))
            run = []
        run.append(change)
    lines.extend(_emit_run(run, file_a, file_b, trailer_a))
    return "\n".join(lines)


def _emit_run(
    run: list[tuple[int, int | None, int | None]],
    file_a: bytes,
    file_b: bytes,
    trailer_a: int,
) -> list[str]:
    lines: list[str] = []
    if len(run) == 1:
        off, old_b, new_b = run[0]
        old_s = "??" if old_b is None else f"{old_b:02x}"
        new_s = "??" if new_b is None else f"{new_b:02x}"
        section = _section_label(file_a, off, trailer_a, 0)
        t_rel = off - trailer_a if off >= trailer_a else "-"
        lines.append(
            f"{off:6d}   {section:16s} {str(t_rel):>10s}  {old_s}→{new_s}   "
            f"{_f32(file_a, off - 1):>9s} {_f32(file_b, off - 1):>9s}  "
            f"{_f64(file_a, off - 1):>10s} {_f64(file_b, off - 1):>10s}"
        )
        return lines

    start = run[0][0]
    end = run[-1][0]
    old_bytes = "".join("??" if b is None else f"{b:02x}" for _, b, _ in run)
    new_bytes = "".join("??" if b is None else f"{b:02x}" for _, _, b in run)
    section = _section_label(file_a, start, trailer_a, 0)
    t_rel = f"{start - trailer_a}-{end - trailer_a}" if start >= trailer_a else "-"
    lines.append(f"{start}-{end}  {section}  rel {t_rel}")
    lines.append(f"    OLD: {old_bytes}")
    lines.append(f"    NEW: {new_bytes}")
    lines.append(
        f"    as f32@start: old={_f32(file_a, start)} new={_f32(file_b, start)}"
    )
    lines.append(
        f"    as f64@start: old={_f64(file_a, start)} new={_f64(file_b, start)}"
    )
    return lines


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: python tools/lchm_byte_diff.py <file_a> <file_b>")
        return 2
    a = Path(argv[1]).read_bytes()
    b = Path(argv[2]).read_bytes()
    print(byte_diff(a, b))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
