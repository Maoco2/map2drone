# Fase 10F — Integración operacional del Optimizer (Apply → UMM → Export)

**Fecha:** 2026-08-18
**Referencia:** `phase-10e-final.md` (score continuo) y auditoría 10F (área,
cobertura, split, readiness, drone dynamics, matriz de exporters).
**Tests finales:** backend **545 passed** (520 al cierre de 10E → +25 nuevos:
19 de apply/readiness + 6 E2E) · frontend **91 vitest passed** ·
`tsc --noEmit` OK · `vite build` OK · **ruff check y format limpios**.

La Fase 10F cierra la cadena operacional `Planning → Optimizer → Winner →
Apply → UMM → Export`: el backend aplica el winner como **misión nueva**
(conservando la original), verifica que es reproducible (gate 12), expone el
diagnóstico de exportabilidad (readiness) y permite exportar el **UMM del winner**
directamente (LCHM/Litchi), sin reconstruir nada en el frontend.

Reglas respetadas: no se tocó `planning/core/*`,
`core/photogrammetry/capture_interval.py`, `planning/turn_radius/*`,
`export/litchi_lchm.py`, la **UMM schema 1.0** ni los adapters de export. Se
tocaron `optimizer/apply.py`, `export/readiness.py` (nuevos), endpoints,
schemas, tests y frontend (tipos, api, store, panel). **Sin commit.**

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
| `schemas/schemas.py` | `OptimizerApplyRequest`, `OptimizerApplyResponse`, `MissionComparisonItem`, `ExportUmmRequest`, `ExportCheckUmmRequest/Response`, `ExportReadinessStatus` (READY/WARNING/BLOCKED), `ExportReadinessItem` |
| `modules/optimizer/apply.py` | **nuevo**: baseline (`build_base_mission` espeja el flujo de planificación), verificación determinista (`_verify_winner` vía `CandidateBuilder.build`, `_canonical`), comparación Baseline vs Winner (14 métricas), `_modified_variables`, `persist_winner` (nueva fila Mission; baseline/comparación/verificación en `parameters_json["optimizer_apply"]`; `grid_result_json` = UMM winner), `apply_winner` |
| `modules/export/readiness.py` | **nuevo**: `check_mission_readiness(mission, fmt)` ejecuta el exporter real (`validate`/`get_warnings`) → READY/WARNING/BLOCKED con códigos `split_required`, `turn_radius_invalid`, `turn_radius_warning`, `validation` |
| `api/v1/endpoints.py` | `POST /optimizer/apply` (WinnerMismatchError→**409**, ValueError→400), `POST /export/umm/{fmt}` (UMM → exporter, `options` override), `POST /export/check-umm`. **Rutas UMM registradas ANTES de `/export/{fmt}`** (conflicto de ruta corregido) |
| Tests nuevos | `test_api_optimizer_apply.py` (10), `test_optimizer_apply.py` (4), `test_export_readiness.py` (6), `test_e2e_10f.py` (6, Casos A–F) |
| Frontend | `project.ts` (tipos 10F), `api.ts` (`optimizer.apply`, `export.umm`, `export.checkUmm`), `optimizerStore.ts` (`lastSolveRequest` capturado, `applyWinner`, `applyResult`), `OptimizerPanel.tsx` (Apply winner, tabla Baseline vs Winner, variables modificadas, verificación, readiness LCHM, descarga del LCHM del winner) |
| Docs | este informe + 4 análisis (sección A) |

---

## C. Diseño

### C.1 Apply Winner (puntos 7 y 10)

`POST /optimizer/apply` recibe el **solve_request original + el winner del solve**
(exactamente la misión evaluada, no una reconstrucción del cliente) y, en el
backend:

1. Re-deriva el **baseline** con `build_base_mission` (misma cadena de
   planificación) y lo puntúa con el mismo pipeline de 10E.
2. **Verifica el winner** (`_verify_winner`): si hay `variable_values`, reconstruye
   con `CandidateBuilder.build` y compara la firma canónica (`_canonical`) con la
   misión enviada. Divergencia → **409 WinnerMismatchError** (gate 12). Sin
   `variable_values` → passthrough documentado (camino de candidato único).
3. Construye la **comparación** Baseline vs Winner (altitud, GSD, overlaps,
   velocidad, intervalo, spacing, fotos, distancia, tiempo, giros, radio,
   baterías, score) y las **variables modificadas**.
4. **Persiste** el winner como **nueva fila `Mission`** (la original nunca se
   toca): `grid_result_json` = UMM del winner, `parameters_json["optimizer_apply"]`
   = {original_mission_id, modified_variables, comparison, verification,
   baseline_mission, baseline_score, winner_score}. Límite de 30 misiones/proyecto.
5. Devuelve baseline_mission, baseline_score, winner_mission, winner_score,
   comparison, modified_variables, verification (`verified`), warnings,
   mission_id.

### C.2 Export del UMM del winner (punto 9)

`POST /export/umm/{fmt}` transforma la misión con `from_universal_mission` (única
fuente de adaptación, sin recálculo) y serializa con el **exporter real** — el
archivo resultante representa exactamente el winner evaluado. `options` opcional
permite override (p. ej. `photo_capture`/`path_mode`) sin tocar la UMM. El
exporter conserva la **validación final** (400 si falla, p. ej. > 99 WP).

### C.3 Readiness (punto 8)

`POST /export/check-umm` → por formato, `check_mission_readiness` usa el
`validate`/`get_warnings` del exporter real: READY (vuela), WARNING (turn
CONSTRAINED, warnings), BLOCKED (`split_required` > 99, turn INVALID). El panel
bloquea la descarga del LCHM cuando `split_required`.

### C.4 Rutas (orden corregido)

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
| 7 | Apply Winner backend (baseline + verificación + persistencia) | **PASS** | C.1; `test_optimizer_apply.py` (4) |
| 8 | Readiness por formato | **PASS** | C.3; `test_export_readiness.py` (6) |
| 9 | Export del UMM del winner | **PASS** | C.2; `test_api_export_umm_*`, Casos A/C |
| 10 | Persistencia (misión nueva, original intacta) | **PASS** | `persist_winner`; E2E mission_id + blobs |
| 11 | Frontend (apply + comparación + readiness + descarga) | **PASS** | sección E |
| 12 | Gate verificación winner (re-derive → 409) | **PASS** | `test_api_apply_tampered_winner_409`, `test_apply_winner_tampered_mission_raises` |
| 13 | Tests mínimos + regresiones | **PASS** | sección F |

**Veredicto de fase:** 1 **CONFIRMED** · 10 **PASS** · 1 **DATA_REQUIRED** (→
DEUDA 10G) · 0 **FAIL** · 0 **UNKNOWN**. Cobertura, split 4B y drone dynamics
quedan como **deuda 10G** (diseño documentado, sin tocar UMM 1.0 ni motores).

---

## E. Frontend (punto 11)

`OptimizerPanel.tsx` añade `ApplyWinnerSection`: botón "Apply winner mission",
y tras aplicar muestra mission_id, variables modificadas, tabla **Baseline vs
Winner**, scores, badge de verificación (`✓ re-derived`), warnings, readiness
LCHM (READY/WARNING/BLOCKED con `split_required`) y botón **"Download winner
LCHM"** (vía `export.umm('litchi_lchm', { mission: winner_mission })`, bloqueado
si BLOCKED). `optimizerStore.applyWinner` guarda el `solve_request` al resolver
para reutilizarlo. **El cliente no recalcula nada.**

---

## F. Regresiones

| Gate | Resultado |
|---|---|
| `pytest` backend completo | **545 passed** (+25 de 10F) |
| `ruff check .` / `ruff format --check .` | limpio |
| frontend `tsc --noEmit` | OK |
| frontend `vitest run` | **91 passed** |
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