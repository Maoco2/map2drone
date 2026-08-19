"""Flight-line spacing (single source of truth).

    line_spacing  = footprint_width  * (1 - sidelap  / 100)
    photo_spacing = footprint_length * (1 - overlap / 100)

Percentages are expressed as 0-100 (e.g. ``65`` for 65 %), matching the API
request fields ``overlap_lateral`` / ``overlap_frontal``.
"""


def calculate_line_spacing(footprint_width_m: float, sidelap_percent: float) -> float:
    """Distance between parallel flight lines (m)."""
    return footprint_width_m * (1.0 - sidelap_percent / 100.0)


def calculate_photo_spacing(footprint_length_m: float, overlap_percent: float) -> float:
    """Along-track photo spacing (m) for the requested front overlap."""
    return footprint_length_m * (1.0 - overlap_percent / 100.0)
