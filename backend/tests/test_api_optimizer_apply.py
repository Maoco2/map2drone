"""API tests for the Fase 10F operational flow: /optimizer/apply, /export/umm, /export/check-umm.

Covers the gate: the exported LCHM represents exactly the evaluated winner and
no calculation is duplicated on the frontend.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.modules.export.litchi_lchm import parse_lchm

client = TestClient(app)

_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [-5.99, 37.35],
            [-5.94, 37.35],
            [-5.94, 37.39],
            [-5.99, 37.39],
            [-5.99, 37.35],
        ]
    ],
}

_CENTERLINE = {
    "type": "LineString",
    "coordinates": [[-5.99, 37.35], [-5.97, 37.36], [-5.95, 37.37]],
}


def _grid_payload(**overrides) -> dict:
    payload = {
        "polygon": _POLYGON,
        "altitude": 100.0,
        "overlap_frontal": 75.0,
        "overlap_lateral": 65.0,
        "camera_id": "cam-1-20mp",
        "drone_id": "dji-p4rtk",
        "altitude_mode": "takeoff",
    }
    payload.update(overrides)
    return payload


def _small_grid_payload() -> dict:
    """A grid small enough to stay within the LCHM 99-waypoint capacity."""
    return _grid_payload(altitude=250.0, overlap_frontal=80.0, overlap_lateral=75.0)


def _corridor_payload(**overrides) -> dict:
    payload = {
        "centerline": _CENTERLINE,
        "width_left": 60.0,
        "width_right": 60.0,
        "altitude": 100.0,
        "overlap_frontal": 75.0,
        "overlap_lateral": 65.0,
        "camera_id": "cam-1-20mp",
        "drone_id": "dji-p4rtk",
        "altitude_mode": "takeoff",
    }
    payload.update(overrides)
    return payload


def _altitude_variables(altitudes):
    return {"variables": [{"name": "altitude_m", "mode": "candidate_values", "values": altitudes}]}


def _solve_grid(altitudes=(80, 100, 120)):
    resp = client.post(
        "/api/v1/optimizer/solve",
        json={"grid": _grid_payload(), "variables": _altitude_variables(list(altitudes))},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _solve_small_grid():
    resp = client.post(
        "/api/v1/optimizer/solve",
        json={"grid": _small_grid_payload(), "variables": _altitude_variables([250])},
    )
    assert resp.status_code == 200, resp.text
    winner = resp.json()["best_candidate"]
    assert len(winner["mission"]["waypoints"]) <= 99
    return winner


def _apply_payload(solve_data, winner, values, **overrides):
    payload = {
        "solve_request": {"grid": _grid_payload(), "variables": _altitude_variables([80, 100, 120])},
        "winner": winner,
        "winner_variable_values": values,
    }
    payload.update(overrides)
    return payload


# ── Apply (Fase 10F-1/2) ─────────────────────────────────────────────────────


def test_api_apply_grid_search_applies_winner():
    solve = _solve_grid()
    winner = solve["best_candidate"]
    assert winner is not None
    payload = _apply_payload(solve, winner["mission"], winner["variable_values"])
    resp = client.post("/api/v1/optimizer/apply", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["applied"] is True
    assert data["winner_mission"]["mission_type"] == "grid"
    assert data["baseline_mission"]["mission_type"] == "grid"

    # Verification: winner == the mission the search evaluated (deterministic rebuild).
    assert data["verification"]["method"] == "candidate_builder"
    assert data["verification"]["rebuilt"] is True
    assert data["verification"]["matches"] is True

    # Winner payload round-trips: the applied winner equals the evaluated mission.
    assert data["winner_mission"]["metrics"]["total_distance_m"] == winner["mission"]["metrics"]["total_distance_m"]

    # Baseline is the original planned mission (altitude 100).
    baseline = data["baseline_mission"]
    assert baseline["parameters"]["altitude_m"] == 100.0
    assert data["winner_mission"]["parameters"]["altitude_m"] == winner["mission"]["parameters"]["altitude_m"]

    # Comparison table has the required rows with deltas.
    metrics = {r["metric"]: r for r in data["comparison"]}
    assert "altitude_m" in metrics
    assert "gsd_cm" in metrics
    assert "overlap_front" in metrics
    assert "overlap_side" in metrics
    assert "speed_mps" in metrics
    assert "capture_interval_s" in metrics
    assert "photo_count" in metrics
    assert "total_distance_m" in metrics
    assert "estimated_time_s" in metrics
    assert "turn_count" in metrics
    assert "turn_radius_m" in metrics
    assert "battery_count" in metrics
    assert "total_score" in metrics
    assert metrics["altitude_m"]["baseline"] == 100.0
    assert metrics["altitude_m"]["winner"] == winner["mission"]["parameters"]["altitude_m"]

    # Score rows populated.
    assert data["baseline_score"]["total_score"] is not None
    assert data["winner_score"]["total_score"] is not None
    assert data["baseline_score"]["total_score"] <= 1.0

    # Modified variables detected (altitude differs from baseline).
    assert "altitude_m" in data["modified_variables"]


def test_api_apply_corridor_applies_winner():
    solve = client.post(
        "/api/v1/optimizer/solve",
        json={"corridor": _corridor_payload(), "variables": _altitude_variables([90, 110])},
    ).json()
    winner = solve["best_candidate"]
    payload = {
        "solve_request": {
            "corridor": _corridor_payload(),
            "variables": _altitude_variables([90, 110]),
        },
        "winner": winner["mission"],
        "winner_variable_values": winner["variable_values"],
    }
    resp = client.post("/api/v1/optimizer/apply", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["winner_mission"]["mission_type"] == "linear_corridor"
    assert data["verification"]["matches"] is True


def test_api_apply_single_candidate_no_variables():
    solve = client.post("/api/v1/optimizer/solve", json={"grid": _grid_payload()}).json()
    winner = solve["best_candidate"]
    payload = {
        "solve_request": {"grid": _grid_payload()},
        "winner": winner["mission"],
        "winner_variable_values": winner["variable_values"],
    }
    resp = client.post("/api/v1/optimizer/apply", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["applied"] is True
    assert data["verification"]["method"] == "passthrough"
    assert data["modified_variables"] == []
    # Single candidate: baseline == winner (all deltas zero).
    for row in data["comparison"]:
        assert row["delta"] == 0.0 or row["delta"] is None


def test_api_apply_rejects_tampered_winner_409():
    solve = _solve_grid()
    winner = solve["best_candidate"]
    tampered = {**winner["mission"], "metrics": {**winner["mission"]["metrics"], "total_distance_m": 999999.0}}
    payload = _apply_payload(solve, tampered, winner["variable_values"])
    resp = client.post("/api/v1/optimizer/apply", json=payload)
    assert resp.status_code == 409, resp.text
    assert "does not match" in resp.json()["detail"]


def test_api_apply_invalid_payload_400():
    resp = client.post(
        "/api/v1/optimizer/apply",
        json={
            "solve_request": {"grid": _grid_payload()},
            "winner": {"schema_version": [], "parameters": {"altitude_m": "nope"}},
            "winner_variable_values": {},
        },
    )
    assert resp.status_code == 400


# ── UMM export (Fase 10F-5/12) ───────────────────────────────────────────────


def test_api_export_umm_litchi_matches_evaluated_winner():
    winner = _solve_small_grid()
    resp = client.post(
        "/api/v1/export/umm/litchi_lchm",
        json={"mission": winner["mission"]},
    )
    assert resp.status_code == 200, resp.text
    parsed = parse_lchm(resp.content)
    assert parsed.waypoint_count == len(winner["mission"]["waypoints"])
    first = parsed.waypoints[0]
    winner_first = winner["mission"]["waypoints"][0]
    assert round(first.latitude, 6) == round(winner_first["latitude"], 6)
    assert round(first.longitude, 6) == round(winner_first["longitude"], 6)
    assert abs(first.altitude - winner_first["altitude_m"]) < 0.01


def test_api_export_umm_unknown_format_400():
    resp = client.post(
        "/api/v1/export/umm/nope",
        json={"mission": _solve_small_grid()["mission"]},
    )
    assert resp.status_code == 400


# ── Export readiness (Fase 10F-8) ────────────────────────────────────────────


def test_api_check_umm_readiness_ready():
    winner = _solve_small_grid()
    resp = client.post(
        "/api/v1/export/check-umm",
        json={"mission": winner["mission"], "formats": ["litchi_lchm"]},
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == "litchi_lchm"
    assert items[0]["status"] == "READY"


def test_api_check_umm_readiness_blocked_over_99():
    solve = _solve_grid()
    winner = solve["best_candidate"]
    mission = dict(winner["mission"])
    # Duplicate the first waypoint to exceed the LCHM capacity.
    wps = [dict(mission["waypoints"][0]) for _ in range(100)]
    mission["waypoints"] = wps
    mission["metrics"] = {**mission["metrics"], "waypoint_count": 100}
    resp = client.post(
        "/api/v1/export/check-umm",
        json={"mission": mission, "formats": ["litchi_lchm"]},
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    assert item["status"] == "BLOCKED"
    assert "split_required" in item["codes"]
