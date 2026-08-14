"""
Map2Drone Capture Interval Engine.

Universal photogrammetry capture-interval calculator shared by every mission
type (Area Grid, Linear Corridor and future modes). Pure math — no GIS, no DB.

Internal math keeps decimal precision; the operational recommendation
(`recommended_interval_s`) is ALWAYS an integer number of seconds. The decimal
`ideal_interval_s` is informational only and is never used as the operational
value (no `round()` is applied to it).
"""

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from app.schemas.schemas import CaptureIntervalBlock

STATUS_VALID = "VALID"
STATUS_WARNING = "WARNING"
STATUS_INCOMPATIBLE = "INCOMPATIBLE"
STATUS_ERROR = "ERROR"

DEFAULT_MIN_INTERVAL_S = 1.0
DEFAULT_MAX_INTERVAL_S = 60.0

# Floor for the minimum plausible AGL in terrain-follow mode. Prevents a
# degenerate/negative clearance (e.g. from DEM quirks) from producing a
# zero/negative footprint that would otherwise be reported as ERROR.
MIN_PLAUSIBLE_AGL_FLOOR_M = 1.0

# Ratio above which the integer floor forces "substantially more photos than
# mathematically necessary" and the result is flagged as WARNING instead of
# VALID. WARNING never means the required overlap is violated.
WARNING_RATIO = 1.25

_EPS = 1e-9


@dataclass
class CaptureIntervalResult:
    required_photo_spacing_m: float
    ideal_interval_s: Optional[float]
    recommended_interval_s: Optional[int]
    actual_photo_spacing_m: Optional[float]
    effective_front_overlap: Optional[float]
    required_front_overlap: float
    speed_mps: float
    maximum_speed_for_1s: Optional[float]
    status: str


def compute_capture_interval(
    footprint_length_m: float,
    front_overlap: float,
    flight_speed_mps: float,
    interval_step_s: float = 1.0,
    min_interval_s: float = DEFAULT_MIN_INTERVAL_S,
    max_interval_s: float = DEFAULT_MAX_INTERVAL_S,
    warning_ratio: float = WARNING_RATIO,
) -> CaptureIntervalResult:
    """Compute the recommended photo capture interval.

    Args:
        footprint_length_m: along-track (flight direction) footprint in meters.
        front_overlap: requested front overlap, in percent (0 < overlap < 100).
        flight_speed_mps: planned cruise speed in m/s.
        interval_step_s: minimum resolution between candidate intervals.
        min_interval_s: minimum allowed interval in seconds (floor, default 1).
        max_interval_s: maximum allowed interval in seconds.
        warning_ratio: ratio ideal/recommended above which the result is WARNING.

    Selection rule: among the integer (step-aligned) intervals inside
    [min_interval_s, max_interval_s], the LARGEST one whose actual spacing keeps
    `effective_front_overlap >= required_front_overlap` is recommended. If even
    the minimum interval fails, the result is INCOMPATIBLE and
    `maximum_speed_for_1s` reports the speed that would allow the minimum
    interval to satisfy the required overlap.
    """
    required_front_overlap = front_overlap if front_overlap is not None else 0.0
    speed_mps = flight_speed_mps if flight_speed_mps is not None else 0.0

    if (
        footprint_length_m is None
        or footprint_length_m <= 0
        or flight_speed_mps is None
        or flight_speed_mps <= 0
        or front_overlap is None
        or not (0.0 < front_overlap < 100.0)
        or interval_step_s <= 0
        or min_interval_s < interval_step_s
        or max_interval_s < min_interval_s
    ):
        return CaptureIntervalResult(
            required_photo_spacing_m=0.0,
            ideal_interval_s=None,
            recommended_interval_s=None,
            actual_photo_spacing_m=None,
            effective_front_overlap=None,
            required_front_overlap=required_front_overlap,
            speed_mps=speed_mps,
            maximum_speed_for_1s=None,
            status=STATUS_ERROR,
        )

    required_photo_spacing_m = footprint_length_m * (1.0 - front_overlap / 100.0)
    ideal_interval_s = required_photo_spacing_m / flight_speed_mps

    top = int(math.floor(max_interval_s / interval_step_s))
    bottom = int(math.ceil(min_interval_s / interval_step_s))

    recommended_interval_s: Optional[int] = None
    for k in range(top, bottom - 1, -1):
        candidate = k * interval_step_s
        if candidate * flight_speed_mps <= required_photo_spacing_m * (1.0 + _EPS):
            recommended_interval_s = int(round(candidate))
            break

    if recommended_interval_s is None:
        maximum_speed_for_1s = required_photo_spacing_m / min_interval_s
        return CaptureIntervalResult(
            required_photo_spacing_m=required_photo_spacing_m,
            ideal_interval_s=ideal_interval_s,
            recommended_interval_s=None,
            actual_photo_spacing_m=None,
            effective_front_overlap=None,
            required_front_overlap=front_overlap,
            speed_mps=flight_speed_mps,
            maximum_speed_for_1s=maximum_speed_for_1s,
            status=STATUS_INCOMPATIBLE,
        )

    actual_photo_spacing_m = recommended_interval_s * flight_speed_mps
    effective_front_overlap = 1.0 - actual_photo_spacing_m / footprint_length_m

    if ideal_interval_s / recommended_interval_s > warning_ratio:
        status = STATUS_WARNING
    else:
        status = STATUS_VALID

    return CaptureIntervalResult(
        required_photo_spacing_m=required_photo_spacing_m,
        ideal_interval_s=ideal_interval_s,
        recommended_interval_s=recommended_interval_s,
        actual_photo_spacing_m=actual_photo_spacing_m,
        effective_front_overlap=effective_front_overlap,
        required_front_overlap=front_overlap,
        speed_mps=flight_speed_mps,
        maximum_speed_for_1s=None,
        status=status,
    )


def compute_minimum_plausible_agl(
    requested_agl_m: float,
    ground_elevations: Sequence[float | None],
    fallback_agl_m: Optional[float] = None,
) -> float:
    """Lowest plausible camera-to-ground distance along a terrain-follow mission.

    Conservative assumption: the drone tracks the reference ground at the
    requested AGL, and where the terrain rises above the reference the actual
    clearance shrinks by that relief. The minimum plausible AGL is therefore
    the requested AGL minus the maximum rise above the reference sample. This
    yields the *smallest* footprint the payload can see, so the capture
    interval derived from it always honours the requested front overlap even
    where the drone gets closer to the ground than planned.

    When no usable ground elevations are available (`ground_elevations` empty
    or all non-positive), the minimum plausible AGL is `fallback_agl_m` if
    provided, else `requested_agl_m`. The result is floored at
    `MIN_PLAUSIBLE_AGL_FLOOR_M` so it can never go degenerate.
    """
    valid = [e for e in ground_elevations if e is not None and e > 0]
    if not valid:
        value = fallback_agl_m if fallback_agl_m is not None else requested_agl_m
    else:
        ref_ground = valid[0]
        max_rise = max(0.0, max(valid) - ref_ground)
        value = requested_agl_m - max_rise
    return max(value, MIN_PLAUSIBLE_AGL_FLOOR_M)


def build_capture_interval_block(ci: CaptureIntervalResult) -> CaptureIntervalBlock:
    """Map an engine result onto the API schema block (single source of truth)."""
    return CaptureIntervalBlock(
        status=ci.status,
        required_photo_spacing_m=(
            round(ci.required_photo_spacing_m, 3) if ci.required_photo_spacing_m > 0 else None
        ),
        ideal_interval_s=round(ci.ideal_interval_s, 3) if ci.ideal_interval_s is not None else None,
        recommended_interval_s=ci.recommended_interval_s,
        actual_photo_spacing_m=(
            round(ci.actual_photo_spacing_m, 3) if ci.actual_photo_spacing_m is not None else None
        ),
        effective_front_overlap=(
            round(ci.effective_front_overlap * 100.0, 2)
            if ci.effective_front_overlap is not None else None
        ),
        required_front_overlap=ci.required_front_overlap,
        speed_mps=round(ci.speed_mps, 2),
        maximum_speed_for_1s=(
            round(ci.maximum_speed_for_1s, 2) if ci.maximum_speed_for_1s is not None else None
        ),
    )
