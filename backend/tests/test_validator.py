"""Tests for the Universal Mission Validator (Fase 10B)."""

from app.modules.mission.models import (
    CaptureMode,
    CapturePlan,
    MissionGeometry,
    MissionMetrics,
    MissionParameters,
    TurnPlan,
    UniversalMission,
    UniversalWaypoint,
)


def _valid_mission(**overrides) -> UniversalMission:
    params = MissionParameters(
        altitude_m=100.0,
        overlap_frontal=75.0,
        overlap_lateral=65.0,
        speed_ms=6.8,
        altitude_mode="takeoff",
    )
    metrics = MissionMetrics(
        total_distance_m=1000.0,
        estimated_time_sec=150.0,
        line_spacing_m=40.0,
        photo_spacing_m=20.0,
        gsd_cm=2.74,
        footprint_width_m=120.0,
        footprint_height_m=80.0,
        num_lines=2,
        photo_count=10,
        battery_count=1,
        waypoint_count=3,
        flight_time_s=150.0,
    )
    waypoints = [
        UniversalWaypoint(
            index=0, latitude=37.10, longitude=-3.60, altitude_m=100.0, heading_deg=90.0, capture_enabled=True
        ),
        UniversalWaypoint(
            index=1, latitude=37.10, longitude=-3.55, altitude_m=100.0, heading_deg=90.0, capture_enabled=True
        ),
        UniversalWaypoint(
            index=2, latitude=37.10, longitude=-3.50, altitude_m=100.0, heading_deg=90.0, capture_enabled=True
        ),
    ]
    flight_lines = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[-3.60, 37.10], [-3.50, 37.10]]},
                "properties": {},
            },
        ],
    }
    mission = UniversalMission(
        mission_type="grid",
        parameters=params,
        waypoints=waypoints,
        metrics=metrics,
        flight_lines_geojson=flight_lines,
        capture_plan=CapturePlan(
            mode=CaptureMode.TIME,
            scientific_interval_s=5.3,
            commercial_interval_s=5,
            status="VALID",
        ),
    )
    if overrides:
        mission = mission.model_copy(update=overrides)
    return mission


def _codes(result) -> set[str]:
    return {i.code for i in [*result.errors, *result.warnings]}


def test_valid_mission_passes():
    from app.modules.mission import UniversalMissionValidator

    result = UniversalMissionValidator().validate(_valid_mission())
    assert result.valid is True
    assert result.status == "VALID"
    assert result.errors == []
    assert result.warnings == []


def test_waypoint_without_coords_is_error():
    from app.modules.mission import UniversalMissionValidator

    mission = _valid_mission()
    mission.waypoints[1].latitude = None
    result = UniversalMissionValidator().validate(mission)
    assert result.valid is False
    assert "waypoint_missing_coords" in _codes(result)
    assert result.status == "INVALID"


def test_empty_waypoints_is_error():
    from app.modules.mission import UniversalMissionValidator

    mission = _valid_mission(waypoints=[])
    result = UniversalMissionValidator().validate(mission)
    assert result.valid is False
    assert "waypoints_empty" in _codes(result)


def test_empty_flight_lines_is_error():
    from app.modules.mission import UniversalMissionValidator

    mission = _valid_mission(flight_lines_geojson={"type": "FeatureCollection", "features": []})
    result = UniversalMissionValidator().validate(mission)
    assert result.valid is False
    assert "flight_lines_empty" in _codes(result)


def test_invalid_crs_is_error():
    from app.modules.mission import UniversalMissionValidator

    mission = _valid_mission(
        geometry=MissionGeometry(
            flight_lines_geojson={"type": "FeatureCollection", "features": []},
            epsg_out=9999,
        )
    )
    result = UniversalMissionValidator().validate(mission)
    assert result.valid is False
    assert "invalid_crs" in _codes(result)


def test_photo_point_outside_lines_warns():
    from app.modules.mission import UniversalMissionValidator

    mission = _valid_mission(photo_points=[{"index": 0, "latitude": 40.0, "longitude": 50.0, "capture": True}])
    result = UniversalMissionValidator().validate(mission)
    assert "photo_point_outside_lines" in _codes(result)
    assert result.status == "WARNING"


def test_photogrammetry_errors():
    from app.modules.mission import UniversalMissionValidator

    m = _valid_mission()
    m.metrics.line_spacing_m = 0
    assert "spacing_invalid" in _codes(UniversalMissionValidator().validate(m))
    m = _valid_mission()
    m.metrics.gsd_cm = 0
    assert "gsd_invalid" in _codes(UniversalMissionValidator().validate(m))
    m = _valid_mission()
    m.parameters.overlap_frontal = 100.0
    assert "overlap_invalid" in _codes(UniversalMissionValidator().validate(m))
    m = _valid_mission()
    m.metrics.footprint_width_m = 0
    assert "footprint_invalid" in _codes(UniversalMissionValidator().validate(m))


def test_flight_errors_and_heading_warning():
    from app.modules.mission import UniversalMissionValidator

    m = _valid_mission()
    m.parameters.speed_ms = 0
    m.parameters.recommended_speed_mps = 0
    assert "speed_invalid" in _codes(UniversalMissionValidator().validate(m))
    m = _valid_mission()
    m.parameters.altitude_m = 0
    assert "altitude_invalid" in _codes(UniversalMissionValidator().validate(m))
    m = _valid_mission()
    m.waypoints[0].heading_deg = None
    result = UniversalMissionValidator().validate(m)
    assert "waypoint_missing_heading" in _codes(result)
    assert result.status == "WARNING"


def test_capture_errors():
    from app.modules.mission import UniversalMissionValidator

    m = _valid_mission(
        capture_plan=CapturePlan(
            mode=CaptureMode.TIME,
            scientific_interval_s=0,
            commercial_interval_s=5,
        )
    )
    assert "capture_interval_invalid" in _codes(UniversalMissionValidator().validate(m))
    m = _valid_mission(
        capture_plan=CapturePlan(
            mode=CaptureMode.TIME,
            scientific_interval_s=5.0,
            commercial_interval_s=0,
        )
    )
    assert "capture_interval_invalid" in _codes(UniversalMissionValidator().validate(m))
    m = _valid_mission(capture_plan=CapturePlan(mode=CaptureMode.DISTANCE, photo_spacing_m=0))
    assert "capture_distance_invalid" in _codes(UniversalMissionValidator().validate(m))
    m = _valid_mission(capture_plan=CapturePlan(mode=CaptureMode.NONE))
    result = UniversalMissionValidator().validate(m)
    assert "capture_none_with_active_capture" in _codes(result)


def test_turn_errors():
    from app.modules.mission import UniversalMissionValidator

    m = _valid_mission(turn_plan=TurnPlan(mode="AUTO", status="INVALID", radius_m=12.0))
    assert "turn_status_invalid" in _codes(UniversalMissionValidator().validate(m))
    m = _valid_mission(turn_plan=TurnPlan(mode="AUTO", status="VALID", radius_m=12.0, available_radius_m=8.0))
    assert "turn_radius_exceeds_available" in _codes(UniversalMissionValidator().validate(m))
    m = _valid_mission(turn_plan=TurnPlan(mode="AUTO", status="VALID", radius_m=-1.0))
    assert "turn_radius_invalid" in _codes(UniversalMissionValidator().validate(m))
    m = _valid_mission(turn_plan=TurnPlan(mode="AUTO", status="CONSTRAINED", radius_m=12.0, warnings=["tight"]))
    result = UniversalMissionValidator().validate(m)
    assert "turn_warning" in _codes(result)
    assert result.status == "WARNING"


def test_battery_errors_and_flight_time_warning():
    from app.modules.mission import UniversalMissionValidator

    m = _valid_mission()
    m.metrics.battery_count = 0
    assert "battery_count_invalid" in _codes(UniversalMissionValidator().validate(m))
    m = _valid_mission()
    m.drone_profile = type("DP", (), {"flight_time_min": 0.0})()
    result = UniversalMissionValidator().validate(m)
    assert "flight_time_invalid" in _codes(result)


def test_validator_never_mutates():
    from app.modules.mission import UniversalMissionValidator

    m = _valid_mission()
    m.metrics.gsd_cm = 0
    UniversalMissionValidator().validate(m)
    assert m.metrics.gsd_cm == 0
