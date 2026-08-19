"""Turn radius engine — data models.

Fase 8: an independent turn-radius geometry engine.

The engine has NO Litchi knowledge. It works exclusively with geometry,
speed, line separation, area/corridor width, turn angle, safety constraints
and vehicle parameters. Its output is consumed later by LCHM and other
exporters.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DroneDynamicsSource(str, Enum):
    """Provenance of the flight-dynamics parameters.

    ``DEFAULT`` values are conservative engineering defaults and are NEVER
    presented as manufacturer specifications. ``DRONE_PROFILE`` values come
    from a drone profile (future); ``USER`` values come from user input.
    """

    DEFAULT = "DEFAULT"
    USER = "USER"
    DRONE_PROFILE = "DRONE_PROFILE"


class TurnRadiusMode(str, Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    NONE = "NONE"


class TurnStatus(str, Enum):
    VALID = "VALID"
    CONSTRAINED = "CONSTRAINED"
    INVALID = "INVALID"
    NONE = "NONE"


class MissionType(str, Enum):
    AREA_GRID = "AREA_GRID"
    LINEAR_CORRIDOR = "LINEAR_CORRIDOR"


class DroneFlightDynamics(BaseModel):
    """Configurable vehicle parameters.

    IMPORTANT: none of these defaults are manufacturer specifications. They
    are conservative, configurable engineering defaults (``DEFAULT`` source)
    suitable for small/medium survey drones. Do not assume they are valid for
    every drone model; per-model profiles can be provided later via the
    ``DRONE_PROFILE`` source.
    """

    max_lateral_acceleration_ms2: float = Field(4.5, gt=0)
    min_turn_radius_m: float = Field(2.0, ge=0)
    max_turn_radius_m: float = Field(50.0, gt=0)
    preferred_turn_speed_ms: Optional[float] = Field(None, gt=0)
    max_speed_ms: Optional[float] = Field(None, gt=0)
    source: DroneDynamicsSource = DroneDynamicsSource.DEFAULT
    notes: str = Field(
        "Engineering default (conservative, no manufacturer data). No DJI-specific flight dynamics are assumed.",
    )


class TurnRadiusInput(BaseModel):
    """Typed input for the turn-radius engine.

    Optional fields fall back to AUTO values:

    * ``turn_speed_ms``            → ``speed_ms`` (survey speed).
    * ``line_spacing_m``           → derived by the planner from the plan.
    * ``turn_angle_deg``           → 180 for Area Grid; computed from the real
      flight-line geometry for Linear Corridor. Valid range 0–180.
    * ``available_width_m``        → derived from the plan (corridor width /
      line spacing); 0 means "not provided".
    * ``available_length_m``       → 0 means "not provided" (unconstrained).
    * ``max_lateral_acceleration_ms2``, ``min_turn_radius_m``,
      ``max_turn_radius_m``       → from ``drone_dynamics``.
    * ``turn_extension_m``         → AUTO = turn radius (see engine docs).
    * ``safety_factor``            → 1.25 default. This is an engineering
      safety factor, NOT a manufacturer specification.

    ``boundary_polygon`` is an optional GeoJSON Polygon in EPSG:4326 used by
    the geometric available-radius check. When absent, the engine falls back
    to the analytic spacing/length formula (exact for U-turns between
    parallel lines).
    """

    mission_type: MissionType = MissionType.AREA_GRID
    mode: TurnRadiusMode = TurnRadiusMode.AUTO
    speed_ms: float = Field(..., gt=0)
    turn_speed_ms: Optional[float] = Field(None, gt=0)
    line_spacing_m: float = Field(0.0, ge=0)
    turn_angle_deg: Optional[float] = Field(None, gt=0, le=180)
    available_width_m: float = Field(0.0, ge=0)
    available_length_m: float = Field(0.0, ge=0)
    safety_factor: float = Field(1.25, ge=1.0)
    max_lateral_acceleration_ms2: Optional[float] = Field(None, gt=0)
    min_turn_radius_m: Optional[float] = Field(None, ge=0)
    max_turn_radius_m: Optional[float] = Field(None, gt=0)
    turn_clearance_m: float = Field(4.0, ge=0)
    turn_extension_m: Optional[float] = Field(None, ge=0)
    manual_radius_m: Optional[float] = Field(None, ge=0)
    boundary_polygon: Optional[dict] = None
    drone_dynamics: Optional[DroneFlightDynamics] = None


class TurnGeometryResult(BaseModel):
    """Result of planning a single turn.

    ``radius_m`` is the recommended radius actually used (geometry-constrained
    when ``status == CONSTRAINED``). ``dynamic_radius_m`` / ``safe_radius_m`` /
    ``available_radius_m`` are the intermediate physics/space values. When
    ``status == CONSTRAINED``, ``radius_m`` equals ``available_radius_m`` and
    the warning explains the shortfall — the engine never silently reduces the
    safe radius.

    ``geometry`` is a GeoJSON FeatureCollection in EPSG:4326 containing the
    turn arc, the turn center and the clearance buffer.
    """

    mode: str = TurnRadiusMode.AUTO.value
    status: str = TurnStatus.NONE.value
    radius_m: float = 0.0
    dynamic_radius_m: float = 0.0
    safe_radius_m: float = 0.0
    available_radius_m: float = 0.0
    turn_angle_deg: float = 0.0
    turn_speed_ms: float = 0.0
    survey_speed_ms: float = 0.0
    extension_before_m: float = 0.0
    extension_after_m: float = 0.0
    clearance_m: float = 0.0
    turn_distance_m: float = 0.0
    turn_duration_s: float = 0.0
    photo_capture_recommended_during_turn: bool = False
    turn_direction: str = ""
    warnings: list[str] = Field(default_factory=list)
    explanation: str = ""
    geometry: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class TurnPlanResult(BaseModel):
    """Mission-level result produced by a planner (Grid / Corridor).

    ``radius_m`` is the uniform mission radius (minimum across turns).
    ``turns`` holds one ``TurnGeometryResult`` per turn between consecutive
    flight lines. ``per_waypoint_curve_size`` maps global waypoint indices to
    the curve size that should be applied at that waypoint (informational;
    the export integration currently applies the uniform mission radius).
    """

    mission_type: str = MissionType.AREA_GRID.value
    mode: str = TurnRadiusMode.AUTO.value
    status: str = TurnStatus.NONE.value
    radius_m: float = 0.0
    turn_count: int = 0
    turns: list[TurnGeometryResult] = Field(default_factory=list)
    per_waypoint_curve_size: dict[int, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    explanation: str = ""
    geometry: dict = Field(default_factory=dict)
    epsg: int = 4326
    crs_name: str = "WGS84"


__all__ = [
    "DroneDynamicsSource",
    "DroneFlightDynamics",
    "MissionType",
    "TurnGeometryResult",
    "TurnPlanResult",
    "TurnRadiusInput",
    "TurnRadiusMode",
    "TurnStatus",
]
