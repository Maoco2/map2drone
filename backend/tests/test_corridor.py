import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app

client = TestClient(app)

CENTERLINE = {
    "type": "LineString",
    "coordinates": [
        [-3.60, 37.18],
        [-3.585, 37.1803],
        [-3.57, 37.1802],
        [-3.555, 37.1797],
        [-3.54, 37.179],
    ],
}


class FakeProvider:
    def get_elevations(self, points):
        return [100.0 + (i % 7) * 3.0 for i in range(len(points))]


def _req(**kw):
    base = {
        "centerline": CENTERLINE,
        "width_left": 120,
        "width_right": 80,
        "altitude": 100,
        "overlap_frontal": 75,
        "overlap_lateral": 65,
        "camera_id": "cam-1-20mp",
        "altitude_mode": "takeoff",
    }
    base.update(kw)
    return base


def _ensure_db():
    Base.metadata.create_all(bind=engine)
    from app.api.v1.endpoints import init_db
    init_db()


def test_api_corridor_vertex():
    _ensure_db()
    resp = client.post("/api/v1/planning/corridor", json=_req())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["waypoints"]) >= 2
    assert data["num_lines"] >= 1
    assert data["waypoint_mode"] == "vertex"
    assert data["corridor_length_m"] > 0
    assert data["corridor_area_m2"] > 0
    assert data["gsd"] > 0
    # geometry in geographic coords
    assert data["geometry"]["polygon_geojson"]["type"] == "Polygon"
    fc = data["geometry"]["flight_lines_geojson"]
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == data["num_lines"]
    assert data["geometry"]["epsg_out"] != 4326  # projected CRS used


def test_api_corridor_photo():
    _ensure_db()
    resp = client.post("/api/v1/planning/corridor", json=_req(altitude_mode="photo"))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["waypoint_mode"] == "photo"
    assert data["photo_count"] == len(data["waypoints"])
    for wp in data["waypoints"]:
        assert wp["action_type"] == 1


def test_api_corridor_terrain():
    _ensure_db()
    with patch("app.modules.corridor.engine.create_provider", return_value=FakeProvider()):
        resp = client.post("/api/v1/planning/corridor", json=_req(altitude_mode="ground"))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["waypoint_mode"] == "terrain"
    for wp in data["waypoints"]:
        assert wp["agl"] == 100
        assert wp["elevation_msnm"] > 0


def test_api_corridor_short_centerline():
    _ensure_db()
    req = _req()
    req["centerline"] = {"type": "LineString", "coordinates": [[-3.6, 37.18]]}
    resp = client.post("/api/v1/planning/corridor", json=req)
    assert resp.status_code == 400


def test_api_corridor_no_camera():
    _ensure_db()
    req = _req(camera_id="ghost-cam")
    resp = client.post("/api/v1/planning/corridor", json=req)
    assert resp.status_code == 400


def test_api_corridor_creates_mission():
    _ensure_db()
    reg = client.post("/api/v1/auth/register", json={
        "full_name": "Corr Test", "email": "corr@test.dev",
        "password": "secret123", "country": "", "city": "",
        "phone": "", "gender": "", "profession": "",
    })
    if reg.status_code != 200:
        login = client.post("/api/v1/auth/login", json={"email": "corr@test.dev", "password": "secret123"})
        assert login.status_code == 200
        token = login.json()["access_token"]
    else:
        token = reg.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    proj = client.post("/api/v1/projects", json={"name": "Corr Project"}, headers=headers)
    assert proj.status_code == 200
    pid = proj.json()["id"]

    resp = client.post("/api/v1/planning/corridor", json=_req(project_id=pid), headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["mission_id"] is not None

    missions = client.get(f"/api/v1/projects/{pid}/missions", headers=headers)
    assert missions.status_code == 200
    saved = missions.json()[0]
    assert saved["mission_type"] == "linear_corridor"
    poly = json.loads(saved["polygon_geojson"])
    assert poly["type"] == "Polygon"
    params = json.loads(saved["parameters_json"])
    assert params["width_left"] == 120 and params["width_right"] == 80
