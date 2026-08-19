"""End-to-end UMM export flow tests (Planning → UMM → Export).

Caso A: small grid → LCHM + Litchi CSV exports match the planned mission.
Caso B: grid over the LCHM 99-waypoint capacity → BLOCKED ``split_required``,
        and the UMM export endpoint refuses instead of emitting a corrupt file.
Caso C: photo capture NONE → LCHM is emitted without the photo trailer.
Caso D: DISTANCE photo capture → LCHM carries the photo trailer.
Caso E: TIME capture interval floors only in the Litchi export chain (integer in
        CSV) while the Universal Mission keeps the scientific decimal value.
"""

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.schemas import Camera, Drone
from app.modules.export.litchi_lchm import LCHM_TRAILER_PHOTO_BLOCK_SIZE, parse_lchm
from app.modules.mission import build_universal_mission
from app.modules.planning.engine import compute_grid
from app.schemas.schemas import GridRequest

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


def _base_mission(**overrides) -> dict:
    """Build the planned Universal Mission through the planning engine
    (the same path the planner endpoint uses)."""
    payload = _grid_payload(**overrides)
    db = next(get_db())
    try:
        req = GridRequest(**payload)
        result = compute_grid(req, db)
        camera = db.query(Camera).filter(Camera.id == req.camera_id).first()
        drone = db.query(Drone).filter(Drone.id == req.drone_id).first()
        mission = build_universal_mission("grid", req, result, camera=camera, drone=drone)
        return mission.model_dump(mode="json")
    finally:
        db.close()


def _small_grid_mission() -> dict:
    return _base_mission(altitude=250.0, overlap_frontal=80.0, overlap_lateral=75.0)


# ── Caso A: grid → LCHM + Litchi CSV ─────────────────────────────────────────


def test_e2e_grid_export_lchm_and_litchi():
    mission = _small_grid_mission()
    assert len(mission["waypoints"]) <= 99

    resp = client.post(
        "/api/v1/export/umm/litchi_lchm",
        json={"mission": mission},
    )
    assert resp.status_code == 200, resp.text
    parsed = parse_lchm(resp.content)
    assert parsed.waypoint_count == len(mission["waypoints"])

    resp = client.post(
        "/api/v1/export/umm/litchi",
        json={"mission": mission},
    )
    assert resp.status_code == 200, resp.text
    csv = resp.content.decode("utf-8")
    lines = [line for line in csv.splitlines() if line.strip()]
    assert lines[0].startswith("latitude,longitude")
    assert len(lines) - 1 == len(mission["waypoints"])


# ── Caso B: over 99 waypoints → BLOCKED, export refused ──────────────────────


def test_e2e_grid_over_99_blocked_and_export_refused():
    mission = _base_mission()
    assert len(mission["waypoints"]) > 99

    resp = client.post(
        "/api/v1/export/check-umm",
        json={"mission": mission, "formats": ["litchi_lchm"]},
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    assert item["status"] == "BLOCKED"
    assert "split_required" in item["codes"]

    resp = client.post(
        "/api/v1/export/umm/litchi_lchm",
        json={"mission": mission},
    )
    assert resp.status_code == 400


# ── Caso C: photo capture NONE → LCHM without trailer ────────────────────────


def test_e2e_lchm_without_photo_trailer_when_none():
    mission = _small_grid_mission()

    resp = client.post(
        "/api/v1/export/umm/litchi_lchm",
        json={"mission": mission, "options": {"photo_capture": None}},
    )
    assert resp.status_code == 200, resp.text
    no_trailer = resp.content
    parse_lchm(no_trailer)  # still a valid LCHM

    resp = client.post(
        "/api/v1/export/umm/litchi_lchm",
        json={
            "mission": mission,
            "options": {"photo_capture": {"mode": "TIME", "time_interval_s": 5}},
        },
    )
    assert resp.status_code == 200, resp.text
    with_trailer = resp.content
    assert len(with_trailer) - len(no_trailer) >= LCHM_TRAILER_PHOTO_BLOCK_SIZE


# ── Caso D: DISTANCE photo capture → LCHM trailer ────────────────────────────


def test_e2e_lchm_distance_photo_capture():
    mission = _small_grid_mission()
    resp = client.post(
        "/api/v1/export/umm/litchi_lchm",
        json={
            "mission": mission,
            "options": {"photo_capture": {"mode": "DISTANCE", "distance_interval_m": 20.5}},
        },
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.content) > parse_lchm(resp.content).waypoint_count  # trailer present


# ── Caso E: TIME interval floors only in the Litchi export chain ─────────────


def test_e2e_time_floor_only_in_litchi_export_chain():
    mission = _small_grid_mission()

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
