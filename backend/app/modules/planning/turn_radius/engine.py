"""Turn radius engine.

``TurnRadiusEngine`` is an independent, self-contained engine that computes
turn geometry for drone survey missions. It has no knowledge of LCHM or any
exporter: it only deals with speed, vehicle parameters, line separation,
turn angle, clearance and space constraints, in a projected (metric) CRS.

Public API
----------
* ``calculate_dynamic_radius``   — R = v² / a_lat
* ``calculate_safe_radius``      — R_safe = R_dynamic * safety_factor
* ``calculate_available_radius`` — space constraint (analytic + geometric)
* ``calculate_turn_extension``   — extension before/after the turn
* ``generate_turn_geometry``     — circular arc + center (projected meters)
* ``validate_turn``              — VALID / CONSTRAINED / INVALID
* ``plan_turn``                  — full turn planning, returns TurnGeometryResult

Design decisions (Fase 8)
-------------------------
* ``safety_factor`` default 1.25 is an engineering safety factor, not a
  manufacturer specification.
* ``max_lateral_acceleration_ms2`` default 4.5 is a conservative engineering
  default (provenance DEFAULT) — never presented as DJI data.
* When ``R_safe > R_available`` the engine does NOT silently reduce the
  radius: it returns ``status = CONSTRAINED``, sets ``radius_m`` to the
  largest geometry-constrained radius and explains the mitigation options.
* All metric math is done in projected coordinates; headings are angles only.
"""

from __future__ import annotations

from typing import Optional

from shapely.geometry import Polygon

from app.modules.planning.turn_radius.geometry import (
    arc_length,
    generate_circular_arc,
)
from app.modules.planning.turn_radius.models import (
    DroneFlightDynamics,
    TurnGeometryResult,
    TurnRadiusInput,
    TurnRadiusMode,
    TurnStatus,
)

DEFAULT_SAFETY_FACTOR = 1.25
DEFAULT_CLEARANCE_M = 4.0


class TurnRadiusEngine:
    def __init__(self, dynamics: Optional[DroneFlightDynamics] = None) -> None:
        self.dynamics = dynamics or DroneFlightDynamics()

    # ------------------------------------------------------------------
    # Physics
    # ------------------------------------------------------------------
    @staticmethod
    def calculate_dynamic_radius(speed_ms: float, lateral_accel_ms2: float) -> float:
        """R = v² / a_lat. Speed and acceleration must be positive."""
        if speed_ms <= 0:
            raise ValueError("speed_ms must be > 0")
        if lateral_accel_ms2 <= 0:
            raise ValueError("lateral_accel_ms2 must be > 0")
        return speed_ms**2 / lateral_accel_ms2

    @staticmethod
    def calculate_safe_radius(dynamic_radius_m: float, safety_factor: float = DEFAULT_SAFETY_FACTOR) -> float:
        """R_safe = R_dynamic * safety_factor (engineering factor, >= 1)."""
        if safety_factor < 1.0:
            raise ValueError("safety_factor must be >= 1.0")
        return dynamic_radius_m * safety_factor

    # ------------------------------------------------------------------
    # Effective parameters
    # ------------------------------------------------------------------
    def _effective_turn_speed(self, inp: TurnRadiusInput) -> float:
        if inp.turn_speed_ms and inp.turn_speed_ms > 0:
            return inp.turn_speed_ms
        if self.dynamics.preferred_turn_speed_ms and self.dynamics.preferred_turn_speed_ms > 0:
            return self.dynamics.preferred_turn_speed_ms
        speed = inp.speed_ms
        if self.dynamics.max_speed_ms and speed > self.dynamics.max_speed_ms:
            return self.dynamics.max_speed_ms
        return speed

    def _effective_acceleration(self, inp: TurnRadiusInput) -> float:
        if inp.max_lateral_acceleration_ms2 and inp.max_lateral_acceleration_ms2 > 0:
            return inp.max_lateral_acceleration_ms2
        return self.dynamics.max_lateral_acceleration_ms2

    def _effective_min_radius(self, inp: TurnRadiusInput) -> float:
        return inp.min_turn_radius_m if inp.min_turn_radius_m is not None else self.dynamics.min_turn_radius_m

    def _effective_max_radius(self, inp: TurnRadiusInput) -> float:
        return inp.max_turn_radius_m if inp.max_turn_radius_m is not None else self.dynamics.max_turn_radius_m

    # ------------------------------------------------------------------
    # Available radius
    # ------------------------------------------------------------------
    def calculate_available_radius(
        self,
        inp: TurnRadiusInput,
        turn_angle_deg: float,
        start: tuple[float, float],
        heading_in: float,
        heading_out: float,
        turn_direction: str,
        boundary: Optional[Polygon] = None,
    ) -> float:
        """Largest radius the available space allows, in meters.

        Analytic constraints (exact for U-turns between parallel lines):

        * width:  ``R <= (line_spacing - 2*clearance) / 2``
        * length: ``R <= available_length - clearance``

        An optional ``boundary`` (projected Polygon) adds an exact geometric
        check via binary search over the swept arc buffer. When no constraint
        applies the configured maximum radius is returned.
        """
        r_max = self._effective_max_radius(inp)
        clearance = max(0.0, inp.turn_clearance_m)

        candidates: list[float] = []
        spacing = inp.line_spacing_m if inp.line_spacing_m > 0 else inp.available_width_m
        if spacing > 0:
            candidates.append(max(0.0, (spacing - 2.0 * clearance) / 2.0))
        if inp.available_length_m > 0:
            candidates.append(max(0.0, inp.available_length_m - clearance))
        if boundary is not None:
            candidates.append(
                self._geometric_available_radius(
                    inp, turn_angle_deg, start, heading_in, heading_out, turn_direction, boundary
                )
            )

        if not candidates:
            return r_max
        return max(0.0, min(min(candidates), r_max))

    def _geometric_available_radius(
        self,
        inp: TurnRadiusInput,
        turn_angle_deg: float,
        start: tuple[float, float],
        heading_in: float,
        heading_out: float,
        turn_direction: str,
        boundary: Polygon,
    ) -> float:
        clearance = max(0.0, inp.turn_clearance_m)
        lo, hi = 0.0, self._effective_max_radius(inp)
        best = 0.0
        for _ in range(48):
            mid = (lo + hi) / 2.0
            arc, _ = generate_circular_arc(start, heading_in, heading_out, mid, turn_direction, turn_angle_deg)
            swept = arc.buffer(clearance)
            if swept.is_empty:
                hi = mid
                continue
            if boundary.covers(swept):
                best = mid
                lo = mid
            else:
                hi = mid
        return best

    # ------------------------------------------------------------------
    # Extension / geometry
    # ------------------------------------------------------------------
    @staticmethod
    def calculate_turn_extension(inp: TurnRadiusInput, radius: float) -> tuple[float, float]:
        """(extension_before, extension_after) in meters.

        AUTO = one turn radius on each side (documented engineering default:
        the tangent point lands one radius ahead of the line end, giving the
        arc room to leave the line without clipping the photo strip).
        """
        if inp.turn_extension_m and inp.turn_extension_m > 0:
            return (inp.turn_extension_m, inp.turn_extension_m)
        return (radius, radius)

    def generate_turn_geometry(
        self,
        start: tuple[float, float],
        heading_in: float,
        heading_out: float,
        radius: float,
        turn_direction: str,
        turn_angle_deg: float,
        clearance: float = DEFAULT_CLEARANCE_M,
    ) -> tuple["object", "object", Optional["object"]]:
        """Return ``(arc, center, swept_buffer)`` in projected meters."""
        arc, center = generate_circular_arc(start, heading_in, heading_out, radius, turn_direction, turn_angle_deg)
        swept: Optional[object] = None
        if radius > 0:
            swept = arc.buffer(max(0.0, clearance))
        return arc, center, swept

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate_turn(
        self,
        radius: float,
        turn_angle_deg: float,
        r_min: float,
        r_max: float,
        boundary: Optional[Polygon] = None,
        clearance: float = DEFAULT_CLEARANCE_M,
        start: Optional[tuple[float, float]] = None,
        heading_in: float = 0.0,
        heading_out: float = 180.0,
        turn_direction: str = "RIGHT",
    ) -> tuple[TurnStatus, list[str]]:
        """Validate a radius → (status, warnings)."""
        warnings: list[str] = []
        if radius <= 0:
            return TurnStatus.INVALID, ["Radius must be positive."]
        if radius < r_min:
            return (
                TurnStatus.INVALID,
                [f"Radius {radius:.2f} m is below the vehicle minimum radius {r_min:.2f} m."],
            )
        if turn_angle_deg <= 0 or turn_angle_deg > 180:
            return (
                TurnStatus.INVALID,
                [f"Turn angle {turn_angle_deg:.2f}° is outside the valid range (0, 180]."],
            )
        if radius > r_max:
            warnings.append(
                f"Radius {radius:.2f} m exceeds the configured maximum {r_max:.2f} m. "
                "Recommendation: reduce the turn speed or configure a larger maximum radius."
            )
        if boundary is not None and start is not None:
            arc, _, swept = self.generate_turn_geometry(
                start, heading_in, heading_out, radius, turn_direction, turn_angle_deg, clearance
            )
            if arc.is_empty or swept is None or not boundary.covers(swept):
                warnings.append(
                    "The turn geometry does not fit inside the available maneuver space. "
                    "Mitigations: reduce turn speed, enlarge the maneuver area, or extend the flight lines."
                )
        if warnings:
            return TurnStatus.CONSTRAINED, warnings
        return TurnStatus.VALID, []

    # ------------------------------------------------------------------
    # Plan one turn
    # ------------------------------------------------------------------
    def plan_turn(
        self,
        start: tuple[float, float],
        heading_in: float,
        heading_out: float,
        turn_angle_deg: float,
        turn_direction: str,
        inp: TurnRadiusInput,
        boundary: Optional[Polygon] = None,
        epsg: int = 4326,
        crs_name: str = "WGS84",
    ) -> TurnGeometryResult:
        result = TurnGeometryResult(
            mode=inp.mode.value,
            survey_speed_ms=inp.speed_ms,
            turn_angle_deg=abs(turn_angle_deg),
            turn_direction=turn_direction,
            clearance_m=inp.turn_clearance_m,
            metadata={
                "crs": f"EPSG:{epsg}",
                "crs_name": crs_name,
                "radius_selection": "none",
            },
        )

        if inp.mode == TurnRadiusMode.NONE:
            result.status = TurnStatus.NONE.value
            result.explanation = "Turn radius disabled (NONE): no curve is applied to the mission."
            return result

        turn_speed = self._effective_turn_speed(inp)
        accel = self._effective_acceleration(inp)
        r_min = self._effective_min_radius(inp)
        r_max = self._effective_max_radius(inp)

        result.metadata["a_lat_ms2"] = round(accel, 4)
        result.metadata["safety_factor"] = round(inp.safety_factor, 4)

        r_dynamic = self.calculate_dynamic_radius(turn_speed, accel)
        r_safe = self.calculate_safe_radius(r_dynamic, inp.safety_factor)

        dynamic_warnings: list[str] = []
        if r_dynamic < r_min:
            dynamic_warnings.append(
                f"Dynamic radius {r_dynamic:.2f} m is below the vehicle minimum {r_min:.2f} m; clamped to the minimum."
            )
        if r_dynamic > r_max:
            dynamic_warnings.append(
                f"Dynamic radius {r_dynamic:.2f} m exceeds the configured maximum {r_max:.2f} m; "
                "clamped to the maximum."
            )
        r_dynamic = max(r_min, min(r_dynamic, r_max))
        r_safe = max(r_min, min(r_safe, r_max))

        r_available = self.calculate_available_radius(
            inp, turn_angle_deg, start, heading_in, heading_out, turn_direction, boundary
        )

        result.dynamic_radius_m = r_dynamic
        result.safe_radius_m = r_safe
        result.available_radius_m = r_available
        result.turn_speed_ms = turn_speed
        result.warnings.extend(dynamic_warnings)

        radius: float
        if inp.mode == TurnRadiusMode.MANUAL:
            radius = inp.manual_radius_m or 0.0
            status, status_warnings = self.validate_turn(
                radius,
                turn_angle_deg,
                r_min,
                r_max,
                boundary=boundary,
                clearance=inp.turn_clearance_m,
                start=start,
                heading_in=heading_in,
                heading_out=heading_out,
                turn_direction=turn_direction,
            )
            result.warnings.extend(status_warnings)
            result.status = status.value
            result.metadata["radius_selection"] = "manual"
            result.explanation = (
                f"Manual turn radius {radius:.2f} m requested by the user."
                if status is not TurnStatus.INVALID
                else f"Manual turn radius {radius:.2f} m is mathematically invalid."
            )
        else:  # AUTO
            if r_safe <= r_available:
                radius = r_safe
                result.status = TurnStatus.VALID.value
                result.metadata["radius_selection"] = "safe"
                result.explanation = (
                    f"Calculated dynamic radius {r_dynamic:.2f} m (R = v²/a_lat at {turn_speed:.2f} m/s "
                    f"and a_lat = {accel:.2f} m/s²); safe radius {r_safe:.2f} m "
                    f"(×{inp.safety_factor:.2f}) fits the available space."
                )
            else:
                radius = r_available
                result.status = TurnStatus.CONSTRAINED.value
                result.metadata["radius_selection"] = "available"
                result.warnings.append(
                    f"Safe radius {r_safe:.2f} m exceeds the geometry-constrained maximum "
                    f"{r_available:.2f} m. The radius was NOT reduced silently; the mission uses "
                    f"{radius:.2f} m with status CONSTRAINED. Mitigations: reduce the turn speed "
                    "(lower R_dynamic), enlarge the maneuver area / line separation, or extend the "
                    "flight lines outside the capture area."
                )
                result.explanation = (
                    f"Geometry-constrained radius {radius:.2f} m used because the safe radius "
                    f"{r_safe:.2f} m does not fit the available space {r_available:.2f} m."
                )

        result.radius_m = radius
        extension_before, extension_after = self.calculate_turn_extension(inp, radius)
        result.extension_before_m = extension_before
        result.extension_after_m = extension_after

        if radius > 0:
            arc, center, swept = self.generate_turn_geometry(
                start, heading_in, heading_out, radius, turn_direction, turn_angle_deg, inp.turn_clearance_m
            )
            result.turn_distance_m = arc_length(radius, turn_angle_deg)
            result.turn_duration_s = result.turn_distance_m / turn_speed if turn_speed > 0 else 0.0
            result.photo_capture_recommended_during_turn = False
            result.geometry = self._geometry_geojson(arc, center, swept, epsg)

        return result

    @staticmethod
    def _geometry_geojson(arc: "object", center: "object", swept: Optional["object"], epsg: int) -> dict:
        from app.modules.planning.turn_radius.geometry import make_transformer, to_geojson_geometry

        try:
            transformer = make_transformer(epsg, 4326)
        except Exception:
            return {}
        return to_geojson_geometry(arc, center, swept, transformer)
