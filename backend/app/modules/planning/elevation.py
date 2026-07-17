from __future__ import annotations

import io
import json
import math
import os
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import Optional

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


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


class MapboxTerrainRgbProvider(ElevationProvider):
    """Elevation via Mapbox Terrain-RGB tiles (~10m resolution)."""

    TILE_SIZE = 512
    ZOOM = 14

    def __init__(self, token: str) -> None:
        self.token = token
        self._cache: dict[tuple[int, int, int], bytes] = {}

    def _tile_coords(self, lat: float, lng: float) -> tuple[int, int, int]:
        n = 2.0 ** self.ZOOM
        x = (lng + 180.0) / 360.0 * n
        y = (1.0 - math.log(math.tan(math.radians(lat)) + 1.0 / math.cos(math.radians(lat))) / math.pi) / 2.0 * n
        return self.ZOOM, int(x), int(y)

    def _pixel_pos(self, lat: float, lng: float, tx: int, ty: int) -> tuple[int, int]:
        n = 2.0 ** self.ZOOM
        x = (lng + 180.0) / 360.0 * n
        y = (1.0 - math.log(math.tan(math.radians(lat)) + 1.0 / math.cos(math.radians(lat))) / math.pi) / 2.0 * n
        px = int((x - tx) * self.TILE_SIZE)
        py = int((y - ty) * self.TILE_SIZE)
        return max(0, min(px, self.TILE_SIZE - 1)), max(0, min(py, self.TILE_SIZE - 1))

    def _fetch_tile(self, z: int, x: int, y: int) -> bytes:
        key = (z, x, y)
        data = self._cache.get(key)
        if data is not None:
            return data
        url = (
            f"https://api.mapbox.com/v4/mapbox.terrain-rgb/{z}/{x}/{y}@2x.pngraw"
            f"?access_token={self.token}"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Map2Drone/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                self._cache[key] = data
                return data
        except Exception:
            self._cache[key] = b""
            return b""

    def _decode_elevation(self, r: int, g: int, b: int) -> float:
        return -10000.0 + ((r * 256 * 256 + g * 256 + b) * 0.1)

    def get_elevations(self, points: list[tuple[float, float]]) -> list[float]:
        if not HAS_PILLOW or not points:
            return [0.0] * len(points)

        # Group points by tile key
        tile_groups: dict[tuple[int, int, int], list[int]] = {}
        for idx, (lat, lng) in enumerate(points):
            z, tx, ty = self._tile_coords(lat, lng)
            key = (z, tx, ty)
            tile_groups.setdefault(key, []).append(idx)

        elevations: list[float] = [0.0] * len(points)

        for (z, tx, ty), indices in tile_groups.items():
            tile_data = self._fetch_tile(z, tx, ty)
            if not tile_data:
                continue
            try:
                img = Image.open(io.BytesIO(tile_data)).convert("RGB")
            except Exception:
                continue
            for idx in indices:
                lat, lng = points[idx]
                px, py = self._pixel_pos(lat, lng, tx, ty)
                r, g, b = img.getpixel((px, py))
                elevations[idx] = self._decode_elevation(r, g, b)

        return elevations

    def display_name(self) -> str:
        return "Mapbox Terrain-RGB (~10m)"


class OpenTopographyProvider(ElevationProvider):
    """Elevation via OpenTopography Point Elevation API.

    Supports COP30 (Copernicus GLO-30), ANADEM (South America DTM), and others.
    Requires OPENTOPOGRAPHY_API_KEY env var. Free tier: 200 calls/24h (academic).
    Closest to Google Earth DEM quality.
    """

    BASE_URL = "https://portal.opentopography.org/API/v1/elevation"

    def __init__(self, api_key: str, demtype: str = "COP30") -> None:
        self.api_key = api_key
        self.demtype = demtype
        self._cache: dict[tuple[float, float], float] = {}

    def display_name(self) -> str:
        name_map = {"COP30": "Copernicus GLO-30", "ANADEM": "ANADEM"}
        return f"OpenTopography {name_map.get(self.demtype, self.demtype)} (~30m)"

    def get_elevations(self, points: list[tuple[float, float]]) -> list[float]:
        if not points:
            return []
        elevations: list[float] = [0.0] * len(points)
        uncached: list[tuple[int, float, float]] = []
        for idx, (lat, lng) in enumerate(points):
            key = (round(lat, 6), round(lng, 6))
            cached = self._cache.get(key)
            if cached is not None:
                elevations[idx] = cached
            else:
                uncached.append((idx, lat, lng))
        for idx, lat, lng in uncached:
            elev = self._fetch_point(lat, lng)
            self._cache[(round(lat, 6), round(lng, 6))] = elev
            elevations[idx] = elev
        return elevations

    def _fetch_point(self, lat: float, lng: float) -> float:
        params = urllib.parse.urlencode({
            "longitude": lng, "latitude": lat,
            "dataset": self.demtype, "API_Key": self.api_key,
        })
        url = f"{self.BASE_URL}?{params}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Map2Drone/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                return float(data["Elevation"])
        except Exception:
            return 0.0


def create_provider() -> ElevationProvider:
    """Create an ElevationProvider based on env config.

    Priority:
      1. OPENTOPOGRAPHY_API_KEY present → OpenTopography (COP30 by default)
      2. ELEVATION_SOURCE=mapbox + MAPBOX_TOKEN → Mapbox Terrain-RGB
      3. Otherwise → Open-Elevation API (free, SRTM ~30m, no key needed)

    OPENTOPOGRAPHY_DEMTYPE can be set to ANADEM, COP30, AW3D30, etc.
    """
    api_key = os.getenv("OPENTOPOGRAPHY_API_KEY", "").strip()
    if api_key:
        demtype = os.getenv("OPENTOPOGRAPHY_DEMTYPE", "COP30").strip()
        return OpenTopographyProvider(api_key, demtype)

    source = os.getenv("ELEVATION_SOURCE", "").lower()
    if source == "mapbox":
        token = os.getenv("MAPBOX_TOKEN")
        if token:
            return MapboxTerrainRgbProvider(token)
    return OpenElevationProvider()
