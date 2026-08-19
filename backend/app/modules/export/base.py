from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel

from .models import MissionExportData


class ExportResult(BaseModel):
    data: str | bytes
    filename: str
    mime_type: str = "text/plain"
    is_binary: bool = False


class ValidationError(BaseModel):
    field: str = ""
    message: str = ""


class ValidationResult(BaseModel):
    valid: bool = True
    errors: list[ValidationError] = []


class CompatibilityCategory(str, Enum):
    OFFICIAL = "official"
    IMPORTABLE_LIMITED = "importable_limited"
    PROPRIETARY = "proprietary"
    REVERSE_ENGINEERED = "reverse_engineered"
    GIS_ONLY = "gis_only"


CATEGORY_LABELS = {
    CompatibilityCategory.OFFICIAL: "Formato oficialmente documentado",
    CompatibilityCategory.IMPORTABLE_LIMITED: "Importable con funcionalidades limitadas",
    CompatibilityCategory.PROPRIETARY: "Formato propietario",
    CompatibilityCategory.REVERSE_ENGINEERED: "Generado por ingeniería inversa",
    CompatibilityCategory.GIS_ONLY: "Solo representación GIS (no es misión de vuelo)",
}


class CompatibilityInfo(BaseModel):
    category: CompatibilityCategory
    label: str = ""
    description: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        if not self.label:
            self.label = CATEGORY_LABELS.get(self.category, self.category.value)


class ExportWarning(BaseModel):
    code: str
    message: str
    fields: list[str] = []


class MissionExporter(ABC):
    name: str = ""
    extension: str = ""
    version: str = "1.0"
    description: str = ""
    compatibility: CompatibilityInfo | None = None

    def validate(self, mission: MissionExportData) -> ValidationResult:
        return ValidationResult()

    def get_warnings(self, mission: MissionExportData) -> list[ExportWarning]:
        return []

    @abstractmethod
    def export(self, mission: MissionExportData) -> ExportResult: ...


# ── Shared compatibility helpers ────────────────────────────────────────────


def has_elevation_data(mission: MissionExportData) -> bool:
    return any(wp.elevation_msnm is not None or wp.agl is not None for wp in mission.waypoints)


def has_gimbal(mission: MissionExportData) -> bool:
    return any(
        (wp.gimbal_pitch is not None and wp.gimbal_pitch != -90) or wp.gimbal_mode != 2 for wp in mission.waypoints
    )


def has_curve(mission: MissionExportData) -> bool:
    return any(wp.curve_size and wp.curve_size > 0 for wp in mission.waypoints)


def has_multiple_actions(mission: MissionExportData) -> bool:
    return any(len(wp.actions) > 0 for wp in mission.waypoints)


def has_heading_per_wp(mission: MissionExportData) -> bool:
    return any(wp.heading for wp in mission.waypoints)


def has_terrain_following(mission: MissionExportData) -> bool:
    return bool(mission.terrain_following)


def gis_warnings(mission: MissionExportData) -> list[ExportWarning]:
    """Warnings for formats that only represent geometry (KML/KMZ/GeoJSON/GPX)."""
    warnings = [
        ExportWarning(
            code="not_a_mission",
            message=(
                "Este formato representa geometría (puntos/líneas); NO es una misión de vuelo "
                "ejecutable por ningún dron ni software de vuelo."
            ),
            fields=[],
        )
    ]
    if has_multiple_actions(mission):
        warnings.append(
            ExportWarning(
                code="actions_lost",
                message="Las acciones de cámara/gimbal por waypoint no se representan.",
                fields=["actions"],
            )
        )
    if has_gimbal(mission):
        warnings.append(
            ExportWarning(
                code="gimbal_lost",
                message="El pitch y modo del gimbal no se representan.",
                fields=["gimbal_pitch", "gimbal_mode"],
            )
        )
    if has_terrain_following(mission):
        warnings.append(
            ExportWarning(
                code="terrain_following_lost",
                message="El seguimiento de terreno (terrain following) no es ejecutable.",
                fields=["terrain_following"],
            )
        )
    return warnings
