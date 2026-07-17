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

try:
    import tifffile
    HAS_TIFFFILE = True
except ImportError:
    HAS_TIFFFILE = False


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
    """Elevation via OpenTopography GlobalDEM API (GeoTIFF per bounding box).

    Downloads a single GeoTIFF covering all requested points, then reads
    elevations locally. This is much faster than point-by-point API calls.
    Supports COP30 (Copernicus GLO-30), ANADEM (South America DTM), and others.
    Requires OPENTOPOGRAPHY_API_KEY env var.
    """

    BASE_URL = "https://portal.opentopography.org/API/globaldem"

    def __init__(self, api_key: str, demtype: str = "COP30") -> None:
        self.api_key = api_key
        self.demtype = demtype
        self._cached_raster: Optional[tuple[float, float, float, float, str, bytes]] = None

    def display_name(self) -> str:
        name_map = {"COP30": "Copernicus GLO-30", "ANADEM": "ANADEM"}
        return f"OpenTopography {name_map.get(self.demtype, self.demtype)} (~30m)"

    def get_elevations(self, points: list[tuple[float, float]]) -> list[float]:
        if not points or not HAS_TIFFFILE:
            return [0.0] * len(points)

        lats = [p[0] for p in points]
        lngs = [p[1] for p in points]
        south, north = min(lats), max(lats)
        west, east = min(lngs), max(lngs)
        # Small padding to avoid edge
        pad = 0.001
        south, north = south - pad, north + pad
        west, east = west - pad, east + pad

        cache_key = (south, north, west, east, self.demtype)
        if self._cached_raster is None or self._cached_raster[:5] != cache_key:
            data = self._fetch_tiff(south, north, west, east)
            if not data:
                return [0.0] * len(points)
            self._cached_raster = (*cache_key, data)

        _, _, _, _, _, tiff_data = self._cached_raster
        try:
            arr = tifffile.imread(io.BytesIO(tiff_data))
        except Exception:
            return [0.0] * len(points)

        if arr.ndim == 3:
            arr = arr[0]

        rows, cols = arr.shape
        elevs: list[float] = []
        for lat, lng in points:
            # Bilinear interpolation
            col = (lng - west) / (east - west) * (cols - 1)
            row = (north - lat) / (north - south) * (rows - 1)
            elev = self._interp(arr, row, col)
            elevs.append(float(elev))
        return elevs

    def _interp(self, arr, r: float, c: float) -> float:
        r0, c0 = int(r), int(c)
        r1 = min(r0 + 1, arr.shape[0] - 1)
        c1 = min(c0 + 1, arr.shape[1] - 1)
        if r0 < 0 or c0 < 0:
            return 0.0
        dr = r - r0
        dc = c - c0
        return (
            arr[r0, c0] * (1 - dr) * (1 - dc) +
            arr[r0, c1] * (1 - dr) * dc +
            arr[r1, c0] * dr * (1 - dc) +
            arr[r1, c1] * dr * dc
        )

    def _fetch_tiff(self, south: float, north: float, west: float, east: float) -> Optional[bytes]:
        params = urllib.parse.urlencode({
            "demtype": self.demtype,
            "south": south, "north": north,
            "west": west, "east": east,
            "outputFormat": "GTiff",
            "API_Key": self.api_key,
        })
        url = f"{self.BASE_URL}?{params}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Map2Drone/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except Exception:
            return None


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
