"""Centerline parsers for corridor import (KMZ, KML, GeoPackage, GeoJSON, Shapefile).

Each parser returns a list of line coordinate lists (each a list of
[lon, lat] pairs). The calling endpoint selects the longest line.
"""

import io
import json
import os
import sqlite3
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from typing import Optional

from shapely import wkb
from shapely.geometry import LineString, MultiLineString

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _pts_from_coords(coords) -> list[list[float]]:
    pts: list[list[float]] = []
    for c in coords:
        if isinstance(c, (list, tuple)) and len(c) >= 2:
            try:
                pts.append([float(c[0]), float(c[1])])
            except (TypeError, ValueError):
                continue
    return pts


def _line_coords(geom) -> Optional[list[list[float]]]:
    """Extract the longest LineString coordinate list from a shapely geometry."""
    if isinstance(geom, LineString):
        return [[float(x), float(y)] for x, y in geom.coords]
    if isinstance(geom, MultiLineString):
        best = max(geom.geoms, key=lambda g: g.length, default=None)
        if best is not None:
            return _line_coords(best)
    return None


# ---------------------------------------------------------------------------
# GeoJSON
# ---------------------------------------------------------------------------


def _collect_line_coords(geom, out: list[list[list[float]]]) -> None:
    if not isinstance(geom, dict):
        return
    t = geom.get("type")
    coords = geom.get("coordinates")
    if t == "LineString":
        pts = _pts_from_coords(coords)
        if len(pts) >= 2:
            out.append(pts)
    elif t == "MultiLineString":
        for part in coords or []:
            pts = _pts_from_coords(part)
            if len(pts) >= 2:
                out.append(pts)
    elif t == "Polygon":
        rings = coords or []
        if rings:
            pts = _pts_from_coords(rings[0])
            if len(pts) >= 4:
                out.append(pts)
    elif t == "MultiPolygon":
        for rings in coords or []:
            if rings:
                pts = _pts_from_coords(rings[0])
                if len(pts) >= 4:
                    out.append(pts)
    elif t == "GeometryCollection":
        for g in geom.get("geometries") or []:
            _collect_line_coords(g, out)


def parse_geojson(data: bytes) -> list[list[list[float]]]:
    obj = json.loads(data.decode("utf-8"))
    out: list[list[list[float]]] = []

    def walk(node) -> None:
        if not isinstance(node, dict):
            return
        t = node.get("type")
        if t == "FeatureCollection":
            for f in node.get("features") or []:
                walk(f)
        elif t == "Feature":
            _collect_line_coords(node.get("geometry"), out)
        else:
            _collect_line_coords(node, out)

    walk(obj)
    return out


# ---------------------------------------------------------------------------
# KML / KMZ
# ---------------------------------------------------------------------------


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _kml_line_coords(elem) -> list[list[float]]:
    text = elem.text or ""
    pts: list[list[float]] = []
    for token in text.strip().replace("\n", " ").split():
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                pts.append([float(parts[0]), float(parts[1])])
            except ValueError:
                continue
    return pts


def parse_kml(data: bytes) -> list[list[list[float]]]:
    root = ET.fromstring(data)
    out: list[list[list[float]]] = []
    for elem in root.iter():
        if _local_tag(elem.tag) not in ("LineString", "LinearRing"):
            continue
        for co in elem.iter():
            if _local_tag(co.tag) == "coordinates" and co.text:
                pts = _kml_line_coords(co)
                if len(pts) >= 2:
                    out.append(pts)
                break
    return out


def _zip_has(entries: list[str], suffix: str) -> Optional[str]:
    for name in entries:
        if name.lower().endswith(suffix):
            return name
    return None


def parse_kmz(data: bytes) -> list[list[list[float]]]:
    zf = zipfile.ZipFile(io.BytesIO(data))
    names = zf.namelist()
    kml_name = _zip_has(names, ".kml")
    if kml_name:
        return parse_kml(zf.read(kml_name))
    shp_name = _zip_has(names, ".shp")
    if shp_name:
        return parse_shapefile(zf.read(shp_name))
    return []


# ---------------------------------------------------------------------------
# Shapefile (pyshp)
# ---------------------------------------------------------------------------

_POLYLINE_TYPES = (3, 13, 23)  # PolyLine, PolyLineZ, PolyLineM
_POLYGON_TYPES = (5, 15, 25)  # Polygon, PolygonZ, PolygonM


def parse_shapefile(data: bytes) -> list[list[list[float]]]:
    import shapefile

    sf = shapefile.Reader(shp=io.BytesIO(data), dbf=None)
    out: list[list[list[float]]] = []
    for shp in sf.iterShapes():
        if shp.shapeType in _POLYLINE_TYPES:
            pts = _pts_from_coords(shp.points)
            if len(pts) >= 2:
                out.append(pts)
        elif shp.shapeType in _POLYGON_TYPES:
            # exterior rings usable as a closed centerline
            parts = shp.parts + [len(shp.points)]
            for i in range(len(shp.parts)):
                pts = _pts_from_coords(shp.points[parts[i] : parts[i + 1]])
                if len(pts) >= 4:
                    pts.append(pts[0])
                    out.append(pts)
    return out


# ---------------------------------------------------------------------------
# GeoPackage (sqlite + GPB header -> WKB)
# ---------------------------------------------------------------------------


def _gpkg_blob_to_wkb(blob: bytes) -> Optional[bytes]:
    if len(blob) < 8:
        return None
    flags = blob[1]
    env_type = (flags >> 1) & 0x07
    env_size = {0: 0, 1: 32, 2: 48, 3: 64, 4: 64}.get(env_type, 0)
    return blob[6 + env_size :]


def parse_geopackage(data: bytes) -> list[list[list[float]]]:
    fd, path = tempfile.mkstemp(suffix=".gpkg")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        conn = sqlite3.connect(path)
        try:
            out: list[list[list[float]]] = []
            try:
                cols = conn.execute("SELECT table_name, column_name FROM gpkg_geometry_columns").fetchall()
            except sqlite3.Error:
                return out
            for table_name, geom_col in cols:
                rows = conn.execute(f'SELECT "{geom_col}" FROM "{table_name}"').fetchall()
                for (blob,) in rows:
                    if not blob:
                        continue
                    wkb_bytes = _gpkg_blob_to_wkb(blob)
                    if wkb_bytes is None:
                        continue
                    try:
                        geom = wkb.loads(wkb_bytes)
                    except Exception:
                        continue
                    coords = _line_coords(geom)
                    if coords and len(coords) >= 2:
                        out.append(coords)
            return out
        finally:
            conn.close()
    finally:
        os.remove(path)


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


def detect_format(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith((".geojson", ".json")):
        return "geojson"
    if name.endswith(".kml"):
        return "kml"
    if name.endswith(".kmz"):
        return "kmz"
    if name.endswith(".gpkg"):
        return "geopackage"
    if name.endswith(".shp"):
        return "shapefile"
    if data[:16] == b"SQLite format 3\x00":
        return "geopackage"
    if data[:4] == b"\x00\x00\x27\x0a":
        return "shapefile"
    if data[:4] == b"PK\x03\x04":
        return "kmz"
    if data.lstrip()[:1] == b"{":
        return "geojson"
    if b"<kml" in data[:1024].lower():
        return "kml"
    raise ValueError("Unsupported file format (expected KMZ, KML, GeoPackage, GeoJSON or Shapefile)")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_PARSERS = {
    "geojson": parse_geojson,
    "kml": parse_kml,
    "kmz": parse_kmz,
    "geopackage": parse_geopackage,
    "shapefile": parse_shapefile,
}


_CLOSING_EPS_DEG = 1e-9


def _dedup_closing_point(coords: list[list[float]]) -> list[list[float]]:
    """Drop a trailing coordinate equal to the first (closed ring → open centerline)."""
    if len(coords) >= 3:
        first = coords[0]
        last = coords[-1]
        if abs(first[0] - last[0]) <= _CLOSING_EPS_DEG and abs(first[1] - last[1]) <= _CLOSING_EPS_DEG:
            return coords[:-1]
    return coords


def load_centerline(filename: str, data: bytes) -> tuple[str, list[list[float]], int, list[str]]:
    """Detect format, parse lines and return (fmt, best_centerline, features_found, warnings)."""
    fmt = detect_format(filename, data)
    try:
        lines = _PARSERS[fmt](data)
    except Exception as exc:
        raise ValueError(f"Could not parse the {fmt} file: {exc}") from exc
    if not lines:
        raise ValueError(f"No line geometry found in the {fmt} file")
    warnings: list[str] = []
    best = max(lines, key=len)
    if len(lines) > 1:
        warnings.append(f"{len(lines)} line geometries found in the file; using the longest one")
    cleaned = _dedup_closing_point(best)
    if len(cleaned) < len(best):
        warnings.append(
            f"Centerline is a closed ring; removed the duplicate closing vertex "
            f"({len(best)} -> {len(cleaned)} vertices)"
        )
    return fmt, cleaned, len(lines), warnings
