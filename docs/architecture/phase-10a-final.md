# Fase 10A — Informe final (Planning Core + Universal Mission Model)

**Fecha:** 2026-08-18
**Referencia:** `phase-10a-baseline.md` (estado antes de la fase).
**Tests finales:** backend **281 passed** (baseline: 251) · frontend **83 vitest passed** · `tsc` + `vite build` OK.

La Fase 10A consolidó la arquitectura de planificación en un **Planning Core**
compartido y un **Universal Mission Model**, dejando el repositorio preparado
para la **Fase 10B** (UMM extendido). El optimizer automático **NO se implementó**
en esta fase y fue **descartado posteriormente** (decisión de producto).

---

## A. Qué se implementó

| Paso | Entregable |
|---|---|
| 1 | Auditoría + baseline (`phase-10a-baseline.md`, pytest 251) |
| 2 | **Planning Core** — `backend/app/modules/planning/core/` (camera, photogrammetry, speed, spacing, distance, battery, metrics, models, photo_points) |
| 3 | Motor **Grid** migrado al Planning Core |
| 4 | Motor **Corridor** migrado al Planning Core (elimina el import a `planning.engine`) |
| 5 | **Métricas** tiempo/distancia/batería con integración de **Turn Radius** (turnos reales; se elimina el `num_lines × 5` cuando hay plan) |
| 6 | **`flight_lines_geojson`** (grid, EPSG:4326) y **`photo_points`** (ambos motores) |
| 7 | **Universal Mission Model** — `backend/app/modules/mission/` (models, builder, validation) + serializer compatible con `grid_result_json` |
| 8 | **Frontend** — deja de reconstruir geometría; solo visualiza backend |
| 9 | **Exporters validados** (LCHM crítico: 74 wp TIME=5, corridor TIME=5, DISTANCE=20.5, NONE) |
| 10 | Regresión completa: pytest + vitest + build |

---

## B. Arquitectura después

```
planning/core/            ← single source of truth (matemática + modelos)
  camera.py               get_camera / get_camera_required
  photogrammetry.py       calc_gsd / calc_footprint / calculate_gsd_and_footprint
  speed.py                calculate_recommended_speed (shutter)
  spacing.py              calculate_line_spacing / calculate_photo_spacing
  distance.py             utm_epsg_for / make_transformer / calculate_path_distance (UTM)
  battery.py              calculate_battery_requirements (fracción usable 0.80, fallback 25)
  metrics.py              calculate_mission_metrics (straight/transition/turn/baterías)
  models.py               PhotoPoint / FlightLine / MissionMetrics / BatteryRequirements
  photo_points.py         annotate_photo_points (agrupación por línea)

planning/engine.py        Grid engine — usa el core (re-export de calc_gsd/calc_footprint)
corridor/engine.py        Corridor engine — usa el core (sin import a planning.engine)
planning/turn_radius/*    SIN cambios de lógica (comportamiento validado intacto)
core/photogrammetry/capture_interval.py   SIN cambios de lógica
export/litchi_lchm.py     Serializer puro — SIN cambios de lógica

mission/                  Universal Mission Model
  models.py               MissionParameters / MissionMetrics / MissionGeometry / UniversalMission
  builder.py              build_universal_mission / to_legacy_dict
  validation.py           parse_mission_blob (lee blobs nuevos y legacy)
```

Dependencias corregidas: `corridor → planning.engine` (antipatrón) eliminado;
ahora ambos motores dependen únicamente de `planning/core`.

---

## C. Fuentes de verdad y duplicaciones eliminadas

| Antes (copia) | Ahora (única fuente) |
|---|---|
| `_get_camera` ×2 (`engine.py:25`, `corridor/engine.py:32`) | `core/camera.get_camera_required` |
| `calc_gsd`/`calc_footprint` ×2 | `core/photogrammetry` (re-export en engine) |
| Velocidad shutter ×3 (grid, corridor, frontend) | `core/speed.calculate_recommended_speed` |
| Line/photo spacing ×2 | `core/spacing` |
| Distancia equirectangular ×2 | `core/distance` (UTM) |
| Baterías (grid=25, corridor=drone×0.8) **inconsistente** | `core/battery.calculate_battery_requirements` |
| `utm_epsg_for` ×2 | `core/distance.utm_epsg_for` |
| `num_lines × 5 s` ×2 | `core/metrics` con turnos reales del Turn Radius |
| Reconstrucción de líneas + interpolación de fotos (frontend) | backend `flight_lines_geojson` + `photo_points` |

Constantes centralizadas: `DEFAULT_USABLE_BATTERY_FRACTION = 0.80`,
`DEFAULT_FLIGHT_TIME_MIN_FALLBACK = 25.0`, `DEFAULT_TURN_OVERHEAD_S_PER_LINE = 5.0`,
`HEADING_TOLERANCE_DEG = 1.5`, `PHOTO_POINT_LINE_TOLERANCE_DEG = 15.0`.

---

## D. Deltas matemáticos documentados (antes → después)

> Regla de la fase: antes de cambiar matemática existente se compara el
> resultado anterior y se documenta el delta. Los motores ya **no** usan
> equirectangular (111320 m/°); usan UTM real (pyproj), como el Corridor y el
> Turn Radius ya hacían.

**Caso Grid** — cam-43-20mp · dji-m3e · 100 m AGL · overlap 75/65 · takeoff (vertex):
| Métrica | Antes | Después | Delta |
|---|---|---|---|
| `total_distance` (m) | 1 968 054.39 | 1 961 362.14 | **−0.34 %** (equirect→UTM, R3) |
| `estimated_time_sec` (sin turn plan) | 289 874.8 | 288 786.4 | −0.38 % |
| `battery_count` | 194 (25 min fijos) | **134** (45 min × 0.8 = 36 min usable) | batería unificada (R1) |
| con `turn_radius` AUTO (turnos reales) | 288 786.4 | 288 946.7 | **+0.06 %** (turnos reales > 5 s/línea, R2) |

**Caso Corridor** — cam-1-20mp · dji-m3e · 100 m AGL · overlap 75/65 · 120/80 m · takeoff:
| Métrica | Antes | Después | Delta |
|---|---|---|---|
| `total_distance` (m) | 21 459.16 | 21 476.65 | **+0.08 %** (UTM) |
| `estimated_time_sec` (sin turn plan) | 3 152.7 | 3 156.8 | +0.13 % |
| `battery_count` | 2 | 2 | sin cambio (corridor ya usaba drone×0.8) |
| con `turn_radius` AUTO | 3 156.8 | 3 154.3 | **−0.08 %** |

Interpretación: la batería del grid con drone cambia de forma esperada (antes
ignoraba el drone); el resto son variaciones < 1 % por proyección métrica y
turnos reales. Sin `turn_radius` configurado, el comportamiento es
prácticamente idéntico (fallback documentado reproduce `num_lines × 5`).

---

## E. Nuevas salidas (aditivas, no rompen)

- **`GridResponse.flight_lines_geojson`** (EPSG:4326): FeatureCollection con las
  líneas de vuelo (`cl_i`, properties `type: scan`). El corridor ya la tenía en
  `geometry.flight_lines_geojson`; el grid ahora la entrega en la raíz.
- **`photo_points`** (grid y corridor): puntos autoritativos con `index`,
  `latitude`, `longitude`, `altitude_m`, `distance_along_line_m` (desde el
  inicio de la línea), `speed_ms`, `heading_deg`, `capture`. Incluye modos
  VERTEX/TERRAIN (capture=False) y PHOTO (capture=True).

---

## F. Universal Mission Model (`backend/app/modules/mission/`)

- **`models.py`**: `MissionParameters`, `MissionMetrics`, `MissionGeometry`,
  `UniversalMission` (schema_version 1.0, mission_type, waypoints,
  flight_lines_geojson, photo_points, capture_interval, turn_radius, warnings).
- **`builder.py`**: `build_universal_mission(mission_type, req, result)` +
  `to_legacy_dict(umm)` → serialización plana compatible con el histórico
  `result.model_dump()` (mismas claves de primer nivel, más `schema_version`,
  `parameters` y `metrics`).
- **`validation.py`**: `parse_mission_blob(raw)` lee tanto el payload nuevo
  (anidado) como el blob legacy plano (R6) sin romper; valida con pydantic.
- Los endpoints `/planning/grid` y `/planning/corridor` ahora persisten
  `Mission.grid_result_json` a través del serializer del UMM. El blob resultante
  sigue siendo consumible por el loader legacy del frontend.

---

## G. Frontend — solo visualizar

- **`planningStore.ts`**: eliminada `interpolatePhotoPoints` y la reconstrucción
  de líneas por heading. `setGridResult` ahora construye las líneas desde
  `result.flight_lines_geojson ?? result.geometry?.flight_lines_geojson` y los
  marcadores de foto desde `result.photo_points` (capture=True).
- **`project.ts`**: nuevos tipos `PhotoPoint`, `flight_lines_geojson`,
  `photo_points` en `GridResult`.
- `captureInterval.ts` sigue como **preview documentado** (no autoritativo).

---

## H. Exporters validados (LCHM crítico)

Sin tocar `litchi_lchm.py`, se validaron los casos críticos con el motor ya
migrado: **Area Grid 74 wp TIME=5**, **Linear Corridor TIME=5**,
**Area Grid DISTANCE=20.5**, **Area Grid NONE**, más CURVED_TURNS/curve_size y
la referencia `area_grid_74_time5_curve.lchm`.
→ `tests/test_litchi_lchm.py`, `test_lchm_photo_capture.py`,
`test_lchm_photo_matrix.py`, `test_turn_radius_lchm_integration.py`,
`test_export.py` = **123 passed**.

---

## I. APIs que siguen funcionando (no rotas)

`POST /planning/grid` · `/planning/corridor` · `/planning/turn-radius` ·
`/planning/gsd` · `/corridor/parse` · `/corridor/import` · `/export/*` ·
auth · projects · missions. `GridResponse`/`CorridorResponse` conservan todos
sus campos; solo se añadieron `flight_lines_geojson` (grid) y `photo_points`.

---

## J. Tests

| Suite | Baseline | Final | Δ |
|---|---|---|---|
| Backend pytest | 251 | **281** | +30 (19 core + 8 UMM + 3 grid/corridor/flight·photo) |
| Frontend vitest | 83 | **83** | sin cambios |
| `tsc --noEmit` / `tsc -b` | OK | OK | — |
| `vite build` | OK | OK | — |

El `npm run lint` no tiene `eslint.config.*` en el repo (configuración
pre-existente, no relacionada con la fase).

---

## K. Riesgos (del baseline) — estado

| Riesgo | Estado |
|---|---|
| R1 baterías grid vs corridor | **Mitigado** — `calculate_battery_requirements` unificado |
| R2 `num_lines × 5 s` | **Mitigado** — turnos reales del Turn Radius cuando hay plan; fallback documentado |
| R3 grid equirect→UTM | **Mitigado** — delta −0.34 % documentado (sección D) |
| R4 `flight_lines_geojson` grid | **Hecho** — aditivo; frontend ya no reconstruye |
| R5 espejo CaptureInterval | **Documentado** — preview-only |
| R6 `grid_result_json` blob | **Mitigado** — UMM serializer compatible hacia atrás |
| R7 LCHM floor interval | **Intacto** — no se tocó |

---

## L. Preparación Fase 10B — Universal Mission Model

La arquitectura quedó lista para el **Universal Mission Model** como única fuente
de verdad de la misión:
1. **Planificación autoritativa en backend** (`planning/core` + `mission/`): el
   UMM se construye llamando a `build_universal_mission` sobre el resultado de
   los motores y consume `MissionMetrics` (tiempo, baterías, GSD, overlap
   efectivo) — todo desde una única fuente de verdad.
2. **`flight_lines_geojson` + `photo_points`** ya disponibles para coste de
   cobertura real.
3. **Turn Radius real** ya integrado en `estimated_time_sec` y
   `battery_count`.
4. El frontend solo consume resultados → el UMM se exporta directamente sin
   reconstruir nada en el cliente.
5. Fases 9 (validación fixtures) y 10 (regresión) sientan la red de seguridad
   para iterar el motor sin regresiones.
