from __future__ import annotations
import io
import zipfile
import xml.etree.ElementTree as ET
from xml.dom import minidom

from .base import MissionExporter, ExportResult, ValidationResult, ValidationError
from .models import MissionExportData
from .dji_wpml import _build_xml


def _build_waylines_wpml(mission: MissionExportData) -> str:
    root = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
    doc = ET.SubElement(root, "Document")

    for i, wp in enumerate(mission.waypoints):
        pm = ET.SubElement(doc, "Placemark")
        name = ET.SubElement(pm, "name")
        name.text = f"WPT{i + 1}"
        pt = ET.SubElement(pm, "Point")
        coords = ET.SubElement(pt, "coordinates")
        coords.text = f"{wp.longitude:.7f},{wp.latitude:.7f},{wp.altitude:.1f}"
        h = ET.SubElement(pm, "heading")
        h.text = f"{wp.heading:.1f}"
        sp = ET.SubElement(pm, "speed")
        sp.text = f"{wp.speed or mission.speed_ms:.1f}"

    raw = ET.tostring(root, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ")


def _build_manifest(sources: list[tuple[str, str]]) -> str:
    root = ET.Element("manifest")
    for fname, ftype in sources:
        f = ET.SubElement(root, "file")
        n = ET.SubElement(f, "name")
        n.text = fname
        t = ET.SubElement(f, "type")
        t.text = ftype
    raw = ET.tostring(root, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ")


def _build_kmz(mission: MissionExportData) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        mission_xml = _build_xml(mission)
        zf.writestr("mission.wpml", mission_xml.encode("utf-8"))

        waylines_xml = _build_waylines_wpml(mission)
        zf.writestr("waylines.wpml", waylines_xml.encode("utf-8"))

        sources = [
            ("mission.wpml", "wpml"),
            ("waylines.wpml", "waylines"),
        ]
        manifest = _build_manifest(sources)
        zf.writestr("manifest.xml", manifest.encode("utf-8"))

    return buf.getvalue()


class DjiKmzExporter(MissionExporter):
    name = "DJI KMZ"
    extension = ".kmz"
    version = "2.0"
    description = "KMZ compatible con DJI Pilot 2 (mission.wpml + waylines.wpml + manifest)"

    def validate(self, mission: MissionExportData) -> ValidationResult:
        errors: list[ValidationError] = []
        if len(mission.waypoints) > 240:
            errors.append(ValidationError(
                field="waypoints",
                message=f"DJI Pilot 2 soporta máximo 240 waypoints (se tienen {len(mission.waypoints)})"
            ))
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def export(self, mission: MissionExportData) -> ExportResult:
        kmz = _build_kmz(mission)
        return ExportResult(
            data=kmz,
            filename=f"{mission.project_name}.kmz",
            mime_type="application/vnd.google-earth.kmz",
            is_binary=True,
        )
