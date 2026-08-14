import io
import json
import os
import sqlite3
import struct
import tempfile
import zipfile

from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app
from app.modules.corridor.parsers import load_centerline

client = TestClient(app)

LINKS = [[-3.60, 37.18], [-3.58, 37.18], [-3.56, 37.19]]


def build_geojson():
    return {"type": "LineString", "coordinates": LINKS}


def build_kml():
    cs = " ".join(f"{p[0]},{p[1]},0" for p in LINKS)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<kml xmlns='http://www.opengis.net/kml/2.2'>"
        "<Document><Placemark><name>route</name><LineString>"
        f"<coordinates>{cs}</coordinates>"
        "</LineString></Placemark></Document></kml>"
    )


def build_kmz():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("doc.kml", build_kml())
    return buf.getvalue()


def build_shapefile():
    import shapefile

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "route")
    w = shapefile.Writer(path, shapeType=3)
    w.field("name", "C")
    w.line([LINKS])
    w.record("r1")
    w.close()
    with open(path + ".shp", "rb") as f:
        data = f.read()
    for suffix in (".shp", ".shx", ".dbf"):
        try:
            os.remove(path + suffix)
        except OSError:
            pass
    return data


def build_geopackage():
    from shapely.geometry import LineString

    geom = LineString(LINKS)
    blob = bytes([0, 1]) + struct.pack("<I", 4326) + geom.wkb
    fd, path = tempfile.mkstemp(suffix=".gpkg")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE gpkg_spatial_ref_sys (srs_name TEXT, srs_id INTEGER PRIMARY KEY, "
        "organization TEXT, organization_coordsys_id INTEGER, definition TEXT, description TEXT)"
    )
    conn.execute(
        "INSERT INTO gpkg_spatial_ref_sys VALUES ('WGS 84',4326,'EPSG',4326,'','')"
    )
    conn.execute(
        "CREATE TABLE gpkg_contents (table_name TEXT PRIMARY KEY, data_type TEXT, identifier TEXT, "
        "description TEXT, last_change TEXT, min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER)"
    )
    conn.execute(
        "INSERT INTO gpkg_contents VALUES ('centerline','features','centerline','',"
        "'2024-01-01T00:00:00Z',-3.6,37.18,-3.56,37.19,4326)"
    )
    conn.execute(
        "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, "
        "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
    )
    conn.execute(
        "INSERT INTO gpkg_geometry_columns VALUES ('centerline','geom','LINESTRING',4326,0,0)"
    )
    conn.execute("CREATE TABLE centerline (id INTEGER PRIMARY KEY, geom BLOB)")
    conn.execute("INSERT INTO centerline (geom) VALUES (?)", (blob,))
    conn.commit()
    conn.close()
    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    return data


def _ensure_db():
    Base.metadata.create_all(bind=engine)
    from app.api.v1.endpoints import init_db

    init_db()


def _import(filename, data, overrides=None):
    fields = {
        "width_left": "100",
        "width_right": "60",
        "altitude": "100",
        "overlap_frontal": "75",
        "overlap_lateral": "65",
        "altitude_mode": "takeoff",
        "camera_id": "cam-1-20mp",
    }
    if overrides:
        fields.update(overrides)
    return client.post(
        "/api/v1/corridor/import",
        files={"file": (filename, data, "application/octet-stream")},
        data=fields,
    )


# --- parser unit tests -----------------------------------------------------


def test_parse_geojson():
    fmt, line, n, _ = load_centerline("a.geojson", json.dumps(build_geojson()).encode())
    assert fmt == "geojson"
    assert line == LINKS
    assert n == 1


def test_parse_kml_and_kmz():
    fmt, line, n, _ = load_centerline("a.kml", build_kml().encode())
    assert fmt == "kml" and line == LINKS and n == 1
    fmt2, line2, n2, _ = load_centerline("a.kmz", build_kmz())
    assert fmt2 == "kmz" and line2 == LINKS and n2 == 1


def test_parse_shapefile():
    fmt, line, n, _ = load_centerline("a.shp", build_shapefile())
    assert fmt == "shapefile"
    assert len(line) >= 2 and n == 1
    assert abs(line[0][0] - -3.60) < 1e-9


def test_parse_geopackage():
    fmt, line, n, _ = load_centerline("a.gpkg", build_geopackage())
    assert fmt == "geopackage"
    assert line[0] == LINKS[0]
    assert n == 1


def test_detect_magic():
    fmt, _, _, _ = load_centerline("route.dat", json.dumps(build_geojson()).encode())
    assert fmt == "geojson"


# --- API tests -------------------------------------------------------------


def test_import_all_formats():
    _ensure_db()
    cases = [
        ("route.geojson", json.dumps(build_geojson()).encode()),
        ("route.kml", build_kml().encode()),
        ("route.kmz", build_kmz()),
        ("route.shp", build_shapefile()),
        ("route.gpkg", build_geopackage()),
    ]
    for filename, data in cases:
        resp = _import(filename, data)
        assert resp.status_code == 200, f"{filename}: {resp.text[:300]}"
        body = resp.json()
        assert body["import_format"] in ("geojson", "kml", "kmz", "shapefile", "geopackage")
        assert len(body["waypoints"]) >= 2
        assert body["num_lines"] >= 1
        center = body["geometry"]["centerline_geojson"]
        assert center["type"] == "LineString"
        assert len(center["coordinates"]) >= 2


def test_import_generates_mission():
    _ensure_db()
    reg = client.post("/api/v1/auth/register", json={
        "full_name": "Imp Test", "email": "imp@test.dev",
        "password": "secret123", "country": "", "city": "",
        "phone": "", "gender": "", "profession": "",
    })
    if reg.status_code != 200:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "imp@test.dev", "password": "secret123"},
        ).json()
        token = login["access_token"]
    else:
        token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    pid = client.post("/api/v1/projects", json={"name": "Imp Project"}, headers=headers).json()["id"]

    resp = _import("route.geojson", json.dumps(build_geojson()).encode(), overrides={"project_id": pid})
    assert resp.status_code == 200
    assert resp.json()["mission_id"] is not None

    missions = client.get(f"/api/v1/projects/{pid}/missions", headers=headers).json()
    saved = missions[0]
    assert saved["mission_type"] == "linear_corridor"
    params = json.loads(saved["parameters_json"])
    assert params["width_left"] == 100 and params["width_right"] == 60


def test_import_invalid_file():
    _ensure_db()
    resp = _import("route.kml", b"this is not kml")
    assert resp.status_code == 400


def test_import_unsupported_format():
    _ensure_db()
    resp = _import("route.txt", b"hello world")
    assert resp.status_code == 400
    assert "Unsupported" in resp.json()["detail"]


def test_import_empty_file():
    _ensure_db()
    resp = _import("route.geojson", b"")
    assert resp.status_code == 400


# --- parse-only endpoint (no flight plan generated) ------------------------


def _parse(filename, data):
    return client.post(
        "/api/v1/corridor/parse",
        files={"file": (filename, data, "application/octet-stream")},
    )


def test_parse_returns_centerline_only():
    _ensure_db()
    resp = _parse("route.kmz", build_kmz())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["import_format"] == "kmz"
    assert body["centerline"]["type"] == "LineString"
    assert len(body["centerline"]["coordinates"]) >= 2
    assert "mission_id" not in body
    assert "waypoints" not in body


def test_parse_api_geopackage():
    _ensure_db()
    resp = _parse("route.gpkg", build_geopackage())
    assert resp.status_code == 200, resp.text
    assert resp.json()["import_format"] == "geopackage"


def test_parse_invalid_returns_400():
    _ensure_db()
    resp = _parse("route.kml", b"garbage")
    assert resp.status_code == 400
