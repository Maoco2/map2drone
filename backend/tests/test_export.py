from fastapi.testclient import TestClient
from app.main import app
from app.modules.export import (
    MissionExportData, ExportWaypoint, HomePoint, DroneInfo, CameraInfo,
    get_exporter, list_exporters,
)

client = TestClient(app)

SAMPLE_WPS = [
    {"latitude": 37.18, "longitude": -3.60, "altitude": 100, "heading": 0},
    {"latitude": 37.19, "longitude": -3.59, "altitude": 120, "heading": 90},
    {"latitude": 37.20, "longitude": -3.58, "altitude": 110, "heading": 180},
]


def test_list_formats():
    resp = client.get("/api/v1/export/formats")
    assert resp.status_code == 200
    fmts = resp.json()
    assert len(fmts) >= 10
    ids = [f["id"] for f in fmts]
    for expected in ["litchi", "dji_wpml", "dji_kmz", "qgc", "mission_planner",
                     "mavlink", "kml", "kmz", "geojson", "gpx"]:
        assert expected in ids


def test_get_exporter_all():
    fmts = list_exporters()
    for fmt in fmts:
        exporter = get_exporter(fmt["id"])
        assert exporter is not None
        assert exporter.name


def test_get_exporter_unknown():
    try:
        get_exporter("nonexistent")
        assert False, "expected ValueError"
    except ValueError:
        pass


def _mission(**kw):
    wps = [ExportWaypoint(**wp) for wp in SAMPLE_WPS]
    return MissionExportData(waypoints=wps, **kw)


def test_export_litchi():
    exporter = get_exporter("litchi")
    m = _mission()
    result = exporter.export(m)
    assert result.filename.endswith(".csv")
    lines = result.data.strip().split("\n")
    assert len(lines) == 4


def test_export_dji_wpml():
    exporter = get_exporter("dji_wpml")
    m = _mission(home=HomePoint(latitude=37.17, longitude=-3.61))
    result = exporter.export(m)
    assert result.filename.endswith(".wpml")
    data = result.data.decode() if isinstance(result.data, bytes) else result.data
    assert '<?xml' in data or '<kml' in data


def test_export_dji_kmz():
    exporter = get_exporter("dji_kmz")
    m = _mission(home=HomePoint(latitude=37.17, longitude=-3.61))
    result = exporter.export(m)
    assert result.filename.endswith(".kmz")
    import zipfile, io
    z = zipfile.ZipFile(io.BytesIO(result.data))
    names = z.namelist()
    assert "mission.wpml" in names
    assert "waylines.wpml" in names
    assert "manifest.xml" in names


def test_export_qgc():
    exporter = get_exporter("qgc")
    m = _mission(home=HomePoint(latitude=37.17, longitude=-3.61))
    result = exporter.export(m)
    assert result.filename.endswith(".plan")
    import json
    data = json.loads(result.data)
    assert "mission" in data
    assert "plannedHomePosition" in data["mission"]


def test_export_mission_planner():
    exporter = get_exporter("mission_planner")
    m = _mission(home=HomePoint(latitude=37.17, longitude=-3.61))
    result = exporter.export(m)
    assert result.filename.endswith(".waypoints")
    assert "QGC WPL 110" in result.data


def test_export_mavlink():
    exporter = get_exporter("mavlink")
    m = _mission(home=HomePoint(latitude=37.17, longitude=-3.61))
    result = exporter.export(m)
    assert result.filename.endswith(".json")
    import json
    data = result.data.decode() if isinstance(result.data, bytes) else result.data
    obj = json.loads(data)
    assert "mission" in obj


def test_export_mavlink_binary():
    exporter = get_exporter("mavlink_binary")
    m = _mission(home=HomePoint(latitude=37.17, longitude=-3.61))
    result = exporter.export(m)
    assert result.filename.endswith(".bin")
    assert result.is_binary


def test_export_kml():
    exporter = get_exporter("kml")
    m = _mission()
    result = exporter.export(m)
    assert result.filename.endswith(".kml")
    data = result.data.decode() if isinstance(result.data, bytes) else result.data
    assert '<kml' in data


def test_export_kmz():
    exporter = get_exporter("kmz")
    m = _mission()
    result = exporter.export(m)
    assert result.filename.endswith(".kmz")
    import zipfile, io
    z = zipfile.ZipFile(io.BytesIO(result.data))
    names = z.namelist()
    assert "doc.kml" in names


def test_export_geojson():
    import json
    exporter = get_exporter("geojson")
    m = _mission()
    result = exporter.export(m)
    assert result.filename.endswith(".geojson")
    data = result.data.decode() if isinstance(result.data, bytes) else result.data
    obj = json.loads(data)
    assert obj["type"] == "FeatureCollection"


def test_export_gpx():
    exporter = get_exporter("gpx")
    m = _mission()
    result = exporter.export(m)
    assert result.filename.endswith(".gpx")
    data = result.data.decode() if isinstance(result.data, bytes) else result.data
    assert '<gpx' in data


# --- API endpoint tests ---

def test_api_export_legacy_litchi():
    resp = client.post("/api/v1/export/litchi", json={
        "filename": "Test",
        "waypoints": SAMPLE_WPS,
        "speed": 10,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "csv" in data
    assert "filename" in data
    lines = data["csv"].strip().split("\n")
    assert len(lines) == 4


def test_api_export_unified():
    for fmt in ["litchi", "dji_wpml", "qgc", "mission_planner", "kml", "geojson", "gpx"]:
        resp = client.post(f"/api/v1/export/{fmt}", json={
            "project_name": "Test",
            "waypoints": SAMPLE_WPS,
            "speed": 10, "altitude": 100,
            "home_latitude": 37.17, "home_longitude": -3.61,
        })
        assert resp.status_code == 200, f"{fmt} failed: {resp.text[:200]}"


def test_api_multi_export():
    resp = client.post("/api/v1/export/multi", json={
        "formats": ["litchi", "kml", "geojson", "gpx"],
        "project_name": "MultiTest",
        "waypoints": SAMPLE_WPS,
        "speed": 10, "altitude": 100,
    })
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    import zipfile, io
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    assert len(z.namelist()) == 4


def test_api_export_unknown_format():
    resp = client.post("/api/v1/export/nonexistent", json={
        "project_name": "Test",
        "waypoints": SAMPLE_WPS,
    })
    assert resp.status_code == 400


def test_api_export_validation_failure():
    # Empty waypoints -> Litchi CSV returns header-only
    resp = client.post("/api/v1/export/litchi", json={
        "project_name": "Test",
        "waypoints": [],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "latitude" in data["csv"]
