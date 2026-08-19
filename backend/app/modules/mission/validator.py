"""Universal Mission Validator (Fase 10B).

Detects structural, photogrammetric, flight, capture, turn and battery
problems in a :class:`UniversalMission` and reports ``errors`` / ``warnings``
plus a global ``status``. The validator NEVER silently modifies invalid
values — it only reports them.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel

from app.modules.mission.models import (
    CaptureMode,
    UniversalMission,
    is_supported_version,
)


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class ValidationIssue(BaseModel):
    severity: ValidationSeverity
    code: str
    field: str = ""
    message: str = ""


class MissionValidationResult(BaseModel):
    valid: bool
    status: str  # VALID | WARNING | INVALID
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []


def _issue(severity: ValidationSeverity, code: str, field: str, message: str) -> ValidationIssue:
    return ValidationIssue(severity=severity, code=code, field=field, message=message)


def _error(code: str, field: str, message: str) -> ValidationIssue:
    return _issue(ValidationSeverity.ERROR, code, field, message)


def _warning(code: str, field: str, message: str) -> ValidationIssue:
    return _issue(ValidationSeverity.WARNING, code, field, message)


def _line_bbox(flight_lines_geojson: Optional[dict]) -> Optional[tuple]:
    """Bounding box (min_lon, min_lat, max_lon, max_lat) of the flight lines."""
    if not flight_lines_geojson:
        return None
    feats = flight_lines_geojson.get("features") or []
    coords: list[list[float]] = []
    for f in feats:
        geom = f.get("geometry") or {}
        if geom.get("type") != "LineString":
            continue
        coords.extend(geom.get("coordinates") or [])
    if not coords:
        return None
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return (min(lons), min(lats), max(lons), max(lats))


def _valid_crs(epsg_out: Optional[int]) -> bool:
    if epsg_out is None:
        return False
    if epsg_out == 4326:
        return True
    return 32601 <= epsg_out <= 32660 or 32701 <= epsg_out <= 32760


class UniversalMissionValidator:
    """Validates a mission without mutating it."""

    def validate(self, mission: UniversalMission) -> MissionValidationResult:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        self._validate_version(mission, warnings)
        self._validate_geometry(mission, errors, warnings)
        self._validate_photogrammetry(mission, errors)
        self._validate_flight(mission, errors, warnings)
        self._validate_capture(mission, errors, warnings)
        self._validate_turn(mission, errors, warnings)
        self._validate_battery(mission, errors, warnings)

        status = "VALID"
        if errors:
            status = "INVALID"
        elif warnings:
            status = "WARNING"
        return MissionValidationResult(valid=not bool(errors), status=status, errors=errors, warnings=warnings)

    # ── Geometry ────────────────────────────────────────────────────────────

    def _validate_version(self, mission: UniversalMission, warnings: list) -> None:
        if not is_supported_version(mission.schema_version):
            warnings.append(
                _warning(
                    "unsupported_version",
                    "schema_version",
                    f"schema_version '{mission.schema_version}' is not in the supported set; "
                    "results may be incomplete.",
                )
            )

    def _validate_geometry(self, mission: UniversalMission, errors: list, warnings: list) -> None:
        wps = mission.waypoints
        if not wps:
            errors.append(_error("waypoints_empty", "waypoints", "Mission has no waypoints."))
        for i, wp in enumerate(wps):
            if wp.latitude is None or wp.longitude is None:
                errors.append(
                    _error(
                        "waypoint_missing_coords",
                        f"waypoints[{i}]",
                        f"Waypoint {i} has no coordinates.",
                    )
                )

        fl = mission.flight_lines_geojson
        if fl is not None:
            feats = fl.get("features") if isinstance(fl, dict) else None
            if feats is None:
                errors.append(
                    _error(
                        "geometry_invalid",
                        "flight_lines_geojson",
                        "flight_lines_geojson is not a valid GeoJSON object.",
                    )
                )
            elif len(feats) == 0:
                errors.append(
                    _error(
                        "flight_lines_empty",
                        "flight_lines_geojson",
                        "Flight lines collection is empty.",
                    )
                )

        g = mission.geometry
        if g is not None:
            if not _valid_crs(g.epsg_out):
                errors.append(_error("invalid_crs", "geometry.epsg_out", f"Invalid projected CRS EPSG:{g.epsg_out}."))

        bbox = _line_bbox(mission.flight_lines_geojson)
        if bbox:
            for p in mission.photo_points:
                lon = p.get("longitude")
                lat = p.get("latitude")
                if lon is None or lat is None:
                    continue
                if not (bbox[0] - 1e-6 <= lon <= bbox[2] + 1e-6 and bbox[1] - 1e-6 <= lat <= bbox[3] + 1e-6):
                    warnings.append(
                        _warning(
                            "photo_point_outside_lines",
                            "photo_points",
                            f"Photo point ({lon:.6f}, {lat:.6f}) lies outside the flight-line bounding box.",
                        )
                    )

    # ── Photogrammetry ──────────────────────────────────────────────────────

    def _validate_photogrammetry(self, mission: UniversalMission, errors: list) -> None:
        m = mission.metrics
        if m.line_spacing_m <= 0:
            errors.append(_error("spacing_invalid", "line_spacing_m", "line_spacing_m must be > 0."))
        if m.photo_spacing_m <= 0:
            errors.append(_error("spacing_invalid", "photo_spacing_m", "photo_spacing_m must be > 0."))
        for ov in (mission.parameters.overlap_frontal, mission.parameters.overlap_lateral):
            if not (0.0 < ov < 100.0):
                errors.append(_error("overlap_invalid", "parameters.overlap", "Overlap must be in (0, 100)."))
        if m.gsd_cm <= 0:
            errors.append(_error("gsd_invalid", "gsd_cm", "GSD must be > 0."))
        if m.footprint_width_m <= 0 or m.footprint_height_m <= 0:
            errors.append(_error("footprint_invalid", "footprint", "Footprint dimensions must be > 0."))

    # ── Flight ──────────────────────────────────────────────────────────────

    def _validate_flight(self, mission: UniversalMission, errors: list, warnings: list) -> None:
        p = mission.parameters
        if p.speed_ms <= 0 and (p.recommended_speed_mps or 0) <= 0:
            errors.append(_error("speed_invalid", "speed_ms", "Flight speed must be > 0."))
        if p.altitude_m <= 0:
            errors.append(_error("altitude_invalid", "altitude_m", "Altitude must be > 0."))
        missing_heading = [wp.index for wp in mission.waypoints if wp.heading_deg is None]
        if missing_heading:
            warnings.append(
                _warning(
                    "waypoint_missing_heading",
                    "waypoints",
                    f"{len(missing_heading)} waypoint(s) have no heading (e.g. indices {missing_heading[:5]}).",
                )
            )

    # ── Capture ─────────────────────────────────────────────────────────────

    def _validate_capture(self, mission: UniversalMission, errors: list, warnings: list) -> None:
        plan = mission.capture_plan
        if plan is None:
            return
        if plan.mode == CaptureMode.TIME:
            if plan.scientific_interval_s is not None and plan.scientific_interval_s <= 0:
                errors.append(
                    _error(
                        "capture_interval_invalid",
                        "capture_plan.scientific_interval_s",
                        "TIME interval must be > 0.",
                    )
                )
            if plan.commercial_interval_s is not None and plan.commercial_interval_s <= 0:
                errors.append(
                    _error(
                        "capture_interval_invalid",
                        "capture_plan.commercial_interval_s",
                        "TIME interval must be > 0.",
                    )
                )
        elif plan.mode == CaptureMode.DISTANCE:
            if (plan.photo_spacing_m or 0) <= 0:
                errors.append(
                    _error(
                        "capture_distance_invalid",
                        "capture_plan.photo_spacing_m",
                        "DISTANCE spacing must be > 0.",
                    )
                )
        elif plan.mode == CaptureMode.NONE:
            active = [wp.index for wp in mission.waypoints if wp.capture_enabled or wp.action_type == 1]
            if active:
                warnings.append(
                    _warning(
                        "capture_none_with_active_capture",
                        "capture_plan",
                        f"Capture mode is NONE but {len(active)} waypoint(s) have active capture.",
                    )
                )

    # ── Turn ────────────────────────────────────────────────────────────────

    def _validate_turn(self, mission: UniversalMission, errors: list, warnings: list) -> None:
        plan = mission.turn_plan
        if plan is None:
            return
        if plan.status == "INVALID":
            errors.append(_error("turn_status_invalid", "turn_plan.status", "Turn plan status is INVALID."))
        radius = plan.radius_m
        if radius is not None and radius < 0:
            errors.append(_error("turn_radius_invalid", "turn_plan.radius_m", "Turn radius must be >= 0."))
        if plan.available_radius_m is not None and radius is not None:
            if radius > plan.available_radius_m + 1e-6:
                errors.append(
                    _error(
                        "turn_radius_exceeds_available",
                        "turn_plan.radius_m",
                        "Turn radius exceeds the available radius.",
                    )
                )
        for w in plan.warnings:
            warnings.append(_warning("turn_warning", "turn_plan", w))

    # ── Battery ─────────────────────────────────────────────────────────────

    def _validate_battery(self, mission: UniversalMission, errors: list, warnings: list) -> None:
        if mission.metrics.battery_count < 1:
            errors.append(_error("battery_count_invalid", "battery_count", "Battery count must be >= 1."))
        flight_time = None
        if mission.drone_profile is not None:
            flight_time = mission.drone_profile.flight_time_min
        if flight_time is not None and flight_time <= 0:
            warnings.append(
                _warning(
                    "flight_time_invalid",
                    "drone_profile.flight_time_min",
                    "Drone flight time must be > 0.",
                )
            )
