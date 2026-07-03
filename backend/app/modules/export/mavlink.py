from __future__ import annotations
import json
import struct
from typing import Any

from .base import MissionExporter, ExportResult, ValidationResult
from .models import MissionExportData


def _build_mavlink_json(mission: MissionExportData) -> str:
    items: list[dict[str, Any]] = []
    seq = 0

    if mission.home:
        items.append({
            "seq": seq, "frame": 0, "command": 22,
            "current": 1, "autoContinue": 1,
            "param1": 0, "param2": 0, "param3": 0, "param4": 0,
            "param5": 0, "param6": 0, "param7": mission.altitude,
            "x": int(mission.home.latitude * 1e7),
            "y": int(mission.home.longitude * 1e7),
            "z": mission.altitude,
        })
        seq += 1

    for wp in mission.waypoints:
        items.append({
            "seq": seq, "frame": 3, "command": 16,
            "current": 0, "autoContinue": 1,
            "param1": wp.curve_size or 0,
            "param2": wp.speed or mission.speed_ms,
            "param3": 0, "param4": wp.heading or 0,
            "param5": wp.action_type if wp.action_type > 0 else -1,
            "param6": wp.action_param or 0,
            "param7": 0,
            "x": int(wp.latitude * 1e7),
            "y": int(wp.longitude * 1e7),
            "z": round(wp.altitude, 2),
        })
        seq += 1

    doc: dict[str, Any] = {
        "protocol": "MAVLink 2.0",
        "messageType": "MISSION_ITEM_INT",
        "mission": {
            "count": len(items),
            "items": items,
        },
    }
    return json.dumps(doc, indent=2)


def _build_mavlink_binary(mission: MissionExportData) -> bytes:
    buf = bytearray()
    seq = 0

    if mission.home:
        buf.extend(_pack_item(seq, 0, 22, 1, 1,
                              0, 0, 0, 0,
                              0, 0, mission.altitude))
        seq += 1

    for wp in mission.waypoints:
        buf.extend(_pack_item(seq, 3, 16, 0, 1,
                              wp.curve_size or 0,
                              wp.speed or mission.speed_ms,
                              0,
                              wp.heading or 0,
                              int(wp.latitude * 1e7),
                              int(wp.longitude * 1e7),
                              round(wp.altitude, 2)))
        seq += 1

    return bytes(buf)


def _pack_item(seq: int, frame: int, cmd: int,
               current: int, autocontinue: int,
               p1: float, p2: float, p3: float, p4: float,
               x: int, y: int, z: float) -> bytes:
    # MAVLink MISSION_ITEM_INT payload:
    # uint8_t target_system, uint8_t target_component,
    # uint16_t seq, uint8_t frame, uint16_t command,
    # uint8_t current, uint8_t autocontinue,
    # float param1..param4, int32_t x, int32_t y, float z
    payload = struct.pack("<BBHBHBBffffiif",
                          0, 0,      # target_system, target_component
                          seq, frame, cmd, current, autocontinue,
                          p1, p2, p3, p4,
                          x, y, z)
    return payload


class MavlinkExporter(MissionExporter):
    name = "MAVLink Mission"
    extension = ".mavlink"
    version = "2.0"
    description = "Misión en formato MAVLink (JSON + binario)"

    def export(self, mission: MissionExportData) -> ExportResult:
        json_data = _build_mavlink_json(mission)
        return ExportResult(
            data=json_data,
            filename=f"{mission.project_name}.mavlink.json",
            mime_type="application/json",
        )


class MavlinkBinaryExporter(MissionExporter):
    name = "MAVLink Binary"
    extension = ".bin"
    version = "2.0"
    description = "Misión en formato MAVLink binario (.mavlink)"

    def export(self, mission: MissionExportData) -> ExportResult:
        binary = _build_mavlink_binary(mission)
        return ExportResult(
            data=binary,
            filename=f"{mission.project_name}.mavlink.bin",
            mime_type="application/octet-stream",
            is_binary=True,
        )
