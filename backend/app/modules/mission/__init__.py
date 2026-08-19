"""Universal Mission Model (Fase 10A + 10B).

A typed, validated, serializable mission payload shared by every mission type,
with a backward-compatible serializer for ``Mission.grid_result_json``. Fase
10B adds the rich blocks the exporters consume: typed waypoints, flight
segments, capture plan, turn plan and drone/camera profiles, plus a
non-mutating validator.
"""

from .builder import build_universal_mission, to_legacy_dict
from .models import (
    SCHEMA_VERSION,
    SUPPORTED_VERSIONS,
    CameraProfile,
    CaptureMode,
    CapturePlan,
    DroneDynamicsProvenance,
    DroneFlightDynamicsProfile,
    DroneProfile,
    FlightSegment,
    MissionGeometry,
    MissionMetadata,
    MissionMetrics,
    MissionParameters,
    TurnPlan,
    UniversalMission,
    UniversalWaypoint,
    is_supported_version,
    normalize_schema_version,
)
from .segments import build_segments
from .serializer import mission_from_dict, mission_from_json, mission_to_dict, mission_to_json, round_trip
from .validation import parse_mission_blob
from .validator import MissionValidationResult, UniversalMissionValidator, ValidationIssue, ValidationSeverity

__all__ = [
    "SCHEMA_VERSION",
    "SUPPORTED_VERSIONS",
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
    "MissionValidationResult",
    "TurnPlan",
    "UniversalMission",
    "UniversalMissionValidator",
    "UniversalWaypoint",
    "ValidationIssue",
    "ValidationSeverity",
    "build_segments",
    "build_universal_mission",
    "is_supported_version",
    "mission_from_dict",
    "mission_from_json",
    "mission_to_dict",
    "mission_to_json",
    "normalize_schema_version",
    "parse_mission_blob",
    "round_trip",
    "to_legacy_dict",
]
