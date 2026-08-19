"""Universal Mission Serializer (Fase 10B).

Round-trips :class:`UniversalMission` ↔ ``dict`` / JSON, preserving backward
compatibility with the legacy ``grid_result_json`` blob. New fields default
to explicit ``null``/defaults on read; missing information is never rebuilt
by assumption.
"""

from __future__ import annotations

import json
from typing import Union

from app.modules.mission.models import UniversalMission
from app.modules.mission.validation import parse_mission_blob


def mission_to_dict(mission: UniversalMission) -> dict:
    """Full typed serialization of a Universal Mission (all blocks)."""
    return mission.model_dump(mode="json")


def mission_to_json(mission: UniversalMission) -> str:
    """Full typed JSON serialization of a Universal Mission."""
    return json.dumps(mission_to_dict(mission))


def mission_from_dict(data: Union[dict, str]) -> UniversalMission:
    """Deserialize a Universal Mission from a dict or JSON string (tolerant)."""
    return parse_mission_blob(data)


def mission_from_json(raw: str) -> UniversalMission:
    """Deserialize a Universal Mission from a JSON string."""
    return parse_mission_blob(raw)


def round_trip(mission: UniversalMission) -> UniversalMission:
    """Serialize and deserialize a mission (round-trip stability helper)."""
    return mission_from_dict(mission_to_dict(mission))
