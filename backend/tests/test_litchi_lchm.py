from __future__ import annotations

import math
import struct
from pathlib import Path

import pytest

from app.modules.export import ExportWaypoint, MissionExportData, get_exporter
from app.modules.export.litchi_lchm import (
    LCHM_HEADER_SIZE,
    LCHM_WAYPOINT_RECORD_SIZE,
    LchmExporter,
    LchmFormatError,
    LchmHeadingMode,
    LchmPathMode,
    LchmUnsupportedConfigurationError,
    LchmValidationError,
    LchmWaypointRecord,
    LchmWaypointSerializer,
    lchm_diff,
    lchm_trailer_photo_blocks,
    parse_lchm,
    sanitize_filename,
    serialize_mission,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "litchi"

FIXTURE_A = FIXTURES_DIR / "Mission (3).lchm"
FIXTURE_B = FIXTURES_DIR / "Mission (3) (1).lchm"
FIXTURE_C = FIXTURES_DIR / "Mission (3) (2).lchm"


# ── Fixture helpers ──────────────────────────────────────────────────────────


def _fixture_bytes(path: Path) -> bytes:
    assert path.exists(), f"fixture missing: {path}"
    return path.read_bytes()


def _record(data: bytes, index: int) -> bytes:
    start = LCHM_HEADER_SIZE + index * LCHM_WAYPOINT_RECORD_SIZE
    return data[start : start + LCHM_WAYPOINT_RECORD_SIZE]


def _wp(
    lat: float,
    lon: float,
    alt: float,
    heading: float = 0.0,
    speed: float = 4.1,
    gimbal_pitch: int = -90,
    curve_radius: float = 0.0,
) -> LchmWaypointRecord:
    return LchmWaypointRecord(
        latitude=lat,
        longitude=lon,
        altitude=alt,
        heading=heading,
        speed=speed,
        gimbal_pitch=gimbal_pitch,
        curve_radius_m=curve_radius,
    )


# ── Golden fixture tests ─────────────────────────────────────────────────────


def test_fixture_a_structure():
    data = _fixture_bytes(FIXTURE_A)
    mission = parse_lchm(data)
    assert mission.path_mode == LchmPathMode.CURVED_TURNS
    assert mission.heading_mode == LchmHeadingMode.FOLLOW_PATH
    assert mission.waypoint_count == 10
    assert data[0:4] == b"lchm"
    # record spacing: each record 56 bytes starting at offset 44
    assert _record(data, 0) == data[44:100]
    assert _record(data, 1) == data[100:156]
    assert _record(data, 9) == data[548:604]
    assert len(_record(data, 0)) == LCHM_WAYPOINT_RECORD_SIZE


def test_fixture_b_structure():
    data = _fixture_bytes(FIXTURE_B)
    mission = parse_lchm(data)
    assert mission.path_mode == LchmPathMode.STRAIGHT
    assert mission.heading_mode == LchmHeadingMode.CUSTOM_POI
    assert mission.waypoint_count == 10


def test_fixture_c_structure():
    data = _fixture_bytes(FIXTURE_C)
    mission = parse_lchm(data)
    assert mission.path_mode == LchmPathMode.CURVED_TURNS
    assert mission.heading_mode == LchmHeadingMode.CUSTOM_POI
    assert mission.waypoint_count == 10


def test_fixture_a_waypoint_data_crosscheck():
    """Lat/lon/alt cross-checked against the Litchi CSV for the same mission."""
    data = _fixture_bytes(FIXTURE_A)
    mission = parse_lchm(data)
    expected = [
        (3.5871270, -76.4855905, 60.0),
        (3.5876250, -76.4855437, 59.0),
        (3.5882288, -76.4854664, 58.0),
        (3.5889532, -76.4853263, 57.6),
        (3.5901015, -76.4851629, 56.9),
        (3.5901271, -76.4853412, 57.4),
        (3.5889832, -76.4855039, 58.4),
        (3.5882577, -76.4856442, 58.9),
        (3.5876450, -76.4857227, 59.5),
        (3.5871440, -76.4857697, 60.6),
    ]
    for i, (lat, lon, alt) in enumerate(expected):
        wp = mission.waypoints[i]
        assert wp.latitude == pytest.approx(lat, abs=1e-6)
        assert wp.longitude == pytest.approx(lon, abs=1e-6)
        assert wp.altitude == pytest.approx(alt, abs=0.05)
        assert wp.gimbal_pitch == -90
        assert wp.speed == pytest.approx(4.1, abs=0.01)


# ── Path / heading mode byte tests (Fase 7 confirmed mapping) ──────────────
# byte[7]  = heading mode (0x00=FOLLOW_PATH, 0x03=CUSTOM_POI)
# byte[15] = path mode    (0x00=STRAIGHT,    0x01=CURVED_TURNS)


def test_path_mode_only_changes_offset_15():
    wps = [_wp(37.0, -3.5, 100.0)]
    curved = serialize_mission(wps, LchmPathMode.CURVED_TURNS, LchmHeadingMode.FOLLOW_PATH)
    straight = serialize_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)
    assert curved[15] == 0x01
    assert straight[15] == 0x00
    diff = lchm_diff(curved, straight)
    assert "offset 15: 01 → 00" in diff
    # nothing else changes in the header
    header_same = all(curved[i] == straight[i] for i in range(LCHM_HEADER_SIZE) if i != 15)
    assert header_same
    # waypoint records identical
    assert _record(curved, 0) == _record(straight, 0)


def test_heading_mode_only_changes_offset_7():
    wps = [_wp(37.0, -3.5, 100.0)]
    follow = serialize_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)
    poi = serialize_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.CUSTOM_POI)
    assert follow[7] == 0x00
    assert poi[7] == 0x03
    diff = lchm_diff(follow, poi)
    assert "offset 7: 00 → 03" in diff
    header_same = all(follow[i] == poi[i] for i in range(LCHM_HEADER_SIZE) if i != 7)
    assert header_same


# ── Binary writer / serializer unit tests ────────────────────────────────────


def test_waypoint_record_size_exact():
    serializer = LchmWaypointSerializer()
    result = serializer.serialize_waypoint(_wp(37.0, -3.5, 100.0))
    assert len(result) == LCHM_WAYPOINT_RECORD_SIZE


def test_serialize_mission_length_header_plus_records():
    wps = [_wp(37.0, -3.5, 100.0) for _ in range(5)]
    data = serialize_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)
    assert len(data) == LCHM_HEADER_SIZE + 5 * LCHM_WAYPOINT_RECORD_SIZE


def test_magic_bytes_present():
    data = serialize_mission([], LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)
    assert data[:4] == b"lchm"


def test_parser_rejects_bad_magic():
    data = b"XXXX" + bytes(100)
    with pytest.raises(LchmFormatError):
        parse_lchm(data)


def test_parser_rejects_truncated_file():
    wps = [_wp(37.0, -3.5, 100.0) for _ in range(3)]
    data = serialize_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)
    with pytest.raises(LchmFormatError):
        parse_lchm(data[: LCHM_HEADER_SIZE + 10])


def test_parser_rejects_header_truncated():
    with pytest.raises(LchmFormatError):
        parse_lchm(b"lchm" + bytes(10))


def test_parser_rejects_inconsistent_count():
    # header says 1 waypoint but only 0 records present
    data = bytearray(serialize_mission([], LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH))
    data[43] = 1
    with pytest.raises(LchmFormatError):
        parse_lchm(bytes(data))


# ── Round-trip tests ─────────────────────────────────────────────────────────


def test_roundtrip_basic():
    wps = [_wp(37.18, -3.60, 100.0, heading=0.0, speed=4.1)]
    data = serialize_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)
    mission = parse_lchm(data)
    assert mission.waypoint_count == 1
    wp = mission.waypoints[0]
    assert wp.latitude == pytest.approx(37.18, abs=1e-6)
    assert wp.longitude == pytest.approx(-3.60, abs=1e-6)
    assert wp.altitude == pytest.approx(100.0, abs=0.05)
    assert wp.heading == pytest.approx(0.0, abs=0.05)
    assert wp.speed == pytest.approx(4.1, abs=0.05)
    assert wp.gimbal_pitch == -90
    assert wp.gimbal_mode == 2


def test_roundtrip_altitude_profile():
    altitudes = [100, 110, 120, 115]
    wps = [_wp(37.0 + i * 0.001, -3.5, alt) for i, alt in enumerate(altitudes)]
    data = serialize_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)
    mission = parse_lchm(data)
    assert [wp.altitude for wp in mission.waypoints] == pytest.approx(altitudes, abs=0.05)


def test_roundtrip_headings():
    headings = [0, 90, 180, 270]
    wps = [_wp(37.0, -3.5, 100.0, heading=h) for h in headings]
    data = serialize_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)
    mission = parse_lchm(data)
    assert [wp.heading for wp in mission.waypoints] == pytest.approx(headings, abs=0.05)


def test_roundtrip_gimbal():
    pitches = [-90, -80, -45, 0]
    wps = [_wp(37.0, -3.5, 100.0, gimbal_pitch=p) for p in pitches]
    data = serialize_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)
    mission = parse_lchm(data)
    assert [wp.gimbal_pitch for wp in mission.waypoints] == pitches


def test_roundtrip_speed():
    speeds = [1.0, 4.0, 8.2]
    wps = [_wp(37.0, -3.5, 100.0, speed=s) for s in speeds]
    data = serialize_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)
    mission = parse_lchm(data)
    assert [wp.speed for wp in mission.waypoints] == pytest.approx(speeds, abs=0.05)


def test_roundtrip_curve_radius():
    """curve_radius_m (+36) round-trips; 0.0 written when no curve."""
    wps = [_wp(37.0, -3.5, 100.0, curve_radius=12.637) for _ in range(3)]
    data = serialize_mission(wps, LchmPathMode.CURVED_TURNS, LchmHeadingMode.FOLLOW_PATH)
    mission = parse_lchm(data)
    assert [wp.curve_radius_m for wp in mission.waypoints] == pytest.approx([12.637] * 3, abs=0.001)
    # raw bytes at +36 of each record
    for i in range(3):
        rec = _record(data, i)
        assert struct.unpack(">f", rec[36:40])[0] == pytest.approx(12.637, abs=0.001)


def test_curve_radius_defaults_to_zero():
    wps = [_wp(37.0, -3.5, 100.0)]
    data = serialize_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)
    rec = _record(data, 0)
    assert struct.unpack(">f", rec[36:40])[0] == 0.0


def test_roundtrip_waypoint_order_preserved():
    wps = [
        _wp(37.18, -3.60, 100.0, heading=0.0),
        _wp(37.19, -3.59, 120.0, heading=90.0),
        _wp(37.20, -3.58, 110.0, heading=180.0),
        _wp(37.21, -3.57, 105.0, heading=270.0),
    ]
    data = serialize_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)
    mission = parse_lchm(data)
    for i, (expected, parsed) in enumerate(zip(wps, mission.waypoints)):
        assert parsed.latitude == pytest.approx(expected.latitude, abs=1e-6)
        assert parsed.longitude == pytest.approx(expected.longitude, abs=1e-6)
        assert parsed.heading == pytest.approx(expected.heading, abs=0.05)


# ── Validator tests ──────────────────────────────────────────────────────────


def test_validator_rejects_invalid_latitude():
    from app.modules.export.litchi_lchm import LchmValidator

    validator = LchmValidator()
    wps = [_wp(95.0, -3.5, 100.0)]
    with pytest.raises(LchmValidationError):
        validator.validate_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)


def test_validator_rejects_invalid_longitude():
    from app.modules.export.litchi_lchm import LchmValidator

    validator = LchmValidator()
    wps = [_wp(37.0, -200.0, 100.0)]
    with pytest.raises(LchmValidationError):
        validator.validate_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)


def test_validator_rejects_nan_latitude():
    from app.modules.export.litchi_lchm import LchmValidator

    validator = LchmValidator()
    wps = [_wp(math.nan, -3.5, 100.0)]
    with pytest.raises(LchmValidationError):
        validator.validate_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)


def test_validator_rejects_inf_speed():
    from app.modules.export.litchi_lchm import LchmValidator

    validator = LchmValidator()
    wps = [_wp(37.0, -3.5, 100.0, speed=math.inf)]
    with pytest.raises(LchmValidationError):
        validator.validate_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)


def test_validator_rejects_negative_speed():
    from app.modules.export.litchi_lchm import LchmValidator

    validator = LchmValidator()
    wps = [_wp(37.0, -3.5, 100.0, speed=-1.0)]
    with pytest.raises(LchmValidationError):
        validator.validate_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)


# ── Mission / API export tests ───────────────────────────────────────────────


def test_export_area_grid_mission_order():
    exporter = get_exporter("litchi_lchm")
    # boustrophedon: line 1 heading 0, line 2 heading 180, ...
    waypoints = [
        ExportWaypoint(latitude=37.0, longitude=-3.60, altitude=100, heading=0.0, speed=4.1),
        ExportWaypoint(latitude=37.0, longitude=-3.58, altitude=100, heading=0.0, speed=4.1),
        ExportWaypoint(latitude=37.0, longitude=-3.56, altitude=100, heading=0.0, speed=4.1),
        ExportWaypoint(latitude=37.001, longitude=-3.56, altitude=100, heading=180.0, speed=4.1),
        ExportWaypoint(latitude=37.001, longitude=-3.58, altitude=100, heading=180.0, speed=4.1),
        ExportWaypoint(latitude=37.001, longitude=-3.60, altitude=100, heading=180.0, speed=4.1),
        ExportWaypoint(latitude=37.002, longitude=-3.60, altitude=100, heading=0.0, speed=4.1),
        ExportWaypoint(latitude=37.002, longitude=-3.58, altitude=100, heading=0.0, speed=4.1),
    ]
    mission = MissionExportData(
        project_name="area_grid_test",
        waypoints=waypoints,
        speed_ms=4.1,
        options={"path_mode": "STRAIGHT", "heading_mode": "FOLLOW_PATH"},
    )
    result = exporter.export(mission)
    assert result.is_binary
    assert result.filename == "area_grid_test_litchi.lchm"
    parsed = parse_lchm(result.data)
    assert parsed.path_mode == LchmPathMode.STRAIGHT
    assert parsed.heading_mode == LchmHeadingMode.FOLLOW_PATH
    assert parsed.waypoint_count == 8
    for i, (src, dst) in enumerate(zip(waypoints, parsed.waypoints)):
        assert dst.latitude == pytest.approx(src.latitude, abs=1e-6)
        assert dst.longitude == pytest.approx(src.longitude, abs=1e-6)
        assert dst.heading == pytest.approx(src.heading, abs=0.05)
        assert dst.altitude == pytest.approx(src.altitude, abs=0.05)


def test_export_linear_corridor_mission_order():
    exporter = get_exporter("litchi_lchm")
    waypoints = [
        ExportWaypoint(latitude=37.0, longitude=-3.60, altitude=120, heading=90.0, speed=6.0),
        ExportWaypoint(latitude=37.0, longitude=-3.59, altitude=110, heading=90.0, speed=6.0),
        ExportWaypoint(latitude=37.0, longitude=-3.58, altitude=115, heading=90.0, speed=6.0),
        ExportWaypoint(latitude=37.001, longitude=-3.58, altitude=115, heading=270.0, speed=6.0),
        ExportWaypoint(latitude=37.001, longitude=-3.59, altitude=110, heading=270.0, speed=6.0),
        ExportWaypoint(latitude=37.001, longitude=-3.60, altitude=120, heading=270.0, speed=6.0),
    ]
    mission = MissionExportData(project_name="corridor_test", waypoints=waypoints, speed_ms=6.0)
    result = exporter.export(mission)
    parsed = parse_lchm(result.data)
    assert parsed.waypoint_count == 6
    for i, (src, dst) in enumerate(zip(waypoints, parsed.waypoints)):
        assert dst.latitude == pytest.approx(src.latitude, abs=1e-6)
        assert dst.longitude == pytest.approx(src.longitude, abs=1e-6)
        assert dst.heading == pytest.approx(src.heading, abs=0.05)


def test_exporter_falls_back_to_mission_speed():
    exporter = get_exporter("litchi_lchm")
    mission = MissionExportData(
        project_name="speed_fallback",
        waypoints=[ExportWaypoint(latitude=37.0, longitude=-3.6, altitude=100, heading=0.0, speed=0)],
        speed_ms=6.81,
    )
    result = exporter.export(mission)
    parsed = parse_lchm(result.data)
    assert parsed.waypoints[0].speed == pytest.approx(6.81, abs=0.01)


def test_no_photo_interval_written():
    exporter = get_exporter("litchi_lchm")
    waypoints = [
        ExportWaypoint(latitude=37.0, longitude=-3.6, altitude=100, heading=0.0, speed=4.1),
        ExportWaypoint(latitude=37.0, longitude=-3.59, altitude=100, heading=0.0, speed=4.1),
    ]
    mission = MissionExportData(
        project_name="photo_interval_test",
        waypoints=waypoints,
        speed_ms=4.1,
        photo_spacing=20.6,
        capture_interval_s=5,
    )
    result = exporter.export(mission)
    # header + N*56 bytes only; no trailer, therefore no photo interval bytes
    assert len(result.data) == LCHM_HEADER_SIZE + 2 * LCHM_WAYPOINT_RECORD_SIZE
    assert b"photo" not in result.data


def test_warnings_include_photo_interval_note():
    exporter = get_exporter("litchi_lchm")
    mission = MissionExportData(
        project_name="t",
        waypoints=[ExportWaypoint(latitude=37.0, longitude=-3.6, altitude=100, heading=0.0)],
        capture_interval_s=5,
    )
    codes = [w.code for w in exporter.get_warnings(mission)]
    assert "photo_interval_not_serialized" in codes


def test_sanitize_filename():
    assert sanitize_filename("Area Grid 1!") == "area_grid_1"
    assert sanitize_filename("  Urbanización demo  ") == "urbanizaci_n_demo"
    assert sanitize_filename("") == "mission"


def test_lchm_diff_output():
    wps = [_wp(37.0, -3.5, 100.0)]
    a = serialize_mission(wps, LchmPathMode.CURVED_TURNS, LchmHeadingMode.FOLLOW_PATH)
    b = serialize_mission(wps, LchmPathMode.STRAIGHT, LchmHeadingMode.FOLLOW_PATH)
    diff = lchm_diff(a, b)
    assert "offset 15: 01 → 00" in diff
    assert lchm_diff(a, a) == "No differences."


def test_exporter_validation():
    exporter = get_exporter("litchi_lchm")
    valid = exporter.validate(
        MissionExportData(
            waypoints=[
                ExportWaypoint(latitude=37.0, longitude=-3.6, altitude=100, heading=0.0),
            ]
        )
    )
    assert valid.valid
    empty = exporter.validate(MissionExportData(waypoints=[]))
    assert not empty.valid


def test_exporter_validation_rejects_over_99_waypoints():
    exporter = get_exporter("litchi_lchm")
    waypoints = [
        ExportWaypoint(latitude=37.0 + i * 1e-5, longitude=-3.6, altitude=100, heading=0.0) for i in range(100)
    ]
    result = exporter.validate(MissionExportData(waypoints=waypoints))
    assert not result.valid
    assert any("99" in e.message for e in result.errors)


def test_exporter_export_refuses_over_99_waypoints():
    exporter = get_exporter("litchi_lchm")
    waypoints = [
        ExportWaypoint(latitude=37.0 + i * 1e-5, longitude=-3.6, altitude=100, heading=0.0) for i in range(100)
    ]
    mission = MissionExportData(project_name="too_many", waypoints=waypoints, speed_ms=6.0)
    with pytest.raises(LchmValidationError, match="99"):
        exporter.export(mission)


def test_exporter_export_succeeds_at_99_waypoints():
    exporter = get_exporter("litchi_lchm")
    waypoints = [ExportWaypoint(latitude=37.0 + i * 1e-5, longitude=-3.6, altitude=100, heading=0.0) for i in range(99)]
    mission = MissionExportData(project_name="max_ok", waypoints=waypoints, speed_ms=6.0)
    result = exporter.export(mission)
    assert parse_lchm(result.data).waypoint_count == 99


def test_exporter_unsupported_path_mode():
    exporter = get_exporter("litchi_lchm")
    mission = MissionExportData(
        project_name="t",
        waypoints=[ExportWaypoint(latitude=37.0, longitude=-3.6, altitude=100, heading=0.0)],
        options={"path_mode": "BACKWARD"},
    )
    with pytest.raises(LchmUnsupportedConfigurationError):
        exporter.export(mission)


def test_exporter_is_registered_and_binary():
    exporter = get_exporter("litchi_lchm")
    assert isinstance(exporter, LchmExporter)
    assert exporter.extension == ".lchm"
    assert exporter.name == "Litchi LCHM"
    assert exporter.compatibility.category.value == "reverse_engineered"
    # registered id appears in the list
    ids = [f["id"] for f in __import__("app.modules.export", fromlist=["list_exporters"]).list_exporters()]
    assert "litchi_lchm" in ids


# ── API endpoint test ────────────────────────────────────────────────────────


def test_api_export_litchi_lchm_binary():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/api/v1/export/litchi_lchm",
        json={
            "project_name": "Api Test",
            "waypoints": [
                {"latitude": 37.18, "longitude": -3.60, "altitude": 100, "heading": 0},
                {"latitude": 37.19, "longitude": -3.59, "altitude": 120, "heading": 90},
            ],
            "speed": 10,
            "altitude": 100,
            "options": {"path_mode": "STRAIGHT", "heading_mode": "FOLLOW_PATH"},
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/octet-stream"
    assert "litchi.lchm" in resp.headers["content-disposition"]
    data = resp.content
    assert data[:4] == b"lchm"
    assert len(data) == LCHM_HEADER_SIZE + 2 * LCHM_WAYPOINT_RECORD_SIZE
    parsed = parse_lchm(data)
    assert parsed.waypoint_count == 2
    assert parsed.path_mode == LchmPathMode.STRAIGHT
    assert parsed.heading_mode == LchmHeadingMode.FOLLOW_PATH


def test_api_export_curve_size_flows_to_record():
    """curve_size per waypoint must land in the LCHM record +36 field."""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/api/v1/export/litchi_lchm",
        json={
            "project_name": "Api Curve",
            "waypoints": [
                {"latitude": 37.18, "longitude": -3.60, "altitude": 100, "heading": 0, "curve_size": 12.6},
                {"latitude": 37.19, "longitude": -3.59, "altitude": 120, "heading": 90},
            ],
            "speed": 10,
            "altitude": 100,
            "options": {"path_mode": "CURVED_TURNS", "heading_mode": "FOLLOW_PATH"},
        },
    )
    assert resp.status_code == 200
    parsed = parse_lchm(resp.content)
    assert parsed.waypoints[0].curve_radius_m == pytest.approx(12.6, abs=0.01)
    assert parsed.waypoints[1].curve_radius_m == 0.0


def test_fixtures_are_not_used_as_template():
    """The exporter must build from the Universal Mission, not from fixture bytes."""
    exporter = get_exporter("litchi_lchm")
    fixture = parse_lchm(_fixture_bytes(FIXTURE_A))
    own = ExportWaypoint(latitude=10.5, longitude=-70.25, altitude=200.0, heading=33.3, speed=7.5)
    mission = MissionExportData(project_name="custom", waypoints=[own])
    result = exporter.export(mission)
    parsed = parse_lchm(result.data)
    assert parsed.waypoint_count == 1
    assert parsed.waypoints[0].latitude != fixture.waypoints[0].latitude
    assert parsed.waypoints[0].longitude != fixture.waypoints[0].longitude
    assert parsed.waypoints[0].altitude != fixture.waypoints[0].altitude


# ── Trailer photo blocks (CONFIRMED from fixture A vs CSV) ──────────────────


def test_trailer_photo_blocks_distinterval_match_csv():
    """First f32 of each trailer photo block equals photo_distinterval (10/10)."""
    blocks = lchm_trailer_photo_blocks(_fixture_bytes(FIXTURE_A))
    assert len(blocks) == 10
    stored = [b[0] for b in blocks]
    assert stored == [
        pytest.approx(20.6),
        pytest.approx(20.6),
        pytest.approx(20.6),
        pytest.approx(20.6),
        pytest.approx(-1.0),
        pytest.approx(20.6),
        pytest.approx(20.6),
        pytest.approx(20.6),
        pytest.approx(-1.0),
        pytest.approx(-1.0),
    ]


def test_trailer_photo_blocks_second_f32_unknown():
    """The second f32 of the photo pairs does not match photo_timeinterval (5.0)."""
    blocks = lchm_trailer_photo_blocks(_fixture_bytes(FIXTURE_A))
    second = [b[1] for b in blocks]
    assert all(not math.isclose(v, 5.0, abs_tol=1e-3) for v in second)


def test_trailer_photo_blocks_no_timeinterval_bytes():
    """5.0 (0x40A00000) does not appear anywhere in fixture A."""
    data = _fixture_bytes(FIXTURE_A)
    assert b"\x40\xa0\x00\x00" not in data


def test_trailer_photo_blocks_identical_across_fixtures():
    """A/B/C are the same mission, so photo blocks are byte-identical."""
    a = lchm_trailer_photo_blocks(_fixture_bytes(FIXTURE_A))
    b = lchm_trailer_photo_blocks(_fixture_bytes(FIXTURE_B))
    c = lchm_trailer_photo_blocks(_fixture_bytes(FIXTURE_C))
    assert a == b == c


def test_trailer_photo_blocks_empty_for_exported_files():
    """Exported missions carry no trailer, so no photo blocks are read."""
    exporter = get_exporter("litchi_lchm")
    mission = MissionExportData(
        project_name="grid",
        waypoints=[
            ExportWaypoint(latitude=3.58, longitude=-76.48, altitude=100.0),
            ExportWaypoint(latitude=3.59, longitude=-76.48, altitude=100.0),
        ],
    )
    result = exporter.export(mission)
    assert lchm_trailer_photo_blocks(result.data) == []
