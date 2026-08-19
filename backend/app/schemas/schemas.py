from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


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


class CaptureIntervalBlock(BaseModel):
    """Photo capture interval recommendation from the universal engine.

    `recommended_interval_s` is the operational value and is ALWAYS an integer
    number of seconds. `ideal_interval_s` is informational only. Overlap values
    are expressed in percent (0-100).

    Terrain-follow fields (`terrain_follow`, `planned_agl_m`, `assumed_agl_m`,
    `assumed_footprint_length_m`) expose the AGL that was actually used for the
    conservative photogrammetric footprint. `assumed_agl_m` is the minimum
    plausible AGL and is an ESTIMATE (it can be below the planned altitude);
    it is never the nominal flight altitude by itself.
    """

    status: str = "ERROR"
    required_photo_spacing_m: Optional[float] = None
    ideal_interval_s: Optional[float] = None
    recommended_interval_s: Optional[int] = None
    actual_photo_spacing_m: Optional[float] = None
    effective_front_overlap: Optional[float] = None
    required_front_overlap: Optional[float] = None
    speed_mps: Optional[float] = None
    maximum_speed_for_1s: Optional[float] = None
    planned_agl_m: Optional[float] = None
    terrain_follow: bool = False
    assumed_agl_m: Optional[float] = None
    assumed_footprint_length_m: Optional[float] = None


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
    turn_radius: Optional[dict] = None


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
    warnings: list[str] = []
    capture_interval: Optional[CaptureIntervalBlock] = None
    turn_radius_result: Optional[dict] = None
    turn_radius_warnings: list[str] = []
    flight_lines_geojson: Optional[dict] = None
    photo_points: list[dict] = []


class TurnRadiusRequest(BaseModel):
    """Live recompute of the turn-radius plan for an existing flight plan.

    ``waypoints`` are the mission waypoints as returned by the grid/corridor
    planner (heading groups reconstruct the flight lines). ``mission_type``
    selects the planner; for LINEAR_CORRIDOR the real ``flight_lines_geojson``
    is used when provided so turn angles follow the corridor bends.
    """

    mission_type: str = "AREA_GRID"
    waypoints: list[WaypointSchema] = []
    line_spacing: float = 0
    recommended_speed_ms: float = 6.8
    turn_radius: dict = {}
    flight_lines_geojson: Optional[dict] = None


class TurnRadiusResponse(BaseModel):
    turn_radius_result: Optional[dict] = None
    turn_radius_warnings: list[str] = []


class CorridorRequest(BaseModel):
    centerline: dict
    width_left: float = Field(..., gt=0, le=10000)
    width_right: float = Field(..., gt=0, le=10000)
    altitude: float = Field(..., ge=10, le=500)
    overlap_frontal: float = Field(..., ge=50, le=95)
    overlap_lateral: float = Field(..., ge=30, le=90)
    camera_id: Optional[str] = None
    drone_id: Optional[str] = None
    project_id: Optional[str] = None
    home_latitude: Optional[float] = None
    home_longitude: Optional[float] = None
    altitude_mode: str = "takeoff"
    dem_resolution_m: Optional[float] = None
    turn_radius: Optional[dict] = None


class CorridorGeometry(BaseModel):
    polygon_geojson: dict = {}
    flight_lines_geojson: dict = {}
    centerline_geojson: dict = {}
    epsg_out: int = 4326
    crs_name: str = "WGS84"
    transformation: str = ""


class CorridorResponse(BaseModel):
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
    num_lines: int = 0
    waypoint_mode: str = "photo"
    corridor_length_m: float = 0
    corridor_area_m2: float = 0
    geometry: CorridorGeometry = CorridorGeometry()
    warnings: list[str] = []
    capture_interval: Optional[CaptureIntervalBlock] = None
    turn_radius_result: Optional[dict] = None
    turn_radius_warnings: list[str] = []
    photo_points: list[dict] = []


class CorridorImportResponse(CorridorResponse):
    import_format: str = ""
    import_source: str = ""
    features_found: int = 0


class CorridorParseResponse(BaseModel):
    centerline: dict
    import_format: str = ""
    import_source: str = ""
    features_found: int = 0
    warnings: list[str] = []


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
    shutter_type: str = "electronic"
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
    compatibility: Optional[dict] = None


class ExportFormatCheckItem(BaseModel):
    id: str
    name: str
    extension: str
    compatibility: Optional[dict] = None
    warnings: list[dict] = []


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
    capture_interval_s: Optional[int] = None
    options: dict = {}


class MissionValidateRequest(BaseModel):
    payload: dict | str


class MissionValidateResponse(BaseModel):
    valid: bool
    status: str = "VALID"
    errors: list[dict] = []
    warnings: list[dict] = []


class OptimizerEvaluateRequest(BaseModel):
    mission: dict
    drone_profile: Optional[dict] = None
    camera_profile: Optional[dict] = None
    constraints: Optional[dict] = None
    weights: Optional[dict] = None


class OptimizerEvaluateResponse(BaseModel):
    valid: bool
    status: str = "VALID"
    metrics: dict = {}
    score: Optional[dict] = None
    warnings: list[str] = []
    validation: Optional[dict] = None


# ── Optimizer solve (Fase 10C-10) ────────────────────────────────────────────


class OptimizerVariableDeclaration(BaseModel):
    """Single optimizable variable declaration (mirrors the optimizer contract).

    ``mode`` is ``fixed`` / ``range`` / ``candidate_values``; only the fields
    relevant to the mode are used.
    """

    name: str
    mode: str = "fixed"
    value: Optional[Any] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    values: list[Any] = Field(default_factory=list)


class OptimizerVariablesRequest(BaseModel):
    variables: list[OptimizerVariableDeclaration] = Field(default_factory=list)


class OptimizerSolveRequest(BaseModel):
    """POST /optimizer/solve payload.

    Exactly one of ``grid`` / ``corridor`` must be provided (the base planning
    request the search starts from). ``variables`` declares what to optimize;
    when omitted the base mission itself is evaluated as a single candidate.
    """

    grid: Optional[GridRequest] = None
    corridor: Optional[CorridorRequest] = None
    variables: Optional[OptimizerVariablesRequest] = None
    constraints: Optional[dict] = None
    weights: Optional[dict] = None
    max_candidates: int = 1000

    @model_validator(mode="after")
    def _validate(self) -> "OptimizerSolveRequest":
        if (self.grid is None) == (self.corridor is None):
            raise ValueError("Provide exactly one of 'grid' or 'corridor'")
        if self.max_candidates < 1:
            raise ValueError("max_candidates must be >= 1")
        return self


class OptimizerCandidateResponse(BaseModel):
    """One selected candidate: its variable values, rebuilt mission and score."""

    label: str
    variable_values: dict = Field(default_factory=dict)
    mission: dict = Field(default_factory=dict)
    score: Optional[dict] = None


class OptimizerSolveResponse(BaseModel):
    status: str
    message: str = ""
    best_candidate: Optional[OptimizerCandidateResponse] = None
    best_score: Optional[dict] = None
    alternatives: list[OptimizerCandidateResponse] = Field(default_factory=list)
    stats: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    explanation: Optional[dict] = None


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
    capture_interval_s: Optional[int] = None
    options: dict = {}


class ExportUmmRequest(BaseModel):
    """Export a Universal Mission directly (no legacy rebuild — Fase 10F).

    ``mission`` is a serialized :class:`UniversalMission` (the winner payload
    from the optimizer). ``options`` optionally overrides exporter options
    (e.g. LCHM ``path_mode``); every value is otherwise read from the mission.
    """

    mission: dict
    options: dict = Field(default_factory=dict)


# ── Export readiness (Fase 10F) ──────────────────────────────────────────────


class ExportReadinessStatus(str, Enum):
    READY = "READY"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"


class ExportReadinessItem(BaseModel):
    """Export readiness diagnostic for a single exporter (Fase 10F-8).

    ``status`` is ``READY`` (the exporter can serialize the mission), ``WARNING``
    (serializable with caveats) or ``BLOCKED`` (the exporter refuses — e.g.
    LCHM over its 99-waypoint capacity). ``codes`` carry structured reasons
    (``split_required``, ``turn_radius_invalid``, ``turn_radius_warning``, ...).
    """

    id: str
    name: str
    extension: str
    status: ExportReadinessStatus
    reasons: list[str] = Field(default_factory=list)
    codes: list[str] = Field(default_factory=list)
    compatibility: Optional[dict] = None
    warnings: list[dict] = Field(default_factory=list)


class ExportCheckUmmRequest(BaseModel):
    mission: dict
    formats: list[str] = Field(default_factory=lambda: ["litchi"])


class ExportCheckUmmResponse(BaseModel):
    items: list[ExportReadinessItem] = Field(default_factory=list)


# ── Optimizer apply (Fase 10F-1/2) ───────────────────────────────────────────


class OptimizerApplyRequest(BaseModel):
    """Apply the winner of an optimizer search to the Universal Mission.

    ``solve_request`` is the original ``/optimizer/solve`` payload (the backend
    re-derives the baseline and reproduces the winner deterministically from
    it); ``winner`` is ``best_candidate.mission`` and ``winner_variable_values``
    is ``best_candidate.variable_values`` from the solve response.
    """

    solve_request: OptimizerSolveRequest
    winner: dict
    winner_variable_values: dict = Field(default_factory=dict)
    project_id: Optional[str] = None
    original_mission_id: Optional[str] = None
    name: Optional[str] = None


class MissionComparisonItem(BaseModel):
    """One row of the Baseline vs Winner comparison table (Fase 10F-2)."""

    metric: str
    label: str
    baseline: Optional[float] = None
    winner: Optional[float] = None
    delta: Optional[float] = None
    unit: str = ""


class OptimizerApplyResponse(BaseModel):
    """Backend result of applying the winner (Fase 10F-1).

    ``baseline_mission`` / ``winner_mission`` are the serialized Universal
    Missions (winner == the mission the search evaluated, re-derived and
    verified). ``comparison`` is the before/after table, ``modified_variables``
    the variables that changed, and ``verification`` reports the deterministic
    rebuild check.
    """

    applied: bool = True
    mission_id: Optional[str] = None
    baseline_mission: dict = Field(default_factory=dict)
    baseline_score: Optional[dict] = None
    winner_mission: dict = Field(default_factory=dict)
    winner_score: Optional[dict] = None
    comparison: list[MissionComparisonItem] = Field(default_factory=list)
    modified_variables: list[str] = Field(default_factory=list)
    verification: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
