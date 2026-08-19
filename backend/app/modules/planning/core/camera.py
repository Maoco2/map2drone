"""Camera resolution helpers (single source of truth)."""

from typing import Optional

from app.models.schemas import Camera


def get_camera(db_session, camera_id: Optional[str]) -> Optional[Camera]:
    """Return the camera by id, or ``None`` when it does not exist.

    Single implementation shared by every planning module. Replaces the
    duplicated ``_get_camera`` helpers that used to live in the Grid and
    Corridor engines.
    """
    if not camera_id:
        return None
    return db_session.query(Camera).filter(Camera.id == camera_id).first()


def get_camera_required(db_session, camera_id: Optional[str]) -> Camera:
    """Like :func:`get_camera` but raises ``ValueError`` when missing."""
    camera = get_camera(db_session, camera_id)
    if camera is None:
        raise ValueError("Camera not found")
    return camera
