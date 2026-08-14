import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from pyproj import CRS, Transformer
from shapely.geometry import LineString

from app.core.database import Base, engine
from app.main import app
from app.modules.corridor.engine import _vertex_waypoints

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


class ZeroProvider:
    def get_elevations(self, points):
        return [0.0] * len(points)


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
    assert data["photo_count"] == sum(1 for wp in data["waypoints"] if wp["action_type"] == 1)
    assert data["photo_count"] <= len(data["waypoints"])
    # flight-line vertices (corridor outline) must exist as navigation waypoints
    assert any(wp["action_type"] == -1 for wp in data["waypoints"])
    for wp in data["waypoints"]:
        assert wp["action_type"] in (1, -1)


def test_api_corridor_photo_includes_flight_line_vertices():
    _ensure_db()
    resp = client.post("/api/v1/planning/corridor", json=_req(altitude_mode="photo"))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    line_coords = data["geometry"]["flight_lines_geojson"]["features"][0]["geometry"]["coordinates"]
    first = line_coords[0]
    last = line_coords[-1]
    wps = data["waypoints"]
    tol = 0.0005
    assert any(
        abs(wp["longitude"] - first[0]) < tol and abs(wp["latitude"] - first[1]) < tol
        for wp in wps
    )
    assert any(
        abs(wp["longitude"] - last[0]) < tol and abs(wp["latitude"] - last[1]) < tol
        for wp in wps
    )


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


def test_api_corridor_terrain_dem_unavailable_falls_back_with_warning():
    _ensure_db()
    with patch("app.modules.corridor.engine.create_provider", return_value=ZeroProvider()):
        resp = client.post("/api/v1/planning/corridor", json=_req(altitude_mode="ground"))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["waypoint_mode"] == "terrain"
    assert len(data["waypoints"]) >= 2
    assert any("Elevation data unavailable" in w for w in data["warnings"])


def test_api_corridor_closed_ring_matches_open_centerline():
    _ensure_db()
    open_cl = {"type": "LineString", "coordinates": CENTERLINE["coordinates"]}
    closed_cl = {
        "type": "LineString",
        "coordinates": CENTERLINE["coordinates"] + [CENTERLINE["coordinates"][0]],
    }
    r1 = client.post("/api/v1/planning/corridor", json=_req(centerline=open_cl, altitude_mode="photo"))
    r2 = client.post("/api/v1/planning/corridor", json=_req(centerline=closed_cl, altitude_mode="photo"))
    assert r1.status_code == 200 and r2.status_code == 200
    d1, d2 = r1.json(), r2.json()
    assert len(d2["waypoints"]) == len(d1["waypoints"])
    assert d2["corridor_length_m"] == d1["corridor_length_m"]
    assert d2["num_lines"] == d1["num_lines"]


def test_corridor_linear_joins_no_rounded_arcs():
    """Corridor offsets must use linear (mitre) joins so flight lines keep
    their sharp corner vertices instead of rounded arc interpolations."""
    _ensure_db()
    cl = {
        "type": "LineString",
        "coordinates": [[-3.6000, 37.1800], [-3.5800, 37.1800], [-3.5800, 37.1700]],
    }
    resp = client.post(
        "/api/v1/planning/corridor",
        json=_req(centerline=cl, width_left=30, width_right=30),
    )
    assert resp.status_code == 200, resp.text
    d = resp.json()
    lines = d["geometry"]["flight_lines_geojson"]["features"]
    assert len(lines) >= 2
    for f in lines:
        assert len(f["geometry"]["coordinates"]) == 3  # start + corner + end, no arc points


def test_boustrophedon_return_line_reversed():
    """The return (odd) flight line must be flown from its far end back to its
    near end, so the drone turns at the corridor end instead of flying back
    over the first line."""
    _ensure_db()
    cl = {"type": "LineString", "coordinates": [[-3.6000, 37.1800], [-3.5600, 37.1800]]}
    base = {
        "centerline": cl,
        "width_left": 40, "width_right": 40,
        "altitude": 100,
        "overlap_frontal": 75, "overlap_lateral": 65,
        "camera_id": "cam-1-20mp",
    }
    for am in ("photo", "ground"):
        resp = client.post("/api/v1/planning/corridor", json={**base, "altitude_mode": am})
        assert resp.status_code == 200, resp.text
        d = resp.json()
        lines = d["geometry"]["flight_lines_geojson"]["features"]
        assert len(lines) >= 2
        l0end = lines[0]["geometry"]["coordinates"][-1]
        l1far = lines[1]["geometry"]["coordinates"][-1]
        wps = d["waypoints"]

        def near(p, q, tol=1e-4):
            return abs(p["longitude"] - q[0]) < tol and abs(p["latitude"] - q[1]) < tol

        idx = next(i for i, w in enumerate(wps) if near(w, l0end))
        assert near(wps[idx + 1], l1far), (
            f"{d['waypoint_mode']}: return line must start at its far end "
            f"(boustrophedon), got {wps[idx + 1]['longitude']},{wps[idx + 1]['latitude']}"
        )


def test_vertex_waypoints_kept_at_minimal_direction_change():
    """A waypoint must exist at every real vertex, even a tiny angle change."""
    fwd = Transformer.from_crs(CRS.from_epsg(4326), CRS.from_epsg(32630), always_xy=True)
    inv = Transformer.from_crs(CRS.from_epsg(32630), CRS.from_epsg(4326), always_xy=True)
    a = fwd.transform(-3.6000, 37.18000)
    b = fwd.transform(-3.5800, 37.18001)  # ~1 m lateral: minimal direction change
    c = fwd.transform(-3.5600, 37.18000)
    seg = LineString([a, b, c])
    wps = _vertex_waypoints([seg], 100.0, inv)
    lon, lat = inv.transform(b[0], b[1])
    assert any(abs(w.longitude - lon) < 1e-9 and abs(w.latitude - lat) < 1e-9 for w in wps)
    assert len(wps) == 3  # entry + vertex + exit, none simplified away


def test_vertex_waypoints_drop_only_collinear_points():
    """Truly collinear interior points (no direction change) are still dropped."""
    inv = Transformer.from_crs(CRS.from_epsg(32630), CRS.from_epsg(4326), always_xy=True)
    seg = LineString([(500000, 4100000), (501000, 4100000), (502000, 4100000)])
    wps = _vertex_waypoints([seg], 100.0, inv)
    assert len(wps) == 2


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
