# Fase 10B — Informe final (Universal Mission Model extendido + arquitectura del Optimizer)

**Fecha:** 2026-08-18
**Referencia:** `phase-10a-final.md` (estado antes de la fase).
**Tests finales:** backend **332 passed** (baseline 10A: 281) · frontend **83 vitest passed** · `tsc --noEmit` OK · `vite build` OK.

La Fase 10B extendió el **Universal Mission Model (UMM)** como única fuente de
verdad normativa de la misión fotogramétrica (parámetros, métricas, waypoints
tipados, segmentos, plan de captura, plan de giro, perfiles de dron y cámara,
bloque de geometría) y preparó la **arquitectura base del Photogrammetry Mission
Optimizer**: constraints, scoring, evaluator y el stub `Optimizer` (la búsqueda
automática es Fase 10C).

Reglas respetadas: **no** se tocó CaptureInterval, la física de TurnRadius, la
estructura binaria/trailer de LCHM ni la política `floor`; **no** se implementó
optimización automática; **no** se inventaron parámetros de drones/cámaras; los
exporters no interpretan ni recalculan la misión. **Sin commit.**

---

## A. Qué se implementó

| Paso | Entregable |
|---|---|
| 1 | **`mission/models.py` extendido** — `MissionMetadata`, `UniversalWaypoint` (tipado), `FlightSegment`, `CaptureMode`/`CapturePlan` (científico/comercial), `TurnPlan`, `DroneDynamicsProvenance`/`DroneFlightDynamicsProfile`/`DroneProfile`, `CameraProfile`, bloque `MissionParameters`/`MissionMetrics`/`MissionGeometry` normalizado (10B), `UniversalMission` ampliado (`mission_id`, `name`, `coordinate_reference`, `waypoints: list[UniversalWaypoint]`, `segments`, `capture_plan`, `turn_plan`, `drone_profile`, `camera_profile`) + versionado (`schema_version`, `normalize_schema_version`, `is_supported_version`) |
| 2 | **`mission/segments.py`** — `build_segments` (runs rectos con UTM del Planning Core + giros del turn plan) y anotación de waypoints (`line_index`/`segment_index`/`photo_index`) |
| 3 | **`mission/builder.py`** — `build_universal_mission` produce todo el bloque 10B; `_apply_curve_sizes` (radio uniforme + `per_waypoint_curve_size`); `to_legacy_dict` 100 % compatible con `grid_result_json` (waypoints legacy: `latitude/longitude/altitude/heading/speed/action_type/action_param/elevation_msnm/agl`) y aditivo para lo nuevo |
| 4 | **`mission/validation.py`** — parse tolerante nuevo + legacy (`_waypoint_from_any`, `_opt_model`, `_segments_from_any`) |
| 5 | **`mission/validator.py`** — `UniversalMissionValidator`: errores/warnings/status por geometría, fotogrametría, vuelo, captura, giro y batería; **no muta** la misión |
| 6 | **`mission/serializer.py`** — `mission_to_dict/from_dict/to_json/from_json/round_trip` |
| 7 | **`mission/__init__.py`** — exports públicos actualizados |
| 8 | **`optimizer/`** — `models.py` (`OptimizerInput`, `OptimizationConstraints`, `OptimizationWeights`, `MissionScore`, `CandidateMission`, `EvaluationResult`, `OptimizationResult`), `constraints.py` (`evaluate_constraints`), `objective.py` (`score_mission`), `evaluator.py` (`evaluate`/`evaluate_candidate`), `optimizer.py` (**stub**: `solve()` → `NotImplementedError`) |
| 9 | **`export/adapters.py`** — `from_universal_mission` → `MissionExportData` (transforma, no recalcula; `floor(scientific)` **solo aquí** como fallback Litchi; `path_mode` CURVED_TURNS/STRAIGHT; `photo_capture` TIME/DISTANCE) |
| 10 | **Schemas + endpoints** — `MissionValidateRequest/Response`, `OptimizerEvaluateRequest/Response`; helper `_umm_legacy_json` (grid + corridor); **POST `/api/v1/missions/validate`** y **POST `/api/v1/optimizer/evaluate`** |
| 11 | **Frontend (solo tipos)** — `frontend/src/shared/types/project.ts`: `UniversalMission`, `UniversalWaypoint`, `FlightSegment`, `CapturePlan`, `TurnPlan`, `DroneProfile`, `CameraProfile`, `UniversalMissionMetrics`, `OptimizationConstraints`, `OptimizationWeights`, `MissionScore`, `OptimizerInput`, `OptimizerEvaluateResponse`, `MissionValidateResponse` |
| 12 | **Tests** — `test_umm_10b.py`, `test_validator.py`, `test_optimizer.py`, `test_export_adapter.py`, `test_api_fase10b.py` |
| 13 | Regresión completa (pytest 332, ruff en archivos 10B, tsc, build, vitest) |

---

## B. Arquitectura después

```
modules/mission/               ← Universal Mission Model (fuente única normativa)
  models.py                    modelos + versionado de schema ("1.0")
  builder.py                   build_universal_mission / to_legacy_dict
  segments.py                  build_segments + anotación de waypoints
  validation.py                parse tolerante nuevo + legacy
  validator.py                 UniversalMissionValidator (no muta)
  serializer.py                round-trip dict/JSON

modules/optimizer/             ← arquitectura base del Photogrammetry Optimizer (10C: search)
  models.py                    inputs/constraints/weights/score/candidate/result
  constraints.py               evaluate_constraints (violaciones → inválido)
  objective.py                 score_mission [0,1] por criterio (solo lee el UMM)
  evaluator.py                 evaluate() = validator + constraints + score
  optimizer.py                 Optimizer (stub: solve() NotImplementedError)

modules/export/adapters.py     UMM → MissionExportData (transforma; floor Litchi aquí)

api/v1/endpoints.py            _umm_legacy_json · POST /missions/validate · POST /optimizer/evaluate
schemas/schemas.py             peticiones/respuestas de validate y evaluate
```

**Flujo de datos:** los motores (grid/corridor) emiten su resultado → `build_universal_mission` lo normaliza al UMM (bloque 10B) → `from_universal_mission` lo transforma a `MissionExportData` → los exporters existentes lo vuelcan a cada formato. `/optimizer/evaluate` ejecuta `evaluate()` sobre el UMM (validate + constraints + score) sin modificar nada.

---

## C. Schema del UMM (v1.0)

- `schema_version`: `"1.0"`; `SUPPORTED_VERSIONS={"1.0"}`; alias `"1.0.0"→"1.0"`. Versiones desconocidas se conservan en el parse y el validator emite warning `unsupported_version`.
- Bloques: `metadata`, `parameters` (incl. `capture_mode`, `turn_mode`, `turn_radius_m`, `sweep_deg`), `metrics`, `geometry`, `waypoints` (tipados), `segments`, `capture_plan`, `turn_plan`, `drone_profile`, `camera_profile`, `photo_points`, `flight_lines_geojson`.
- `CapturePlan`: `scientific_interval_s` (ideal del engine) + `commercial_interval_s` (entero recomendado del engine). La política `floor` del engine no cambió; la conversión solo existe en el adapter Litchi.
- `to_legacy_dict` emite la forma legacy plana exacta y añade de forma **aditiva** los bloques nuevos (los loaders viejos ignoran claves desconocidas). `parse_mission_blob` acepta payload nuevo y legacy.

---

## D. APIs nuevas

| Endpoint | Petición | Respuesta |
|---|---|---|
| `POST /api/v1/missions/validate` | `MissionValidateRequest.payload` (dict UMM o legacy) | `valid`, `status` (VALID/WARNING/INVALID), `errors[]`, `warnings[]`, `mission` (UMM normalizado) |
| `POST /api/v1/optimizer/evaluate` | `OptimizerEvaluateRequest.mission` (UMM) + `constraints` opcionales | `valid`, `status`, `score` (per-criterion + `total_score`), `metrics`, `validation`, `warnings` |

`/optimizer/run` **no** se creó (10C).

---

## E. Tests

Nuevos: **51** en `backend/tests/` (bloques ricos del UMM, round-trip, versionado,
coerción legacy, capture NONE/TIME/DISTANCE, validator por categoría, optimizer
constraints/score/evaluate, adapter→LCHM y equivalencia con el grid real, API
validate/evaluate). Total backend: **332 passed**.

Equivalencia verificada: `UMM → from_universal_mission → LCHM` conserva
waypoint_count, speed, `CURVED_TURNS`, radio de curva y `TIME interval`. El grid
real con la poligonal de referencia da **352 waypoints** (speed 6.81, intervalo 3,
turn radius 12.89): el UMM preserva todo, pero **el binario LCHM está limitado a
99 waypoints** (ver Riesgos) — por eso la equivalencia sobre ese caso se afirma a
nivel adapter.

---

## F. Regresión y compatibilidad

- Backend `pytest tests` → **332 passed** (baseline 10A: 281).
- `ruff check` sobre **todos los archivos 10B** → limpio (0 errores).
- Frontend: `tsc --noEmit` OK · `vite build` OK · `vitest` 83 passed.
- **LCHM / Grid / Corridor / Exporters:** sin cambios de comportamiento (la
  totalidad de los tests 10A sigue en verde, incluidos los binarios LCHM 74 wp
  TIME=5, corridor TIME=5, DISTANCE=20.5, NONE).

---

## G. Deuda técnica y riesgos

- **Ruff preexistente (~250 avisos):** `seed_data.py` (E501), `export/*` (I001,
  F401, W292), `planning/core/*`, `corridor`, `turn_radius/*`, tests de fases
  anteriores y E402/E501 en `endpoints.py` y `main.py`. No se tocaron por estar
  fuera del alcance de 10B; conviene una pasada `ruff --fix` + formateo en la
  Fase 10C.
- **LCHM y >99 waypoints (preexistente):** el header almacena `waypoint_count` en
  un **u8** (256 máx. y el propio Litchi limita a 99). Con 352 waypoints el valor
  envuelve (352 mod 256 = 96) y `parse_lchm` se desalinea. El UMM/adapter no lo
  causan; la corrección pertenece al validador/exportador LCHM y debe decidirse
  fuera de 10B para no alterar la estructura binaria.
- **Sin decisiones de compatibilidad rotas:** se procedió sin detenerse (la única
  anomalía detectada —el `is_straight` inexistente en `FlightSegment`— era un bug
  del test recién escrito y se corrigió).
- `OptimizationWeights` y umbrales de `score_mission` son provisionales: la
  calibración definitiva es parte de 10C.

---

## H. Qué queda para la Fase 10C

- `Optimizer.solve()` (búsqueda: variación de altura/overlaps/velocidad/intervalo/
  radio, respetando constraints y sin tocar los motores).
- Calibración de pesos (`OptimizationWeights`), endpoint `/optimizer/run` y
  frontend de optimización.
- Decidir el manejo de misiones >99 waypoints en el exportador LCHM (guard/de
  splitting) y limpiar el lint preexistente.