from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Action(BaseModel):
    action_type: int = -1
    action_param: float = 0


class ExportWaypoint(BaseModel):
    latitude: float
    longitude: float
    altitude: float
    heading: float = 0
    speed: Optional[float] = None
    curve_size: float = 0
    rotation_dir: int = 0
    gimbal_pitch: float = -90
    gimbal_mode: int = 2
    action_type: int = -1
    action_param: float = 0
    actions: list[Action] = []
    elevation_msnm: Optional[float] = None
    agl: Optional[float] = None


class HomePoint(BaseModel):
    latitude: float = 0
    longitude: float = 0
    altitude: float = 0


class DroneInfo(BaseModel):
    id: str = ""
    name: str = ""
    manufacturer: str = ""
    max_speed_ms: float = 10.0
    flight_time_min: float = 25
    max_altitude_m: float = 500


class CameraInfo(BaseModel):
    id: str = ""
    name: str = ""
    focal_length_mm: float = 0
    pixel_size_um: float = 0
    image_width_px: int = 0
    image_height_px: int = 0


class MissionExportData(BaseModel):
    project_name: str = "Untitled"
    export_date: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    software: str = "Map2Drone"
    version: str = "1.0.0"
    user: str = ""
    drone: Optional[DroneInfo] = None
    camera: Optional[CameraInfo] = None
    coordinate_system: str = "WGS84"
    epsg: int = 4326

    home: Optional[HomePoint] = None
    waypoints: list[ExportWaypoint] = []
    speed_ms: float = 10.0
    altitude: float = 100.0
    altitude_mode: str = "takeoff"
    waypoint_mode: str = "photo"
    overlap_frontal: float = 75
    overlap_lateral: float = 65
    terrain_following: bool = False
    mission_type: str = "grid"

    total_distance_m: float = 0
    estimated_time_s: float = 0
    photo_count: int = 0
    area_ha: float = 0
    gsd_cm: float = 0
    sweep_deg: float = 0
    line_spacing: float = 0
    photo_spacing: float = 0
    battery_count: int = 0
