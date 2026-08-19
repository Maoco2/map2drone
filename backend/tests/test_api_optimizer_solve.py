"""API tests for POST /optimizer/solve (Fase 10C-10)."""

from fastapi.testclient import TestClient

from app.main import app

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
    return {
        "variables": [
            {"name": "altitude_m", "mode": "candidate_values", "values": altitudes},
        ]
    }


# ── Grid search ──────────────────────────────────────────────────────────────


def test_api_solve_grid_search_optimal():
    resp = client.post(
        "/api/v1/optimizer/solve",
        json={
            "grid": _grid_payload(),
            "variables": _altitude_variables([80, 100, 120]),
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "OPTIMAL"
    assert data["best_candidate"] is not None
    assert data["best_candidate"]["mission"]["mission_type"] == "grid"
    assert data["best_candidate"]["variable_values"]
    assert data["best_score"]["total_score"] is not None
    assert len(data["alternatives"]) == 2
    assert data["stats"] == {"total": 3, "evaluated": 3, "valid": 3, "invalid": 0, "rejected": 0}
    assert data["explanation"]["summary"].startswith("Selected mission")


def test_api_solve_grid_single_candidate_no_variables():
    resp = client.post("/api/v1/optimizer/solve", json={"grid": _grid_payload()})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "OPTIMAL"
    assert data["best_candidate"]["label"] == "base"
    assert data["best_candidate"]["variable_values"] == {}
    assert data["alternatives"] == []


def test_api_solve_grid_no_solution_with_constraints():
    resp = client.post(
        "/api/v1/optimizer/solve",
        json={
            "grid": _grid_payload(),
            "variables": _altitude_variables([100, 140]),
            "constraints": {"max_altitude": 10.0},
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "NO_SOLUTION"
    assert data["best_candidate"] is None
    assert data["best_score"] is None
    assert data["explanation"]["summary"].startswith("No feasible mission found")


def test_api_solve_grid_constrained_by_max_candidates():
    resp = client.post(
        "/api/v1/optimizer/solve",
        json={
            "grid": _grid_payload(),
            "variables": _altitude_variables([60, 80, 100, 120, 140]),
            "max_candidates": 2,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "CONSTRAINED"
    assert "max_candidates=2" in data["message"]
    assert data["stats"]["evaluated"] == 2


def test_api_solve_corridor_search():
    resp = client.post(
        "/api/v1/optimizer/solve",
        json={
            "corridor": _corridor_payload(),
            "variables": _altitude_variables([90, 110]),
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["best_candidate"]["mission"]["mission_type"] == "linear_corridor"
    assert data["stats"]["evaluated"] == 2


# ── Input validation ─────────────────────────────────────────────────────────


def test_api_solve_requires_exactly_one_mission_type():
    resp = client.post("/api/v1/optimizer/solve", json={})
    assert resp.status_code == 422
    both = client.post(
        "/api/v1/optimizer/solve",
        json={
            "grid": _grid_payload(),
            "corridor": _corridor_payload(),
        },
    )
    assert both.status_code == 422


def test_api_solve_unknown_variable_name_returns_400():
    resp = client.post(
        "/api/v1/optimizer/solve",
        json={
            "grid": _grid_payload(),
            "variables": {
                "variables": [
                    {"name": "not_a_variable", "mode": "fixed", "value": 1.0},
                ]
            },
        },
    )
    assert resp.status_code == 400
    assert "not_a_variable" in resp.json()["detail"]


def test_api_solve_invalid_variable_mode_returns_400():
    resp = client.post(
        "/api/v1/optimizer/solve",
        json={
            "grid": _grid_payload(),
            "variables": {
                "variables": [
                    {"name": "altitude_m", "mode": "bogus"},
                ]
            },
        },
    )
    assert resp.status_code == 400


def test_api_solve_invalid_constraints_returns_400():
    resp = client.post(
        "/api/v1/optimizer/solve",
        json={
            "grid": _grid_payload(),
            "constraints": {"min_gsd": "not-a-number"},
        },
    )
    assert resp.status_code == 400


def test_api_solve_max_candidates_zero_returns_422():
    resp = client.post(
        "/api/v1/optimizer/solve",
        json={
            "grid": _grid_payload(),
            "max_candidates": 0,
        },
    )
    assert resp.status_code == 422
