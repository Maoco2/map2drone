from __future__ import annotations
import io
import zipfile
import xml.etree.ElementTree as ET
from xml.dom import minidom

from .base import MissionExporter, ExportResult, ValidationResult
from .models import MissionExportData


# Minimal SVG icons for KMZ
HOME_ICON_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <circle cx="16" cy="16" r="14" fill="#00ff00" stroke="#ffffff" stroke-width="2"/>
  <text x="16" y="21" text-anchor="middle" font-size="14" fill="#ffffff" font-weight="bold">H</text>
</svg>"""

WP_ICON_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
  <circle cx="12" cy="12" r="10" fill="#ffff00" stroke="#000000" stroke-width="1"/>
  <text x="12" y="16" text-anchor="middle" font-size="10" fill="#000000" font-weight="bold">W</text>
</svg>"""


def _altitude_mode(mission: MissionExportData) -> str:
    mode = (mission.altitude_mode or "").lower()
    if mode in ("absolute", "asl", "sea_level", "msl"):
        return "absolute"
    return "relativeToGround"


def _build_kmz_kml(mission: MissionExportData) -> str:
    root = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
    doc = ET.SubElement(root, "Document")

    name = ET.SubElement(doc, "name")
    name.text = mission.project_name

    # Styles with custom icons
    hs = ET.SubElement(doc, "Style", id="homeStyle")
    hi = ET.SubElement(hs, "IconStyle")
    ET.SubElement(hi, "scale").text = "1.2"
    ET.SubElement(hi, "Icon").text = "files/home.svg"

    ws = ET.SubElement(doc, "Style", id="wpStyle")
    wi = ET.SubElement(ws, "IconStyle")
    ET.SubElement(wi, "scale").text = "0.8"
    ET.SubElement(wi, "Icon").text = "files/wp.svg"

    ls = ET.SubElement(doc, "Style", id="lineStyle")
    ln = ET.SubElement(ls, "LineStyle")
    ET.SubElement(ln, "color").text = "ff00ffff"
    ET.SubElement(ln, "width").text = "2"

    alt_mode = _altitude_mode(mission)

    # Home
    if mission.home:
        pm = ET.SubElement(doc, "Placemark")
        ET.SubElement(pm, "name").text = "Home"
        ET.SubElement(pm, "styleUrl").text = "#homeStyle"
        pt = ET.SubElement(pm, "Point")
        ET.SubElement(pt, "altitudeMode").text = alt_mode
        ET.SubElement(pt, "coordinates").text = (
            f"{mission.home.longitude:.7f},{mission.home.latitude:.7f},{mission.altitude:.1f}"
        )

    # Route
    if mission.waypoints:
        route = ET.SubElement(doc, "Placemark")
        ET.SubElement(route, "name").text = "Route"
        ET.SubElement(route, "styleUrl").text = "#lineStyle"
        ls = ET.SubElement(route, "LineString")
        ET.SubElement(ls, "altitudeMode").text = alt_mode
        parts = " ".join(
            f"{wp.longitude:.7f},{wp.latitude:.7f},{wp.altitude:.1f}"
            for wp in mission.waypoints
        )
        ET.SubElement(ls, "coordinates").text = parts

    # Waypoints
    for i, wp in enumerate(mission.waypoints):
        pm = ET.SubElement(doc, "Placemark")
        ET.SubElement(pm, "name").text = f"WP {i + 1}"
        ET.SubElement(pm, "styleUrl").text = "#wpStyle"
        desc = ET.SubElement(pm, "description")
        desc.text = (
            f"Alt: {wp.altitude:.1f}m<br/>Hdg: {wp.heading:.1f}°<br/>"
            f"Spd: {wp.speed or mission.speed_ms:.1f}m/s"
        )
        pt = ET.SubElement(pm, "Point")
        ET.SubElement(pt, "altitudeMode").text = alt_mode
        ET.SubElement(pt, "coordinates").text = (
            f"{wp.longitude:.7f},{wp.latitude:.7f},{wp.altitude:.1f}"
        )

    raw = ET.tostring(root, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ")


def _build_kmz(mission: MissionExportData) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        kml = _build_kmz_kml(mission)
        zf.writestr("doc.kml", kml.encode("utf-8"))
        zf.writestr("files/home.svg", HOME_ICON_SVG.encode("utf-8"))
        zf.writestr("files/wp.svg", WP_ICON_SVG.encode("utf-8"))
    return buf.getvalue()


class KmzExporter(MissionExporter):
    name = "KMZ (Google Earth)"
    extension = ".kmz"
    version = "2.2"
    description = "KMZ comprimido para Google Earth con iconos personalizados"

    def export(self, mission: MissionExportData) -> ExportResult:
        kmz = _build_kmz(mission)
        return ExportResult(
            data=kmz,
            filename=f"{mission.project_name}.kmz",
            mime_type="application/vnd.google-earth.kmz",
            is_binary=True,
        )
