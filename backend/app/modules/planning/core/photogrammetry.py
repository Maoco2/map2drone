"""Photogrammetry primitives: GSD and ground footprint.

Single source of truth. The formulas are unchanged from the original
implementations (``planning/engine.py``); they are simply centralized so Grid
and Corridor share the exact same code.
"""

from app.models.schemas import Camera


def calc_gsd(altitude_m: float, focal_length_mm: float, pixel_size_um: float) -> float:
    """Ground Sample Distance in cm/pixel."""
    return (altitude_m * pixel_size_um) / (focal_length_mm * 10)


def calc_footprint(gsd: float, image_width_px: int, image_height_px: int) -> tuple[float, float]:
    """Ground footprint ``(width_m, height_m)`` for a GSD in cm/pixel."""
    return gsd * image_width_px / 100, gsd * image_height_px / 100


def calculate_gsd_and_footprint(
    altitude_m: float,
    camera: Camera,
) -> tuple[float, float, float]:
    """Return ``(gsd_cm, footprint_width_m, footprint_height_m)``."""
    gsd = calc_gsd(altitude_m, camera.focal_length_mm, camera.pixel_size_um)
    fw, fh = calc_footprint(gsd, camera.image_width_px, camera.image_height_px)
    return gsd, fw, fh
