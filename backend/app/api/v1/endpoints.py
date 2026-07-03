import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.core.database import get_db, engine, Base
from app.schemas.schemas import (
    ProjectCreate,
    ProjectResponse,
    MissionCreate,
    MissionUpdate,
    MissionResponse,
    DroneResponse,
    CameraResponse,
    GridRequest,
    GridResponse,
    GSDRequest,
    GSDResponse,
    RegisterRequest,
    LoginRequest,
    UserResponse,
    TokenResponse,
)
from app.models.schemas import Project, Mission, Drone, Camera, User
from app.core.seed_data import CAMERAS, DRONES
from app.modules.planning.engine import compute_grid, compute_gsd
from app.core.auth import hash_password, verify_password, create_access_token, get_current_user_id

router = APIRouter(prefix="/api/v1")


def init_db():
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    if db.query(Camera).count() == 0:
        db.add_all(CAMERAS)
        db.flush()
        db.add_all(DRONES)
        db.commit()
    db.close()


# ── Auth ────────────────────────────────────────────────────────────────────

@router.post("/auth/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(400, "Email already registered")
    user = User(
        full_name=req.full_name,
        email=req.email,
        hashed_password=hash_password(req.password),
        country=req.country,
        city=req.city,
        phone=req.phone,
        gender=req.gender,
        profession=req.profession,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": user.id})
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")
    token = create_access_token({"sub": user.id})
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/auth/me", response_model=UserResponse)
def get_me(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return user


# ── Projects ────────────────────────────────────────────────────────────────

@router.post("/projects", response_model=ProjectResponse)
def create_project(req: ProjectCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    proj = Project(**req.model_dump(), user_id=user_id)
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return db.query(Project).filter(Project.user_id == user_id).order_by(Project.created_at.desc()).all()


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == project_id, Project.user_id == user_id).first()
    if not proj:
        raise HTTPException(404, "Project not found")
    return proj


@router.put("/projects/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, req: ProjectCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == project_id, Project.user_id == user_id).first()
    if not proj:
        raise HTTPException(404, "Project not found")
    for key, val in req.model_dump().items():
        setattr(proj, key, val)
    db.commit()
    db.refresh(proj)
    return proj


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == project_id, Project.user_id == user_id).first()
    if not proj:
        raise HTTPException(404, "Project not found")
    db.query(Mission).filter(Mission.project_id == project_id).delete()
    db.delete(proj)
    db.commit()
    return {"ok": True}


# ── Missions ────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/missions", response_model=MissionResponse)
def create_mission(project_id: str, req: MissionCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == project_id, Project.user_id == user_id).first()
    if not proj:
        raise HTTPException(404, "Project not found")
    count = db.query(Mission).filter(Mission.project_id == project_id).count()
    if count >= 30:
        raise HTTPException(400, "Maximum 30 missions per project")
    mission = Mission(project_id=project_id, **req.model_dump())
    db.add(mission)
    db.commit()
    db.refresh(mission)
    return mission


@router.get("/projects/{project_id}/missions", response_model=list[MissionResponse])
def list_missions(project_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == project_id, Project.user_id == user_id).first()
    if not proj:
        raise HTTPException(404, "Project not found")
    return db.query(Mission).filter(Mission.project_id == project_id).order_by(Mission.created_at.desc()).all()


@router.get("/missions/{mission_id}", response_model=MissionResponse)
def get_mission(mission_id: str, db: Session = Depends(get_db)):
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        raise HTTPException(404, "Mission not found")
    return mission


@router.put("/missions/{mission_id}", response_model=MissionResponse)
def update_mission(mission_id: str, req: MissionUpdate, db: Session = Depends(get_db)):
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        raise HTTPException(404, "Mission not found")
    for key, val in req.model_dump(exclude_unset=True).items():
        if val is not None:
            setattr(mission, key, val)
    db.commit()
    db.refresh(mission)
    return mission


@router.delete("/missions/{mission_id}")
def delete_mission(mission_id: str, db: Session = Depends(get_db)):
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        raise HTTPException(404, "Mission not found")
    db.delete(mission)
    db.commit()
    return {"ok": True}


# ── Drones & Cameras ────────────────────────────────────────────────────────

@router.get("/drones", response_model=list[DroneResponse])
def list_drones(db: Session = Depends(get_db)):
    return db.query(Drone).all()


@router.get("/cameras", response_model=list[CameraResponse])
def list_cameras(db: Session = Depends(get_db)):
    return db.query(Camera).all()


# ── Planning ────────────────────────────────────────────────────────────────

@router.post("/planning/gsd", response_model=GSDResponse)
def calculate_gsd(req: GSDRequest, db: Session = Depends(get_db)):
    try:
        return compute_gsd(req, db)
    except ValueError as e:
        raise HTTPException(400, str(e))


def _resolve_camera_id(req: GridRequest | GSDRequest, db: Session) -> str:
    if req.camera_id:
        return req.camera_id
    if hasattr(req, 'drone_id') and req.drone_id:
        drone = db.query(Drone).filter(Drone.id == req.drone_id).first()
        if drone and drone.camera_id:
            return drone.camera_id
    raise ValueError("No camera_id provided and could not resolve from drone_id")


@router.post("/planning/grid", response_model=GridResponse)
def calculate_grid(req: GridRequest, db: Session = Depends(get_db)):
    try:
        req.camera_id = _resolve_camera_id(req, db)
        result = compute_grid(req, db)

        # Auto-create mission if project_id provided
        mission_id = None
        if req.project_id:
            proj = db.query(Project).filter(Project.id == req.project_id).first()
            if proj:
                count = db.query(Mission).filter(Mission.project_id == req.project_id).count()
                if count < 30:
                    mission = Mission(
                        project_id=req.project_id,
                        name=f"Mission {count + 1}",
                        mission_type="grid",
                        polygon_geojson=json.dumps(req.polygon),
                        waypoints_json=json.dumps([wp.model_dump() for wp in result.waypoints]),
                        parameters_json=json.dumps({
                            "altitude": req.altitude,
                            "overlap_frontal": req.overlap_frontal,
                            "overlap_lateral": req.overlap_lateral,
                            "drone_id": req.drone_id,
                            "camera_id": req.camera_id,
                            "altitude_mode": req.altitude_mode,
                        }),
                        grid_result_json=json.dumps(result.model_dump()),
                    )
                    db.add(mission)
                    db.commit()
                    db.refresh(mission)
                    mission_id = mission.id

        result.mission_id = mission_id
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Grid computation failed: {str(e)}")


# ── Export ──────────────────────────────────────────────────────────────────

from app.modules.export import (
    get_exporter, list_exporters,
    MissionExportData, ExportWaypoint, HomePoint, DroneInfo, CameraInfo, Action,
)
from app.schemas.schemas import ExportFormatItem, ExportRequest, MultiExportRequest


@router.get("/export/formats", response_model=list[ExportFormatItem])
def get_export_formats():
    return list_exporters()


# Legacy litchi endpoint (keep for backward compatibility)
@router.post("/export/litchi")
def export_litchi(data: dict):
    from app.modules.export.litchi import LitchiExporter
    exporter = LitchiExporter()
    from app.schemas.schemas import ExportWaypointSchema
    waypoints = [ExportWaypointSchema(**wp) for wp in data.get("waypoints", [])]
    export_wps = [
        ExportWaypoint(
            latitude=wp.latitude, longitude=wp.longitude,
            altitude=wp.altitude, heading=wp.heading,
            action_type=wp.action_type, action_param=wp.action_param,
        )
        for wp in waypoints
    ]
    mission = MissionExportData(
        project_name=data.get("filename", "mission").replace(".csv", ""),
        waypoints=export_wps,
        speed_ms=data.get("speed", 10),
        waypoint_mode="photo",
    )
    result = exporter.export(mission)
    csv = result.data if isinstance(result.data, str) else result.data.decode("utf-8")
    return {"csv": csv, "filename": result.filename}


@router.post("/export/multi")
def export_multi(req: MultiExportRequest):
    import io, zipfile
    from datetime import datetime

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fmt in req.formats:
            try:
                exporter = get_exporter(fmt)
            except ValueError:
                continue

            home = None
            if req.home_latitude is not None and req.home_longitude is not None:
                home = HomePoint(latitude=req.home_latitude, longitude=req.home_longitude)

            drone = DroneInfo(name=req.drone_name) if req.drone_name else None
            camera = CameraInfo(name=req.camera_name) if req.camera_name else None

            waypoints = [
                ExportWaypoint(
                    latitude=wp.latitude, longitude=wp.longitude,
                    altitude=wp.altitude, heading=wp.heading,
                    speed=wp.speed, curve_size=wp.curve_size,
                    gimbal_pitch=wp.gimbal_pitch,
                    action_type=wp.action_type, action_param=wp.action_param,
                )
                for wp in req.waypoints
            ]

            mission = MissionExportData(
                project_name=req.project_name,
                waypoints=waypoints, home=home, drone=drone, camera=camera,
                speed_ms=req.speed, altitude=req.altitude,
    altitude_mode=req.altitude_mode,
    waypoint_mode={"takeoff": "vertex", "ground": "terrain"}.get(req.altitude_mode, "photo"),
    total_distance_m=req.total_distance,
    estimated_time_s=req.estimated_time,
    photo_count=req.photo_count, area_ha=req.area_ha,
    gsd_cm=req.gsd, sweep_deg=req.sweep_deg,
    line_spacing=req.line_spacing, photo_spacing=req.photo_spacing,
    overlap_frontal=req.overlap_frontal,
    overlap_lateral=req.overlap_lateral,
    battery_count=req.battery_count,
)

            result = exporter.export(mission)
            data_bytes = result.data if isinstance(result.data, bytes) else result.data.encode("utf-8")
            zf.writestr(result.filename, data_bytes)

    zip_data = buf.getvalue()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return Response(
        content=zip_data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{req.project_name}_{ts}.zip"'},
    )


@router.post("/export/{fmt}")
def export_mission(fmt: str, req: ExportRequest):
    try:
        exporter = get_exporter(fmt)
    except ValueError as e:
        raise HTTPException(400, str(e))

    home = None
    if req.home_latitude is not None and req.home_longitude is not None:
        home = HomePoint(latitude=req.home_latitude, longitude=req.home_longitude)

    drone = DroneInfo(name=req.drone_name) if req.drone_name else None
    camera = CameraInfo(name=req.camera_name) if req.camera_name else None

    waypoints = [
        ExportWaypoint(
            latitude=wp.latitude,
            longitude=wp.longitude,
            altitude=wp.altitude,
            heading=wp.heading,
            speed=wp.speed,
            curve_size=wp.curve_size,
            gimbal_pitch=wp.gimbal_pitch,
            action_type=wp.action_type,
            action_param=wp.action_param,
        )
        for wp in req.waypoints
    ]

    mission = MissionExportData(
        project_name=req.project_name,
        waypoints=waypoints,
        home=home,
        drone=drone,
        camera=camera,
        speed_ms=req.speed,
        altitude=req.altitude,
        altitude_mode=req.altitude_mode,
        waypoint_mode={"takeoff": "vertex", "ground": "terrain"}.get(req.altitude_mode, "photo"),
        total_distance_m=req.total_distance,
        estimated_time_s=req.estimated_time,
        photo_count=req.photo_count,
        area_ha=req.area_ha,
        gsd_cm=req.gsd,
        sweep_deg=req.sweep_deg,
        line_spacing=req.line_spacing,
        photo_spacing=req.photo_spacing,
        overlap_frontal=req.overlap_frontal,
        overlap_lateral=req.overlap_lateral,
        battery_count=req.battery_count,
    )

    validation = exporter.validate(mission)
    if not validation.valid:
        raise HTTPException(400, {
            "error": "Validation failed",
            "details": [e.model_dump() for e in validation.errors],
        })

    result = exporter.export(mission)

    media_type = result.mime_type
    headers = {"Content-Disposition": f'attachment; filename="{result.filename}"'}

    if result.is_binary:
        return Response(content=result.data, media_type=media_type, headers=headers)
    else:
        data_str = result.data if isinstance(result.data, str) else result.data.decode("utf-8")
        return Response(content=data_str, media_type=media_type, headers=headers)
