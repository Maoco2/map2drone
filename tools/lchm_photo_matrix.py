"""LCHM photo-capture experimental matrix analyzer (Phase 4).

Infrastructure to analyze NEW real Litchi-generated LCHM files when they become
available. Determines, per file, the stored ``photo_distinterval``, the stored
``photo_timeinterval``, the record speed and the derived time, WITHOUT assuming
any generation formula.

NOT yet implemented / intentionally NOT wired to the exporter:
  - photo_distinterval writing
  - photo_timeinterval writing
  - LchmTrailerSerializer changes

Trailer layout (CONFIRMED on real 10-wp fixtures AND real 65-wp M/V files):

  rel 0..5              : 6 zero bytes
  section1 (rel 6..)    : n_wp blocks of 10 B each (altitude mirror)
  settings_start        : 6 + n_wp * 10
  settings_start + 10   : ``photo_timeinterval`` f32 (GLOBAL, one value)
  settings_start + 106  : per-waypoint photo pairs ``[photo_distinterval f32][other f32]``
                          one 8 B pair per waypoint, ``-1.0`` is the sentinel.

The M-series (M1..M6) differ ONLY at ``settings_start + 10`` (f32 1.0..6.0),
which CONFIRMS the field is ``photo_timeinterval``. The earlier 10-wp fixtures
stored 0.0 there (distance-based capture), which is why Fase 3 could not find 5.0.

The tool reports observed facts only:
  - ``photo_distinterval`` is read from the trailer at ``settings_start+106+i*8``.
  - ``photo_timeinterval`` is read from ``settings_start+10``.
  - ``-1.0`` is treated as a sentinel ("no interval").
  - ``derived_time = floor(photo_distinterval / speed, 1)`` is computed only for
    comparison with the CSV export; it is NOT assumed to be the internal rule.

Usage:
    python tools/lchm_photo_matrix.py M1.lchm M2.lchm M3.lchm ...
    python tools/lchm_photo_matrix.py --combined M1.lchm M2.lchm ...
    python tools/lchm_photo_matrix.py --diff A.lchm B.lchm
"""

from __future__ import annotations

import argparse
import math
import statistics
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.modules.export.litchi_lchm import (
    LCHM_HEADER_SIZE,
    _trailer_start,
    parse_lchm,
)

SETTINGS_HEADER = 6           # zero bytes before section1
SECTION1_BLOCK = 10           # bytes per waypoint in section1 (altitude mirror)
TIMEINTERVAL_OFFSET = 10      # settings_start + 10 -> photo_timeinterval f32 (global)
DIST_BLOCK_OFFSET = 106       # settings_start + 106 -> per-waypoint photo pairs
PHOTO_BLOCK_SIZE = 8
SENTINEL = -1.0


def settings_start(n_wp: int) -> int:
    """Trailer-relative offset of the settings section (scales with waypoints)."""
    return SETTINGS_HEADER + n_wp * SECTION1_BLOCK


def timeinterval_rel(n_wp: int) -> int:
    return settings_start(n_wp) + TIMEINTERVAL_OFFSET


def photo_blocks_rel(n_wp: int) -> int:
    return settings_start(n_wp) + DIST_BLOCK_OFFSET


def _f32_be(data: bytes, off: int) -> float:
    return struct.unpack(">f", data[off:off + 4])[0]


@dataclass
class PhotoBlock:
    """One per-waypoint [distinterval, other] pair from the trailer."""

    index: int
    trailer_rel: int
    abs_offset: int
    raw: bytes
    distinterval: float
    other: float

    @property
    def is_sentinel(self) -> bool:
        return abs(self.distinterval - SENTINEL) < 1e-3

    @property
    def raw_hex(self) -> str:
        return self.raw.hex()


@dataclass
class FileAnalysis:
    path: Path
    data: bytes
    mission: object
    trailer_start: int
    trailer_len: int
    photo_blocks: list[PhotoBlock] = field(default_factory=list)
    timeinterval: float | None = None  # photo_timeinterval f32 at settings_start+10

    @property
    def waypoint_count(self) -> int:
        return self.mission.waypoint_count

    @property
    def speeds(self) -> list[float]:
        return [w.speed for w in self.mission.waypoints]

    def unique_speeds(self) -> list[float]:
        return sorted(set(round(s, 4) for s in self.speeds))

    def valid_distintervals(self) -> list[float]:
        return [b.distinterval for b in self.photo_blocks if not b.is_sentinel]

    def sentinel_count(self) -> int:
        return sum(1 for b in self.photo_blocks if b.is_sentinel)

    def unique_distintervals(self) -> list[float]:
        return sorted(set(round(d, 4) for d in self.valid_distintervals()))

    def photo_statistics(self) -> dict[str, float | int | None]:
        vals = self.valid_distintervals()
        if not vals:
            return {"valid": 0, "sentinel": self.sentinel_count(),
                    "min": None, "max": None, "mean": None, "median": None}
        return {
            "valid": len(vals),
            "sentinel": self.sentinel_count(),
            "min": min(vals),
            "max": max(vals),
            "mean": statistics.fmean(vals),
            "median": statistics.median(vals),
        }

    def derived_times(self) -> list[float]:
        """derived_time = photo_distinterval / speed (valid pairs only)."""
        out: list[float] = []
        for w, b in zip(self.mission.waypoints, self.photo_blocks):
            if b.is_sentinel or w.speed <= 0:
                continue
            out.append(b.distinterval / w.speed)
        return out


def extract_photo_blocks(data: bytes, trailer_start: int, n_wp: int) -> list[PhotoBlock]:
    """Read per-waypoint [f32, f32] photo pairs at settings_start+106 + i*8.

    Returns an empty list when the trailer is absent/too short (the exporter
    does not emit one, so exported files naturally yield no blocks).
    """
    trailer = data[trailer_start:]
    block_rel = photo_blocks_rel(n_wp)
    if len(trailer) < block_rel + n_wp * PHOTO_BLOCK_SIZE:
        return []
    blocks: list[PhotoBlock] = []
    for i in range(n_wp):
        off = block_rel + i * PHOTO_BLOCK_SIZE
        raw = trailer[off:off + PHOTO_BLOCK_SIZE]
        a = struct.unpack(">f", raw[:4])[0]
        b = struct.unpack(">f", raw[4:8])[0]
        blocks.append(PhotoBlock(
            index=i,
            trailer_rel=off,
            abs_offset=trailer_start + off,
            raw=raw,
            distinterval=a,
            other=b,
        ))
    return blocks


def read_timeinterval(data: bytes, trailer_start: int, n_wp: int) -> float | None:
    """Global photo_timeinterval f32 at settings_start+10 (None when absent)."""
    rel = timeinterval_rel(n_wp)
    trailer = data[trailer_start:]
    if len(trailer) < rel + 4:
        return None
    return struct.unpack(">f", trailer[rel:rel + 4])[0]


def analyze_file(path: Path) -> FileAnalysis:
    data = path.read_bytes()
    mission = parse_lchm(data)
    trailer_start = _trailer_start(data)
    blocks = extract_photo_blocks(data, trailer_start, mission.waypoint_count)
    return FileAnalysis(
        path=path,
        data=data,
        mission=mission,
        trailer_start=trailer_start,
        trailer_len=len(data) - trailer_start,
        photo_blocks=blocks,
        timeinterval=read_timeinterval(data, trailer_start, mission.waypoint_count),
    )


# ── Pairwise photo_distinterval comparison ─────────────────────────────────

@dataclass
class PairDiffRow:
    index: int
    old: float | None
    new: float | None
    diff: float | None
    pct: float | None

    @property
    def candidate_photo_change(self) -> bool:
        return (
            self.old is not None and self.new is not None
            and abs(self.old - self.new) > 1e-6
        )


def pairwise_photo_diff(a: FileAnalysis, b: FileAnalysis) -> list[PairDiffRow]:
    """Compare photo_distinterval per waypoint between two files."""
    n = min(len(a.photo_blocks), len(b.photo_blocks))
    rows: list[PairDiffRow] = []
    for i in range(n):
        old = a.photo_blocks[i].distinterval
        new = b.photo_blocks[i].distinterval
        diff = new - old if old is not None and new is not None else None
        pct = (abs(diff) / abs(old) * 100) if diff is not None and abs(old) > 1e-9 else None
        rows.append(PairDiffRow(i, old, new, diff, pct))
    return rows


# ── Trailer byte diff with candidate marking ───────────────────────────────

@dataclass
class ByteChange:
    offset: int
    trailer_rel: int
    section: str
    old_byte: int
    new_byte: int
    old_data: bytes = b""
    new_data: bytes = b""

    @property
    def f32_align(self) -> int:
        """Offset of the 4-byte window that contains this byte (f32 decode)."""
        return self.offset - (self.offset % 4)

    def old_f32(self) -> str:
        align = self.f32_align
        if align < 0 or align + 4 > len(self.old_data):
            return "n/a"
        return f"{struct.unpack('>f', self.old_data[align:align + 4])[0]:.4f}"

    def new_f32(self) -> str:
        align = self.f32_align
        if align < 0 or align + 4 > len(self.new_data):
            return "n/a"
        return f"{struct.unpack('>f', self.new_data[align:align + 4])[0]:.4f}"


def trailer_byte_diff(a: FileAnalysis, b: FileAnalysis) -> list[ByteChange]:
    """Changed trailer bytes between two files (absolute + trailer-relative)."""
    changes: list[ByteChange] = []
    start = min(a.trailer_start, b.trailer_start)
    length = max(a.trailer_len, b.trailer_len)
    for i in range(length):
        off = start + i
        old = a.data[off] if off < len(a.data) else None
        new = b.data[off] if off < len(b.data) else None
        if old != new:
            section = (
                "header" if off < LCHM_HEADER_SIZE
                else ("waypoint" if off < start else "trailer")
            )
            changes.append(ByteChange(
                offset=off,
                trailer_rel=i if off >= start else -1,
                section=section,
                old_byte=old or 0,
                new_byte=new or 0,
                old_data=a.data,
                new_data=b.data,
            ))
    return changes


def format_byte_diff(a: FileAnalysis, b: FileAnalysis) -> str:
    changes = trailer_byte_diff(a, b)
    if not changes:
        return f"BYTE DIFF  {a.path.name} -> {b.path.name}\nNo trailer byte differences."
    # candidate: byte falls inside a photo block at settings_start+106 + i*8,
    # or in the global timeinterval at settings_start+10.
    block_rel = photo_blocks_rel(a.waypoint_count)
    ti_rel = timeinterval_rel(a.waypoint_count)
    lines = [f"BYTE DIFF  {a.path.name} -> {b.path.name}",
             "abs_offset  trailer_rel  section   old→new  f32(old)   f32(new)  candidate"]
    for c in changes:
        rel = c.trailer_rel
        candidate = ""
        if rel >= 0:
            if rel == ti_rel:
                candidate = "candidate photo_timeinterval change"
            elif rel >= block_rel and (rel - block_rel) % PHOTO_BLOCK_SIZE < 4:
                candidate = "candidate photo_distinterval change"
        lines.append(
            f"{c.offset:9d}  {c.trailer_rel:10d}  {c.section:9s}  "
            f"{c.old_byte:02x}→{c.new_byte:02x}  {c.old_f32():>8s}  {c.new_f32():>8s}  {candidate}"
        )
    return "\n".join(lines)


# ── Rendering ──────────────────────────────────────────────────────────────

def render_file_table(analyses: list[FileAnalysis]) -> str:
    header = ["file", "speed", "waypoint_count", "photo_timeinterval",
              "photo_distinterval", "derived_time(floor1)", "trailer_offset",
              "raw_f32(first)"]
    lines = ["\t".join(header)]
    for a in analyses:
        speed = a.unique_speeds()
        speed_s = ",".join(f"{s:.2f}" for s in speed)
        ti = f"{a.timeinterval:.2f}" if a.timeinterval is not None else "n/a"
        di = a.unique_distintervals()
        di_s = ",".join(f"{d:.2f}" for d in di) if di else "n/a"
        times = sorted(set(round(math.floor(t * 10) / 10, 1) for t in a.derived_times()))
        times_s = ",".join(f"{t:.1f}" for t in times) if times else "n/a"
        raw = a.photo_blocks[0].raw_hex if a.photo_blocks else "n/a"
        lines.append("\t".join([
            a.path.name,
            speed_s,
            str(a.waypoint_count),
            ti,
            di_s,
            times_s,
            str(a.trailer_start),
            raw,
        ]))
    return "\n".join(lines)


def render_stats_table(analyses: list[FileAnalysis]) -> str:
    header = ["file", "valid", "sentinel", "min", "max", "mean", "median", "unique"]
    lines = ["\t".join(header)]
    for a in analyses:
        s = a.photo_statistics()
        lines.append("\t".join([
            a.path.name,
            str(s["valid"]),
            str(s["sentinel"]),
            f"{s['min']:.3f}" if s["min"] is not None else "n/a",
            f"{s['max']:.3f}" if s["max"] is not None else "n/a",
            f"{s['mean']:.3f}" if s["mean"] is not None else "n/a",
            f"{s['median']:.3f}" if s["median"] is not None else "n/a",
            ",".join(f"{d:.2f}" for d in a.unique_distintervals()),
        ]))
    return "\n".join(lines)


def render_pairwise(analyses: list[FileAnalysis]) -> str:
    out: list[str] = []
    for i in range(1, len(analyses)):
        a, b = analyses[i - 1], analyses[i]
        rows = pairwise_photo_diff(a, b)
        header = f"PAIR {a.path.name} vs {b.path.name}"
        out.append(header)
        out.append("wp   old_dist  new_dist  diff     %change   candidate")
        for r in rows:
            old = f"{r.old:.2f}" if r.old is not None else "n/a"
            new = f"{r.new:.2f}" if r.new is not None else "n/a"
            d = f"{r.diff:+.2f}" if r.diff is not None else "n/a"
            pct = f"{r.pct:+.1f}%" if r.pct is not None else "n/a"
            cand = "YES" if r.candidate_photo_change else ""
            out.append(f"{r.index:2d}   {old:>8s}  {new:>8s}  {d:>8s}  {pct:>8s}  {cand}")
    return "\n".join(out)


def render_combined(analyses: list[FileAnalysis]) -> str:
    """Combined matrix: derived_time | speed | photo_distinterval."""
    header = ["derived_time(floor1)", "speed", "photo_distinterval"]
    lines = ["\t".join(header)]
    for a in analyses:
        speed = a.unique_speeds()[0] if a.unique_speeds() else float("nan")
        for t in sorted(set(math.floor(t * 10) / 10 for t in a.derived_times())):
            # dist for the waypoint(s) matching this derived time
            dists: set[float] = set()
            for w, b in zip(a.mission.waypoints, a.photo_blocks):
                if b.is_sentinel or w.speed <= 0:
                    continue
                if abs(math.floor((b.distinterval / w.speed) * 10) / 10 - t) < 1e-6:
                    dists.add(round(b.distinterval, 2))
            for d in sorted(dists):
                lines.append("\t".join([
                    f"{t:.1f}",
                    f"{speed:.2f}",
                    f"{d:.2f}",
                ]))
    return "\n".join(lines)


def render_timeinterval(analyses: list[FileAnalysis]) -> str:
    """Per-file stored photo_timeinterval + expected distance if dist = v*t."""
    lines = ["file\tspeed\tphoto_timeinterval\tphoto_distinterval\tv*t\tmatch?"]
    for a in analyses:
        speed = a.unique_speeds()[0] if a.unique_speeds() else float("nan")
        ti = a.timeinterval
        dists = a.unique_distintervals()
        di = dists[0] if dists else float("nan")
        vt = speed * ti if ti is not None else float("nan")
        match = (
            "YES" if ti is not None and abs(di - vt) < 1e-2 else
            "no" if ti is not None else "n/a"
        )
        ti_s = f"{ti:.2f}" if ti is not None else "n/a"
        lines.append("\t".join([
            a.path.name,
            f"{speed:.2f}",
            ti_s,
            f"{di:.2f}",
            f"{vt:.2f}" if ti is not None else "n/a",
            match,
        ]))
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--combined", action="store_true",
                        help="emit combined matrix (derived_time | speed | dist)")
    parser.add_argument("--timeinterval", action="store_true",
                        help="emit stored photo_timeinterval + speed*interval vs dist")
    parser.add_argument("--diff", action="store_true",
                        help="emit trailer byte diff for each consecutive pair")
    args = parser.parse_args(argv[1:])

    analyses = [analyze_file(p) for p in args.files]

    print(render_file_table(analyses))
    print()
    print(render_stats_table(analyses))
    print()
    if args.combined:
        print(render_combined(analyses))
        print()
    if args.timeinterval:
        print(render_timeinterval(analyses))
        print()
    if args.diff:
        for i in range(1, len(analyses)):
            print(format_byte_diff(analyses[i - 1], analyses[i]))
            print()
    print(render_pairwise(analyses))
    print()
    print("NOTA: photo_distinterval se lee del trailer (settings_start+106 + i*8, primer f32).")
    print("NOTA: photo_timeinterval se lee del trailer (settings_start+10, f32 global).")
    print("derived_time = floor(photo_distinterval / speed, 1) — para comparar con CSV.")
    print("NO se asume ninguna fórmula de generación de distance todavía.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
