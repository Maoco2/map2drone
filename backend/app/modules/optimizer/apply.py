"""Optimizer — apply the winner to the Universal Mission (Fase 10F).

Applying a winner is a backend responsibility. The endpoint never rebuilds the
candidate on the frontend: it receives the winner already produced by
``/optimizer/solve`` (the exact mission the search evaluated), re-derives the
baseline from the original planning request, evaluates both with the same
scoring pipeline, builds the Baseline vs Winner comparison, verifies that the
winner is reproducible (deterministic rebuild) and persists the winner as a new
mission (the original mission row is never touched).

No formula is computed here: the baseline and the rebuilt winner come from the
existing engines through :class:`CandidateBuilder`, and both scores come from
the same :func:`evaluate` pipeline the optimizer used during the search.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from app.models.schemas import Camera, Drone, Mission, Project
from app.modules.corridor.engine import compute_corridor
from app.modules.mission.builder import build_universal_mission, to_legacy_dict
from app.modules.mission.validation import parse_mission_blob
from app.modules.optimizer.candidate_builder import CandidateBuilder
from app.modules.optimizer.evaluator import evaluate
from app.modules.optimizer.models import OptimizationConstraints, OptimizationWeights
from app.modules.planning.engine import compute_grid
from app.schemas.schemas import CorridorRequest, MissionComparisonItem, OptimizerSolveRequest


class WinnerMismatchError(Exception):
    """The submitted winner cannot be reproduced deterministically from the solve request."""


class ApplyResult:
    """Backend result of an apply operation (mapped to the API schema)."""

    def __init__(
        self,
        baseline_mission,
        baseline_score,
        applied_winner,
        winner_score,
        comparison,
        modified,
        verification,
        warnings,
        mission_id=None,
    ) -> None:
        self.baseline_mission = baseline_mission
        self.baseline_score = baseline_score
        self.applied_winner = applied_winner
        self.winner_score = winner_score
        self.comparison = comparison
        self.modified = modified
        self.verification = verification
        self.warnings = warnings
        self.mission_id = mission_id


# ── Baseline ─────────────────────────────────────────────────────────────────


def build_base_mission(base_req, db_session):
    """Build the original (baseline) Universal Mission from a planning request.

    Mirrors the planning endpoints: resolves the camera from the drone when
    needed, runs the engine and attaches the DB profiles. The request is
    expected to be an already-deep-copied request owned by this module.
    """
    mission_type = "linear_corridor" if isinstance(base_req, CorridorRequest) else "grid"
    if not getattr(base_req, "camera_id", None):
        camera_id = _resolve_camera_id(base_req, db_session)
        if camera_id is not None:
            base_req.camera_id = camera_id
    if mission_type == "linear_corridor":
        result = compute_corridor(base_req, db_session)
    else:
        result = compute_grid(base_req, db_session)
    camera = (
        db_session.query(Camera).filter(Camera.id == base_req.camera_id).first()
        if getattr(base_req, "camera_id", None)
        else None
    )
    drone = (
        db_session.query(Drone).filter(Drone.id == base_req.drone_id).first()
        if getattr(base_req, "drone_id", None)
        else None
    )
    return build_universal_mission(mission_type, base_req, result, camera=camera, drone=drone)


def _resolve_camera_id(req, db_session) -> Optional[str]:
    if getattr(req, "camera_id", None):
        return req.camera_id
    if getattr(req, "drone_id", None):
        drone = db_session.query(Drone).filter(Drone.id == req.drone_id).first()
        if drone is not None and drone.camera_id:
            return drone.camera_id
    return None


# ── Winner verification (gate: evaluated winner == applied winner) ──────────


def _canonical(mission) -> dict:
    """Deterministic signature of the mission for reproducibility checks."""
    m = mission.metrics
    p = mission.parameters
    cp = mission.capture_plan
    tp = mission.turn_plan
    sci = None if cp is None or cp.scientific_interval_s is None else round(cp.scientific_interval_s, 6)
    comm = None if cp is None or cp.commercial_interval_s is None else int(cp.commercial_interval_s)
    radius = p.turn_radius_m
    if tp is not None and tp.radius_m is not None:
        radius = round(tp.radius_m, 6)
    return {
        "mission_type": mission.mission_type,
        "altitude_m": round(p.altitude_m, 6),
        "overlap_frontal": round(p.overlap_frontal, 6),
        "overlap_lateral": round(p.overlap_lateral, 6),
        "speed_ms": round(p.speed_ms, 6),
        "scientific_interval_s": sci,
        "commercial_interval_s": comm,
        "total_distance_m": round(m.total_distance_m, 6),
        "estimated_time_sec": round(m.estimated_time_sec, 6),
        "battery_count": int(m.battery_count),
        "gsd_cm": round(m.gsd_cm, 6),
        "photo_count": int(m.photo_count),
        "waypoint_count": int(m.waypoint_count),
        "line_count": int(m.line_count),
        "turn_radius_m": radius,
        "turn_count": int(tp.turn_count) if tp is not None else 0,
        "turn_status": tp.status if tp is not None else "NONE",
        "waypoints": [
            (
                round(w.latitude or 0.0, 8),
                round(w.longitude or 0.0, 8),
                round(w.altitude_m or 0.0, 6),
                round(w.heading_deg or 0.0, 6),
                round(w.speed_mps or 0.0, 6),
                round(w.curve_size_m or 0.0, 6),
            )
            for w in mission.waypoints
        ],
    }


def _verify_winner(builder, winner_mission, variable_values: dict) -> tuple[Any, dict]:
    """Deterministically rebuild the winner and compare it with the submitted one.

    Returns ``(applied_mission, verification)``. When the submitted payload
    matches the rebuild, the rebuilt mission is used as the applied winner (it
    is, structurally, the mission the search evaluated).
    """
    if not variable_values:
        return winner_mission, {
            "verified": True,
            "method": "passthrough",
            "rebuilt": False,
            "matches": True,
            "reason": (
                "No variable_values submitted (single-candidate path); the evaluated mission is applied as received."
            ),
        }
    rebuilt = builder.build(variable_values)
    matches = _canonical(rebuilt) == _canonical(winner_mission)
    if not matches:
        raise WinnerMismatchError(
            "The submitted winner does not match the deterministic rebuild from the solve request "
            "(candidate_builder). Apply refused to guarantee that the exported file represents the evaluated winner."
        )
    return rebuilt, {"verified": True, "method": "candidate_builder", "rebuilt": True, "matches": True}


# ── Baseline vs Winner comparison ────────────────────────────────────────────


def _interval_s(mission) -> Optional[float]:
    cp = mission.capture_plan
    if cp is None:
        return mission.parameters.capture_interval_s
    return cp.commercial_interval_s if cp.commercial_interval_s is not None else cp.scientific_interval_s


def _photo_spacing_m(mission) -> Optional[float]:
    cp = mission.capture_plan
    if cp is not None and cp.photo_spacing_m is not None:
        return cp.photo_spacing_m
    return mission.metrics.photo_spacing_m or None


def _turn_count(mission) -> Optional[int]:
    tp = mission.turn_plan
    return tp.turn_count if tp is not None else 0


def _turn_radius_m(mission) -> Optional[float]:
    tp = mission.turn_plan
    if tp is not None and tp.radius_m is not None:
        return tp.radius_m
    return mission.parameters.turn_radius_m


def _score_total(score) -> Optional[float]:
    return score.total_score if score is not None else None


def _comparison_rows(baseline, winner, baseline_score, winner_score) -> list[MissionComparisonItem]:
    rows: list[MissionComparisonItem] = []
    bp, wp = baseline.parameters, winner.parameters
    bm, wm = baseline.metrics, winner.metrics

    def add(metric: str, label: str, b, w, unit: str = "") -> None:
        b = None if b is None else round(float(b), 4)
        w = None if w is None else round(float(w), 4)
        delta = None if (b is None or w is None) else round(w - b, 4)
        rows.append(MissionComparisonItem(metric=metric, label=label, baseline=b, winner=w, delta=delta, unit=unit))

    add("altitude_m", "Altitude", bp.altitude_m, wp.altitude_m, "m")
    add("gsd_cm", "GSD", bm.gsd_cm, wm.gsd_cm, "cm/px")
    add("overlap_front", "Front overlap", bp.overlap_frontal, wp.overlap_frontal, "%")
    add("overlap_side", "Side overlap", bp.overlap_lateral, wp.overlap_lateral, "%")
    add("speed_mps", "Speed", bp.speed_ms, wp.speed_ms, "m/s")
    add("capture_interval_s", "Capture interval", _interval_s(baseline), _interval_s(winner), "s")
    add("photo_spacing_m", "Photo spacing", _photo_spacing_m(baseline), _photo_spacing_m(winner), "m")
    add("photo_count", "Photos", bm.photo_count, wm.photo_count, "")
    add("total_distance_m", "Distance", bm.total_distance_m, wm.total_distance_m, "m")
    add("estimated_time_s", "Time", bm.estimated_time_sec, wm.estimated_time_sec, "s")
    add("turn_count", "Turns", _turn_count(baseline), _turn_count(winner), "")
    add("turn_radius_m", "Turn radius", _turn_radius_m(baseline), _turn_radius_m(winner), "m")
    add("battery_count", "Batteries", bm.battery_count, wm.battery_count, "")
    add("total_score", "Score", _score_total(baseline_score), _score_total(winner_score), "")
    return rows


def _baseline_value_for_variable(name: str, mission) -> Optional[float]:
    p = mission.parameters
    if name == "altitude_m":
        return p.altitude_m
    if name == "speed_mps":
        return p.speed_ms
    if name == "front_overlap":
        return p.overlap_frontal
    if name == "side_overlap":
        return p.overlap_lateral
    if name == "photo_interval_s":
        return _interval_s(mission)
    if name == "turn_radius_m":
        return _turn_radius_m(mission)
    return None


def _modified_variables(winner_values: dict, baseline) -> list[str]:
    modified: list[str] = []
    for name, value in (winner_values or {}).items():
        base = _baseline_value_for_variable(name, baseline)
        if base is None:
            modified.append(name)
        elif abs(float(value) - float(base)) > 1e-9:
            modified.append(name)
    return modified


# ── Persistence ──────────────────────────────────────────────────────────────


def _legacy_waypoint(wp) -> dict:
    return {
        "latitude": wp.latitude,
        "longitude": wp.longitude,
        "altitude": wp.altitude_m,
        "heading": wp.heading_deg if wp.heading_deg is not None else 0,
        "speed": wp.speed_mps,
        "action_type": wp.action_type if wp.action_type is not None else -1,
        "action_param": wp.action if wp.action is not None else 0,
        "elevation_msnm": wp.terrain_elevation_m,
        "agl": wp.agl_m,
    }


def _polygon_geojson(base_req, winner) -> Optional[str]:
    if winner.mission_type == "linear_corridor":
        if winner.geometry is not None and winner.geometry.polygon_geojson:
            return json.dumps(winner.geometry.polygon_geojson)
        return None
    polygon = getattr(base_req, "polygon", None)
    return json.dumps(polygon) if polygon is not None else None


def persist_winner(
    db_session,
    project_id: str,
    name: Optional[str],
    base_req,
    baseline,
    applied_winner,
    comparison,
    modified,
    verification,
    baseline_score,
    winner_score,
    original_mission_id: Optional[str],
) -> Optional[str]:
    """Persist the winner as a new mission; the original mission is untouched.

    The baseline and the comparison are stored inside the winner mission's
    ``parameters_json`` blob (under ``optimizer_apply``); ``grid_result_json``
    carries the full winner Universal Mission (legacy-compatible).
    """
    proj = db_session.query(Project).filter(Project.id == project_id).first()
    if proj is None:
        return None
    count = db_session.query(Mission).filter(Mission.project_id == project_id).count()
    if count >= 30:
        return None

    winner_name = name or (applied_winner.name or "Mission")
    if not name and applied_winner.name is None:
        winner_name = f"{winner_name} (optimized)"

    mission = Mission(
        project_id=project_id,
        name=winner_name,
        mission_type=applied_winner.mission_type,
        polygon_geojson=_polygon_geojson(base_req, applied_winner) or "",
        waypoints_json=json.dumps([_legacy_waypoint(wp) for wp in applied_winner.waypoints]),
        parameters_json=json.dumps(
            {
                "altitude": applied_winner.parameters.altitude_m,
                "overlap_frontal": applied_winner.parameters.overlap_frontal,
                "overlap_lateral": applied_winner.parameters.overlap_lateral,
                "drone_id": applied_winner.parameters.drone_id,
                "camera_id": applied_winner.parameters.camera_id,
                "altitude_mode": applied_winner.parameters.altitude_mode,
                "recommended_speed_ms": applied_winner.parameters.speed_ms,
                "capture_interval_s": _interval_s(applied_winner),
                "optimizer_apply": {
                    "original_mission_id": original_mission_id,
                    "modified_variables": modified,
                    "comparison": [r.model_dump(mode="json") for r in comparison],
                    "verification": verification,
                    "baseline_mission": to_legacy_dict(baseline),
                    "baseline_score": baseline_score.model_dump(mode="json") if baseline_score else None,
                    "winner_score": winner_score.model_dump(mode="json") if winner_score else None,
                },
            }
        ),
        grid_result_json=json.dumps(to_legacy_dict(applied_winner)),
    )
    db_session.add(mission)
    db_session.commit()
    db_session.refresh(mission)
    return mission.id


# ── Orchestration ────────────────────────────────────────────────────────────


def apply_winner(
    solve_request: OptimizerSolveRequest,
    winner_payload: dict,
    winner_variable_values: dict,
    constraints: Optional[OptimizationConstraints],
    weights: Optional[OptimizationWeights],
    db_session,
    *,
    project_id: Optional[str] = None,
    original_mission_id: Optional[str] = None,
    name: Optional[str] = None,
) -> ApplyResult:
    """Apply the optimizer winner end to end (Fase 10F-1/2/10)."""
    base_req = (solve_request.grid if solve_request.grid is not None else solve_request.corridor).model_copy(deep=True)

    baseline = build_base_mission(base_req, db_session)
    baseline_eval = evaluate(baseline, constraints=constraints, weights=weights)

    winner_mission = parse_mission_blob(winner_payload)
    builder = CandidateBuilder(winner_mission.mission_type, base_req, db_session)
    applied_winner, verification = _verify_winner(builder, winner_mission, winner_variable_values)
    winner_eval = evaluate(applied_winner, constraints=constraints, weights=weights)

    comparison = _comparison_rows(baseline, applied_winner, baseline_eval.score, winner_eval.score)
    modified = _modified_variables(winner_variable_values, baseline)

    warnings: list[str] = []
    for w in list(dict.fromkeys(baseline_eval.warnings + winner_eval.warnings)):
        warnings.append(w)

    mission_id = None
    if project_id:
        mission_id = persist_winner(
            db_session,
            project_id,
            name,
            base_req,
            baseline,
            applied_winner,
            comparison,
            modified,
            verification,
            baseline_eval.score,
            winner_eval.score,
            original_mission_id,
        )

    return ApplyResult(
        baseline_mission=baseline,
        baseline_score=baseline_eval.score,
        applied_winner=applied_winner,
        winner_score=winner_eval.score,
        comparison=comparison,
        modified=modified,
        verification=verification,
        warnings=warnings,
        mission_id=mission_id,
    )


__all__ = ["ApplyResult", "WinnerMismatchError", "apply_winner"]
