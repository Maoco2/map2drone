from __future__ import annotations
import xml.etree.ElementTree as ET
from xml.dom import minidom

from .base import MissionExporter, ExportResult, ValidationResult, ValidationError
from .models import MissionExportData


def _build_xml(mission: MissionExportData) -> str:
    root = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
    doc = ET.SubElement(root, "Document")

    # Mission config
    mc = ET.SubElement(doc, "MissionConfig")
    flight_speed = ET.SubElement(mc, "flightSpeed")
    flight_speed.text = f"{mission.speed_ms:.1f}"
    home = ET.SubElement(mc, "homePoint")
    home_lat = ET.SubElement(home, "latitude")
    home_lat.text = f"{mission.home.latitude:.7f}" if mission.home else "0"
    home_lng = ET.SubElement(home, "longitude")
    home_lng.text = f"{mission.home.longitude:.7f}" if mission.home else "0"

    takeoff = ET.SubElement(mc, "takeOffAltitude")
    takeoff.text = f"{mission.altitude:.1f}"
    action = ET.SubElement(mc, "actionOnRCLost")
    action.text = "goHome"
    end = ET.SubElement(mc, "actionOnMissionFinish")
    end.text = "goHome"
    ref = ET.SubElement(mc, "coordinateSystem")
    ref.text = "WGS84"
    total = ET.SubElement(mc, "totalWaypoints")
    total.text = str(len(mission.waypoints))
    mode = ET.SubElement(mc, "headingMode")
    mode.text = "auto"

    is_interval_mode = mission.altitude_mode in ("takeoff", "ground")

    # Waypoints
    for i, wp in enumerate(mission.waypoints):
        wp_elem = ET.SubElement(doc, "MissionItem")
        wp_id = ET.SubElement(wp_elem, "waypointIndex")
        wp_id.text = str(i)
        lat = ET.SubElement(wp_elem, "latitude")
        lat.text = f"{wp.latitude:.7f}"
        lng = ET.SubElement(wp_elem, "longitude")
        lng.text = f"{wp.longitude:.7f}"
        alt = ET.SubElement(wp_elem, "executeHeight")
        alt.text = f"{wp.altitude:.1f}"
        wps = ET.SubElement(wp_elem, "waypointSpeed")
        wps.text = f"{wp.speed or mission.speed_ms:.1f}"
        heading = ET.SubElement(wp_elem, "heading")
        heading.text = f"{wp.heading:.1f}"
        turn = ET.SubElement(wp_elem, "turnMode")
        turn.text = "banked" if wp.curve_size > 0 else "stop"
        cs = ET.SubElement(wp_elem, "curveSize")
        cs.text = f"{wp.curve_size:.1f}"

        # Determine if this waypoint starts a scan line (for interval mode)
        is_scan_entry = False
        is_scan_exit = False
        if is_interval_mode and i < len(mission.waypoints) - 1:
            nxt = mission.waypoints[i + 1]
            hdg_diff = abs(wp.heading - nxt.heading) % 360
            if hdg_diff > 180:
                hdg_diff = 360 - hdg_diff
            is_scan_entry = hdg_diff <= 45
        if is_interval_mode and i > 0:
            prev = mission.waypoints[i - 1]
            hdg_diff = abs(prev.heading - wp.heading) % 360
            if hdg_diff > 180:
                hdg_diff = 360 - hdg_diff
            is_scan_exit = hdg_diff > 45

        _add_action_group(wp_elem, wp, is_interval_mode, is_scan_entry, is_scan_exit,
                          mission.photo_spacing, mission.speed_ms)

    raw = ET.tostring(root, encoding="unicode")
    return minidom.parseString(raw).toprettyxml(indent="  ")


def _add_action_group(parent: ET.Element, wp: ExportWaypoint,
                      is_interval_mode: bool, is_scan_entry: bool, is_scan_exit: bool,
                      photo_spacing: float, speed_ms: float) -> None:
    ag = ET.SubElement(parent, "actionGroup")
    ag_id = ET.SubElement(ag, "actionGroupIndex")
    ag_id.text = "1"
    ag_en = ET.SubElement(ag, "actionGroupEnable")
    ag_en.text = "1"
    trig = ET.SubElement(ag, "actionTrigger")
    trig_type = ET.SubElement(trig, "actionTriggerType")
    trig_type.text = "reachPoint"
    act_list = ET.SubElement(ag, "actionList")

    if is_interval_mode and is_scan_entry and photo_spacing > 0 and speed_ms > 0:
        interval_ms = int(photo_spacing / speed_ms * 1000)
        _add_action(act_list, 15, float(interval_ms))
    elif is_interval_mode and is_scan_exit:
        _add_action(act_list, 16, 0)
    else:
        _add_action(act_list, wp.action_type, wp.action_param)
        for a in wp.actions:
            _add_action(act_list, a.action_type, a.action_param)


def _add_action(parent: ET.Element, action_type: int, action_param: float) -> None:
    if action_type < 0:
        return
    ae = ET.SubElement(parent, "action")
    at = ET.SubElement(ae, "actionType")
    at.text = str(action_type)
    ap = ET.SubElement(ae, "actionParam")
    ap.text = f"{action_param:.1f}"


class DjiWpmlExporter(MissionExporter):
    name = "DJI WPML"
    extension = ".wpml"
    version = "2.0"
    description = "Waypoint Markup Language compatible con DJI Pilot 2"

    def validate(self, mission: MissionExportData) -> ValidationResult:
        errors: list[ValidationError] = []
        if len(mission.waypoints) > 240:
            errors.append(ValidationError(
                field="waypoints",
                message=f"DJI Pilot 2 soporta máximo 240 waypoints (se tienen {len(mission.waypoints)})"
            ))
        if not mission.home or (mission.home.latitude == 0 and mission.home.longitude == 0):
            errors.append(ValidationError(
                field="home",
                message="Se requiere un Home Point válido para DJI WPML"
            ))
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def export(self, mission: MissionExportData) -> ExportResult:
        xml = _build_xml(mission)
        return ExportResult(
            data=xml.encode("utf-8"),
            filename=f"{mission.project_name}.wpml",
            mime_type="application/vnd.google-earth.kml+xml",
            is_binary=False,
        )
