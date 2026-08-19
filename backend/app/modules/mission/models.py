"""Universal Mission Model — typed mission payload (Fase 10A + 10B).

The Universal Mission Model is the single source of truth for a
photogrammetric mission. It supersedes the ad-hoc ``grid_result_json`` blob
while remaining *backward compatible*: the legacy serializer emits the same
flat shape the API responses and the frontend use, and the legacy reader
accepts old blobs that lack the new fields.

Fase 10B extends the model with the normative blocks consumed by the exporters:

* :class:`UniversalWaypoint` — a rich, per-waypoint structure.
* :class:`FlightSegment` — flight/turn segmentation.
* :class:`CapturePlan` — capture mode + scientific/commercial intervals.
* :class:`TurnPlan` — turn-radius plan adapted from the engine (no physics
  duplicated here).
* :class:`DroneProfile` / :class:`CameraProfile` — platform profiles.
* Versioning (``schema_version``) with a forward-compatible mechanism.

No formula is implemented in this module: every value is copied from the
existing engines (Planning Core, CaptureInterval, TurnRadius).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"

#: Versions accepted by ``parse_mission_blob`` / the serializer. New minor
#: versions must stay readable; only major bumps require migration helpers.
SUPPORTED_VERSIONS = {"1.0"}

#: Version aliases accepted when reading stored missions (e.g. a legacy
#: ``"1.0.0"`` string). Migrations for future major versions live here.
VERSION_ALIASES = {"1.0.0": "1.0"}


def normalize_schema_version(raw) -> str:
    """Normalize an arbitrary stored version string to the canonical form."""
    if raw is None:
        return SCHEMA_VERSION
    text = str(raw).strip()
    return VERSION_ALIASES.get(text, text)


def is_supported_version(version: str) -> bool:
    return normalize_schema_version(version) in SUPPORTED_VERSIONS


# ── Mission metadata ─────────────────────────────────────────────────────────


class MissionMetadata(BaseModel):
    """Mission identity and coordinate reference metadata."""

    mission_id: Optional[str] = None
    name: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    coordinate_reference: str = "EPSG:4326 (WGS84)"


# ── Mission parameters ───────────────────────────────────────────────────────


class MissionParameters(BaseModel):
    """Mission planning parameters (authoritative copy, no recomputation)."""

    altitude_m: float = 0.0
    overlap_frontal: float = 0.0
    overlap_lateral: float = 0.0
    altitude_mode: str = "takeoff"
    speed_ms: float = 0.0
    drone_id: Optional[str] = None
    camera_id: Optional[str] = None
    capture_interval_s: Optional[float] = None
    sweep_deg: Optional[float] = None
    width_left_m: Optional[float] = None
    width_right_m: Optional[float] = None
    dem_resolution_m: Optional[float] = None

    # ── Fase 10B: normalized parameter block (values copied from engines) ──
    altitude_reference: str = "takeoff"
    recommended_speed_mps: Optional[float] = None
    gsd_cm: Optional[float] = None
    footprint_width_m: Optional[float] = None
    footprint_length_m: Optional[float] = None
    overlap_front: Optional[float] = None
    overlap_side: Optional[float] = None
    line_spacing_m: Optional[float] = None
    photo_spacing_m: Optional[float] = None
    capture_mode: str = "NONE"  # NONE | TIME | DISTANCE
    turn_mode: str = "NONE"  # AUTO | MANUAL | NONE
    turn_radius_m: Optional[float] = None
    turn_radius_result: Optional[dict] = None
    battery_count: Optional[int] = None
    flight_time_min: Optional[float] = None
    estimated_time_s: Optional[float] = None
    total_distance_m: Optional[float] = None
    photo_count: Optional[int] = None


# ── Universal waypoint ───────────────────────────────────────────────────────


class UniversalWaypoint(BaseModel):
    """A universal waypoint that every exporter can read.

    Not every exporter needs every field, but the universal model preserves
    them all. Coordinates are EPSG:4326. ``action_type`` mirrors the engine
    convention (``1`` → photo trigger); ``action`` is the legacy action
    parameter. ``line_index`` / ``segment_index`` / ``photo_index`` are filled
    by the builder from the mission structure.
    """

    index: int = 0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None
    heading_deg: Optional[float] = None
    speed_mps: Optional[float] = None

    action_type: Optional[int] = None
    action: Optional[float] = None

    gimbal_mode: Optional[int] = None
    gimbal_pitch_deg: Optional[float] = None

    curve_size_m: float = 0.0

    capture_enabled: bool = False
    capture_time_interval_s: Optional[float] = None
    capture_distance_interval_m: Optional[float] = None

    photo_index: Optional[int] = None
    line_index: Optional[int] = None
    segment_index: Optional[int] = None

    terrain_elevation_m: Optional[float] = None
    agl_m: Optional[float] = None


# ── Flight segments ──────────────────────────────────────────────────────────


class FlightSegment(BaseModel):
    """A straight or turn segment between two waypoints.

    Values are copied from the engines (metrics + turn plan); the segment
    distances reuse the Planning Core distance helpers — no formula is
    duplicated here.
    """

    segment_index: int = 0
    start_waypoint: int = 0
    end_waypoint: int = 0
    distance_m: float = 0.0
    heading_deg: Optional[float] = None
    speed_mps: Optional[float] = None
    duration_s: float = 0.0
    line_index: Optional[int] = None
    is_photo_segment: bool = False
    is_turn_segment: bool = False
    turn_angle_deg: Optional[float] = None


# ── Capture plan ─────────────────────────────────────────────────────────────


class CaptureMode(str, Enum):
    NONE = "NONE"
    TIME = "TIME"
    DISTANCE = "DISTANCE"


class CapturePlan(BaseModel):
    """Capture plan adapted from the CaptureInterval engine (engine untouched).

    ``scientific_interval_s`` is the exact ideal interval; ``commercial_interval_s``
    is the operational integer already produced by the engine (no floor policy is
    applied here — the engine owns it). Platform-specific conversion (e.g. Litchi's
    ``floor(scientific)``) belongs to the exporter adapter.
    """

    mode: CaptureMode = CaptureMode.NONE
    scientific_interval_s: Optional[float] = None
    commercial_interval_s: Optional[int] = None
    photo_spacing_m: Optional[float] = None
    status: str = "NONE"  # VALID | WARNING | INCOMPATIBLE | ERROR | NONE


# ── Turn plan ────────────────────────────────────────────────────────────────


class TurnPlan(BaseModel):
    """Turn-radius plan adapted from the TurnRadius engine (physics untouched)."""

    mode: str = "NONE"  # AUTO | MANUAL | NONE
    status: str = "NONE"  # VALID | CONSTRAINED | INVALID | NONE
    radius_m: Optional[float] = None
    safe_radius_m: Optional[float] = None
    available_radius_m: Optional[float] = None
    extension_m: Optional[float] = None
    a_lat_ms2: Optional[float] = None
    safety_factor: Optional[float] = None
    turn_duration_s: Optional[float] = None
    turn_distance_m: Optional[float] = None
    turn_count: int = 0
    turns: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    geometry: Optional[dict] = None


# ── Drone / camera profiles ──────────────────────────────────────────────────


class DroneDynamicsProvenance(str, Enum):
    DEFAULT = "DEFAULT"
    USER = "USER"
    DRONE_PROFILE = "DRONE_PROFILE"


class DroneFlightDynamicsProfile(BaseModel):
    """Flight-dynamics parameters with explicit provenance.

    ``DEFAULT`` is used whenever the drone profile carries no dynamic data —
    it must be explicitly indicated, and never presented as manufacturer data.
    """

    max_lateral_acceleration_ms2: Optional[float] = None
    preferred_turn_speed_mps: Optional[float] = None
    min_turn_radius_m: Optional[float] = None
    max_turn_radius_m: Optional[float] = None
    provenance: DroneDynamicsProvenance = DroneDynamicsProvenance.DEFAULT


class DroneProfile(BaseModel):
    """Drone profile as known at planning time (no invented parameters)."""

    id: Optional[str] = None
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    weight_kg: Optional[float] = None
    max_speed_ms: Optional[float] = None
    flight_time_min: Optional[float] = None
    max_altitude_m: Optional[float] = None
    dynamics: DroneFlightDynamicsProfile = DroneFlightDynamicsProfile()


class CameraProfile(BaseModel):
    """Camera profile as known at planning time.

    ``shutter_latency_ms`` / ``gimbal_max_rotation_rate_deg_s`` / ``burst_rate_fps``
    are reserved optional fields — never invented.
    """

    id: Optional[str] = None
    name: Optional[str] = None
    sensor_width_mm: Optional[float] = None
    sensor_height_mm: Optional[float] = None
    resolution_width_px: Optional[int] = None
    resolution_height_px: Optional[int] = None
    focal_length_mm: Optional[float] = None
    pixel_size_um: Optional[float] = None
    shutter_type: Optional[str] = None
    shutter_speed_s: Optional[float] = None
    shutter_latency_ms: Optional[float] = None
    gimbal_max_rotation_rate_deg_s: Optional[float] = None
    burst_rate_fps: Optional[float] = None


# ── Mission metrics ──────────────────────────────────────────────────────────


class MissionMetrics(BaseModel):
    """Consolidated mission metrics (Planning Core accounting model).

    All values are copied from the engines, never recomputed here.
    """

    total_distance_m: float = 0.0
    estimated_time_sec: float = 0.0
    straight_distance_m: float = 0.0
    transition_distance_m: float = 0.0
    turn_distance_m: float = 0.0
    straight_time_s: float = 0.0
    transition_time_s: float = 0.0
    turn_time_s: float = 0.0
    turn_source: str = "overhead_fallback"
    battery_count: int = 1
    gsd_cm: float = 0.0
    footprint_width_m: float = 0.0
    footprint_height_m: float = 0.0
    line_spacing_m: float = 0.0
    photo_spacing_m: float = 0.0
    num_lines: int = 0
    photo_count: int = 0

    # ── Fase 10B: normalized metrics block ────────────────────────────────
    flight_distance_m: float = 0.0
    flight_time_s: float = 0.0
    straight_flight_time_s: float = 0.0
    line_count: int = 0
    waypoint_count: int = 0
    estimated_energy: Optional[float] = None


# ── Geometry ─────────────────────────────────────────────────────────────────


class MissionGeometry(BaseModel):
    """Optional projected geometry block (corridor) or grid flight lines.

    All GeoJSON payloads for interchange are EPSG:4326; the original projected
    CRS is preserved as metadata (``epsg_out`` / ``crs_name``).

    * AREA_GRID:        centerline = None, polygon = None, flight_lines set.
    * LINEAR_CORRIDOR:  centerline + polygon (corridor) + flight_lines set.
    """

    polygon_geojson: Optional[dict] = None
    flight_lines_geojson: Optional[dict] = None
    centerline_geojson: Optional[dict] = None
    epsg_out: int = 4326
    crs_name: str = "WGS84"
    transformation: str = ""

    # ── Fase 10B ──────────────────────────────────────────────────────────
    turn_geometry: Optional[dict] = None
    photo_points: list[dict] = Field(default_factory=list)


# ── Universal mission root ───────────────────────────────────────────────────


class UniversalMission(BaseModel):
    """Typed, serializable mission payload (source of truth)."""

    schema_version: str = SCHEMA_VERSION
    mission_type: str = "grid"  # "grid" | "linear_corridor"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Fase 10B metadata
    mission_id: Optional[str] = None
    name: Optional[str] = None
    coordinate_reference: str = "EPSG:4326 (WGS84)"

    parameters: MissionParameters
    waypoints: list[UniversalWaypoint] = Field(default_factory=list)
    segments: list[FlightSegment] = Field(default_factory=list)

    flight_lines_geojson: Optional[dict] = None
    geometry: Optional[MissionGeometry] = None
    photo_points: list[dict] = Field(default_factory=list)

    metrics: MissionMetrics = MissionMetrics()
    capture_interval: Optional[dict] = None
    capture_plan: Optional[CapturePlan] = None
    turn_radius_result: Optional[dict] = None
    turn_plan: Optional[TurnPlan] = None
    turn_radius_warnings: list[str] = Field(default_factory=list)

    drone_profile: Optional[DroneProfile] = None
    camera_profile: Optional[CameraProfile] = None

    warnings: list[str] = Field(default_factory=list)


__all__ = [
    "SCHEMA_VERSION",
    "SUPPORTED_VERSIONS",
    "VERSION_ALIASES",
    "CameraProfile",
    "CaptureMode",
    "CapturePlan",
    "DroneDynamicsProvenance",
    "DroneFlightDynamicsProfile",
    "DroneProfile",
    "FlightSegment",
    "MissionGeometry",
    "MissionMetadata",
    "MissionMetrics",
    "MissionParameters",
    "TurnPlan",
    "UniversalMission",
    "UniversalWaypoint",
    "is_supported_version",
    "normalize_schema_version",
]
