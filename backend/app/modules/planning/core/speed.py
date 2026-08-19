"""Shutter-limited recommended survey speed (single source of truth).

The formula is unchanged from the original Grid/Corridor implementations:

    v_shutter = gsd_m / (2.0 * shutter_speed_s) * shutter_factor

with ``shutter_factor`` 1.0 for mechanical shutters and 0.5 for electronic
ones, and the result capped by the drone's maximum speed when known.
"""

from typing import Optional

MECHANICAL_SHUTTER_FACTOR = 1.0
ELECTRONIC_SHUTTER_FACTOR = 0.5


def calculate_recommended_speed(
    gsd_cm_per_px: float,
    shutter_speed_s: float,
    shutter_type: str = "electronic",
    drone_max_speed_ms: Optional[float] = None,
) -> float:
    """Recommended survey speed (m/s) so motion blur stays within one pixel.

    ``gsd_cm_per_px`` is the GSD in cm/pixel (already computed for the
    altitude in use). ``shutter_type`` is ``"mechanical"`` or ``"electronic"``.
    """
    gsd_m = gsd_cm_per_px / 100.0
    shutter_factor = MECHANICAL_SHUTTER_FACTOR if shutter_type == "mechanical" else ELECTRONIC_SHUTTER_FACTOR
    v_shutter = gsd_m / (2.0 * shutter_speed_s) * shutter_factor
    if drone_max_speed_ms:
        return min(v_shutter, drone_max_speed_ms)
    return v_shutter
