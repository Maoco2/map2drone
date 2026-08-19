"""Fase 10D — validation corpus of real photogrammetric missions.

Every case keeps the original planning request AND the built Universal Mission
so the validation tests can re-derive any metric without re-planning. The matrix
covers: grid under the LCHM waypoint limit, grid over the LCHM limit, corridor,
varied altitude / speed / overlap, capture modes (TIME / DISTANCE / NONE) and
turn radii (AUTO / MANUAL small / MANUAL large).

``lchm_export_status`` is the explicit LCHM exportability state for a mission:
``LCHM_OK`` or ``LCHM_UNSUPPORTED_WAYPOINT_COUNT`` (Fase 10D — no auto-split
exists yet, so the state must be explicit).
"""

from dataclasses import dataclass

from app.modules.export.litchi_lchm import LCHM_MAX_WAYPOINTS
from app.modules.mission.models import CaptureMode, CapturePlan, UniversalMission
from app.modules.optimizer.candidate_builder import CandidateBuilder
from app.schemas.schemas import CorridorRequest, GridRequest


def _polygon(min_lon: float, max_lon: float, min_lat: float, max_lat: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


# ~200 m x 200 m (vertex mode -> well under the 99-waypoint LCHM limit).
SMALL_POLYGON = _polygon(-5.995, -5.99275, 37.350, 37.3518)
# ~1.8 km x 2.2 km at low altitude -> far over the 99-waypoint LCHM limit.
MEDIUM_POLYGON = _polygon(-5.99, -5.97, 37.35, 37.37)
# Straight ~3 km centerline for the corridor case.
CORRIDOR_CENTERLINE = {
    "type": "LineString",
    "coordinates": [[-5.99, 37.35], [-5.90, 37.35], [-5.70, 37.35]],
}

DEFAULT_OVERLAP_FRONTAL = 75.0
DEFAULT_OVERLAP_LATERAL = 65.0
AUTO_TURN = {"mode": "AUTO"}


@dataclass
class MissionCase:
    """One corpus entry: original request + built Universal Mission."""

    case_id: str
    mission_type: str
    description: str
    request: GridRequest | CorridorRequest
    mission: UniversalMission
    notes: str = ""


def grid_request(
    polygon: dict,
    *,
    altitude: float,
    overlap_frontal: float = DEFAULT_OVERLAP_FRONTAL,
    overlap_lateral: float = DEFAULT_OVERLAP_LATERAL,
    altitude_mode: str = "takeoff",
    turn_radius: dict | None = None,
) -> GridRequest:
    return GridRequest(
        polygon=polygon,
        altitude=altitude,
        overlap_frontal=overlap_frontal,
        overlap_lateral=overlap_lateral,
        camera_id="cam-1-20mp",
        drone_id="dji-p4rtk",
        altitude_mode=altitude_mode,
        turn_radius=turn_radius,
    )


def corridor_request(
    *,
    altitude: float,
    width_left: float = 100.0,
    width_right: float = 100.0,
    overlap_frontal: float = DEFAULT_OVERLAP_FRONTAL,
    overlap_lateral: float = DEFAULT_OVERLAP_LATERAL,
    turn_radius: dict | None = None,
) -> CorridorRequest:
    return CorridorRequest(
        centerline=CORRIDOR_CENTERLINE,
        width_left=width_left,
        width_right=width_right,
        altitude=altitude,
        overlap_frontal=overlap_frontal,
        overlap_lateral=overlap_lateral,
        camera_id="cam-1-20mp",
        drone_id="dji-p4rtk",
        altitude_mode="takeoff",
        turn_radius=turn_radius,
    )


def build_case(
    db, mission_type: str, request, values: dict, case_id: str, description: str, notes: str = ""
) -> MissionCase:
    mission = CandidateBuilder(mission_type, request, db).build(values)
    return MissionCase(
        case_id=case_id,
        mission_type=mission_type,
        description=description,
        request=request,
        mission=mission,
        notes=notes,
    )


def _with_capture_mode(mission: UniversalMission, mode: CaptureMode) -> UniversalMission:
    """Copy a mission with an explicit capture mode (DISTANCE / NONE are
    synthetic here: the planning engines only emit TIME recommendations)."""
    clone = mission.model_copy(deep=True)
    if mode == CaptureMode.DISTANCE:
        clone.capture_plan = CapturePlan(mode=CaptureMode.DISTANCE, photo_spacing_m=15.0, status="VALID")
        clone.parameters.capture_mode = "DISTANCE"
    elif mode == CaptureMode.NONE:
        clone.capture_plan = None
        clone.capture_interval = None
        clone.parameters.capture_mode = "NONE"
    return clone


def get_case(corpus: list[MissionCase], case_id: str) -> MissionCase:
    """Return the corpus entry with the given id (helper for the tests)."""
    return next(c for c in corpus if c.case_id == case_id)


def lchm_export_status(mission: UniversalMission) -> str:
    """Explicit LCHM exportability state for a Universal Mission (Fase 10D).

    No auto-split exists yet: over the LCHM waypoint capacity the mission is
    reported as ``LCHM_UNSUPPORTED_WAYPOINT_COUNT`` instead of being silently
    truncated or wrapped.
    """
    if len(mission.waypoints) > LCHM_MAX_WAYPOINTS:
        return "LCHM_UNSUPPORTED_WAYPOINT_COUNT"
    return "LCHM_OK"


def build_corpus(db) -> list[MissionCase]:
    """Build the full 10D validation corpus (deterministic)."""
    cases: list[MissionCase] = []

    cases.append(
        build_case(
            db,
            "grid",
            grid_request(SMALL_POLYGON, altitude=100.0),
            {"altitude_m": 100.0},
            "grid_small_time",
            "Grid ~200x200 m @100 m, 75/65 overlap, vertex mode, TIME capture (engine default).",
        )
    )

    cases.append(
        build_case(
            db,
            "grid",
            grid_request(SMALL_POLYGON, altitude=80.0),
            {"altitude_m": 80.0},
            "grid_small_low_alt",
            "Grid small @80 m -> finer GSD, more photos/lines than @100 m.",
        )
    )

    cases.append(
        build_case(
            db,
            "grid",
            grid_request(SMALL_POLYGON, altitude=140.0),
            {"altitude_m": 140.0},
            "grid_small_high_alt",
            "Grid small @140 m -> coarser GSD, fewer photos than @100 m.",
        )
    )

    cases.append(
        build_case(
            db,
            "grid",
            grid_request(SMALL_POLYGON, altitude=100.0, overlap_frontal=85.0, overlap_lateral=75.0),
            {"altitude_m": 100.0},
            "grid_small_overlap_high",
            "Grid small @100 m with 85/75 overlap -> tighter line/photo spacing.",
        )
    )

    cases.append(
        build_case(
            db,
            "grid",
            grid_request(MEDIUM_POLYGON, altitude=60.0),
            {"altitude_m": 60.0},
            "grid_large_over_99",
            "Grid ~1.8x2.2 km @60 m -> waypoints exceed the LCHM 99 limit.",
        )
    )

    cases.append(
        build_case(
            db,
            "grid",
            grid_request(SMALL_POLYGON, altitude=100.0, turn_radius=AUTO_TURN),
            {"altitude_m": 100.0, "speed_mps": 10.0},
            "grid_small_fast",
            "Grid small @100 m, AUTO turns @10 m/s -> radius space-constrained.",
        )
    )

    cases.append(
        build_case(
            db,
            "grid",
            grid_request(SMALL_POLYGON, altitude=100.0, turn_radius=AUTO_TURN),
            {"altitude_m": 100.0, "speed_mps": 4.0},
            "grid_small_slow",
            "Grid small @100 m, AUTO turns @4 m/s -> small VALID radius.",
        )
    )

    cases.append(
        build_case(
            db,
            "grid",
            grid_request(SMALL_POLYGON, altitude=100.0, turn_radius={"mode": "MANUAL", "manual_radius_m": 5.0}),
            {"altitude_m": 100.0, "speed_mps": 6.8},
            "grid_small_turn_manual_small",
            "Grid small with MANUAL turn radius 5 m.",
        )
    )

    cases.append(
        build_case(
            db,
            "grid",
            grid_request(SMALL_POLYGON, altitude=100.0, turn_radius={"mode": "MANUAL", "manual_radius_m": 25.0}),
            {"altitude_m": 100.0, "speed_mps": 6.8},
            "grid_small_turn_manual_large",
            "Grid small with MANUAL turn radius 25 m.",
        )
    )

    cases.append(
        MissionCase(
            case_id="grid_small_capture_distance",
            mission_type="grid",
            description="Grid small with a synthetic DISTANCE capture plan (photo spacing 15 m).",
            request=grid_request(SMALL_POLYGON, altitude=100.0),
            mission=_with_capture_mode(
                CandidateBuilder("grid", grid_request(SMALL_POLYGON, altitude=100.0), db).build({"altitude_m": 100.0}),
                CaptureMode.DISTANCE,
            ),
            notes="Synthetic: the planning engines emit TIME recommendations only.",
        )
    )

    cases.append(
        MissionCase(
            case_id="grid_small_capture_none",
            mission_type="grid",
            description="Grid small with no capture plan (NONE).",
            request=grid_request(SMALL_POLYGON, altitude=100.0),
            mission=_with_capture_mode(
                CandidateBuilder("grid", grid_request(SMALL_POLYGON, altitude=100.0), db).build({"altitude_m": 100.0}),
                CaptureMode.NONE,
            ),
            notes="Synthetic: capture plan removed to represent a NONE mode mission.",
        )
    )

    cases.append(
        build_case(
            db,
            "linear_corridor",
            corridor_request(altitude=100.0, turn_radius=AUTO_TURN),
            {"altitude_m": 100.0},
            "corridor_vertex",
            "Straight ~3 km corridor, 100/100 m width, AUTO turns, vertex mode.",
        )
    )

    return cases
