from __future__ import annotations
import xml.etree.ElementTree as ET
from xml.dom import minidom

from .base import MissionExporter, ExportResult, ValidationResult
from .models import MissionExportData


def _altitude_mode(mission: MissionExportData) -> str:
    mode = (mission.altitude_mode or "").lower()
    if mode in ("absolute", "asl", "sea_level", "msl", "ground"):
        return "absolute"
    return "relativeToGround"


def _wp_alt_msl(wp) -> float:
    if wp.elevation_msnm is not None and wp.agl is not None:
        return wp.elevation_msnm + wp.agl
    return wp.altitude


def _build_kml(mission: MissionExportData) -> str:
    root = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
    doc = ET.SubElement(root, "Document")

    name = ET.SubElement(doc, "name")
    name.text = mission.project_name

    desc = ET.SubElement(doc, "description")
    desc.text = (
        f"Map2Drone Export | {len(mission.waypoints)} waypoints | "
        f"Altura: {mission.altitude}m | Velocidad: {mission.speed_ms}m/s"
    )

    # Styles
    _add_style(doc, "homeIcon", "ff00ff00", "1.0")
    _add_style(doc, "wpIcon", "ffff00ff", "0.8")
    _add_style(doc, "lineStyle", "ff00ffff", "0.6")

    alt_mode = _altitude_mode(mission)

    # Home point
    if mission.home:
        home_alt = mission.altitude
        if mission.waypoints and mission.waypoints[0].elevation_msnm is not None:
            home_alt = _wp_alt_msl(mission.waypoints[0])
        hm = ET.SubElement(doc, "Placemark")
        ET.SubElement(hm, "name").text = "Home Point"
        ET.SubElement(hm, "styleUrl").text = "#homeIcon"
        ed_home = ET.SubElement(hm, "ExtendedData")
        _add_data(ed_home, "Altura", f"{home_alt:.1f} m MSL")
        pt = ET.SubElement(hm, "Point")
        ET.SubElement(pt, "altitudeMode").text = alt_mode
        ET.SubElement(pt, "coordinates").text = (
            f"{mission.home.longitude:.7f},{mission.home.latitude:.7f},{home_alt:.1f}"
        )

    # Flight route (LineString)
    if mission.waypoints:
        route = ET.SubElement(doc, "Placemark")
        ET.SubElement(route, "name").text = "Ruta de vuelo"
        ET.SubElement(route, "styleUrl").text = "#lineStyle"
        ls = ET.SubElement(route, "LineString")
        ET.SubElement(ls, "altitudeMode").text = alt_mode
        coords = ET.SubElement(ls, "coordinates")
        coord_pairs = " ".join(
            f"{wp.longitude:.7f},{wp.latitude:.7f},{_wp_alt_msl(wp):.1f}"
            for wp in mission.waypoints
        )
        coords.text = coord_pairs

    # Waypoints
    for i, wp in enumerate(mission.waypoints):
        msl = _wp_alt_msl(wp)
        pm = ET.SubElement(doc, "Placemark")
        ET.SubElement(pm, "name").text = f"WPT {i + 1}"
        ET.SubElement(pm, "styleUrl").text = "#wpIcon"
        agl_str = f"AGL: {wp.agl:.0f}m<br/>" if wp.agl is not None else ""
        elev_str = f"Elevación: {wp.elevation_msnm:.0f}m<br/>" if wp.elevation_msnm is not None else ""
        desc = ET.SubElement(pm, "description")
        desc.text = (
            f"Altura: {msl:.1f}m MSL<br/>"
            f"{agl_str}{elev_str}"
            f"Rumbo: {wp.heading:.1f}°<br/>"
            f"Velocidad: {wp.speed or mission.speed_ms:.1f}m/s<br/>"
            f"Acción: {wp.action_type if wp.action_type > 0 else 'Ninguna'}"
        )
        ed = ET.SubElement(pm, "ExtendedData")
        _add_data(ed, "MSL (Altura sobre el mar)", f"{msl:.1f} m")
        if wp.agl is not None:
            _add_data(ed, "AGL (Altura sobre terreno)", f"{wp.agl:.0f} m")
        if wp.elevation_msnm is not None:
            _add_data(ed, "Elevación del terreno", f"{wp.elevation_msnm:.0f} m")
        _add_data(ed, "Rumbo", f"{wp.heading:.1f}°")
        _add_data(ed, "Velocidad", f"{wp.speed or mission.speed_ms:.1f} m/s")
        if wp.action_type and wp.action_type > 0:
            _add_data(ed, "Acción", str(wp.action_type))
        pt = ET.SubElement(pm, "Point")
        ET.SubElement(pt, "altitudeMode").text = alt_mode
        ET.SubElement(pt, "coordinates").text = (
            f"{wp.longitude:.7f},{wp.latitude:.7f},{msl:.1f}"
        )

    raw = ET.tostring(root, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ")


def _add_data(parent: ET.Element, name: str, value: str) -> None:
    d = ET.SubElement(parent, "Data", name=name)
    ET.SubElement(d, "value").text = value


def _add_style(parent: ET.Element, style_id: str, color: str, scale: str) -> None:
    s = ET.SubElement(parent, "Style", id=style_id)
    icon = ET.SubElement(s, "IconStyle")
    ET.SubElement(icon, "color").text = color
    ET.SubElement(icon, "scale").text = scale
    ET.SubElement(icon, "Icon").text = ""


class KmlExporter(MissionExporter):
    name = "KML"
    extension = ".kml"
    version = "2.2"
    description = "Keyhole Markup Language para Google Earth"

    def export(self, mission: MissionExportData) -> ExportResult:
        kml = _build_kml(mission)
        return ExportResult(
            data=kml.encode("utf-8"),
            filename=f"{mission.project_name}.kml",
            mime_type="application/vnd.google-earth.kml+xml",
        )
