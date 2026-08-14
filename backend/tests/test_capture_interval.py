"""Tests for the Capture Interval Engine (app.core.photogrammetry.capture_interval)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.core.photogrammetry.capture_interval import (
    MIN_PLAUSIBLE_AGL_FLOOR_M,
    STATUS_ERROR,
    STATUS_INCOMPATIBLE,
    STATUS_VALID,
    STATUS_WARNING,
    compute_capture_interval,
    compute_minimum_plausible_agl,
)
from app.main import app

client = TestClient(app)


def _for_ideal_interval(ideal_s: float):
    """Build inputs (speed=1 m/s, 80% front overlap) that yield the given ideal."""
    speed = 1.0
    overlap = 80.0
    footprint = ideal_s / (1.0 - overlap / 100.0)  # required spacing == ideal_s
    return footprint, overlap, speed


def _cases():
    """(ideal, expected_recommended, expected_status) using speed=1, overlap=80."""
    return [
        (0.5, None, STATUS_INCOMPATIBLE),
        (0.9, None, STATUS_INCOMPATIBLE),
        (1.0, 1, STATUS_VALID),
        (1.2, 1, STATUS_VALID),
        (1.9, 1, STATUS_WARNING),
        (2.0, 2, STATUS_VALID),
        (2.1, 2, STATUS_VALID),
        (3.8, 3, STATUS_WARNING),
        (4.0, 4, STATUS_VALID),
        (4.9, 4, STATUS_VALID),
        (5.6, 5, STATUS_VALID),
        (6.0, 6, STATUS_VALID),
    ]


@pytest.mark.parametrize(
    "ideal,expected_rec,expected_status",
    [(c[0], c[1], c[2]) for c in _cases()],
    ids=[f"ideal_{c[0]}s" for c in _cases()],
)
def test_recommended_interval_and_status(ideal, expected_rec, expected_status):
    footprint, overlap, speed = _for_ideal_interval(ideal)
    res = compute_capture_interval(footprint_length_m=footprint, front_overlap=overlap, flight_speed_mps=speed)
    assert res.status == expected_status
    assert res.recommended_interval_s == expected_rec


@pytest.mark.parametrize("ideal", [c[0] for c in _cases()], ids=[f"ideal_{c[0]}s" for c in _cases()])
def test_effective_overlap_never_below_required(ideal):
    footprint, overlap, speed = _for_ideal_interval(ideal)
    res = compute_capture_interval(footprint_length_m=footprint, front_overlap=overlap, flight_speed_mps=speed)
    if res.status in (STATUS_VALID, STATUS_WARNING):
        assert res.effective_front_overlap is not None
        assert res.effective_front_overlap >= overlap / 100.0 - 1e-9


@pytest.mark.parametrize("ideal", [c[0] for c in _cases()], ids=[f"ideal_{c[0]}s" for c in _cases()])
def test_recommended_interval_is_integer(ideal):
    footprint, overlap, speed = _for_ideal_interval(ideal)
    res = compute_capture_interval(footprint_length_m=footprint, front_overlap=overlap, flight_speed_mps=speed)
    if res.recommended_interval_s is not None:
        assert float(res.recommended_interval_s).is_integer()
        assert res.recommended_interval_s >= 1


def test_largest_integer_is_chosen_not_rounded():
    # ideal 2.5 s -> 2 s (never 3 s)
    res = compute_capture_interval(footprint_length_m=20.0, front_overlap=75.0, flight_speed_mps=2.0)
    assert res.status == STATUS_VALID
    assert res.recommended_interval_s == 2
    assert res.ideal_interval_s == pytest.approx(2.5)
    assert res.actual_photo_spacing_m == pytest.approx(4.0)
    assert res.required_photo_spacing_m == pytest.approx(5.0)


def test_spec_example_footprint_20_overlap_75_speed_2():
    res = compute_capture_interval(footprint_length_m=20.0, front_overlap=75.0, flight_speed_mps=2.0)
    assert res.required_photo_spacing_m == pytest.approx(5.0)
    assert res.ideal_interval_s == pytest.approx(2.5)
    assert res.recommended_interval_s == 2
    assert res.effective_front_overlap == pytest.approx(0.8)


def test_ideal_5_6s_recommends_5s():
    footprint, overlap, speed = _for_ideal_interval(5.6)
    res = compute_capture_interval(footprint_length_m=footprint, front_overlap=overlap, flight_speed_mps=speed)
    assert res.recommended_interval_s == 5


def test_incompatible_returns_max_speed_for_1s():
    # ideal 0.5 s -> even 1 s fails -> INCOMPATIBLE with max speed 0.5 m/s
    footprint, overlap, speed = _for_ideal_interval(0.5)
    res = compute_capture_interval(footprint_length_m=footprint, front_overlap=overlap, flight_speed_mps=speed)
    assert res.status == STATUS_INCOMPATIBLE
    assert res.recommended_interval_s is None
    assert res.actual_photo_spacing_m is None
    assert res.effective_front_overlap is None
    assert res.maximum_speed_for_1s == pytest.approx(0.5)


def test_incompatible_reduces_to_required_spacing():
    footprint, overlap, speed = _for_ideal_interval(0.9)
    res = compute_capture_interval(footprint_length_m=footprint, front_overlap=overlap, flight_speed_mps=speed)
    assert res.status == STATUS_INCOMPATIBLE
    assert res.maximum_speed_for_1s == pytest.approx(res.required_photo_spacing_m / 1.0)


def test_error_invalid_inputs():
    assert compute_capture_interval(0, 75, 2).status == STATUS_ERROR
    assert compute_capture_interval(-10, 75, 2).status == STATUS_ERROR
    assert compute_capture_interval(20, 75, 0).status == STATUS_ERROR
    assert compute_capture_interval(20, 100, 2).status == STATUS_ERROR
    assert compute_capture_interval(20, 0, 2).status == STATUS_ERROR
    assert compute_capture_interval(20, 75, -1).status == STATUS_ERROR


# --- Terrain-follow: conservative minimum footprint ------------------------


def test_min_agl_constant_terrain_uses_nominal():
    assert compute_minimum_plausible_agl(100.0, [600.0, 600.0, 600.0]) == pytest.approx(100.0)


def test_min_agl_rising_terrain_reduces_agl():
    # terrain rising 40 m above the reference -> minimum AGL drops by 40 m
    assert compute_minimum_plausible_agl(100.0, [600.0, 620.0, 640.0]) == pytest.approx(60.0)


def test_min_agl_falling_terrain_keeps_nominal():
    # terrain only falls below the reference -> minimum clearance stays nominal
    assert compute_minimum_plausible_agl(100.0, [640.0, 620.0, 600.0]) == pytest.approx(100.0)


def test_min_agl_empty_elevations_falls_back():
    assert compute_minimum_plausible_agl(100.0, []) == pytest.approx(100.0)
    assert compute_minimum_plausible_agl(100.0, [], fallback_agl_m=80.0) == pytest.approx(80.0)


def test_min_agl_all_zero_elevations_falls_back():
    # DEM unavailable (all zeros) -> safest available estimate is the nominal AGL
    assert compute_minimum_plausible_agl(100.0, [0.0, 0.0, 0.0]) == pytest.approx(100.0)


def test_min_agl_never_below_floor():
    assert compute_minimum_plausible_agl(50.0, [600.0, 900.0]) == pytest.approx(MIN_PLAUSIBLE_AGL_FLOOR_M)


def _cam_footprint_length(agl_m: float) -> float:
    """Along-track footprint (m) for cam-1-20mp at the given AGL."""
    from app.modules.planning.engine import calc_footprint, calc_gsd

    gsd = calc_gsd(agl_m, 8.8, 2.41)  # focal 8.8mm, pixel 2.41um
    _, length = calc_footprint(gsd, 5472, 3648)
    return length


def test_min_footprint_is_smaller_than_nominal():
    nominal = _cam_footprint_length(100.0)
    min_agl = compute_minimum_plausible_agl(100.0, [600.0, 620.0, 640.0])
    conservative = _cam_footprint_length(min_agl)
    assert min_agl < 100.0
    assert conservative < nominal


def test_terrain_interval_uses_conservative_footprint_integer_and_overlap():
    nominal_fh = _cam_footprint_length(100.0)
    min_agl = compute_minimum_plausible_agl(100.0, [600.0, 620.0, 640.0])
    conservative_fh = _cam_footprint_length(min_agl)
    speed = 5.0

    nom = compute_capture_interval(nominal_fh, 75.0, speed)
    cons = compute_capture_interval(conservative_fh, 75.0, speed)

    assert cons.recommended_interval_s is not None
    assert float(cons.recommended_interval_s).is_integer()
    if nom.recommended_interval_s is not None:
        # a smaller footprint can only shrink the interval, never grow it
        assert cons.recommended_interval_s <= nom.recommended_interval_s
    if cons.status in (STATUS_VALID, STATUS_WARNING):
        assert cons.effective_front_overlap >= cons.required_front_overlap / 100.0 - 1e-9


def test_terrain_incompatible_when_1s_insufficient():
    # relief >= altitude -> minimum AGL clamps at the floor -> tiny footprint
    min_agl = compute_minimum_plausible_agl(100.0, [600.0, 800.0])
    fh = _cam_footprint_length(min_agl)
    res = compute_capture_interval(fh, 85.0, 12.0)
    assert res.status == STATUS_INCOMPATIBLE
    assert res.recommended_interval_s is None
    assert res.maximum_speed_for_1s == pytest.approx(res.required_photo_spacing_m / 1.0)


# --- Endpoint integration ------------------------------------------------


def _api_grid(altitude_mode: str = "takeoff"):
    return client.post("/api/v1/planning/grid", json={
        "polygon": {
            "type": "Polygon",
            "coordinates": [[[-3.60, 37.10], [-3.50, 37.10], [-3.50, 37.20], [-3.60, 37.20], [-3.60, 37.10]]],
        },
        "altitude": 100,
        "overlap_frontal": 75,
        "overlap_lateral": 65,
        "camera_id": "cam-43-20mp",
        "drone_id": "dji-m3e",
        "altitude_mode": altitude_mode,
    })


def _api_corridor(altitude_mode: str = "takeoff"):
    return client.post("/api/v1/planning/corridor", json={
        "centerline": {
            "type": "LineString",
            "coordinates": [[-3.60, 37.18], [-3.585, 37.1803], [-3.57, 37.1802], [-3.555, 37.1797], [-3.54, 37.179]],
        },
        "width_left": 120,
        "width_right": 80,
        "altitude": 100,
        "overlap_frontal": 75,
        "overlap_lateral": 65,
        "camera_id": "cam-1-20mp",
        "altitude_mode": altitude_mode,
    })


def test_api_grid_returns_capture_interval():
    Base.metadata.create_all(bind=engine)
    resp = _api_grid()
    assert resp.status_code == 200, resp.text
    ci = resp.json()["capture_interval"]
    assert ci is not None
    assert ci["status"] in (STATUS_VALID, STATUS_WARNING, STATUS_INCOMPATIBLE, STATUS_ERROR)
    assert ci["recommended_interval_s"] is None or float(ci["recommended_interval_s"]).is_integer()
    assert ci["recommended_interval_s"] is None or ci["recommended_interval_s"] >= 1
    assert ci["required_front_overlap"] == 75
    if ci["status"] in (STATUS_VALID, STATUS_WARNING):
        assert ci["effective_front_overlap"] >= ci["required_front_overlap"] - 1e-9
    if ci["status"] == STATUS_INCOMPATIBLE:
        assert ci["maximum_speed_for_1s"] is not None


def test_api_corridor_returns_capture_interval():
    Base.metadata.create_all(bind=engine)
    resp = _api_corridor()
    assert resp.status_code == 200, resp.text
    ci = resp.json()["capture_interval"]
    assert ci is not None
    assert ci["status"] in (STATUS_VALID, STATUS_WARNING, STATUS_INCOMPATIBLE, STATUS_ERROR)
    assert ci["recommended_interval_s"] is None or float(ci["recommended_interval_s"]).is_integer()
    assert ci["recommended_interval_s"] is None or ci["recommended_interval_s"] >= 1
    if ci["status"] in (STATUS_VALID, STATUS_WARNING):
        assert ci["recommended_interval_s"] is not None


class FakeProvider:
    """DEM provider whose terrain rises above the first sample (max 118 m)."""

    def get_elevations(self, points):
        return [100.0 + (i % 7) * 3.0 for i in range(len(points))]


def test_api_grid_terrain_capture_interval_is_conservative():
    Base.metadata.create_all(bind=engine)
    with patch("app.modules.planning.engine.create_provider", return_value=FakeProvider()):
        resp = _api_grid(altitude_mode="ground")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["waypoint_mode"] == "terrain"
    ci = data["capture_interval"]
    assert ci is not None

    resp_nom = _api_grid(altitude_mode="takeoff")
    assert resp_nom.status_code == 200
    ci_nom = resp_nom.json()["capture_interval"]
    assert ci_nom is not None

    # terrain relief above the reference shrinks the minimum footprint, so the
    # required photo spacing must be strictly smaller than the nominal-altitude one
    assert ci["required_photo_spacing_m"] is not None
    assert ci_nom["required_photo_spacing_m"] is not None
    assert ci["required_photo_spacing_m"] < ci_nom["required_photo_spacing_m"]
    if ci["recommended_interval_s"] is not None and ci_nom["recommended_interval_s"] is not None:
        assert ci["recommended_interval_s"] <= ci_nom["recommended_interval_s"]


def test_api_corridor_terrain_capture_interval_is_conservative():
    Base.metadata.create_all(bind=engine)
    with patch("app.modules.corridor.engine.create_provider", return_value=FakeProvider()):
        resp = _api_corridor(altitude_mode="ground")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["waypoint_mode"] == "terrain"
    ci = data["capture_interval"]
    assert ci is not None

    resp_nom = _api_corridor(altitude_mode="takeoff")
    assert resp_nom.status_code == 200
    ci_nom = resp_nom.json()["capture_interval"]
    assert ci_nom is not None

    assert ci["required_photo_spacing_m"] is not None
    assert ci_nom["required_photo_spacing_m"] is not None
    assert ci["required_photo_spacing_m"] < ci_nom["required_photo_spacing_m"]
    if ci["recommended_interval_s"] is not None and ci_nom["recommended_interval_s"] is not None:
        assert ci["recommended_interval_s"] <= ci_nom["recommended_interval_s"]


def test_api_grid_terrain_dem_unavailable_warns_and_keeps_nominal_interval():
    Base.metadata.create_all(bind=engine)
    with patch("app.modules.planning.engine.create_provider", return_value=FakeProvider()):
        resp = _api_grid(altitude_mode="ground")
    assert resp.status_code == 200
    # with usable DEM the capture-interval footprint is conservative (smaller)
    ci_ok = resp.json()["capture_interval"]

    class ZeroProvider:
        def get_elevations(self, points):
            return [0.0] * len(points)

    with patch("app.modules.planning.engine.create_provider", return_value=ZeroProvider()):
        resp = _api_grid(altitude_mode="ground")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["waypoint_mode"] == "terrain"
    assert any("Elevation data unavailable" in w for w in data["warnings"])
    ci = data["capture_interval"]
    assert ci is not None
    # DEM unavailable -> interval uses the nominal altitude, which is >= conservative
    assert ci["required_photo_spacing_m"] is not None
    assert ci_ok["required_photo_spacing_m"] is not None
    assert ci["required_photo_spacing_m"] >= ci_ok["required_photo_spacing_m"]
