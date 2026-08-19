"""Battery requirements (single source of truth).

Replaces the old behaviour where the Grid engine hardcoded ``25`` minutes and
the Corridor engine used ``drone.flight_time_min * 0.8``. Both engines now
call :func:`calculate_battery_requirements`, which applies the usable-battery
fraction centrally.
"""

import math
from dataclasses import dataclass
from typing import Optional

# Usable fraction of the nominal flight time (reserve for return, wind, etc.).
DEFAULT_USABLE_BATTERY_FRACTION = 0.80

# Fallback nominal flight time (minutes) when no drone is selected. This is the
# old implicit ``25`` now centralized and documented instead of hidden.
DEFAULT_FLIGHT_TIME_MIN_FALLBACK = 25.0


@dataclass
class BatteryRequirements:
    flight_time_available_min: float
    usable_flight_time_min: float
    required_minutes: float
    battery_count: int
    battery_margin_min: float


def calculate_battery_requirements(
    mission_time_s: float,
    drone_flight_time_min: Optional[float] = None,
    usable_battery_fraction: float = DEFAULT_USABLE_BATTERY_FRACTION,
) -> BatteryRequirements:
    """Compute battery needs for a mission of ``mission_time_s`` seconds.

    With a known drone flight time the usable time is ``flight_time * fraction``
    (default 0.80). Without a drone the fallback nominal flight time
    (``DEFAULT_FLIGHT_TIME_MIN_FALLBACK``) is used as-is (it is already a
    conservative "usable" estimate). At least one battery is always required.
    """
    if drone_flight_time_min and drone_flight_time_min > 0:
        flight_time_available_min = float(drone_flight_time_min)
        usable_flight_time_min = flight_time_available_min * usable_battery_fraction
    else:
        flight_time_available_min = DEFAULT_FLIGHT_TIME_MIN_FALLBACK
        usable_flight_time_min = DEFAULT_FLIGHT_TIME_MIN_FALLBACK

    required_minutes = mission_time_s / 60.0
    if usable_flight_time_min > 0:
        battery_count = max(1, math.ceil(required_minutes / usable_flight_time_min))
    else:
        battery_count = 1
    battery_margin_min = usable_flight_time_min * battery_count - required_minutes
    return BatteryRequirements(
        flight_time_available_min=round(flight_time_available_min, 2),
        usable_flight_time_min=round(usable_flight_time_min, 2),
        required_minutes=round(required_minutes, 2),
        battery_count=battery_count,
        battery_margin_min=round(battery_margin_min, 2),
    )
