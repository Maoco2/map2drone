"""Tests for the Capture Interval Engine (app.core.photogrammetry.capture_interval)."""

import pytest

from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.core.photogrammetry.capture_interval import (
    STATUS_ERROR,
    STATUS_INCOMPATIBLE,
    STATUS_VALID,
    STATUS_WARNING,
    compute_capture_interval,
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


# --- Endpoint integration ------------------------------------------------


def _api_grid():
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
    })


def _api_corridor():
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
        "altitude_mode": "takeoff",
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
