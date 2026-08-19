# Fase 10A — Baseline de auditoría (estado actual)

**Fecha:** 2026-08-18
**Tipo:** auditoría read-only — no se modificó código.
**Test baseline:** `pytest` → **251 passed** (0 failures).

Este documento registra el estado de la arquitectura antes de la Fase 10A
(consolidación del Planning Core) y es la referencia contra la que se medirá
cualquier cambio. No es un documento de diseño; es una fotografía del código.

---

## 1. Estado actual

- **Backend:** FastAPI + SQLAlchemy + pydantic. Los motores fotogramétricos son
  módulos independientes; los planners (Grid/Corridor) comparten parte de la
  lógica por **copia** (no por importación).
- **Frontend:** React 19 + zustand 5 + @tanstack/react-query + react-map-gl/maplibre.
  Consume la API del backend y **reconstruye** geometría de misión en modo grid.
- **Exportación:** 12 exporters; **LCHM es un serializer puro** (no calcula nada).

## 2. Archivos afectados por la Fase 10A

| Archivo | Rol | Acción prevista |
|---|---|---|
| `backend/app/modules/planning/engine.py` | Grid engine + `calc_gsd`/`calc_footprint` | Migrar al Planning Core |
| `backend/app/modules/planning/elevation.py` | DEM provider | Sin cambios |
| `backend/app/modules/corridor/engine.py` | Corridor engine | Migrar al Planning Core |
| `backend/app/modules/corridor/parsers.py` | Import centerline | Sin cambios |
| `backend/app/core/photogrammetry/capture_interval.py` | CaptureIntervalEngine | **NO modificar lógica** |
| `backend/app/modules/planning/turn_radius/*` | TurnRadiusEngine + planners | **NO modificar lógica** |
| `backend/app/modules/export/litchi_lchm.py` | Serializer LCHM | **NO modificar** salvo adaptación de contrato |
| `backend/app/modules/export/models.py` | `MissionExportData` | Adaptador al Universal Mission Model |
| `backend/app/api/v1/endpoints.py` | API v1 | Adaptadores de compatibilidad |
| `backend/app/schemas/schemas.py` | Pydantic API schemas | Extensiones no destructivas |
| `backend/app/models/schemas.py` | ORM (Drone/Camera/Mission) | Añadir enlace dinámica (opcional) |
| `frontend/src/shared/utils/captureInterval.ts` | Espejo preview | Mantener como preview documentado |
| `frontend/src/modules/missions/planningStore.ts` | Reconstruye geometría grid | Eliminar reconstrucción |
| `frontend/src/modules/export/exportStore.ts` | `buildExportData` | Consumir estructura del backend |
| `frontend/src/modules/map/FlightLinesLayer.tsx` | Render | Consumir `flight_lines_geojson` |

## 3. Funciones duplicadas (antes)

| Función/fórmula | Ubicaciones | Notas |
|---|---|---|
| `_get_camera` | `planning/engine.py:25`, `corridor/engine.py:32` | Idénticas |
| `calc_gsd` | `planning/engine.py:29`, espejo frontend `captureInterval.ts` | Backend authoritative |
| `calc_footprint` | `planning/engine.py:33`, espejo frontend | Backend authoritative |
| Velocidad shutter | `engine.py:414-419`, `corridor/engine.py:334-339`, `calcRecommendedSpeedMps` (frontend) | 3 copias |
| Line/photo spacing | `engine.py:430-431`, `corridor/engine.py:379-380` | Idénticas |
| Distancia (111320 + cos) | `engine.py:531-535`, `corridor/engine.py:420-427` | Equirectangular |
| Baterías | `engine.py:538` (**25 hardcoded**), `corridor/engine.py:430` (`drone.flight_time*0.8` o 25) | **Inconsistente** |
| `utm_epsg_for` | `corridor/engine.py:56`, `turn_radius/geometry.py:35` | Idénticas |
| Heading local | `_polyline_local_heading` (corridor), `heading_degrees` (turn_radius) | Misma matemática |

## 4. Constantes duplicadas

| Constante | Valor | Ubicaciones |
|---|---|---|
| `111320` (metros/grado) | 111320.0 | `engine.py`, `corridor/engine.py` |
| Batería default | `25` min | `engine.py:538`, `corridor/engine.py:430` |
| `+5 s` penalización por línea | 5.0 | `engine.py:537`, `corridor/engine.py:429` |
| `WARNING_RATIO` | 1.25 | `capture_interval.py`, frontend mirror |
| `MIN_PLAUSIBLE_AGL_FLOOR_M` | 1.0 | `capture_interval.py`, frontend mirror |
| safety/clearance/a_lat/radios | 1.25 / 4.0 / 4.5 / 2–50 | `turn_radius/models.py` + frontend `turnRadius.ts` |

## 5. Modelos duplicados / solapados

- `WaypointSchema` (API) ≈ `ExportWaypointSchema` (API) ≈ `ExportWaypoint` (export) —
  mismos campos con nombres similares; hay mapeo manual en `_build_mission`.
- `Drone` (ORM) vs `DroneInfo` (export) vs `DroneFlightDynamics` (turn_radius):
  el perfil ORM **no** tiene parámetros dinámicos (a_lat, radios, safety).
- `Mission` (ORM) guarda `grid_result_json` (blob) — no existe un modelo de misión
  universal estructurado.

## 6. Cálculos frontend que deberían pertenecer al backend

1. **`planningStore.setGridResult`**: agrupa waypoints por heading y **reconstruye
   líneas de vuelo** cuando el backend no entrega `flight_lines_geojson` (grid).
2. **`planningStore.interpolatePhotoPoints`**: genera `photo_trigger` interpolando
   con haversine en modos vertex/terrain.
3. **`captureInterval.ts`**: espejo del CaptureIntervalEngine (preview, documentado
   como no autoritativo — se conserva).
4. **`PropertiesPanel.polygonAreaM2`**: área del polígono dibujado (UI; se conserva).

## 7. Diferencias Grid vs Corridor (antes)

| Aspecto | Grid | Corridor |
|---|---|---|
| Proyección | Equirectangular local (111320 m/°) | UTM real vía pyproj |
| `flight_lines_geojson` | **No existe** | Sí (`geometry.flight_lines_geojson`) |
| Baterías | `25` fijo | `drone.flight_time_min*0.8` o `25` |
| `geometry` en respuesta | No | Sí (polygon/lines/centerline/epsg) |
| Sweep/rotación | `sweep_deg` (óptimo o manual) | n/a (sigue la centerline) |
| `corridor_length_m`/`corridor_area_m2` | No | Sí |

## 8. Dependencias entre módulos (antes)

```
planning/engine.py ───► capture_interval (importa build_capture_interval_block,
                                           compute_capture_interval,
                                           compute_minimum_plausible_agl)
corridor/engine.py ───► planning/engine (calc_gsd, calc_footprint)  ← acoplamiento raro
                        ───► capture_interval
turn_radius/* ─────────► geometry/models internos (sin imports de capture_interval)
export/litchi_lchm.py ──► base, models (sin imports de los motores)
```

El acoplamiento `corridor → planning.engine` es un antipatrón que la Fase 10A
debe eliminar (Corridor no debería depender del módulo de Grid).

## 9. APIs existentes que NO deben romperse

- `POST /api/v1/planning/grid`
- `POST /api/v1/planning/corridor`
- `POST /api/v1/planning/turn-radius`
- `POST /api/v1/planning/gsd`
- `POST /api/v1/corridor/parse` e `/import`
- `POST /api/v1/export/{fmt}`, `/export/multi`, `/export/check`, `/export/formats`
- Auth/projects/missions (sin cambios previstos)

## 10. Riesgos

- **R1 (alto):** baterías grid (25) vs corridor (drone×0.8) divergentes → resultados
  engañosos. La función `calculate_battery_requirements` debe unificarlos con un
  default documentado `DEFAULT_USABLE_BATTERY_FRACTION = 0.80`.
- **R2 (alto):** la penalización `num_lines × 5 s` ignora el radio de giro real.
  Sustituir por `turn_distance_m`/`turn_duration_s` del TurnRadius cambiará el
  `estimated_time_sec` y `battery_count` → **requiere documentar el delta** contra
  el valor anterior.
- **R3 (alto):** pasar grid a distancia UTM (pyproj) cambiará `total_distance`,
  `estimated_time_sec` y `battery_count` respecto al equirectangular → delta
  esperado del ~0.1–1% según latitud; documentar.
- **R4 (medio):** generar `flight_lines_geojson` en grid cambia el payload de
  `GridResponse` (aditivo, no rompe). El frontend debe dejar de reconstruir.
- **R5 (medio):** el espejo frontend de CaptureInterval puede desincronizarse —
  mantener constante la fuente autoritativa (backend) y documentar preview-only.
- **R6 (medio):** `grid_result_json` es blob persistido; si cambia la estructura
  interna del resultado, las misiones antiguas persisten con el formato viejo.
  El serializer del Universal Mission Model debe ser **compatible hacia atrás**
  (leer el blob antiguo sin romper).
- **R7 (bajo):** LCHM `normalize_litchi_time_interval` aplica `floor` (5.3 → 5).
  No tocar; es la política documentada y verificada.

## 11. Plan de migración (por pasos, con tests tras cada paso)

1. **Auditoría y baseline** (este documento). ✅
2. **Planning Core** — `backend/app/modules/planning/core/` (camera, photogrammetry,
   speed, spacing, distance, battery, metrics, models) + tests nuevos.
3. **Migrar Grid** a `planning_core` (manteniendo resultado numérico salvo delta
   documentado por UTM/baterías).
4. **Migrar Corridor** a `planning_core` (elimina el import a `planning.engine`).
5. **Métricas de tiempo/distancia/batería** con integración de Turn Radius
   (`turn_distance_m`/`turn_duration_s`), eliminando `num_lines × 5`.
6. **Flight lines + photo points** — `flight_lines_geojson` en grid (EPSG:4326)
   y `photo_points` en ambos motores.
7. **Universal Mission Model** — `backend/app/modules/mission/` (models, builder,
   validation) + serializer compatible con `grid_result_json`.
8. **Frontend** — consumir `flight_lines_geojson`, `photo_points`,
   `turn_radius_result`, `capture_interval`, `mission_metrics`; eliminar la
   reconstrucción de geometría.
9. **Validar exporters** — LCHM (TIME/DISTANCE/NONE, CURVED_TURNS, curve_size)
   contra fixtures; resto de exporters.
10. **Regresión completa** — `pytest` 0 failures nuevos + `vitest` + `tsc` +
    `npm run build` + smoke E2E.

## 12. Compatibilidad hacia atrás

- `GridResponse`/`CorridorResponse` conservan **todos los campos actuales**
  (solo se añaden campos). Los clientes actuales siguen funcionando.
- `estimated_time_sec`/`battery_count`/`total_distance` pueden variar
  (R2/R3) — se documenta el delta en `phase-10a-final.md` con un caso de
  prueba concreto antes/después.
- `Mission.grid_result_json` se mantiene; el Universal Mission Model se serializa
  a ese blob (sin romper misiones existentes).
- LCHM: contrato de `options.photo_capture` y `curve_size` intactos.