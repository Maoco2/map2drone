from __future__ import annotations
import io
import zipfile
import xml.etree.ElementTree as ET
from xml.dom import minidom

from .base import (
    MissionExporter, ExportResult, ValidationResult, ValidationError,
    CompatibilityInfo, CompatibilityCategory, ExportWarning,
    has_elevation_data, has_heading_per_wp, has_multiple_actions, has_gimbal,
)
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
    compatibility = CompatibilityInfo(
        category=CompatibilityCategory.REVERSE_ENGINEERED,
        description=(
            "El paquete KMZ de DJI (mission.wpml + waylines.wpml + manifest.xml) se "
            "construye según la estructura reconstruida por la comunidad. DJI no publica "
            "la especificación completa; verificar la importación en DJI Pilot 2 antes de volar."
        ),
    )

    def validate(self, mission: MissionExportData) -> ValidationResult:
        errors: list[ValidationError] = []
        if len(mission.waypoints) > 240:
            errors.append(ValidationError(
                field="waypoints",
                message=f"DJI Pilot 2 soporta máximo 240 waypoints (se tienen {len(mission.waypoints)})"
            ))
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def get_warnings(self, mission: MissionExportData) -> list[ExportWarning]:
        warnings: list[ExportWarning] = []
        if has_elevation_data(mission):
            warnings.append(ExportWarning(
                code="elevation_lost",
                message=(
                    "El KMZ de DJI no representa la elevación del terreno (MSL/AGL); "
                    "las alturas se exportan como valores del modelo."
                ),
                fields=["elevation_msnm", "agl"],
            ))
        if has_heading_per_wp(mission):
            warnings.append(ExportWarning(
                code="heading_ignored",
                message=(
                    "La misión se exporta con headingMode=auto; el rumbo por waypoint "
                    "no controla la orientación del dron."
                ),
                fields=["heading"],
            ))
        if has_multiple_actions(mission):
            warnings.append(ExportWarning(
                code="actions_approximated",
                message=(
                    "Las acciones múltiples por waypoint se simplifican a disparo "
                    "por intervalo estimado en modo de línea."
                ),
                fields=["actions"],
            ))
        if has_gimbal(mission):
            warnings.append(ExportWarning(
                code="gimbal_approximated",
                message="El pitch/modo del gimbal no se transfiere de forma fiel.",
                fields=["gimbal_pitch", "gimbal_mode"],
            ))
        return warnings

    def export(self, mission: MissionExportData) -> ExportResult:
        kmz = _build_kmz(mission)
        return ExportResult(
            data=kmz,
            filename=f"{mission.project_name}.kmz",
            mime_type="application/vnd.google-earth.kmz",
            is_binary=True,
        )
