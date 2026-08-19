# Fase 10F — UMM → Export y readiness (informe final)

**Fecha:** 2026-08-18
**Referencia:** `phase-10b-final.md` (UMM) y auditoría 10F (área,
cobertura, split, readiness, drone dynamics, matriz de exporters).

La Fase 10F permitió exportar una **Universal Mission** directamente
(LCHM/Litchi) con el **exporter real** y exponer el diagnóstico de exportabilidad
(readiness). El flujo **Apply Winner** del **Photogrammetry Mission Optimizer**
(Planning → Optimizer → Winner → Apply) fue **eliminado posteriormente**
(decisión de producto): el módulo `modules/optimizer/`, el endpoint
`POST /optimizer/apply` y su UI ya no existen. **`POST /export/umm/{fmt}`** y
**`POST /export/check-umm`** permanecen.

Reglas respetadas: no se tocó `planning/core/*`,
`core/photogrammetry/capture_interval.py`, `planning/turn_radius/*`,
`export/litchi_lchm.py`, la **UMM schema 1.0** ni los adapters de export. Se
tocaron `export/readiness.py` (nuevo), endpoints, schemas, tests y frontend
(tipos, api, panel de export). **Sin commit.**

---

## A. Auditoría 10F — hallazgos

| # | Punto auditado | Hallazgo confirmado | Estado |
|---|---|---|---|
| 1 | **Área** | `CorridorResponse.corridor_area_m2` lo calcula el engine (`poly.area`) pero el builder lo descarta (`getattr(..., None)`); `GridResponse.area_ha` es solo default 0 (el grid engine **nunca lo calcula**). | **CONFIRMED** |
| 2 | **UMM = fuente única** | `from_universal_mission` transforma (no recalcula); exporters serializan; LCHM = serialización pura. Se mantiene. | **CONFIRMED → respetado** |
| 3 | **Cobertura** | No existe `area_cubierta` en UMM 1.0 → coverage **DATA_REQUIRED** en 10F. Campo UMM 1.1 (`survey_area_m2`/`covered_area_m2`) → **DEUDA 10G**. | **DATA_REQUIRED (10F) → DEUDA 10G** |
| 4 | **Split 99 WP** | Guard real en `LchmValidator` (nunca emite archivo corrupto). Análisis 4A hecho; split automático 4B → **DEUDA 10G**. | **4A PASS / 4B DEUDA** |
| 5 | **Matriz exporters** | `factory.list_exporters()` expone `compatibility_info` por formato (proprietary/reverse_engineered/official/gis_only). | **CONFIRMED → PASS** |
| 6 | **Drone dynamics** | `DroneDynamicsProvenance` (DEFAULT/USER/DRONE_PROFILE) existe; `DRONE_PROFILE` **sin poblar** desde DB → diseño/deuda 10G. | **CONFIRMED → DEUDA 10G** |

Documentos de análisis: `phase-10f-coverage-umm11.md`, `phase-10f-lchm-split.md`,
`phase-10f-export-matrix.md`, `phase-10f-drone-dynamics.md`.

---

## B. Entregables

| Entregable | Contenido |
|---|---|
| `schemas/schemas.py` | `ExportUmmRequest`, `ExportCheckUmmRequest/Response`, `ExportReadinessStatus` (READY/WARNING/BLOCKED), `ExportReadinessItem` |
| `modules/export/readiness.py` | **nuevo**: `check_mission_readiness(mission, fmt)` ejecuta el exporter real (`validate`/`get_warnings`) → READY/WARNING/BLOCKED con códigos `split_required`, `turn_radius_invalid`, `turn_radius_warning`, `validation` |
| `api/v1/endpoints.py` | `POST /export/umm/{fmt}` (UMM → exporter, `options` override), `POST /export/check-umm`. **Rutas UMM registradas ANTES de `/export/{fmt}`** (conflicto de ruta corregido) |
| Tests nuevos | `test_export_readiness.py` (6), `test_e2e_10f.py` (5, Casos A–E) |
| Frontend | `project.ts` (tipos 10F), `api.ts` (`export.umm`, `export.checkUmm`), panel de export (readiness LCHM, descarga del UMM) |
| Docs | este informe + 4 análisis (sección A) |

---

## C. Diseño

### C.1 Export de la UMM (punto 9)

`POST /export/umm/{fmt}` transforma la misión con `from_universal_mission` (única
fuente de adaptación, sin recálculo) y serializa con el **exporter real** — el
archivo resultante representa exactamente la misión planificada. `options`
opcional permite override (p. ej. `photo_capture`/`path_mode`) sin tocar la UMM.
El exporter conserva la **validación final** (400 si falla, p. ej. > 99 WP).

### C.2 Readiness (punto 8)

`POST /export/check-umm` → por formato, `check_mission_readiness` usa el
`validate`/`get_warnings` del exporter real: READY (vuela), WARNING (turn
CONSTRAINED, warnings), BLOCKED (`split_required` > 99, turn INVALID). El panel
bloquea la descarga del LCHM cuando `split_required`.

### C.3 Rutas (orden corregido)

`/export/umm/{fmt}` y `/export/check-umm` se registran **antes** de
`/export/{fmt}`; de lo contrario `/export/check-umm` era capturada por
`/export/{fmt}`. Verificado por `test_api_check_umm_readiness_*`.

---

## D. Estado por punto 10F

| # | Punto 10F | Estado | Evidencia |
|---|---|---|---|
| 1 | Auditar el área (engine vs UMM vs builder) | **CONFIRMED** | sección A.1 |
| 2 | Resolver sin duplicar fórmulas (UMM = fuente única) | **PASS** | C.2; adapters intactos |
| 3 | Cobertura (`area_cubierta`) | **DATA_REQUIRED (10F) → DEUDA 10G** | `phase-10f-coverage-umm11.md`; `test_coverage_is_data_required` intacto |
| 4 | Split 99 WP | **4A PASS / 4B DEUDA 10G** | `phase-10f-lchm-split.md`; readiness `split_required`; Caso B E2E |
| 5 | Matriz de compatibilidad exporters | **PASS** | `phase-10f-export-matrix.md`; readiness por formato |
| 6 | Drone dynamics (provenance DRONE_PROFILE) | **DEUDA 10G** | `phase-10f-drone-dynamics.md`; enum ya existe |
| 8 | Readiness por formato | **PASS** | C.2; `test_export_readiness.py` (6) |
| 9 | Export de la UMM | **PASS** | C.1; `test_api_export_umm_*`, Casos A/E |

**Veredicto de fase (parte conservada):** 1 **CONFIRMED** · 7 **PASS** · 1
**DATA_REQUIRED** (→ DEUDA 10G) · 0 **FAIL** · 0 **UNKNOWN**. Cobertura, split
4B y drone dynamics quedan como **deuda 10G** (diseño documentado, sin tocar UMM
1.0 ni motores). El flujo Apply del optimizer (puntos 7, 10, 11 y 12) fue
eliminado posteriormente junto con el módulo `optimizer/`.

---

## E. Frontend (punto 11)

`ExportPanel` consume `export.umm('litchi_lchm', { mission })` para descargar el
LCHM de la misión actual y `export.checkUmm` para el readiness por formato
(READY/WARNING/BLOCKED con `split_required`; bloqueo de descarga cuando
BLOCKED). **El cliente no recalcula nada.**

---

## F. Regresiones

| Gate | Resultado |
|---|---|
| `pytest` backend completo | **332 passed** |
| `ruff check .` / `ruff format --check .` | limpio |
| frontend `tsc --noEmit` | OK |
| frontend `vitest run` | **83 passed** |
| frontend `vite build` | OK (aviso pre-existente de chunk > 500 kB) |

**Sin commit** (política).

---

## G. Deuda para 10G

1. **Coverage medible**: UMM ≥ 1.1 con `survey_area_m2`/`covered_area_m2`
   (spec en `phase-10f-coverage-umm11.md`); hasta entonces DATA_REQUIRED.
2. **Split automático LCHM > 99**: implementar 4B (chunks por líneas de vuelo)
   según `phase-10f-lchm-split.md`; hoy se detecta y bloquea.
3. **Drone dynamics DRONE_PROFILE**: poblar `_drone_dynamics_profile` desde la
   fila de `Drone` (cadena USER → DRONE_PROFILE → DEFAULT).
4. **E2E DJI/QGC en UI**: el readiness solo cubre `litchi_lchm` en el panel; el
   check por formato está disponible vía API para cualquier exporter.