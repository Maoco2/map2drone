"""Fase 5 — Litchi photo capture (TIME / DISTANCE / NONE) serialization tests.

Golden references are the real Litchi files M1-M6/V1/V2 (65 waypoints each):
  * ``photo_timeinterval``   f32 BE at ``settings_start + 10``  (M1=1.0 .. M6=6.0).
  * ``photo_distinterval``   f32 BE per waypoint at ``settings_start + 106 + i*8``
    (37 valid = 20.5, 28 sentinel = -1.0 across all real files).
  * trailing bytes ``00 00 00 00 09 00`` constant.

Round-trip test: Universal Mission -> LCHM -> parser -> Universal-equivalent
(waypoint count, altitude, heading, speed, gimbal, coordinates, time/distance
interval).
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.modules.export import ExportWaypoint, MissionExportData, get_exporter
from app.modules.export.litchi_lchm import (
    LCHM_HEADER_SIZE,
    LCHM_PHOTO_DIST_SENTINEL,
    LCHM_TRAILER_PHOTO_BLOCK_SIZE,
    LCHM_TRAILER_TAIL,
    LCHM_TRAILER_TIMEINT_REL,
    LCHM_WAYPOINT_RECORD_SIZE,
    LchmHeadingMode,
    LchmPathMode,
    LchmPhotoCaptureMode,
    LchmPhotoCaptureOptions,
    LchmValidationError,
    LchmWaypointRecord,
    lchm_photo_blocks_rel,
    lchm_settings_start,
    lchm_trailer_photo_blocks,
    normalize_litchi_time_interval,
    parse_lchm,
    serialize_mission_with_photo_capture,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "litchi"
REAL_DIR = FIXTURES_DIR / "real"


def _real(name: str) -> bytes:
    path = REAL_DIR / f"{name}.lchm"
    assert path.exists(), f"real fixture missing: {path}"
    return path.read_bytes()


def _real_trailer(data: bytes) -> bytes:
    mission = parse_lchm(data)
    n = mission.waypoint_count
    return data[LCHM_HEADER_SIZE + n * LCHM_WAYPOINT_RECORD_SIZE :]


def _real_timeinterval(data: bytes) -> float:
    mission = parse_lchm(data)
    n = mission.waypoint_count
    trailer = _real_trailer(data)
    off = lchm_settings_start(n) + LCHM_TRAILER_TIMEINT_REL
    return struct.unpack(">f", trailer[off : off + 4])[0]


def _real_dists(data: bytes) -> list[float]:
    mission = parse_lchm(data)
    n = mission.waypoint_count
    trailer = _real_trailer(data)
    dists = []
    for i in range(n):
        off = lchm_photo_blocks_rel(n) + i * LCHM_TRAILER_PHOTO_BLOCK_SIZE
        dists.append(struct.unpack(">f", trailer[off : off + 4])[0])
    return dists


def _wp(
    lat: float, lon: float, alt: float, heading: float = 0.0, speed: float = 4.1, gimbal_pitch: int = -90
) -> LchmWaypointRecord:
    return LchmWaypointRecord(
        latitude=lat,
        longitude=lon,
        altitude=alt,
        heading=heading,
        speed=speed,
        gimbal_pitch=gimbal_pitch,
    )


# ── Golden references (real M1-M6 / V1 / V2) ────────────────────────────────


@pytest.mark.parametrize(
    "name,expected",
    [
        ("M1", 1.0),
        ("M2", 2.0),
        ("M3", 3.0),
        ("M4", 4.0),
        ("M5", 5.0),
        ("M6", 6.0),
        ("V1", 6.0),
        ("V2", 6.0),
    ],
)
def test_golden_timeinterval(name: str, expected: float):
    assert _real_timeinterval(_real(name)) == pytest.approx(expected)


@pytest.mark.parametrize("name", ["M1", "M2", "M3", "M4", "M5", "M6", "V1", "V2"])
def test_golden_distinterval_20_5(name: str):
    dists = _real_dists(_real(name))
    valid = [d for d in dists if d >= 0]
    sentinels = [d for d in dists if d < 0]
    assert len(valid) == 37
    assert len(sentinels) == 28
    assert all(d == pytest.approx(20.5) for d in valid)
    assert all(d == pytest.approx(LCHM_PHOTO_DIST_SENTINEL) for d in sentinels)


def test_golden_trailing_constant():
    for name in ("M1", "M2", "V1", "V2"):
        data = _real(name)
        mission = parse_lchm(data)
        n = mission.waypoint_count
        trailer = _real_trailer(data)
        tail_start = lchm_photo_blocks_rel(n) + n * LCHM_TRAILER_PHOTO_BLOCK_SIZE
        assert trailer[tail_start : tail_start + 6] == LCHM_TRAILER_TAIL


# ── normalize_litchi_time_interval ──────────────────────────────────────────


def test_normalize_never_rounds_up():
    assert normalize_litchi_time_interval(5.3) == 5
    assert normalize_litchi_time_interval(5.9) == 5
    assert normalize_litchi_time_interval(5) == 5
    assert normalize_litchi_time_interval(1) == 1


def test_normalize_invalid_inputs():
    assert normalize_litchi_time_interval(None) is None
    assert normalize_litchi_time_interval(0) is None
    assert normalize_litchi_time_interval(-3) is None


# ── Trailer serializer ──────────────────────────────────────────────────────


def test_serialize_time_mode_writes_timeint():
    wps = [_wp(37.0, -3.5, 100.0), _wp(37.01, -3.5, 100.0)]
    capture = LchmPhotoCaptureOptions(mode=LchmPhotoCaptureMode.TIME, time_interval_s=5.3, distance_interval_m=None)
    data = serialize_mission_with_photo_capture(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH, capture)
    trailer = _real_trailer(data)
    n = 2
    off = lchm_settings_start(n) + LCHM_TRAILER_TIMEINT_REL
    assert struct.unpack(">f", trailer[off : off + 4])[0] == pytest.approx(5.0)


def test_serialize_distance_mode_writes_dist_blocks():
    wps = [_wp(37.0, -3.5, 100.0), _wp(37.01, -3.5, 100.0)]
    capture = LchmPhotoCaptureOptions(mode=LchmPhotoCaptureMode.DISTANCE, distance_interval_m=20.5)
    data = serialize_mission_with_photo_capture(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH, capture)
    trailer = _real_trailer(data)
    n = 2
    off = lchm_settings_start(n) + LCHM_TRAILER_TIMEINT_REL
    assert struct.unpack(">f", trailer[off : off + 4])[0] == pytest.approx(0.0)
    blocks = [struct.unpack(">f", trailer[lchm_photo_blocks_rel(n) + i * 8 :][:4])[0] for i in range(n)]
    assert blocks == [pytest.approx(20.5), pytest.approx(20.5)]


def test_serialize_none_mode_uses_sentinels_and_zero_timeint():
    wps = [_wp(37.0, -3.5, 100.0)]
    capture = LchmPhotoCaptureOptions(mode=LchmPhotoCaptureMode.NONE)
    data = serialize_mission_with_photo_capture(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH, capture)
    trailer = _real_trailer(data)
    n = 1
    off = lchm_settings_start(n) + LCHM_TRAILER_TIMEINT_REL
    assert struct.unpack(">f", trailer[off : off + 4])[0] == pytest.approx(0.0)
    dist = struct.unpack(">f", trailer[lchm_photo_blocks_rel(n) :][:4])[0]
    assert dist == pytest.approx(LCHM_PHOTO_DIST_SENTINEL)


def test_serialize_time_mode_keeps_distance_when_given():
    wps = [_wp(37.0, -3.5, 100.0)]
    capture = LchmPhotoCaptureOptions(mode=LchmPhotoCaptureMode.TIME, time_interval_s=5, distance_interval_m=20.5)
    data = serialize_mission_with_photo_capture(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH, capture)
    trailer = _real_trailer(data)
    dist = struct.unpack(">f", trailer[lchm_photo_blocks_rel(1) :][:4])[0]
    assert dist == pytest.approx(20.5)


def test_serialize_trailer_scales_with_waypoint_count():
    """settings_start = 6 + N*10 must scale; never a fixed 212."""
    for n in (10, 65, 74):
        assert lchm_settings_start(n) == 6 + n * 10
    assert lchm_photo_blocks_rel(65) == 762
    assert lchm_photo_blocks_rel(10) == 212


# ── Exporter integration (options.photo_capture) ────────────────────────────


def test_exporter_photo_capture_time_roundtrip():
    exporter = get_exporter("litchi_lchm")
    waypoints = [
        ExportWaypoint(latitude=37.0, longitude=-3.60, altitude=100, heading=0.0, speed=4.1),
        ExportWaypoint(latitude=37.01, longitude=-3.60, altitude=110, heading=90.0, speed=4.1),
        ExportWaypoint(latitude=37.02, longitude=-3.60, altitude=120, heading=180.0, speed=4.1),
    ]
    mission = MissionExportData(
        project_name="roundtrip",
        waypoints=waypoints,
        speed_ms=4.1,
        options={"photo_capture": {"mode": "TIME", "time_interval_s": 5}},
    )
    result = exporter.export(mission)
    parsed = parse_lchm(result.data)
    assert parsed.waypoint_count == 3
    assert parsed.waypoints[0].latitude == pytest.approx(37.0, abs=1e-6)
    assert parsed.waypoints[0].longitude == pytest.approx(-3.60, abs=1e-6)
    assert parsed.waypoints[0].altitude == pytest.approx(100.0, abs=0.05)
    assert parsed.waypoints[0].heading == pytest.approx(0.0, abs=0.05)
    assert parsed.waypoints[0].speed == pytest.approx(4.1, abs=0.01)
    assert parsed.waypoints[0].gimbal_pitch == -90
    assert parsed.waypoints[1].altitude == pytest.approx(110.0, abs=0.05)
    assert parsed.waypoints[2].altitude == pytest.approx(120.0, abs=0.05)
    # time interval written
    assert _real_timeinterval(result.data) == pytest.approx(5.0)


def test_exporter_photo_capture_distance_roundtrip():
    exporter = get_exporter("litchi_lchm")
    waypoints = [
        ExportWaypoint(latitude=37.0, longitude=-3.60, altitude=100),
        ExportWaypoint(latitude=37.01, longitude=-3.60, altitude=100),
    ]
    mission = MissionExportData(
        project_name="roundtrip",
        waypoints=waypoints,
        speed_ms=6.0,
        options={"photo_capture": {"mode": "DISTANCE", "distance_interval_m": 20.5}},
    )
    result = exporter.export(mission)
    dists = _real_dists(result.data)
    assert dists == [pytest.approx(20.5), pytest.approx(20.5)]


def test_exporter_photo_capture_none_roundtrip():
    exporter = get_exporter("litchi_lchm")
    waypoints = [
        ExportWaypoint(latitude=37.0, longitude=-3.60, altitude=100),
        ExportWaypoint(latitude=37.01, longitude=-3.60, altitude=100),
    ]
    mission = MissionExportData(
        project_name="roundtrip",
        waypoints=waypoints,
        speed_ms=6.0,
        options={"photo_capture": {"mode": "NONE"}},
    )
    result = exporter.export(mission)
    assert _real_timeinterval(result.data) == pytest.approx(0.0)
    dists = _real_dists(result.data)
    assert all(d == pytest.approx(LCHM_PHOTO_DIST_SENTINEL) for d in dists)


def test_exporter_no_photo_capture_still_no_trailer():
    exporter = get_exporter("litchi_lchm")
    waypoints = [
        ExportWaypoint(latitude=37.0, longitude=-3.60, altitude=100),
        ExportWaypoint(latitude=37.01, longitude=-3.60, altitude=100),
    ]
    mission = MissionExportData(project_name="plain", waypoints=waypoints, speed_ms=6.0)
    result = exporter.export(mission)
    assert len(result.data) == LCHM_HEADER_SIZE + 2 * LCHM_WAYPOINT_RECORD_SIZE
    assert lchm_trailer_photo_blocks(result.data) == []


def test_exporter_invalid_time_capture_raises():
    exporter = get_exporter("litchi_lchm")
    mission = MissionExportData(
        project_name="bad",
        waypoints=[ExportWaypoint(latitude=37.0, longitude=-3.60, altitude=100)],
        options={"photo_capture": {"mode": "TIME", "time_interval_s": 0}},
    )
    with pytest.raises(LchmValidationError):
        exporter.export(mission)


def test_exporter_invalid_distance_capture_raises():
    exporter = get_exporter("litchi_lchm")
    mission = MissionExportData(
        project_name="bad",
        waypoints=[ExportWaypoint(latitude=37.0, longitude=-3.60, altitude=100)],
        options={"photo_capture": {"mode": "DISTANCE", "distance_interval_m": -1}},
    )
    with pytest.raises(LchmValidationError):
        exporter.export(mission)


def test_exporter_unsupported_capture_mode_raises():
    exporter = get_exporter("litchi_lchm")
    mission = MissionExportData(
        project_name="bad",
        waypoints=[ExportWaypoint(latitude=37.0, longitude=-3.60, altitude=100)],
        options={"photo_capture": {"mode": "EVERY_BOOT"}},
    )
    with pytest.raises(Exception):
        exporter.export(mission)


def test_warnings_cleared_when_photo_capture_configured():
    exporter = get_exporter("litchi_lchm")
    mission = MissionExportData(
        project_name="t",
        waypoints=[ExportWaypoint(latitude=37.0, longitude=-3.60, altitude=100)],
        capture_interval_s=5,
        options={"photo_capture": {"mode": "TIME", "time_interval_s": 5}},
    )
    codes = [w.code for w in exporter.get_warnings(mission)]
    assert "photo_interval_not_serialized" not in codes


# ── Area Grid 74 waypoints, TIME=5 ──────────────────────────────────────────


def _grid_waypoints(n: int, base_lat: float = 37.0, base_lon: float = -3.6) -> list[ExportWaypoint]:
    return [
        ExportWaypoint(
            latitude=base_lat + (i % 10) * 0.001,
            longitude=base_lon + (i // 10) * 0.001,
            altitude=100.0,
            heading=(i * 45) % 360,
            speed=8.0,
            action_type=1,
        )
        for i in range(n)
    ]


def test_area_grid_74_waypoints_time5():
    exporter = get_exporter("litchi_lchm")
    waypoints = _grid_waypoints(74)
    mission = MissionExportData(
        project_name="area_grid_74",
        waypoints=waypoints,
        speed_ms=8.0,
        options={"photo_capture": {"mode": "TIME", "time_interval_s": 5}},
    )
    result = exporter.export(mission)
    parsed = parse_lchm(result.data)
    assert parsed.waypoint_count == 74
    assert _real_timeinterval(result.data) == pytest.approx(5.0)
    n = 74
    assert lchm_settings_start(n) == 6 + n * 10
    # dist blocks default to sentinel when TIME has no distance value
    dists = _real_dists(result.data)
    assert all(d == pytest.approx(LCHM_PHOTO_DIST_SENTINEL) for d in dists)


def test_linear_corridor_15_waypoints_time5():
    exporter = get_exporter("litchi_lchm")
    waypoints = [
        ExportWaypoint(
            latitude=37.0 + i * 0.001,
            longitude=-3.6 + (i % 2) * 0.001,
            altitude=100.0,
            heading=90.0,
            speed=8.0,
            action_type=1,
        )
        for i in range(15)
    ]
    mission = MissionExportData(
        project_name="linear_corridor_15",
        waypoints=waypoints,
        speed_ms=8.0,
        options={"photo_capture": {"mode": "TIME", "time_interval_s": 5}},
    )
    result = exporter.export(mission)
    parsed = parse_lchm(result.data)
    assert parsed.waypoint_count == 15
    assert _real_timeinterval(result.data) == pytest.approx(5.0)
    n = 15
    assert lchm_settings_start(n) == 6 + n * 10
    assert lchm_photo_blocks_rel(n) == 6 + n * 10 + 106


# ── API endpoint ────────────────────────────────────────────────────────────


def test_api_export_litchi_lchm_with_photo_capture():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/api/v1/export/litchi_lchm",
        json={
            "project_name": "Api Photo",
            "waypoints": [
                {"latitude": 37.18, "longitude": -3.60, "altitude": 100, "heading": 0},
                {"latitude": 37.19, "longitude": -3.59, "altitude": 120, "heading": 90},
            ],
            "speed": 10,
            "altitude": 100,
            "options": {
                "path_mode": "STRAIGHT",
                "heading_mode": "FOLLOW_PATH",
                "photo_capture": {"mode": "TIME", "time_interval_s": 6},
            },
        },
    )
    assert resp.status_code == 200
    assert resp.content[:4] == b"lchm"
    assert _real_timeinterval(resp.content) == pytest.approx(6.0)
