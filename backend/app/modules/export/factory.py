from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import MissionExporter

_registry: dict[str, type[MissionExporter]] = {}
_instances: dict[str, MissionExporter] = {}


def register(name: str, cls: type[MissionExporter]) -> None:
    _registry[name] = cls


def get_exporter(name: str) -> MissionExporter:
    if name not in _instances:
        if name not in _registry:
            raise ValueError(f"Unknown exporter: {name}. Available: {list(_registry.keys())}")
        _instances[name] = _registry[name]()
    return _instances[name]


def list_exporters() -> list[dict]:
    result = []
    for name, cls in _registry.items():
        inst = get_exporter(name)
        result.append({
            "id": name,
            "name": inst.name,
            "extension": inst.extension,
            "version": inst.version,
            "description": inst.description,
        })
    return result
