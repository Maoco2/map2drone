from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
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


class MissionExporter(ABC):
    name: str = ""
    extension: str = ""
    version: str = "1.0"
    description: str = ""

    def validate(self, mission: MissionExportData) -> ValidationResult:
        return ValidationResult()

    @abstractmethod
    def export(self, mission: MissionExportData) -> ExportResult:
        ...
