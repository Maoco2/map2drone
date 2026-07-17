from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6)
    country: str = ""
    city: str = ""
    phone: str = ""
    gender: str = ""
    profession: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    full_name: str
    email: str
    country: str
    city: str
    phone: str
    gender: str
    profession: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = ""
    client: Optional[str] = ""
    location: Optional[str] = ""


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    client: str
    location: str
    user_id: Optional[str] = None
    date: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MissionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    mission_type: str = "grid"
    polygon_geojson: str = ""
    waypoints_json: str = ""
    parameters_json: str = ""
    grid_result_json: str = ""


class MissionUpdate(BaseModel):
    name: Optional[str] = None
    polygon_geojson: Optional[str] = None
    waypoints_json: Optional[str] = None
    parameters_json: Optional[str] = None
    grid_result_json: Optional[str] = None


class MissionResponse(BaseModel):
    id: str
    project_id: str
    name: str
    mission_type: str
    polygon_geojson: str
    waypoints_json: str
    parameters_json: str
    grid_result_json: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WaypointSchema(BaseModel):
    latitude: float
    longitude: float
    altitude: float
    heading: float = 0
    speed: Optional[float] = None
    action_type: Optional[int] = -1
    action_param: Optional[float] = 0
    elevation_msnm: Optional[float] = None
    agl: Optional[float] = None


class GridRequest(BaseModel):
    polygon: dict
    altitude: float = Field(..., ge=10, le=500)
    overlap_frontal: float = Field(..., ge=50, le=95)
    overlap_lateral: float = Field(..., ge=30, le=90)
    camera_id: Optional[str] = None
    drone_id: Optional[str] = None
    project_id: Optional[str] = None
    home_latitude: Optional[float] = None
    home_longitude: Optional[float] = None
    rotation_deg: Optional[float] = None
    grid_type: str = "simple"
    altitude_mode: str = "takeoff"
    dem_resolution_m: Optional[float] = None


class GridResponse(BaseModel):
    waypoints: list[WaypointSchema]
    total_distance: float
    estimated_time_sec: float
    photo_count: int
    battery_count: int
    gsd: float
    footprint_width: float
    footprint_height: float
    line_spacing: float
    photo_spacing: float
    recommended_speed_ms: float = 0
    mission_id: Optional[str] = None
    sweep_deg: float = 0
    num_lines: int = 0
    waypoint_mode: str = "photo"


class GSDRequest(BaseModel):
    altitude: float = Field(..., ge=10, le=500)
    camera_id: str


class GSDResponse(BaseModel):
    gsd: float
    footprint_width: float
    footprint_height: float


class DroneResponse(BaseModel):
    id: str
    name: str
    manufacturer: str
    weight_kg: float
    max_speed_ms: float
    flight_time_min: float
    max_altitude_m: float
    camera_id: Optional[str] = None

    model_config = {"from_attributes": True}


class CameraResponse(BaseModel):
    id: str
    name: str
    sensor_width_mm: float
    sensor_height_mm: float
    image_width_px: int
    image_height_px: int
    focal_length_mm: float
    pixel_size_um: float
    shutter_speed_s: float = 0.001
    model_config = {"from_attributes": True}


class ExportWaypointSchema(BaseModel):
    latitude: float
    longitude: float
    altitude: float
    heading: float = 0
    speed: Optional[float] = None
    curve_size: float = 0
    gimbal_pitch: float = -90
    action_type: int = -1
    action_param: float = 0
    elevation_msnm: Optional[float] = None
    agl: Optional[float] = None


class ExportFormatItem(BaseModel):
    id: str
    name: str
    extension: str
    version: str
    description: str


class ExportRequest(BaseModel):
    format: str = "litchi"
    project_name: str = "Mission"
    waypoints: list[ExportWaypointSchema] = []
    altitude: float = 100
    speed: float = 10
    altitude_mode: str = "takeoff"
    home_latitude: Optional[float] = None
    home_longitude: Optional[float] = None
    drone_name: str = ""
    camera_name: str = ""
    total_distance: float = 0
    estimated_time: float = 0
    photo_count: int = 0
    area_ha: float = 0
    gsd: float = 0
    sweep_deg: float = 0
    line_spacing: float = 0
    photo_spacing: float = 0
    overlap_frontal: float = 75
    overlap_lateral: float = 65
    battery_count: int = 0


class MultiExportRequest(BaseModel):
    formats: list[str] = ["litchi"]
    project_name: str = "Mission"
    waypoints: list[ExportWaypointSchema] = []
    altitude: float = 100
    speed: float = 10
    altitude_mode: str = "takeoff"
    home_latitude: Optional[float] = None
    home_longitude: Optional[float] = None
    drone_name: str = ""
    camera_name: str = ""
    total_distance: float = 0
    estimated_time: float = 0
    photo_count: int = 0
    area_ha: float = 0
    gsd: float = 0
    sweep_deg: float = 0
    line_spacing: float = 0
    photo_spacing: float = 0
    overlap_frontal: float = 75
    overlap_lateral: float = 65
    battery_count: int = 0
