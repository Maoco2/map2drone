import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.auth import create_access_token, get_current_user_id, hash_password, verify_password
from app.core.database import Base, engine, get_db
from app.core.seed_data import CAMERAS, DRONES
from app.models.schemas import Camera, Drone, Mission, Project, User
from app.modules.corridor import compute_corridor
from app.modules.corridor.parsers import load_centerline
from app.modules.export.adapters import from_universal_mission
from app.modules.export.readiness import check_mission_readiness
from app.modules.mission import UniversalMissionValidator, build_universal_mission, parse_mission_blob, to_legacy_dict
from app.modules.optimizer import Optimizer
from app.modules.optimizer import evaluate as optimizer_evaluate
from app.modules.optimizer.apply import WinnerMismatchError, apply_winner
from app.modules.optimizer.models import OptimizationConstraints, OptimizationWeights, OptimizerInput
from app.modules.optimizer.variables import (
    OptimizationVariable,
    OptimizationVariables,
    VariableMode,
)
from app.modules.planning.engine import compute_grid, compute_gsd
from app.modules.planning.turn_radius.integration import compute_turn_radius_plan
from app.schemas.schemas import (
    CameraResponse,
    CorridorImportResponse,
    CorridorParseResponse,
    CorridorRequest,
    CorridorResponse,
    DroneResponse,
    ExportCheckUmmRequest,
    ExportCheckUmmResponse,
    ExportUmmRequest,
    GridRequest,
    GridResponse,
    GSDRequest,
    GSDResponse,
    LoginRequest,
    MissionCreate,
    MissionResponse,
    MissionUpdate,
    MissionValidateRequest,
    MissionValidateResponse,
    OptimizerApplyRequest,
    OptimizerApplyResponse,
    OptimizerCandidateResponse,
    OptimizerEvaluateRequest,
    OptimizerEvaluateResponse,
    OptimizerSolveRequest,
    OptimizerSolveResponse,
    ProjectCreate,
    ProjectResponse,
    RegisterRequest,
    TokenResponse,
    TurnRadiusRequest,
    TurnRadiusResponse,
    UserResponse,
)

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
def update_project(
    project_id: str,
    req: ProjectCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
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
def create_mission(
    project_id: str,
    req: MissionCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
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
    if hasattr(req, "drone_id") and req.drone_id:
        drone = db.query(Drone).filter(Drone.id == req.drone_id).first()
        if drone and drone.camera_id:
            return drone.camera_id
    raise ValueError("No camera_id provided and could not resolve from drone_id")


def _umm_legacy_json(mission_type: str, req, result, db: Session) -> str:
    """Serialize a planning result into the legacy ``grid_result_json`` blob.

    Resolves the camera/drone profiles so the Universal Mission carries the
    platform profiles (Fase 10B); the legacy shape is preserved for backward
    compatibility.
    """
    camera = None
    if getattr(req, "camera_id", None):
        camera = db.query(Camera).filter(Camera.id == req.camera_id).first()
    drone = None
    if getattr(req, "drone_id", None):
        drone = db.query(Drone).filter(Drone.id == req.drone_id).first()
    mission = build_universal_mission(mission_type, req, result, camera=camera, drone=drone)
    return json.dumps(to_legacy_dict(mission))


def _attach_turn_radius(result, req: GridRequest | CorridorRequest) -> None:
    """Compute the turn-radius plan for a grid/corridor result and attach it.

    The engines already compute the plan (and feed it into the mission
    metrics) when ``req.turn_radius`` is configured; this is a backward
    compatibility guard for callers that bypass the engines.
    """
    if not getattr(req, "turn_radius", None):
        return
    if getattr(result, "turn_radius_result", None) is not None:
        return
    mission_type = "LINEAR_CORRIDOR" if isinstance(req, CorridorRequest) else "AREA_GRID"
    flight_lines_geojson = None
    if mission_type == "LINEAR_CORRIDOR" and getattr(result, "geometry", None):
        flight_lines_geojson = result.geometry.flight_lines_geojson
    plan, warnings = compute_turn_radius_plan(
        result.waypoints,
        req.turn_radius,
        mission_type=mission_type,
        line_spacing=float(getattr(result, "line_spacing", 0) or 0),
        recommended_speed=float(getattr(result, "recommended_speed_ms", 0) or 6.8),
        flight_lines_geojson=flight_lines_geojson,
    )
    if plan is not None:
        result.turn_radius_result = plan.model_dump(mode="json")
        result.turn_radius_warnings = warnings


@router.post("/planning/grid", response_model=GridResponse)
def calculate_grid(req: GridRequest, db: Session = Depends(get_db)):
    try:
        req.camera_id = _resolve_camera_id(req, db)
        result = compute_grid(req, db)
        _attach_turn_radius(result, req)

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
                        parameters_json=json.dumps(
                            {
                                "altitude": req.altitude,
                                "overlap_frontal": req.overlap_frontal,
                                "overlap_lateral": req.overlap_lateral,
                                "drone_id": req.drone_id,
                                "camera_id": req.camera_id,
                                "altitude_mode": req.altitude_mode,
                                "recommended_speed_ms": result.recommended_speed_ms,
                                "capture_interval_s": (
                                    result.capture_interval.recommended_interval_s if result.capture_interval else None
                                ),
                            }
                        ),
                        grid_result_json=_umm_legacy_json("grid", req, result, db),
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


def _auto_create_corridor_mission(db, req: CorridorRequest, result) -> Optional[str]:
    """Create a linear_corridor Mission when a project is provided."""
    mission_id = None
    if req.project_id:
        proj = db.query(Project).filter(Project.id == req.project_id).first()
        if proj:
            count = db.query(Mission).filter(Mission.project_id == req.project_id).count()
            if count < 30:
                mission = Mission(
                    project_id=req.project_id,
                    name=f"Mission {count + 1}",
                    mission_type="linear_corridor",
                    polygon_geojson=json.dumps(result.geometry.polygon_geojson),
                    waypoints_json=json.dumps([wp.model_dump() for wp in result.waypoints]),
                    parameters_json=json.dumps(
                        {
                            "altitude": req.altitude,
                            "overlap_frontal": req.overlap_frontal,
                            "overlap_lateral": req.overlap_lateral,
                            "drone_id": req.drone_id,
                            "camera_id": req.camera_id,
                            "altitude_mode": req.altitude_mode,
                            "width_left": req.width_left,
                            "width_right": req.width_right,
                            "recommended_speed_ms": result.recommended_speed_ms,
                            "capture_interval_s": (
                                result.capture_interval.recommended_interval_s if result.capture_interval else None
                            ),
                        }
                    ),
                    grid_result_json=_umm_legacy_json("linear_corridor", req, result, db),
                )
                db.add(mission)
                db.commit()
                db.refresh(mission)
                mission_id = mission.id
    return mission_id


@router.post("/planning/corridor", response_model=CorridorResponse)
def calculate_corridor(req: CorridorRequest, db: Session = Depends(get_db)):
    try:
        req.camera_id = _resolve_camera_id(req, db)
        result = compute_corridor(req, db)
        _attach_turn_radius(result, req)
        result.mission_id = _auto_create_corridor_mission(db, req, result)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Corridor computation failed: {str(e)}")


@router.post("/planning/turn-radius", response_model=TurnRadiusResponse)
def calculate_turn_radius(req: TurnRadiusRequest):
    """Recompute the turn-radius plan for an existing flight plan."""
    try:
        plan, warnings = compute_turn_radius_plan(
            req.waypoints,
            req.turn_radius,
            mission_type=req.mission_type or "AREA_GRID",
            line_spacing=req.line_spacing,
            recommended_speed=req.recommended_speed_ms or 6.8,
            flight_lines_geojson=req.flight_lines_geojson,
        )
        return TurnRadiusResponse(
            turn_radius_result=plan.model_dump(mode="json") if plan is not None else None,
            turn_radius_warnings=warnings,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Turn radius computation failed: {str(e)}")


# ── Universal Mission validation & optimizer (Fase 10B) ─────────────────────


@router.post("/missions/validate", response_model=MissionValidateResponse)
def validate_mission(req: MissionValidateRequest):
    """Validate a mission payload (Universal Mission or legacy) without mutating it."""
    try:
        mission = parse_mission_blob(req.payload)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"Invalid mission payload: {e}")
    result = UniversalMissionValidator().validate(mission)
    return MissionValidateResponse(
        valid=result.valid,
        status=result.status,
        errors=[e.model_dump(mode="json") for e in result.errors],
        warnings=[w.model_dump(mode="json") for w in result.warnings],
    )


@router.post("/optimizer/evaluate", response_model=OptimizerEvaluateResponse)
def optimizer_evaluate_endpoint(req: OptimizerEvaluateRequest):
    """Evaluate a single mission/candidate (no automatic search — that is Fase 10C)."""
    try:
        mission = parse_mission_blob(req.mission)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"Invalid mission payload: {e}")
    constraints = OptimizationConstraints(**req.constraints) if req.constraints else None
    weights = OptimizationWeights(**req.weights) if req.weights else None
    result = optimizer_evaluate(mission, constraints=constraints, weights=weights)
    return OptimizerEvaluateResponse(
        valid=result.valid,
        status=result.status,
        metrics=result.metrics,
        score=result.score.model_dump(mode="json") if result.score else None,
        warnings=result.warnings,
        validation=result.validation,
    )


# ── Optimizer solve (Fase 10C-10) ────────────────────────────────────────────


def _build_base_mission(req: GridRequest | CorridorRequest, db: Session):
    """Build the base Universal Mission from a planning request (profile-aware)."""
    mission_type = "linear_corridor" if isinstance(req, CorridorRequest) else "grid"
    req.camera_id = _resolve_camera_id(req, db)
    result = compute_corridor(req, db) if mission_type == "linear_corridor" else compute_grid(req, db)
    camera = db.query(Camera).filter(Camera.id == req.camera_id).first() if req.camera_id else None
    drone = db.query(Drone).filter(Drone.id == req.drone_id).first() if req.drone_id else None
    return build_universal_mission(mission_type, req, result, camera=camera, drone=drone)


def _optimizer_variables(vars_req):
    """Map the API variable declarations onto the optimizer contract (validated)."""
    if vars_req is None or not vars_req.variables:
        return None
    return OptimizationVariables(
        variables=[
            OptimizationVariable(
                name=d.name,
                mode=VariableMode(d.mode),
                value=d.value,
                min_value=d.min_value,
                max_value=d.max_value,
                step=d.step,
                values=d.values,
            )
            for d in vars_req.variables
        ]
    )


def _solve_response(result) -> OptimizerSolveResponse:
    """Map an OptimizationResult onto the API response shape."""
    by_values = {json.dumps(e.variable_values, sort_keys=True): e for e in result.evaluations}

    def _candidate(cand) -> Optional[OptimizerCandidateResponse]:
        if cand is None:
            return None
        ev = by_values.get(json.dumps(cand.variable_values, sort_keys=True))
        return OptimizerCandidateResponse(
            label=cand.label,
            variable_values=cand.variable_values,
            mission=cand.mission.model_dump(mode="json"),
            score=ev.score.model_dump(mode="json") if ev is not None and ev.score else None,
        )

    return OptimizerSolveResponse(
        status=result.status,
        message=result.message,
        best_candidate=_candidate(result.best_candidate),
        best_score=result.best_score.model_dump(mode="json") if result.best_score else None,
        alternatives=[_candidate(a) for a in result.alternatives],
        stats=result.explanation.stats if result.explanation else {},
        warnings=result.explanation.warnings if result.explanation else [],
        explanation=result.explanation.model_dump(mode="json") if result.explanation else None,
    )


@router.post("/optimizer/solve", response_model=OptimizerSolveResponse)
def optimizer_solve_endpoint(req: OptimizerSolveRequest, db: Session = Depends(get_db)):
    """Deterministic optimization search (Fase 10C-10)."""
    try:
        base_req = req.grid if req.grid is not None else req.corridor
        mission = _build_base_mission(base_req, db)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Planning failed: {str(e)}")

    try:
        variables = _optimizer_variables(req.variables)
        constraints = OptimizationConstraints(**req.constraints) if req.constraints else None
        weights = OptimizationWeights(**req.weights) if req.weights else None
    except (ValueError, ValidationError) as e:
        raise HTTPException(400, f"Invalid optimizer input: {e}")

    inp = OptimizerInput(
        mission=mission,
        request=base_req,
        constraints=constraints,
        weights=weights,
        variables=variables,
        max_candidates=req.max_candidates,
    )
    try:
        result = Optimizer().solve(inp, db_session=db)
    except Exception as e:
        raise HTTPException(500, f"Optimization failed: {str(e)}")
    return _solve_response(result)


# ── Optimizer apply (Fase 10F-1/2) ───────────────────────────────────────────


@router.post("/optimizer/apply", response_model=OptimizerApplyResponse)
def optimizer_apply_endpoint(req: OptimizerApplyRequest, db: Session = Depends(get_db)):
    """Apply the winner of a previous ``/optimizer/solve`` run to the UMM.

    Backend-authoritative: re-derives the baseline from the original request,
    verifies the winner is reproducible and persists it as a new mission.
    """
    try:
        constraints = (
            OptimizationConstraints(**req.solve_request.constraints) if req.solve_request.constraints else None
        )
        weights = OptimizationWeights(**req.solve_request.weights) if req.solve_request.weights else None
        result = apply_winner(
            req.solve_request,
            req.winner,
            req.winner_variable_values,
            constraints,
            weights,
            db,
            project_id=req.project_id,
            original_mission_id=req.original_mission_id,
            name=req.name,
        )
    except WinnerMismatchError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(400, f"Invalid apply request: {e}")
    except Exception as e:
        raise HTTPException(500, f"Apply failed: {str(e)}")
    return OptimizerApplyResponse(
        applied=True,
        mission_id=result.mission_id,
        baseline_mission=to_legacy_dict(result.baseline_mission),
        baseline_score=result.baseline_score.model_dump(mode="json") if result.baseline_score else None,
        winner_mission=to_legacy_dict(result.applied_winner),
        winner_score=result.winner_score.model_dump(mode="json") if result.winner_score else None,
        comparison=result.comparison,
        modified_variables=result.modified,
        verification=result.verification,
        warnings=result.warnings,
    )


@router.post("/corridor/parse", response_model=CorridorParseResponse)
async def parse_corridor_file(file: UploadFile = File(...)):
    """Parse a centerline file (KMZ/KML/GeoPackage/GeoJSON/Shapefile) without computing a flight plan."""
    data = await file.read()
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 50 MB)")
    if not data:
        raise HTTPException(400, "Empty file")
    try:
        fmt, centerline, features_found, warnings = load_centerline(file.filename or "", data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return CorridorParseResponse(
        centerline={"type": "LineString", "coordinates": centerline},
        import_format=fmt,
        import_source=file.filename or "",
        features_found=features_found,
        warnings=warnings,
    )


@router.post("/corridor/import", response_model=CorridorImportResponse)
async def import_corridor(
    file: UploadFile = File(...),
    width_left: float = Form(100),
    width_right: float = Form(100),
    altitude: float = Form(100),
    overlap_frontal: float = Form(75),
    overlap_lateral: float = Form(65),
    altitude_mode: str = Form("takeoff"),
    camera_id: str = Form(""),
    drone_id: str = Form(""),
    project_id: str = Form(""),
    db: Session = Depends(get_db),
):
    data = await file.read()
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 50 MB)")
    if not data:
        raise HTTPException(400, "Empty file")

    try:
        fmt, centerline, features_found, warnings = load_centerline(file.filename or "", data)
    except ValueError as e:
        raise HTTPException(400, str(e))

    req = CorridorRequest(
        centerline={"type": "LineString", "coordinates": centerline},
        width_left=width_left,
        width_right=width_right,
        altitude=altitude,
        overlap_frontal=overlap_frontal,
        overlap_lateral=overlap_lateral,
        camera_id=camera_id or None,
        drone_id=drone_id or None,
        project_id=project_id or None,
        altitude_mode=altitude_mode,
    )
    try:
        req.camera_id = _resolve_camera_id(req, db)
        result = compute_corridor(req, db)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Corridor computation failed: {str(e)}")

    result.mission_id = _auto_create_corridor_mission(db, req, result)
    merged_warnings = list(result.warnings) + list(warnings)
    payload = result.model_dump()
    payload["warnings"] = merged_warnings
    return CorridorImportResponse(
        **payload,
        import_format=fmt,
        import_source=file.filename or "",
        features_found=features_found,
    )


# ── Export ──────────────────────────────────────────────────────────────────

from app.modules.export import (  # noqa: E402
    CameraInfo,
    DroneInfo,
    ExportWaypoint,
    HomePoint,
    MissionExportData,
    get_exporter,
    list_exporters,
)
from app.modules.planning.turn_radius.integration import apply_turn_radii  # noqa: E402
from app.schemas.schemas import ExportFormatCheckItem, ExportFormatItem, ExportRequest, MultiExportRequest  # noqa: E402


def _build_mission(req: ExportRequest | MultiExportRequest) -> MissionExportData:
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
            elevation_msnm=wp.elevation_msnm,
            agl=wp.agl,
        )
        for wp in req.waypoints
    ]

    options = dict(req.options or {})
    if options.get("turn_radius"):
        waypoints, turn_plan, turn_warnings = apply_turn_radii(
            waypoints,
            options,
            default_speed=req.speed if req.speed else 6.8,
        )
        if turn_plan is not None:
            options["turn_radius_result"] = turn_plan.model_dump(mode="json")
            if turn_warnings:
                options["turn_radius_warnings"] = turn_warnings

    return MissionExportData(
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
        capture_interval_s=req.capture_interval_s,
        options=options,
    )


@router.get("/export/formats", response_model=list[ExportFormatItem])
def get_export_formats():
    return list_exporters()


@router.post("/export/check", response_model=list[ExportFormatCheckItem])
def check_export_formats(req: MultiExportRequest):
    mission = _build_mission(req)
    results = []
    for fmt in req.formats:
        try:
            exporter = get_exporter(fmt)
        except ValueError:
            continue
        results.append(
            {
                "id": fmt,
                "name": exporter.name,
                "extension": exporter.extension,
                "compatibility": (
                    exporter.compatibility.model_dump(mode="json") if exporter.compatibility is not None else None
                ),
                "warnings": [w.model_dump(mode="json") for w in exporter.get_warnings(mission)],
            }
        )
    return results


@router.post("/export/multi")
def export_multi(req: MultiExportRequest):
    import io
    import zipfile
    from datetime import datetime

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fmt in req.formats:
            try:
                exporter = get_exporter(fmt)
            except ValueError:
                continue

            mission = _build_mission(req)

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


# ── UMM export / readiness (Fase 10F-5/8) ────────────────────────────────────
# Registered BEFORE /export/{fmt} so the specific paths win the match.


def _export_response_for(result) -> Response:
    media_type = result.mime_type
    headers = {"Content-Disposition": f'attachment; filename="{result.filename}"'}
    if result.is_binary:
        return Response(content=result.data, media_type=media_type, headers=headers)
    data_str = result.data if isinstance(result.data, str) else result.data.decode("utf-8")
    return Response(content=data_str, media_type=media_type, headers=headers)


@router.post("/export/umm/{fmt}")
def export_umm(fmt: str, req: ExportUmmRequest):
    """Export a Universal Mission directly (no legacy rebuild — Fase 10F-5/12).

    The mission is transformed through ``from_universal_mission`` and serialized
    by the real exporter, so the resulting file represents exactly the evaluated
    winner. Optional ``options`` override exporter options (e.g. LCHM
    ``path_mode``); every value is otherwise read from the mission.
    """
    try:
        mission = parse_mission_blob(req.mission)
        exporter = get_exporter(fmt)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"Invalid export request: {e}")

    export_data = from_universal_mission(mission)
    if req.options:
        merged = dict(export_data.options or {})
        merged.update(req.options)
        export_data.options = merged

    validation = exporter.validate(export_data)
    if not validation.valid:
        raise HTTPException(
            400,
            {
                "error": "Validation failed",
                "details": [e.model_dump() for e in validation.errors],
            },
        )
    try:
        result = exporter.export(export_data)
    except Exception as e:
        raise HTTPException(400, f"Export failed: {e}")
    return _export_response_for(result)


@router.post("/export/check-umm", response_model=ExportCheckUmmResponse)
def check_export_umm(req: ExportCheckUmmRequest):
    """Export readiness diagnostic for a Universal Mission (Fase 10F-8)."""
    try:
        mission = parse_mission_blob(req.mission)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"Invalid mission payload: {e}")
    items = []
    for fmt in req.formats:
        try:
            items.append(check_mission_readiness(mission, fmt))
        except ValueError:
            continue
    return ExportCheckUmmResponse(items=items)


@router.post("/export/{fmt}")
def export_mission(fmt: str, req: ExportRequest):
    try:
        exporter = get_exporter(fmt)
    except ValueError as e:
        raise HTTPException(400, str(e))

    mission = _build_mission(req)

    validation = exporter.validate(mission)
    if not validation.valid:
        raise HTTPException(
            400,
            {
                "error": "Validation failed",
                "details": [e.model_dump() for e in validation.errors],
            },
        )

    result = exporter.export(mission)

    media_type = result.mime_type
    headers = {"Content-Disposition": f'attachment; filename="{result.filename}"'}

    if result.is_binary:
        return Response(content=result.data, media_type=media_type, headers=headers)
    else:
        data_str = result.data if isinstance(result.data, str) else result.data.decode("utf-8")
        return Response(content=data_str, media_type=media_type, headers=headers)
