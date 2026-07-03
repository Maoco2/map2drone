from __future__ import annotations
import xml.etree.ElementTree as ET
from xml.dom import minidom

from .base import MissionExporter, ExportResult, ValidationResult
from .models import MissionExportData

GPX_NS = "http://www.topografix.com/GPX/1/1"
GPX_EXT = "http://www.garmin.com/xmlschemas/GpxExtensions/v3"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOC = "http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd"


def _build_gpx(mission: MissionExportData) -> str:
    attribs = {
        "xmlns": GPX_NS,
        "version": "1.1",
        "creator": "Map2Drone",
        "xmlns:xsi": XSI,
        "xsi:schemaLocation": SCHEMA_LOC,
    }
    root = ET.Element("gpx", attrib=attribs)

    # Metadata
    meta = ET.SubElement(root, "metadata")
    name = ET.SubElement(meta, "name")
    name.text = mission.project_name
    desc = ET.SubElement(meta, "description")
    desc.text = f"Map2Drone mission export - {len(mission.waypoints)} waypoints"
    author = ET.SubElement(meta, "author")
    auth_name = ET.SubElement(author, "name")
    auth_name.text = mission.user or "Map2Drone User"
    time = ET.SubElement(meta, "time")
    time.text = mission.export_date

    # Track
    trk = ET.SubElement(root, "trk")
    trk_name = ET.SubElement(trk, "name")
    trk_name.text = mission.project_name
    trkseg = ET.SubElement(trk, "trkseg")

    for wp in mission.waypoints:
        pt = ET.SubElement(trkseg, "trkpt")
        pt.set("lat", f"{wp.latitude:.7f}")
        pt.set("lon", f"{wp.longitude:.7f}")
        ele = ET.SubElement(pt, "ele")
        ele.text = f"{wp.altitude:.1f}"
        hdg = ET.SubElement(pt, "hdg")
        hdg.text = f"{wp.heading:.1f}"
        spd = ET.SubElement(pt, "speed")
        spd.text = f"{wp.speed or mission.speed_ms:.1f}"
        time = ET.SubElement(pt, "time")
        time.text = mission.export_date

    # Waypoints as wpt elements
    for i, wp in enumerate(mission.waypoints):
        wpt = ET.SubElement(root, "wpt")
        wpt.set("lat", f"{wp.latitude:.7f}")
        wpt.set("lon", f"{wp.longitude:.7f}")
        wpt_name = ET.SubElement(wpt, "name")
        wpt_name.text = f"WPT {i + 1}"
        wpt_ele = ET.SubElement(wpt, "ele")
        wpt_ele.text = f"{wp.altitude:.1f}"
        wpt_hdg = ET.SubElement(wpt, "hdg")
        wpt_hdg.text = f"{wp.heading:.1f}"

    raw = ET.tostring(root, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ")


class GpxExporter(MissionExporter):
    name = "GPX"
    extension = ".gpx"
    version = "1.1"
    description = "GPX con track, segmentos, waypoints y metadatos"

    def export(self, mission: MissionExportData) -> ExportResult:
        gpx = _build_gpx(mission)
        return ExportResult(
            data=gpx.encode("utf-8"),
            filename=f"{mission.project_name}.gpx",
            mime_type="application/gpx+xml",
        )
