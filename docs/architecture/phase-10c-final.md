# Fase 10C — Informe final (Photogrammetry Mission Optimizer)

**Fecha:** 2026-08-18
**Referencia:** `phase-10b-final.md` (estado antes de la fase).
**Tests finales:** backend **463 passed** (baseline 10B: 332) · frontend **91 vitest passed** · `tsc --noEmit` OK · `vite build` OK · **ruff check y format limpios**.

La Fase 10C implementó por completo el **Photogrammetry Mission Optimizer
determinista**: generador de candidatos, variables de optimización, constraints,
construcción de misiones candidatas, evaluación, selección (mejor + alternativas
diversas), explicación, `Optimizer.solve()` orquestador, endpoint
`POST /api/v1/optimizer/solve` y el frontend de optimización. Cerró además los dos
cabos que la Fase 10B dejó pendientes: la **calibración de pesos** de scoring y la
decisión del **guard de 99 waypoints del exportador LCHM**, y limpió el **lint
preexistente** del backend.

Reglas respetadas: el optimizer **orquesta, no reemplaza** los motores — no se
tocaron `planning/core/*`, `core/photogrammetry/capture_interval.py` ni
`planning/turn_radius/*`; la estructura binaria de LCHM no cambió. **Sin commit.**

---

## A. Qué se implementó (10C-1 → 10C-15)

| Sub-fase | Entregable |
|---|---|
| 1 | **`optimizer/generator.py` + `CandidateConfig`/`CandidateGenerationResult`** — producto cartesiano determinista con decimación (reduce la variable con menos valores) y truncado por `max_candidates`; nunca descarta en silencio (`truncated`, `strategy`). 17 tests |
| 2 | **`optimizer/variables.py`** — `VariableMode` FIXED/RANGE/CANDIDATE_VALUES; RANGE con `Decimal` inclusivo sin deriva; nombre desconocido → `ValueError`. 20 tests |
| 3 | **`OptimizationConstraints` ampliado + `optimizer/constraints.py`** — `ConstraintReport` PASS/WARNING/FAIL; WARNING no invalida, FAIL invalida y pliega el score (×0.5). 20 tests |
| 4 | **`optimizer/candidate_builder.py` + `CandidateBuilder` + `mission_to_request`** — reconstruye la misión desde el request base aplicando la asignación de variables; `speed_mps` no inyectable → recálculo post-build (turn radius + métricas + capture interval); `photo_interval_s` override. 17 tests |
| 5 | **`optimizer/evaluator.py`** — `evaluate_candidates()` con try/except → `REJECTED` (nunca silencioso). 5 tests |
| 6 | **`optimizer/selection.py`** — `select_best()`: ranking score desc, empates por índice, alternativas reconstruidas desde `variable_values`. 9 tests |
| 7 | **Variabilidad** — `_similar()` (rel_diff < `diversity_tolerance` por variable) con fallback a casi-duplicados; `diverse_count`. 5 tests |
| 8 | **`optimizer/explanation.py`** — `explain()` derivado solo de datos reales (summary/reasons/warnings/stats), sin umbrales hardcodeados; advisories batería/`overhead_fallback`/banda GSD. 11 tests |
| 9 | **`optimizer/optimizer.py`** — `Optimizer.solve()`: status OPTIMAL/FEASIBLE/CONSTRAINED/NO_SOLUTION; `OptimizerInput.request` fuente autoritativa; ruta single-candidate. 9 tests |
| 10 | **API** — `POST /api/v1/optimizer/solve` (`OptimizerSolveRequest/Response`); schemas API no importan el paquete optimizer; respuesta con misión UMM + score por candidato. 10 tests |
| 11 | **Frontend** — módulo `frontend/src/modules/optimizer/`: `OptimizerPanel.tsx` (variables con modos Range/Values/Fixed, constraints, max_candidates, resultado con mejor candidato/alternativas/explanation/warnings), `optimizerStore.ts`, `optimizerRequest.ts`, tab **Optimizer** en la sidebar, `api.optimizer.solve`, tipos en `project.ts`. 8 tests |
| 12 | **Calibración de pesos** — `OptimizationWeights` con defaults documentados (safety/gsd/overlap/coverage 1.0, time/battery 0.8, turn 0.6, photo_count 0.5) + validación (no negativos, ≥1 positivo). 5 tests |
| 13 | **Guard LCHM 99 waypoints** — `LitchiLchmExporter.export()` invoca `LchmValidator().validate_mission` antes de serializar: rechaza >99 con `LchmValidationError` (el header u8 envolvería el conteo y produciría un archivo corrupto); la estructura binaria no cambió. 3 tests |
| 14 | **Lint preexistente** — `ruff check` 243 errores → **0** (49 auto + manuales); `ruff format` 67 archivos; excepción E501 solo para `seed_data.py` (datos densos). Sin cambios de comportamiento |
| 15 | **Informe final** `phase-10c-final.md` + regresión completa |

**Regresiones backend por sub-fase:** 332 → 389 → 406 → 411 → 420 → 425 → 436 → 445 → 455 → 463.

---

## B. Arquitectura después

```
modules/optimizer/                ← Photogrammetry Mission Optimizer (orquestador)
  variables.py        expansión determinista de variables (10C-2)
  generator.py        producto cartesiano + decimación + truncado (10C-1)
  candidate_builder.py  CandidateBuilder: request base → misión candidata (10C-4)
  evaluator.py        evaluate_candidates() (10C-5)
  constraints.py      evaluate_constraints → ConstraintReport (10C-3)
  objective.py        score_mission [0,1] (pesos calibrados 10C-12)
  selection.py        select_best() + diversidad (10C-6/7)
  explanation.py      explain() (10C-8)
  optimizer.py        Optimizer.solve() (10C-9)
  models.py           tipos de todo el pipeline

modules/mission/                 ← UMM (10A/10B, intacto)
modules/planning/core|turn_radius ← motores (intactos, regla 10C)

api/v1/endpoints.py              POST /optimizer/solve (10C-10)
schemas/schemas.py               OptimizerSolveRequest/Response
frontend/src/modules/optimizer/  OptimizerPanel + optimizerStore (10C-11)
modules/export/litchi_lchm.py    guard >99 waypoints (10C-13)
```

**Flujo `solve()`:** `OptimizerSolveRequest` (exactamente uno de `grid`/`corridor`)
→ misión base UMM → `OptimizationVariables` expandidas → `CandidateGenerator`
→ por candidato: `CandidateBuilder` reconstruye la misión → `evaluate()` (validator
+ constraints + score) → `select_best()` (mejor + alternativas diversas) →
`explain()` → respuesta API con la misión UMM del mejor candidato y su score.

---

## C. Variables de optimización

`altitude_m`, `speed_mps`, `front_overlap`, `side_overlap`, `photo_interval_s`,
`turn_radius_m` con modos `fixed` / `range` (Decimal inclusivo, sin deriva) /
`candidate_values`. `speed_mps` y `photo_interval_s` no se inyectan en el request
(no existen como tal en `GridRequest`/`CorridorRequest`): el builder los aplica
recálculando turn radius, métricas y bloque de captura. El generador es
determinista: mismo input → mismo orden y valores, incluso bajo truncado
(decimación de la variable con menos valores + conservación de extremos).

---

## D. Constraints y scoring calibrado

- `ConstraintReport`: PASS/WARNING/FAIL por constraint (`altitude_m`, `gsd_cm`,
  `speed_ms`, `overlap_frontal/lateral`, `mission_time_s`, `mission_distance_m`,
  `photo_interval_s`, `turn_radius_m`, `turn_extension_m`, `photo_count`,
  `capture_plan.commercial_interval_s`). WARNING no invalida; FAIL invalida y
  pliega el score ×0.5. `allowed_capture_intervals` es específico de plataforma
  (Litchi) y no se asume universal.
- `score_mission`: promedio ponderado de los criterios computables (los que no
  aplican se omiten). **10C-12** fijó los defaults: calidad de datos (gsd,
  overlap, coverage) y seguridad dominan; tiempo/batería (0.8) en segundo nivel;
  giro (0.6) y recuento de fotos (0.5) al final. `OptimizationWeights` valida
  pesos no negativos y ≥1 positivo.

---

## E. API `POST /api/v1/optimizer/solve`

| Petición | Respuesta |
|---|---|
| `grid` **o** `corridor` (exactamente uno) + `variables` (opcional) + `constraints`/`weights` (opcionales) + `max_candidates≥1` | `status` (OPTIMAL/FEASIBLE/CONSTRAINED/NO_SOLUTION), `message`, `best_candidate` (label, `variable_values`, misión UMM, score), `best_score`, `alternatives[]`, `stats` (total/evaluated/valid/invalid/rejected), `warnings`, `explanation` |

Sin variables → evaluación single-candidate. Sin solución factible →
NO_SOLUTION. Truncado por `max_candidates` → CONSTRAINED. Con advertencias →
FEASIBLE; sin ellas → OPTIMAL. Errores de entrada → 400 (variables desconocidas,
modo inválido, constraints inválidas) o 422 (`max_candidates=0`).

---

## F. Frontend

Nueva pestaña **Optimizer** en la sidebar (`Sidebar.tsx`/`sidebarStore.ts`) que
abre `OptimizerPanel`:

- **Variables**: 6 filas con modo Range/Values/Fixed y campos según modo; por
  defecto `altitude_m` y `speed_mps` en modo Range.
- **Constraints**: 14 campos numéricos opcionales (altitud, velocidad, GSD,
  overlaps, tiempo, baterías, fotos, turn radius preferido).
- **max_candidates** + botón *Optimize Mission*.
- **Resultado**: badge de status, mensaje, estadísticas del batch, mejor
  candidato (score + GSD/fotos/tiempo/baterías/distancia/waypoints de su UMM),
  alternativas (plegables), motivos de la explicación y warnings.
- `optimizerStore.solve()` construye el payload grid/corridor desde los stores de
  planning/draw/turn-radius (helpers puros en `optimizerRequest.ts`) y llama a
  `api.optimizer.solve`.

---

## G. Guard LCHM 99 waypoints

Decisión 10C-13: el header LCHM guarda el conteo en un **u8** (offset 43) y
Litchi limita a 99 waypoints; exportar más envolvería el conteo (352 mod 256 = 96)
y `parse_lchm` se desalinearía. `LitchiLchmExporter.export()` ahora llama a
`LchmValidator().validate_mission` **antes** de serializar y rechaza con
`LchmValidationError`. La estructura binaria **no cambió**; el guard complementa
el `validate()` de la API que ya reportaba el error.

---

## H. Tests

- Backend **463 passed** (baseline 10B: 332). Nuevos en 10C: 128 tests en
  `test_optimizer{,_generator,_variables,_constraints,_candidates,_selection,
  _explanation,_solve}.py`, `test_candidate_builder.py`,
  `test_api_optimizer_solve.py` + 5 de pesos (10C-12) + 3 del guard LCHM (10C-13).
- Frontend **91 vitest passed** (baseline 10B: 83) incl. `optimizerStore.test.ts`
  (8). `tsc --noEmit` y `vite build` OK.
- **ruff check 0 errores** (243 → 0) y **ruff format** en 67 archivos; la única
  excepción es E501 para `seed_data.py` (per-file-ignores, datos densos).

---

## I. Regresión y compatibilidad

- LCHM / Grid / Corridor / CaptureInterval / TurnRadius / Exporters: sin cambios
  de comportamiento (toda la suite 10A/10B en verde).
- El guard de 99 waypoints solo añade una validación previa a serializar; los
  casos ≤99 (incl. fixtures binarios 74 wp TIME=5, corridor TIME=5, DISTANCE=20.5,
  NONE) exportan idéntico.
- La calibración de pesos es determinista y overridable por request; el
  `OptimizationWeights()` default cambió (antes uniforme 1.0), sin romper
  aserciones de los tests existentes (relacionales, no absolutas).

---

## J. Deuda técnica y riesgos

- **Fixtures >99 waypoints en LCHM**: el guard **rechaza**; el *splitting* de
  misiones en múltiples archivos LCHM no está implementado y queda fuera de 10C
  (decisión de producto, no de formato).
- **`datetime.utcnow()` deprecado** en `endpoints.py`/`models.py` de export
  (57 warnings de pytest) — cosmético, fuera de alcance.
- El frontend no aplica todavía el mejor candidato sobre el mapa/paneles de
  planificación (solo lo muestra); la integración con `planningStore` es trabajo
  futuro si se desea "plan óptimo vs plan actual".
- `git` sigue **sin commit** de la fase (política del proyecto).

---

## K. Qué queda (fuera de alcance de 10C)

- Splitting de misiones >99 waypoints para LCHM.
- Aplicar el mejor candidato del optimizer al flujo de planificación del frontend.
- Calibración fina de pesos con datos reales de misión (los defaults 10C-12 son
  deterministas y razonables, no optimizados contra un corpus).
- Migración de los warnings `utcnow` deprecado.