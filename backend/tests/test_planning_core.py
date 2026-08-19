"""Tests for the Planning Core (single source of truth primitives)."""

import pytest

from app.modules.planning.core.battery import (
    DEFAULT_FLIGHT_TIME_MIN_FALLBACK,
    DEFAULT_USABLE_BATTERY_FRACTION,
    calculate_battery_requirements,
)
from app.modules.planning.core.distance import calculate_path_distance, utm_epsg_for
from app.modules.planning.core.metrics import calculate_mission_metrics
from app.modules.planning.core.photogrammetry import calc_footprint, calc_gsd, calculate_gsd_and_footprint
from app.modules.planning.core.spacing import calculate_line_spacing, calculate_photo_spacing
from app.modules.planning.core.speed import (
    ELECTRONIC_SHUTTER_FACTOR,
    MECHANICAL_SHUTTER_FACTOR,
    calculate_recommended_speed,
)

# --- GSD / footprint --------------------------------------------------------


def test_calc_gsd_matches_historical_formula():
    # altitude * pixel_um / (focal_mm * 10)
    assert calc_gsd(100.0, 8.8, 2.41) == pytest.approx(100 * 2.41 / 88.0)


def test_calc_footprint_matches_historical_formula():
    gsd = calc_gsd(100.0, 8.8, 2.41)
    fw, fh = calc_footprint(gsd, 5472, 3648)
    assert fw == pytest.approx(gsd * 5472 / 100)
    assert fh == pytest.approx(gsd * 3648 / 100)


def test_calculate_gsd_and_footprint_uses_camera_fields():
    cam = {"focal_length_mm": 8.8, "pixel_size_um": 2.41, "image_width_px": 5472, "image_height_px": 3648}
    gsd, fw, fh = calculate_gsd_and_footprint(100.0, type("C", (), cam))
    assert gsd == pytest.approx(calc_gsd(100.0, 8.8, 2.41))
    assert fw > 0 and fh > 0


# --- Speed -------------------------------------------------------------------


def test_recommended_speed_electronic_half_of_mechanical():
    gsd = 2.74  # cm/px
    v_mech = calculate_recommended_speed(gsd, 0.001, "mechanical")
    v_elec = calculate_recommended_speed(gsd, 0.001, "electronic")
    assert v_mech == pytest.approx(v_elec / ELECTRONIC_SHUTTER_FACTOR * MECHANICAL_SHUTTER_FACTOR)
    assert v_elec == pytest.approx(gsd / 100.0 / (2.0 * 0.001) * 0.5)


def test_recommended_speed_capped_by_drone():
    v = calculate_recommended_speed(100.0, 0.001, "mechanical", drone_max_speed_ms=8.0)
    assert v == pytest.approx(8.0)
    v2 = calculate_recommended_speed(0.5, 0.001, "mechanical", drone_max_speed_ms=50.0)
    assert v2 == pytest.approx(0.5 / 100.0 / (2.0 * 0.001) * 1.0)


# --- Spacing -----------------------------------------------------------------


def test_line_spacing_formula():
    assert calculate_line_spacing(100.0, 65.0) == pytest.approx(35.0)
    assert calculate_line_spacing(100.0, 0.0) == pytest.approx(100.0)


def test_photo_spacing_formula():
    assert calculate_photo_spacing(100.0, 75.0) == pytest.approx(25.0)
    assert calculate_photo_spacing(100.0, 100.0) == pytest.approx(0.0)


# --- Distance ----------------------------------------------------------------


def test_utm_epsg_for_northern_and_southern():
    assert utm_epsg_for(-3.6, 37.18) == 32630  # Spain (N) zone 30
    assert utm_epsg_for(-3.6, -37.18) == 32730  # S hemisphere zone 30


def test_calculate_path_distance_matches_utm_expected():
    # ~1 degree of longitude at lat 37 is ~88.8 km; distance between two points
    # separated by 0.001 deg lon (~89 m) must be in the tens of meters.
    d = calculate_path_distance([(-3.600, 37.180), (-3.599, 37.180)])
    assert 70 < d < 110


def test_calculate_path_distance_zero_and_single():
    assert calculate_path_distance([]) == 0.0
    assert calculate_path_distance([(-3.6, 37.18)]) == 0.0
    assert calculate_path_distance([(-3.6, 37.18), (-3.6, 37.18)]) == pytest.approx(0.0, abs=1e-6)


def test_calculate_path_distance_is_metric_not_equirectangular_rough():
    # 0.001 deg latitude ~ 111 m regardless of longitude
    d = calculate_path_distance([(-3.6, 37.18), (-3.6, 37.181)])
    assert 105 < d < 120


# --- Battery -----------------------------------------------------------------


def test_battery_uses_fraction_with_drone():
    r = calculate_battery_requirements(30 * 60.0, drone_flight_time_min=30.0)
    assert r.usable_flight_time_min == pytest.approx(30.0 * DEFAULT_USABLE_BATTERY_FRACTION)
    assert r.flight_time_available_min == 30.0
    assert r.battery_count == 2  # 30 min required / 24 usable


def test_battery_fallback_without_drone_is_documented_default():
    r = calculate_battery_requirements(30 * 60.0)
    assert r.flight_time_available_min == pytest.approx(DEFAULT_FLIGHT_TIME_MIN_FALLBACK)
    assert r.usable_flight_time_min == pytest.approx(DEFAULT_FLIGHT_TIME_MIN_FALLBACK)
    assert r.battery_count >= 1
    assert r.battery_margin_min == pytest.approx(25.0 * r.battery_count - 30.0)


def test_battery_minimum_one():
    r = calculate_battery_requirements(1.0, drone_flight_time_min=30.0)
    assert r.battery_count == 1
    assert r.battery_margin_min > 0


def test_battery_custom_fraction():
    r = calculate_battery_requirements(12 * 60.0, drone_flight_time_min=20.0, usable_battery_fraction=0.5)
    assert r.usable_flight_time_min == pytest.approx(10.0)
    assert r.battery_count == 2


# --- Mission metrics ---------------------------------------------------------


def _fake_plan(durations, distances):
    class T:
        def __init__(self, d, dist):
            self.turn_duration_s = d
            self.turn_distance_m = dist

    class P:
        def __init__(self):
            self.turns = [T(d, dist) for d, dist in zip(durations, distances)]

    return P()


def _straight_line_waypoints():
    # two parallel lines with a turn connector in between (heading flips 180)
    return [
        (-3.600, 37.180, 90.0),
        (-3.500, 37.180, 90.0),  # line 0 forward
        (-3.500, 37.181, 90.0),  # connector (heading unchanged? -> transition via heading diff)
        (-3.600, 37.181, 270.0),  # line 1 reversed
    ]


def test_metrics_no_plan_falls_back_to_overhead():
    m = calculate_mission_metrics(_straight_line_waypoints(), speed_mps=10.0, num_lines=2)
    assert m.total_distance_m > 0
    assert m.turn_time_s == pytest.approx(2 * 5.0)
    assert m.turn_source == "overhead_fallback"
    assert m.battery_count >= 1


def test_metrics_with_plan_uses_real_turn_times():
    plan = _fake_plan(durations=[4.0, 4.0], distances=[20.0, 20.0])
    m = calculate_mission_metrics(_straight_line_waypoints(), speed_mps=10.0, num_lines=2, turn_plan=plan)
    assert m.turn_source == "turn_plan"
    assert m.turn_time_s == pytest.approx(8.0)
    assert m.turn_distance_m == pytest.approx(40.0)
    assert m.total_time_s == pytest.approx(m.straight_time_s + m.transition_time_s + m.turn_time_s)


def test_metrics_straight_plus_transition_equals_total():
    m = calculate_mission_metrics(_straight_line_waypoints(), speed_mps=10.0, num_lines=2)
    assert m.straight_distance_m + m.transition_distance_m == pytest.approx(m.total_distance_m)


def test_metrics_single_point_is_safe():
    m = calculate_mission_metrics([(-3.6, 37.18, 0.0)], speed_mps=10.0, num_lines=0)
    assert m.total_distance_m == pytest.approx(0.0)
    assert m.battery_count >= 1
