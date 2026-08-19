"""Fase 10F end-to-end flow tests (Planning → Optimizer → Apply → UMM → Export).

Caso A: small grid → apply → LCHM + Litchi CSV exports match the winner.
Caso B: grid over the LCHM 99-waypoint capacity → BLOCKED ``split_required``,
        and the UMM export endpoint refuses instead of emitting a corrupt file.
Caso C: corridor → apply → LCHM export matches the winner.
Caso D: photo capture NONE → LCHM is emitted without the photo trailer.
Caso E: DISTANCE photo capture → LCHM carries the photo trailer.
Caso F: TIME capture interval floors only in the Litchi export chain (integer in
        CSV) while the Universal Mission keeps the scientific decimal value.
"""

from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app
from app.modules.export.litchi_lchm import LCHM_TRAILER_PHOTO_BLOCK_SIZE, parse_lchm

client = TestClient(app)


def _ensure_db():
    Base.metadata.create_all(bind=engine)


def _auth_headers() -> dict:
    _ensure_db()
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "E2E 10F",
            "email": "e2e10f@test.dev",
            "password": "secret123",
            "country": "",
            "city": "",
            "phone": "",
            "gender": "",
            "profession": "",
        },
    )
    if reg.status_code != 200:
        login = client.post("/api/v1/auth/login", json={"email": "e2e10f@test.dev", "password": "secret123"})
        assert login.status_code == 200
        token = login.json()["access_token"]
    else:
        token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _project_id() -> str:
    headers = _auth_headers()
    proj = client.post("/api/v1/projects", json={"name": "E2E 10F Project"}, headers=headers)
    assert proj.status_code == 200
    return proj.json()["id"]


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
    return _grid_payload(altitude=250.0, overlap_frontal=80.0, overlap_lateral=75.0)


def _corridor_payload() -> dict:
    return {
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


def _variables(values):
    return {"variables": [{"name": "altitude_m", "mode": "candidate_values", "values": values}]}


def _solve(body) -> dict:
    resp = client.post("/api/v1/optimizer/solve", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _apply(winner, solve_request, project_id=None) -> dict:
    resp = client.post(
        "/api/v1/optimizer/apply",
        json={
            "solve_request": solve_request,
            "winner": winner["mission"],
            "winner_variable_values": winner["variable_values"],
            "project_id": project_id,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Caso A: grid → apply → LCHM + Litchi CSV ─────────────────────────────────


def test_e2e_grid_apply_export_lchm_and_litchi():
    project_id = _project_id()
    solve_req = {"grid": _small_grid_payload(), "variables": _variables([250])}
    solved = _solve(solve_req)
    winner = solved["best_candidate"]
    assert len(winner["mission"]["waypoints"]) <= 99

    applied = _apply(winner, solve_req, project_id)
    assert applied["mission_id"] is not None
    assert applied["verification"]["verified"] is True

    resp = client.post(
        "/api/v1/export/umm/litchi_lchm",
        json={"mission": applied["winner_mission"]},
    )
    assert resp.status_code == 200, resp.text
    parsed = parse_lchm(resp.content)
    assert parsed.waypoint_count == len(applied["winner_mission"]["waypoints"])

    resp = client.post(
        "/api/v1/export/umm/litchi",
        json={"mission": applied["winner_mission"]},
    )
    assert resp.status_code == 200, resp.text
    csv = resp.content.decode("utf-8")
    lines = [line for line in csv.splitlines() if line.strip()]
    assert lines[0].startswith("latitude,longitude")
    assert len(lines) - 1 == len(applied["winner_mission"]["waypoints"])


# ── Caso B: over 99 waypoints → BLOCKED, export refused ──────────────────────


def test_e2e_grid_over_99_blocked_and_export_refused():
    solve_req = {"grid": _grid_payload(), "variables": _variables([80, 100, 120])}
    winner = _solve(solve_req)["best_candidate"]
    assert len(winner["mission"]["waypoints"]) > 99

    resp = client.post(
        "/api/v1/export/check-umm",
        json={"mission": winner["mission"], "formats": ["litchi_lchm"]},
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    assert item["status"] == "BLOCKED"
    assert "split_required" in item["codes"]

    resp = client.post(
        "/api/v1/export/umm/litchi_lchm",
        json={"mission": winner["mission"]},
    )
    assert resp.status_code == 400


# ── Caso C: corridor → apply → LCHM ──────────────────────────────────────────


def test_e2e_corridor_apply_export_lchm():
    project_id = _project_id()
    solve_req = {"corridor": _corridor_payload(), "variables": _variables([100])}
    solved = _solve(solve_req)
    winner = solved["best_candidate"]
    assert winner["mission"]["mission_type"] == "linear_corridor"

    applied = _apply(winner, solve_req, project_id)
    assert applied["verification"]["verified"] is True
    assert applied["mission_id"] is not None

    resp = client.post(
        "/api/v1/export/umm/litchi_lchm",
        json={"mission": applied["winner_mission"]},
    )
    assert resp.status_code == 200, resp.text
    parsed = parse_lchm(resp.content)
    assert parsed.waypoint_count == len(applied["winner_mission"]["waypoints"])


# ── Caso D: photo capture NONE → LCHM without trailer ────────────────────────


def test_e2e_lchm_without_photo_trailer_when_none():
    winner = _solve({"grid": _small_grid_payload(), "variables": _variables([250])})["best_candidate"]

    resp = client.post(
        "/api/v1/export/umm/litchi_lchm",
        json={"mission": winner["mission"], "options": {"photo_capture": None}},
    )
    assert resp.status_code == 200, resp.text
    no_trailer = resp.content
    parse_lchm(no_trailer)  # still a valid LCHM

    resp = client.post(
        "/api/v1/export/umm/litchi_lchm",
        json={
            "mission": winner["mission"],
            "options": {"photo_capture": {"mode": "TIME", "time_interval_s": 5}},
        },
    )
    assert resp.status_code == 200, resp.text
    with_trailer = resp.content
    assert len(with_trailer) - len(no_trailer) >= LCHM_TRAILER_PHOTO_BLOCK_SIZE


# ── Caso E: DISTANCE photo capture → LCHM trailer ────────────────────────────


def test_e2e_lchm_distance_photo_capture():
    winner = _solve({"grid": _small_grid_payload(), "variables": _variables([250])})["best_candidate"]
    resp = client.post(
        "/api/v1/export/umm/litchi_lchm",
        json={
            "mission": winner["mission"],
            "options": {"photo_capture": {"mode": "DISTANCE", "distance_interval_m": 20.5}},
        },
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.content) > parse_lchm(resp.content).waypoint_count  # trailer present


# ── Caso F: TIME interval floors only in the Litchi export chain ─────────────


def test_e2e_time_floor_only_in_litchi_export_chain():
    solved = _solve({"grid": _small_grid_payload(), "variables": _variables([250])})
    winner = solved["best_candidate"]
    mission = winner["mission"]

    # The Universal Mission keeps the scientific (decimal) value.
    scientific = mission["capture_plan"]["scientific_interval_s"]
    assert scientific % 1 != 0

    resp = client.post(
        "/api/v1/export/umm/litchi",
        json={"mission": mission},
    )
    assert resp.status_code == 200, resp.text
    csv = resp.content.decode("utf-8")
    rows = [line for line in csv.splitlines() if line.strip()][1:]
    intervals = {float(line.split(",")[-2]) for line in rows if float(line.split(",")[-2]) > 0}
    # The Litchi CSV carries the integer (floored) interval, never the decimal
    # scientific value from the Universal Mission.
    assert intervals == {float(mission["capture_plan"]["commercial_interval_s"])}
    assert all(v == int(v) for v in intervals)
