# Fase 10D — Validación funcional del Photogrammetry Mission Optimizer

**Fecha:** 2026-08-18
**Referencia:** `phase-10c-final.md` (estado antes de la fase).
**Tests finales:** backend **506 passed** (463 al cierre de 10C → +43 nuevos de la suite `tests/optimizer/`) · frontend **91 vitest passed** · `tsc --noEmit` OK · `vite build` OK · **ruff check y format limpios**.

La Fase 10D no implementa funcionalidad nueva: **valida** el Photogrammetry
Mission Optimizer de la 10C contra los motores reales de planificación y cierra
el diagnóstico del comportamiento del **score**, de la cadena
**turn radius / capture interval / LCHM**, del **determinismo**, de la
**mejora real sobre el baseline** y del **guard LCHM de 99 waypoints**.

Reglas respetadas: fase de validación/integración/diagnóstico. No se modificaron
`planning/core/*`, `core/photogrammetry/capture_interval.py`,
`planning/turn_radius/*` ni `export/litchi_lchm.py`. Se corrigió **un único
defecto real** (en `optimizer/evaluator.py`) demostrado por un test nuevo — se
detalla en la sección F. **Sin commit.**

---

## A. Entregables

| Entregable | Contenido |
|---|---|
| `tests/optimizer/__init__.py` | paquete de tests (tests/ es paquete) |
| `tests/optimizer/conftest.py` | fixture `db` module-scoped (cámara `cam-1-20mp` + dron `dji-p4rtk`, sqlite in-memory) |
| `tests/optimizer/corpus.py` | corpus de 12 misiones reales + `get_case` + `lchm_export_status` |
| `tests/optimizer/test_optimizer_real_cases.py` | matriz de cobertura, determinismo (3 runs), mejora real sobre el baseline, métricas del ganador, estado LCHM >99 sin auto-split (9 tests) |
| `tests/optimizer/test_optimizer_score_breakdown.py` | auditoría de la fórmula ponderada, normalización, sensibilidad a pesos, orden calibrado, **scores binarios entre candidatos válidos**, diferenciación turn/safety, fold de FAIL (9 tests) |
| `tests/optimizer/test_optimizer_constraints.py` | box completo → OPTIMAL, WARNING no elimina, FAIL elimina, box parcial, NO_SOLUTION, rejected reportado (12 tests) |
| `tests/optimizer/test_optimizer_turn_capture_integration.py` | cadena speed→radius→turn time→batería, arco real vs fallback, MANUAL, CONSTRAINED espacial, capture interval (consumido no reproducido), floor solo en adapter, TIME/DISTANCE/NONE, roundtrip LCHM del candidato optimizado (13 tests) |
| `docs/architecture/phase-10d-validation.md` | este informe |

**43 tests nuevos** (todos contra motores reales, sin mocks de planificación).

---

## B. Corpus de validación (misiones reales)

| case_id | Descripción | Estado clave |
|---|---|---|
| `grid_small_time` | grid ~200×200 m @100 m, 75/65, modo vértice, captura TIME (motor) | **LCHM_OK** (6 wps) |
| `grid_small_low_alt` | grid small @80 m | GSD 2.19, 36 fotos |
| `grid_small_high_alt` | grid small @140 m | GSD 3.83, 10 fotos |
| `grid_small_overlap_high` | grid small @100 m, 85/75 | espaciados más densos |
| `grid_large_over_99` | grid ~1.8×2.2 km @60 m | **LCHM_UNSUPPORTED_WAYPOINT_COUNT** (140 wps) |
| `grid_small_fast` / `grid_small_slow` | AUTO turns @10 / @4 m/s | CONSTRAINED / VALID |
| `grid_small_turn_manual_small/large` | MANUAL 5 / 25 m | VALID / VALID-para motor, INVALID para validador (25>available) |
| `grid_small_capture_distance` / `_none` | captura DISTANCE (15 m) / NONE | sintéticos: el motor solo emite TIME |
| `corridor_vertex` | corredor recto ~3 km, 100/100 m, AUTO turns | LCHM_OK (12 wps) |

Cada caso conserva el **request original + la Universal Mission construida**,
de modo que los tests pueden re-derivar cualquier métrica sin re-planificar.

---

## C. Hallazgos confirmados con motores reales (CONFIRMED / PASS)

### C.1 Determinismo del search (10D punto 2) — PASS
3 solves idénticos sobre `grid_small_time` [80,100,120]: `status`, variable del
ganador, `total_score`, alternativas, scores por evaluación, summary/reasons/
stats **y la misión UMM completa** (excluyendo `created_at`) son iguales.
Con constraints + pesos también. *Test: `test_determinism_across_repeated_runs`,
`test_determinism_with_constraints_and_weights`.*

### C.2 El optimizador mejora de verdad sobre el baseline (10D punto 3) — PASS
Baseline `grid_small_time` = 21 fotos. Con `max_photo_count=20` el baseline es
INVALID; la búsqueda [80,100,120,140] devuelve OPTIMAL con ganador **altitud 120**
(18 fotos, GSD 3.29 dentro de banda [2,4]): satisface el presupuesto y reduce
fotos reales. *Test: `test_optimizer_improves_over_baseline`.*

### C.3 Estado LCHM explícito >99, sin auto-split (10D punto 8) — PASS
El grid grande excede 99 waypoints; `lchm_export_status` lo reporta como
`LCHM_UNSUPPORTED_WAYPOINT_COUNT` y el exportador **rechaza** con
`LchmValidationError("LCHM supports at most 99 waypoints…")` (guard 10C-13) en
lugar de envolver el conteo. **No existe auto-split aún** → deuda para 10E.
*Test: `test_large_mission_lchm_unsupported_no_auto_split`.*

### C.4 Cadena speed → radius → turn time → tiempo → batería (10D punto 6) — PASS
En grid small con AUTO turns: 4 m/s → radio 4.44 VALID; 6.8 → 12.84 VALID;
10 y 14 → **CONSTRAINED en el tope espacial** `(line_spacing − 2·clearance)/2 =
(52.45 − 8)/2 ≈ 22.22 m`. El radio crece con v² mientras es VALID
(r6.8/r4 ≈ (6.8/4)²). Batería recomputada siempre por fórmula real
`max(1, ceil((flight_time_s/60)/(30·0.8)))` (el grid grande @4 m/s → 22). El
optimizador usa el **arco real** (`turn_source = "turn_plan"`, `turn_time_s =
Σ turn_duration_s`) y el fallback `num_lines·5` solo sin turn config. El
**MANUAL 25 m se mantiene** (el motor confía en el usuario) pero el **validador
lo marca INVALID** porque excede el `available_radius_m` del grid → hallazgo.
*Tests: `test_speed_drives_turn_radius_and_status`, `test_radius_scales…`,
`test_space_constrained_radius_caps_at_available`,
`test_arc_turn_times_used_instead_of_fallback`, `test_battery_recomputed…`,
`test_manual_turn_radius_is_honored`.*

### C.5 Capture interval: consumido, no reproducido (10D punto 7) — PASS
`compute_capture_interval(footprint_height, overlap_frontal, speed)` reproduce
exactamente `capture_plan.commercial_interval_s` (la UMM es la fuente, el motor
no se re-ejecuta en el optimizer). La velocidad fuerza el intervalo (4→6 s,
6.8→3 s, 10→2 s, 12→2 s, 15→1 s, monótono no creciente). El valor científico
decimal **NO se trunca en la UMM** (`photo_interval_s=5.3` → 5.3 en
`scientific_interval_s` y `parameters.capture_interval_s`); el floor es **solo
del adapter Litchi** (`normalize_litchi_time_interval(5.3)=5`, nunca redondea
arriba) y el adapter **prefiere `commercial_interval_s`**. TIME / DISTANCE /
NONE → `photo_capture` correcto, y DISTANCE serializa al trailer LCHM.
*Tests: `test_capture_interval_consumed_not_reproduced`,
`test_speed_forces_capture_interval_change`,
`test_scientific_decimal_not_floored_in_umm`,
`test_litchi_floor_policy_never_rounds_up`,
`test_adapter_floors_scientific_when_no_commercial`,
`test_capture_modes_time_distance_none`, `test_distance_capture_exports_to_lchm`.*

### C.6 Roundtrip LCHM del candidato optimizado (10D punto 8) — PASS
Un candidato con AUTO turns @6.8 m/s → export → `parse_lchm`: path
`CURVED_TURNS`, heading `FOLLOW_PATH`, conteo exacto, coords/speed 6.8/heading
coincidentes, **curve 0 en primer/último waypoint y radio 12.84 en interiores**
(encaje con el fichero físico de referencia). *Test:
`test_lchm_roundtrip_of_turn_candidate`.*

### C.7 Constraint box integrado (10D punto 5) — PASS
Box completo (GSD, overlaps, altitud, speed, batería, tiempo, distancia, foto,
intervalo, intervalos Litchi permitidos) → **OPTIMAL**, 3/3 válidos.
**WARNING no elimina** (preferred_turn_radius ≠ actual → FEASIBLE con warnings;
constraint no evaluable → WARNING, nunca FAIL). **FAIL elimina**
(`max_photo_count=20` invalida 80/100, ganador 120). Box parcial (`min_gsd=3`)
deja solo 120/140. Todos inválidos → **NO_SOLUTION**. Candidates `REJECTED`
reportados, nunca silenciados. *Tests: `test_full_constraint_box_passes`,
`test_warning_does_not_eliminate_candidate`, `test_fail_eliminates…`,
`test_partial_box…`, `test_all_invalid_yields_no_solution`,
`test_rejected_candidates_reported_in_stats`.*

### C.8 Auditoría del score (10D punto 4) — CONFIRMED
- Fórmula ponderada reprodujo el `total_score` exactamente; scores normalizados
  en [0,1]; sensibilidad a pesos coherente (subir `gsd` con GSD fuera de banda
  arrastra el total hacia 0.5); orden calibrado respetado
  (safety/gsd/overlap/coverage ≥ time/battery > turn > photo_count).
  *Tests: `test_weighted_formula_reproduces_total_score`,
  `test_scores_normalized_to_unit_interval`, `test_weight_sensitivity_is_coherent`,
  `test_calibrated_weights_prioritize_quality_and_safety`.*
- **Hallazgo clave (bloqueo para 10E):** en candidatos VALID reales los scores
  guiados por constraints (gsd/overlap/time/battery/photo_count) son **binarios
  = 1.0**, porque los mismos bounds que producen score parcial también elevan
  FAIL (y un FAIL ya no es candidato). Solo `turn_score`
  (VALID 1.0 / CONSTRAINED 0.75 / NONE 0.5) y `safety_score` (1 − 0.2·warnings)
  diferencian entre factibles. Un FAIL de constraint pliega el total ×0.5.
  *Tests: `test_valid_real_candidates_have_binary_constraint_scores`,
  `test_turn_and_safety_scores_differentiate_real_candidates`,
  `test_constraint_fail_halves_total_score`.*

---

## D. Estado por punto 10D

| Punto 10D | Estado | Evidencia |
|---|---|---|
| 2 determinismo | **PASS** | C.1 |
| 3 mejora real | **PASS** | C.2 |
| 4 auditoría score | **CONFIRMED (con hallazgo)** | C.8 → deuda 10E |
| 5 constraints integrados | **PASS** | C.7 |
| 6 turn radius cadena | **PASS** | C.4 |
| 7 capture interval | **PASS** | C.5 |
| 8 LCHM 99 / roundtrip | **PASS** (sin auto-split) | C.3 / C.6 |
| 10 frontend muestra resultado real | **PASS** | sección E |

Sin estados **FAIL** ni **UNKNOWN** en esta fase: cada punto pudo ser validado.

---

## E. Verificación frontend (punto 10)

`OptimizerPanel.tsx` **muestra exclusivamente el resultado del backend**:
`result.status` / `message` / `stats`, `best_candidate` (métricas UMM, p. ej.
`mission.metrics.gsd_cm`), `best_score`, `alternatives`, `explanation.reasons`
y `warnings` — **no recalcula GSD, geometría, turn radius ni capture interval**
en el cliente. Gates: `tsc --noEmit` OK, **91 vitest passed** (8 de
`optimizerStore.test.ts`), `vite build` OK (aviso pre-existente de chunk > 500 kB).

---

## F. Defecto encontrado y corregido (demostrado por test)

**`optimizer/evaluator.py` — crash con warnings del validador.** `evaluate()`
construía `warnings` como `list(validation.warnings)` (objetos `ValidationIssue`)
mezclados con strings de constraints, pero `EvaluationResult.warnings` es
`list[str]` → **pydantic ValidationError** en cualquier misión válida con
warnings del validador (p. ej. un turn plan CONSTRAINED, que añade
`turn_warning`). El test nuevo
`test_turn_and_safety_scores_differentiate_real_candidates` lo demostró.
**Fix:** `warnings = [f"{w.code}: {w.message}" for w in validation.warnings]`
(el bloque estructurado `validation.warnings` ya viaja en el propio resultado).
Regresión completa: **506 passed**, ruff limpio.

---

## G. Deuda para 10E (no implementada en 10D — fase de validación)

1. **El score no rankea preferencia fotogramétrica entre candidatos factibles**
   (C.8): con los bounds actuales todo candidato VALID empata en 1.0, por lo que
   `time_score`/`battery_score`/`photo_count_score` son decorativos y la
   selección recae en turn/safety o el índice. Requiere rediseño del criterio
   (p. ej. optimizar hacia el interior de la banda GSD, minimizar tiempo/batería
   dentro del límite, o score continuo por separación del bound) + re-calibración
   de pesos + re-validación con los tests de score_breakdown.
2. **Auto-split de misiones >99 waypoints para LCHM** (C.3): hoy el estado es
   explícito `LCHM_UNSUPPORTED_WAYPOINT_COUNT`; no hay partición multi-misión.
3. **Polígono canónico de los tests 10C** (`[-5.99,-5.94]×[37.35,37.39]`) es en
   realidad **~4.4 km × 4.4 km → 168 waypoints a 100 m**, ya por encima de 99:
   los tests de la 10C que lo usan asumen implícitamente un caso pequeño. La
   suite 10D introduce `SMALL_POLYGON` (~200 m) para casos < 99; migrar los
   tests 10C a un polígono pequeño explícito quitaría la ambigüedad.
4. **`turn_time_s` vacío en la misión base**: `build_universal_mission` (sin
   variable `speed_mps`) deja `metrics.turn_time_s = 0.0` con
   `turn_source = overhead_fallback`; solo `_recompute_metrics` (variable
   `speed_mps`) lo rellena. El optimizer es correcto, pero el dato base puede
   sorprender en pantalla.
5. **Speed override no propagado a la búsqueda**: si la misión base lleva una
   velocidad manual (6.8) y la búsqueda no declara `speed_mps`, los candidatos
   se reconstruyen con la velocidad recomendada del motor (6.85). Esperado por
   diseño (el request no lleva speed), pero conviene documentarlo en la UI.

---

## H. Resumen de regresiones

| Gate | Resultado |
|---|---|
| `pytest tests/optimizer` | **43 passed** |
| `pytest` backend completo | **506 passed** |
| `ruff check .` / `ruff format --check .` | limpio |
| frontend `tsc --noEmit` | OK |
| frontend `vitest run` | **91 passed** |
| frontend `vite build` | OK |

**Sin commit** (política). Fase 10D completa.