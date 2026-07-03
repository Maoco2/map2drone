from __future__ import annotations

import json
import urllib.request
from abc import ABC, abstractmethod
from typing import Optional


class ElevationProvider(ABC):
    """Abstract elevation data provider."""

    @abstractmethod
    def get_elevations(self, points: list[tuple[float, float]]) -> list[float]:
        ...

    @abstractmethod
    def display_name(self) -> str:
        ...

    def description(self) -> str:
        return self.display_name()


class OpenElevationProvider(ElevationProvider):
    """SRTM ~30m DEM via the Open-Elevation API."""

    def get_elevations(self, points: list[tuple[float, float]]) -> list[float]:
        if not points:
            return []
        elevations: list[float] = []
        batch_size = 10000
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            locs = [{"latitude": float(lat), "longitude": float(lng)} for lat, lng in batch]
            body = json.dumps({"locations": locs}).encode()
            url = "https://api.open-elevation.com/api/v1/lookup"
            try:
                req = urllib.request.Request(
                    url,
                    data=body,
                    headers={"Content-Type": "application/json", "User-Agent": "Map2Drone/1.0"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode())
                    elevations.extend(r["elevation"] for r in data["results"])
            except Exception:
                elevations.extend([0.0] * len(batch))
        return elevations

    def display_name(self) -> str:
        return "Open-Elevation API (SRTM ~30m)"


def create_provider(
    elevation_source: str = "api",
    dem_filepath: Optional[str] = None,
    dem_resolution_m: float = 30.0,
) -> ElevationProvider:
    """Create an ElevationProvider (always Open-Elevation API for now).

    Returns:
        An OpenElevationProvider instance.
    """
    return OpenElevationProvider()
