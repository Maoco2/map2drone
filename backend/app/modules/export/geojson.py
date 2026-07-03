from __future__ import annotations
import json
from typing import Any

from .base import MissionExporter, ExportResult, ValidationResult
from .models import MissionExportData


def _build_geojson(mission: MissionExportData) -> str:
    features: list[dict[str, Any]] = []

    # Home point
    if mission.home:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [mission.home.longitude, mission.home.latitude, mission.altitude],
            },
            "properties": {
                "name": "Home Point",
                "type": "home",
                "altitude": mission.altitude,
            },
        })

    # Waypoints as Point features
    for i, wp in enumerate(mission.waypoints):
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [wp.longitude, wp.latitude, wp.altitude],
            },
            "properties": {
                "name": f"Waypoint {i + 1}",
                "type": "waypoint",
                "index": i,
                "altitude": wp.altitude,
                "heading": wp.heading,
                "speed": wp.speed or mission.speed_ms,
                "action_type": wp.action_type,
                "action_param": wp.action_param,
            },
        })

    # Flight route as LineString
    if len(mission.waypoints) >= 2:
        coords = [[wp.longitude, wp.latitude, wp.altitude] for wp in mission.waypoints]
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
            "properties": {
                "name": "Flight Route",
                "type": "route",
                "distance_m": mission.total_distance_m,
                "waypoint_count": len(mission.waypoints),
            },
        })

    # Mission metadata
    fc: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "project": mission.project_name,
            "software": mission.software,
            "version": mission.version,
            "export_date": mission.export_date,
            "drone": mission.drone.name if mission.drone else "",
            "camera": mission.camera.name if mission.camera else "",
            "coordinate_system": mission.coordinate_system,
            "epsg": mission.epsg,
            "altitude_mode": mission.altitude_mode,
            "terrain_following": mission.terrain_following,
            "speed_ms": mission.speed_ms,
            "total_distance_m": mission.total_distance_m,
            "estimated_time_s": mission.estimated_time_s,
            "photo_count": mission.photo_count,
            "area_ha": mission.area_ha,
            "gsd_cm": mission.gsd_cm,
        },
    }

    return json.dumps(fc, indent=2)


class GeoJsonExporter(MissionExporter):
    name = "GeoJSON"
    extension = ".geojson"
    version = "1.0"
    description = "GeoJSON FeatureCollection con waypoints, ruta y metadatos"

    def export(self, mission: MissionExportData) -> ExportResult:
        geojson = _build_geojson(mission)
        return ExportResult(
            data=geojson,
            filename=f"{mission.project_name}.geojson",
            mime_type="application/geo+json",
        )
