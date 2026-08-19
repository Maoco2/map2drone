# Fase 10E — Rediseño y calibración del Score Fotogramétrico

**Fecha:** 2026-08-18
**Referencia:** `phase-10d-validation.md` (deuda G.1: score binario entre factibles).
**Tests finales:** backend **520 passed** (506 al cierre de 10D → +14 nuevos de
`tests/optimizer/test_optimizer_preferences.py`; 5 tests de 10D actualizados a
la nueva semántica) · frontend **91 vitest passed** · `tsc --noEmit` OK ·
`vite build` OK · **ruff check y format limpios**.

La Fase 10E rediseña el criterio de preferencia del Photogrammetry Mission
Optimizer: separa **factibilidad** (constraints PASS/WARNING/FAIL — intocada)
de **preferencia** (score continuo), reemplaza los scores binarios por
funciones de utilidad continuas en `[0, 1]` con resolución explícita de
objetivos, y expone el **desglose completo del score** en la respuesta
(`score.details`: raw, target, normalized, weight, contribution, status).

Reglas respetadas: no se modificó `planning/core/*`,
`core/photogrammetry/capture_interval.py`, `planning/turn_radius/*`,
`export/litchi_lchm.py`, la **UMM schema 1.0** ni los adapters de export. Solo
se tocó el módulo `optimizer/` (modelos, nuevo `preferences.py`, `objective.py`
como re-export, `explanation.py`) y el frontend. **Sin commit.**

---

## A. Entregables

| Entregable | Contenido |
|---|---|
| `optimizer/models.py` | `ScoreComponentStatus` (SCORED/UNKNOWN/DATA_REQUIRED), `ScoreComponentDetail` (component, label, raw_value, target, normalized_value, weight, contribution, status, message), `MissionScore.details`, y objetivos de preferencia en `OptimizationConstraints`: `preferred_gsd`, `preferred_overlap_front`, `preferred_overlap_side` |
| `optimizer/preferences.py` | **nuevo**: funciones de utilidad continuas (`_tent`, `_one_sided_high/low`), resolución de objetivos por componente y `score_mission` que construye el desglose |
| `optimizer/objective.py` | re-export de `score_mission` (nombre/signatura pública estable) |
| `optimizer/explanation.py` | `_score_breakdown` ahora deriva las razones de `score.details` (incluye targets y estados UNKNOWN/DATA_REQUIRED) |
| `tests/optimizer/test_optimizer_preferences.py` | **nuevo (14 tests)**: continuidad/monotonicidad, resolución de targets, tiempo/batería/fotos lineales, turn con datos reales, coverage DATA_REQUIRED, contribuciones = total, determinismo, sensibilidad a pesos, breakdown en explanation, corpus completo |
| Tests 10D actualizados | `test_optimizer.py`, `test_optimizer_score_breakdown.py`, `test_optimizer_constraints.py` (semántica binaria → continua) |
| `frontend/src/shared/types/project.ts` | `ScoreComponentDetail`, `MissionScore.details`, constraints `preferred_*` |
| `frontend/src/modules/optimizer/optimizerStore.ts` | claves de constraint `preferred_gsd/overlap_front/overlap_side` |
| `frontend/src/modules/optimizer/OptimizerPanel.tsx` | tarjeta de candidato muestra el **breakdown** (raw/target/normalized/status por componente) — **sin recalcular** |
| `docs/architecture/phase-10e-final.md` | este informe |

---

## B. Diseño: factibilidad vs preferencia

La factibilidad sigue viviendo en `constraints.py` (PASS/WARNING/FAIL, sin
cambios) y en `evaluator.py` (fold ×0.5 sobre el total ante FAIL, sin cambios).
`preferences.py` expresa **solo preferencia**: qué tan cerca está el candidato
del objetivo resuelto de cada componente.

Cadena de resolución de objetivo (primera coincidencia):

| Componente | Target | Escala | Si no hay dato |
|---|---|---|---|
| **gsd** | `preferred_gsd` → punto medio de banda [min,max] → bound único | mitad de banda, o `target` si solo preferido | `UNKNOWN` (mensaje: configura un target) |
| **overlap** (por eje) | `preferred_overlap_*` → punto medio de banda → bound único → **overlap del propio request** (siempre disponible) | mitad de banda, o `target` | siempre SCORED |
| **time** | `max_flight_time` | `max(0, 1 − flight_time/budget)` | `UNKNOWN` |
| **battery** | `max_battery_count` | `max(0, 1 − count/budget)` | `UNKNOWN` |
| **photo_count** | `max_photo_count` | `max(0, 1 − count/budget)` | `UNKNOWN` |
| **turn** | datos reales del TurnRadiusEngine: `base(status) × (0.5 + 0.5·fullness)` con `fullness = min(1, radius/available_radius)` | — | `UNKNOWN` solo si turn_mode NONE |
| **safety** | validador (sin cambios) | `1 − 0.2·warnings` | — |
| **coverage** | no medible en UMM 1.0 (falta área proyectada + footprint) | — | **`DATA_REQUIRED`** con mensaje |

`base(status)`: VALID 1.0 · CONSTRAINED 0.75 · NONE 0.5 · INVALID 0.0.
`overlap_score = min(front, side)` (análogo continuo del AND actual); el
desglose reporta el eje **ligante** (menor utilidad).

**Total:** `Σ(normalized·weight) / Σ(weight de SCORED)` redondeado a 4;
`contribution = normalized·weight/Σ(weight)` por componente, de modo que
**la suma de contribuciones = total_score**. Un componente UNKNOWN/DATA_REQUIRED
se excluye del denominador pero **nunca desaparece** del desglose.

---

## C. Tabla de las 12 misiones del corpus (10E punto 13)

Box estándar: GSD [2,4] · front [70,90] · side [60,80] · `max_flight_time` 400 s ·
`max_battery_count` 4 · `max_photo_count` 100 · pesos calibrados por defecto.
`score_mission` directa sobre cada misión del corpus.

| case_id | GSD | fotos | t(s) | batt | turn | gsd_s | ov_s | time_s | bat_s | photo_s | turn_s | safety | **total** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `grid_small_time` | 2.74 | 21 | 121.9 | 1 | NONE | 0.739 | 0.500 | 0.695 | 0.750 | 0.790 | UNKNOWN | 1.000 | **0.7431** |
| `grid_small_low_alt` | 2.19 | 36 | 193.0 | 1 | NONE | 0.191 | 0.500 | 0.518 | 0.750 | 0.640 | UNKNOWN | 1.000 | **0.5932** |
| `grid_small_high_alt` | 3.83 | 10 | 62.0 | 1 | NONE | 0.166 | 0.500 | 0.845 | 0.750 | 0.900 | UNKNOWN | 1.000 | **0.6651** |
| `grid_small_overlap_high` | 2.74 | 65 | 194.0 | 1 | NONE | 0.739 | 0.500 | 0.515 | 0.750 | 0.350 | UNKNOWN | 1.000 | **0.6718** |
| `grid_large_over_99` | 1.64 | 8260 | 31088 | 22 | NONE | 0.000 | 0.500 | 0.000 | 0.000 | 0.000 | UNKNOWN | 1.000 | **0.2941** |
| `grid_small_fast` | 2.74 | 21 | 87.1 | 1 | CONSTRAINED | 0.739 | 0.500 | 0.782 | 0.750 | 0.790 | 0.750 | 0.800 | **0.7210** |
| `grid_small_slow` | 2.74 | 21 | 189.9 | 1 | VALID | 0.739 | 0.500 | 0.525 | 0.750 | 0.790 | 0.600 | 1.000 | **0.7042** |
| `grid_small_turn_manual_small` | 2.74 | 21 | 112.2 | 1 | VALID | 0.739 | 0.500 | 0.720 | 0.750 | 0.790 | 0.612 | 1.000 | **0.7328** |
| `grid_small_turn_manual_large` | 2.74 | 21 | 130.7 | 1 | VALID* | 0.739 | 0.500 | 0.673 | 0.750 | 0.790 | 1.000 | 0.000 | **0.5916** |
| `grid_small_capture_distance` | 2.74 | 21 | 121.9 | 1 | NONE | 0.739 | 0.500 | 0.695 | 0.750 | 0.790 | UNKNOWN | 1.000 | **0.7431** |
| `grid_small_capture_none` | 2.74 | 21 | 121.9 | 1 | NONE | 0.739 | 0.500 | 0.695 | 0.750 | 0.790 | UNKNOWN | 1.000 | **0.7431** |
| `corridor_vertex` | 2.74 | 4116 | 15057 | 11 | VALID | 0.739 | 0.500 | 0.000 | 0.000 | 0.000 | 0.793 | 1.000 | **0.4763** |

\* `grid_small_turn_manual_large` (MANUAL 25 m): el motor lo mantiene VALID pero
el **validador lo invalida** (25 > `available_radius_m` ≈ 22.22) → `safety` 0.000.
En `evaluate()` esa misión no llega a score (valid=False).

**Lectura:** el score ahora **diferencia continuamente** entre candidatos
factibles (p. ej. `grid_small_time` 0.7431 vs `grid_small_low_alt` 0.5932 vs
`grid_small_high_alt` 0.6651), penaliza uso real de presupuesto (tiempo/batería/
fotos de `grid_large_over_99` saturan a 0), premia el radio que usa el espacio
disponible del turn engine y **no inventa** cobertura (DATA_REQUIRED en todas).

**Demo de selección** (`grid_small_time`, altitudes [80,100,120], mismo box) →
**OPTIMAL**, ganador **120 m (0.7482)**, seguido de 100 m (0.7431) y 80 m
(0.5932): 120 m queda casi en el target GSD 3.0 con mucho mejor tiempo y menos
fotos. El desglose y la selección salen de los mismos datos (deterministas).

---

## D. Estado por punto 10E

| # | Punto 10E | Estado | Evidencia |
|---|---|---|---|
| 1 | Auditar el score actual (tabla matemática por componente) | **CONFIRMED → resuelto** | 10D C.8 (binario) + esta fase |
| 2 | Separar constraints (PASS/WARNING/FAIL) de preferencias | **PASS** | `constraints.py`/`evaluator.py` intactos; `preferences.py` puro |
| 3 | Funciones continuas, sin saltos 0→1 | **PASS** | `test_gsd_utility_is_continuous…`, `test_time_battery_photo_are_linear…` |
| 4 | GSD monotónico respecto al objetivo | **PASS** | tent centrado en target; `test_gsd_target_resolution_chain` |
| 5 | Overlap sin premiar exceso indefinido | **PASS** | tent/one-sided a partir del target; `test_overlap_*` |
| 6 | Tiempo/batería continuos con tiempo real (flight + turn), sin `num_lines*5` | **PASS** | usa `flight_time_s` real; la cadena de turn real la validó 10D C.4 |
| 7 | Turn con datos reales del TurnRadiusEngine (sin recalcular física) | **PASS** | `test_turn_score_uses_radius_fullness` |
| 8 | Penalización continua de photo_count | **PASS** | `1 − count/budget`, satura a 0 |
| 9 | Coverage: no medible → UNKNOWN/DATA_REQUIRED documentado | **PASS** | `test_coverage_is_data_required` (mensaje: falta área proyectada) |
| 10 | Pesos configurables y deterministas | **PASS** | `OptimizationWeights` intacto; `test_score_mission_is_deterministic` |
| 11 | Breakdown en la respuesta (component, raw, normalized, weight, contribution, total) | **PASS** | `MissionScore.details` viaja en `model_dump(mode="json")`; `test_contributions_sum_to_total…` |
| 12 | Tests de sensibilidad (una variable a la vez + empates/pesos) | **PASS** | `test_weight_sensitivity_moves_only_the_target_component`, `test_weight_sensitivity_is_coherent` |
| 13 | Tabla con las 12 misiones (baseline/candidatos/ganador/motivo) | **PASS** | sección C de este informe |
| 14 | Determinismo | **PASS** | `test_score_mission_is_deterministic` + determinismo 10C intacto (520 passed) |
| 15 | Compatibilidad (no tocar motores/UMM 1.0/adapters) | **PASS** | solo `optimizer/` + frontend |
| 16 | Frontend: panel muestra el breakdown, sin recalcular | **PASS** | sección E |
| 17 | Tests mínimos | **PASS** | backend 520 · frontend 91 |
| 18 | Gate de aceptación + informe | **PASS** | este informe + sección F |

Sin estados **FAIL** ni **UNKNOWN** de fase: los 18 puntos quedaron cubiertos.
`UNKNOWN`/`DATA_REQUIRED` existen **dentro del desglose del score** (estado por
componente), que es el comportamiento pedido, no un bloqueo.

---

## E. Frontend (punto 16)

`OptimizerPanel.tsx` añade `ScoreBreakdown` en cada tarjeta de candidato: por
componente muestra `raw_value / target`, el `normalized_value` (o el estado
`UNKNOWN`/`DATA_REQUIRED` con su mensaje) y la contribución ponderada. Se añaden
los campos `preferred_gsd` / `preferred_overlap_front` / `preferred_overlap_side`
al panel de constraints. **El cliente no recalcula nada** — consume
`best_score.details` y los `*_score` ya calculados por el backend.

---

## F. Regresiones

| Gate | Resultado |
|---|---|
| `pytest tests/optimizer` (+ tests optimizer 10B/10C) | **93 passed** |
| `pytest` backend completo | **520 passed** |
| `ruff check .` / `ruff format --check .` | limpio |
| frontend `tsc --noEmit` | OK |
| frontend `vitest run` | **91 passed** |
| frontend `vite build` | OK (aviso pre-existente de chunk > 500 kB) |

**Sin commit** (política).

---

## G. Deuda para 10F

1. **Coverage sigue siendo DATA_REQUIRED**: para hacerla medible hace falta el
   área del polígono proyectado y el footprint en la UMM (schema ≥ 1.1). Hasta
   entonces el score no inventa cobertura.
2. **Constante de mezcla del turn score** (`base × (0.5 + 0.5·fullness)`): es una
   decisión de calibración; validar contra preferencia de operador/datos de
   vuelo reales (p. ej. qué es mejor: VALID con radio pequeño o CONSTRAINED a
   tope de espacio).
3. **Overlap por defecto = overlap del request**: sin `preferred_overlap_*` el
   target es el overlap base de la misión; si el usuario quiere otro objetivo
   debe configurarlo. Documentar en la UI.
4. **Tiempo con turn fallback**: cuando `turn_source = overhead_fallback` (sin
   turn plan) `flight_time_s` puede subestimar los giros reales (heredado de la
   deuda 10D G.4); el score usa lo que hay, no lo inventa.
5. **Edición de pesos en UI**: `OptimizationWeights` es configurable por API;
   exponer sliders de pesos en el panel permitiría explotar la sensibilidad del
   punto 12 en el cliente.
6. **One-sided de bound único queda plano (1.0) en el lado conforme** — decisión
   de diseño ("cumplir el bound es suficiente"); revisar si 10F quiere premiar
   margen adicional de seguridad.