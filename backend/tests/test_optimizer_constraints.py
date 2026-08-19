"""Tests for structured constraint evaluation (Fase 10C-3)."""

from app.modules.mission.models import (
    CaptureMode,
    CapturePlan,
    MissionMetrics,
    MissionParameters,
    TurnPlan,
    UniversalMission,
    UniversalWaypoint,
)
from app.modules.optimizer.constraints import evaluate_constraints
from app.modules.optimizer.evaluator import evaluate
from app.modules.optimizer.models import (
    ConstraintReport,
    ConstraintStatus,
    OptimizationConstraints,
)


def _mission(**overrides) -> UniversalMission:
    params = MissionParameters(
        altitude_m=100.0,
        overlap_frontal=75.0,
        overlap_lateral=65.0,
        speed_ms=6.8,
        altitude_mode="takeoff",
        capture_mode="TIME",
        turn_mode="AUTO",
        turn_radius_m=12.0,
        capture_interval_s=5.3,
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
        battery_count=2,
        waypoint_count=3,
        flight_time_s=150.0,
        flight_distance_m=1000.0,
        line_count=2,
    )
    waypoints = [
        UniversalWaypoint(
            index=0, latitude=37.10, longitude=-3.60, altitude_m=100.0, heading_deg=90.0, capture_enabled=True
        ),
        UniversalWaypoint(
            index=1, latitude=37.10, longitude=-3.55, altitude_m=100.0, heading_deg=90.0, capture_enabled=True
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
        turn_plan=TurnPlan(mode="AUTO", status="VALID", radius_m=12.0, extension_m=5.0),
    )
    if overrides:
        mission = mission.model_copy(update=overrides)
    return mission


def _report_for(reports, constraint):
    return [r for r in reports if r.constraint == constraint]


def _statuses(reports):
    return {r.constraint: r.status for r in reports}


# ── Structure ────────────────────────────────────────────────────────────────


def test_reports_have_required_structure():
    reports = evaluate_constraints(OptimizationConstraints(min_altitude=60.0), _mission())
    assert len(reports) == 1
    r = reports[0]
    assert isinstance(r, ConstraintReport)
    assert r.constraint == "altitude_m"
    assert r.value == 100.0
    assert r.limit == {"min": 60.0}
    assert r.status is ConstraintStatus.PASS
    assert isinstance(r.reason, str) and r.reason


def test_no_constraints_yields_empty_report():
    assert evaluate_constraints(None, _mission()) == []


def test_unknown_dimensions_are_not_reported_when_unconfigured():
    reports = evaluate_constraints(OptimizationConstraints(), _mission())
    assert reports == []


# ── Bounds → PASS / FAIL ─────────────────────────────────────────────────────


def test_altitude_within_bounds_is_pass():
    reports = evaluate_constraints(
        OptimizationConstraints(min_altitude=60.0, max_altitude=200.0),
        _mission(),
    )
    r = _report_for(reports, "altitude_m")[0]
    assert r.status is ConstraintStatus.PASS
    assert r.limit == {"min": 60.0, "max": 200.0}


def test_altitude_below_minimum_is_fail():
    reports = evaluate_constraints(
        OptimizationConstraints(min_altitude=150.0),
        _mission(),
    )
    r = _report_for(reports, "altitude_m")[0]
    assert r.status is ConstraintStatus.FAIL
    assert "below the minimum" in r.reason


def test_altitude_above_maximum_is_fail():
    reports = evaluate_constraints(
        OptimizationConstraints(max_altitude=80.0),
        _mission(),
    )
    r = _report_for(reports, "altitude_m")[0]
    assert r.status is ConstraintStatus.FAIL
    assert "exceeds the maximum" in r.reason


def test_gsd_and_overlaps_and_speed_reported():
    mission = _mission()
    reports = evaluate_constraints(
        OptimizationConstraints(
            min_gsd=2.0,
            max_gsd=4.0,
            min_overlap_front=70.0,
            max_overlap_front=90.0,
            min_overlap_side=60.0,
            max_overlap_side=80.0,
            min_speed=4.0,
            max_speed=12.0,
        ),
        mission,
    )
    statuses = _statuses(reports)
    assert statuses == {
        "gsd_cm": ConstraintStatus.PASS,
        "overlap_frontal": ConstraintStatus.PASS,
        "overlap_lateral": ConstraintStatus.PASS,
        "speed_ms": ConstraintStatus.PASS,
    }


def test_violated_bounds_all_reported_never_hidden():
    mission = _mission()
    reports = evaluate_constraints(
        OptimizationConstraints(
            min_altitude=150.0,  # FAIL (100 < 150)
            max_gsd=2.0,  # FAIL (2.74 > 2)
            max_speed=5.0,  # FAIL (6.8 > 5)
            max_photo_count=5,  # FAIL (10 > 5)
            max_battery_count=1,  # FAIL (2 > 1)
        ),
        mission,
    )
    statuses = _statuses(reports)
    assert statuses["altitude_m"] is ConstraintStatus.FAIL
    assert statuses["gsd_cm"] is ConstraintStatus.FAIL
    assert statuses["speed_ms"] is ConstraintStatus.FAIL
    assert statuses["photo_count"] is ConstraintStatus.FAIL
    assert statuses["battery_count"] is ConstraintStatus.FAIL
    # every configured constraint appears — none is dropped
    assert len(reports) == 5


# ── Time / distance / interval ──────────────────────────────────────────────


def test_mission_time_min_and_max():
    reports = evaluate_constraints(
        OptimizationConstraints(min_flight_time=100.0, max_flight_time=200.0),
        _mission(),
    )
    r = _report_for(reports, "flight_time_s")[0]
    assert r.status is ConstraintStatus.PASS
    assert r.limit == {"min": 100.0, "max": 200.0}

    reports = evaluate_constraints(
        OptimizationConstraints(max_flight_time=120.0),
        _mission(),
    )
    assert _report_for(reports, "flight_time_s")[0].status is ConstraintStatus.FAIL


def test_mission_distance_min_and_max():
    reports = evaluate_constraints(
        OptimizationConstraints(min_mission_distance_m=900.0, max_mission_distance_m=1100.0),
        _mission(),
    )
    r = _report_for(reports, "flight_distance_m")[0]
    assert r.status is ConstraintStatus.PASS
    assert r.limit == {"min": 900.0, "max": 1100.0}

    reports = evaluate_constraints(
        OptimizationConstraints(max_mission_distance_m=500.0),
        _mission(),
    )
    assert _report_for(reports, "flight_distance_m")[0].status is ConstraintStatus.FAIL


def test_photo_interval_uses_scientific_interval():
    reports = evaluate_constraints(
        OptimizationConstraints(min_photo_interval_s=4.0, max_photo_interval_s=6.0),
        _mission(),
    )
    r = _report_for(reports, "photo_interval_s")[0]
    assert r.status is ConstraintStatus.PASS
    assert r.value == 5.3

    reports = evaluate_constraints(
        OptimizationConstraints(min_photo_interval_s=6.0),
        _mission(),
    )
    assert _report_for(reports, "photo_interval_s")[0].status is ConstraintStatus.FAIL


def test_photo_interval_falls_back_to_configured_parameter():
    mission = _mission(capture_plan=None)
    reports = evaluate_constraints(
        OptimizationConstraints(max_photo_interval_s=6.0),
        mission,
    )
    r = _report_for(reports, "photo_interval_s")[0]
    assert r.status is ConstraintStatus.PASS
    assert r.value == 5.3


# ── Turn radius / extension ─────────────────────────────────────────────────


def test_turn_radius_bounds():
    reports = evaluate_constraints(
        OptimizationConstraints(min_turn_radius_m=10.0, max_turn_radius_m=20.0),
        _mission(),
    )
    r = _report_for(reports, "turn_radius_m")[0]
    assert r.status is ConstraintStatus.PASS
    assert r.limit == {"min": 10.0, "max": 20.0}

    reports = evaluate_constraints(
        OptimizationConstraints(max_turn_radius_m=10.0),
        _mission(),
    )
    assert _report_for(reports, "turn_radius_m")[0].status is ConstraintStatus.FAIL


def test_preferred_turn_radius_is_soft_warning():
    reports = evaluate_constraints(
        OptimizationConstraints(preferred_turn_radius=15.0),
        _mission(),
    )
    r = _report_for(reports, "turn_radius_m")[0]
    assert r.status is ConstraintStatus.WARNING
    assert r.limit == {"preferred": 15.0}

    reports = evaluate_constraints(
        OptimizationConstraints(preferred_turn_radius=12.0),
        _mission(),
    )
    assert _report_for(reports, "turn_radius_m")[0].status is ConstraintStatus.PASS


def test_turn_extension_max():
    reports = evaluate_constraints(
        OptimizationConstraints(max_turn_extension_m=8.0),
        _mission(),
    )
    r = _report_for(reports, "turn_extension_m")[0]
    assert r.status is ConstraintStatus.PASS
    assert r.limit == {"max": 8.0}

    reports = evaluate_constraints(
        OptimizationConstraints(max_turn_extension_m=4.0),
        _mission(),
    )
    assert _report_for(reports, "turn_extension_m")[0].status is ConstraintStatus.FAIL


# ── Not evaluable (never silently hidden) ───────────────────────────────────


def test_constraint_without_data_is_warning_not_pass():
    mission = _mission(turn_plan=None)
    reports = evaluate_constraints(
        OptimizationConstraints(max_turn_extension_m=8.0),
        mission,
    )
    r = _report_for(reports, "turn_extension_m")[0]
    assert r.status is ConstraintStatus.WARNING
    assert "no turn plan extension" in r.reason


def test_capture_interval_not_allowed_is_fail():
    mission = _mission()
    reports = evaluate_constraints(
        OptimizationConstraints(allowed_capture_intervals=[1, 2, 3]),
        mission,
    )
    r = _report_for(reports, "capture_plan.commercial_interval_s")[0]
    assert r.status is ConstraintStatus.FAIL
    assert r.limit == {"allowed": [1, 2, 3]}


def test_capture_interval_allowed_is_pass():
    mission = _mission()
    reports = evaluate_constraints(
        OptimizationConstraints(allowed_capture_intervals=[1, 5, 6]),
        mission,
    )
    r = _report_for(reports, "capture_plan.commercial_interval_s")[0]
    assert r.status is ConstraintStatus.PASS


# ── Effect on evaluation ─────────────────────────────────────────────────────


def test_warning_does_not_invalidate_mission():
    result = evaluate(_mission(), constraints=OptimizationConstraints(preferred_turn_radius=15.0))
    assert result.valid is True
    assert result.status == "WARNING"
    assert any(w.startswith("constraint:turn_radius_m") for w in result.warnings)


def test_fail_invalidates_mission():
    result = evaluate(_mission(), constraints=OptimizationConstraints(max_flight_time=120.0))
    assert result.valid is False
    assert result.status == "INVALID"
    # score is still produced (mission is structurally valid) but knocked down
    assert result.score is not None
    assert result.score.total_score < 1.0
