# 10F — Cobertura del score: spec campo UMM 1.1 (Punto 3, auditoría 10F)

**Fecha:** 2026-08-18 · **Estado:** DEUDA 10G (diseño; UMM 1.0 NO se toca en 10F).

## Diagnóstico confirmado en la auditoría

- **Grid engine** (`app/modules/planning/engine.py`): el campo `GridResponse.area_ha`
  es un default `0` — el engine **nunca calcula** el área del polígono proyectado.
- **Corridor engine** (`app/modules/corridor/engine.py`): sí calcula
  `corridor_area = poly.area` (línea 377) y lo expone como `corridor_area_m2`
  (línea 492) en `CorridorResponse`, pero el **builder lo descarta**:
  `app/modules/mission/builder.py` hace `getattr(mission, "corridor_area_m2", None)`
  → el UniversalMission **no tiene el campo**.
- **Score coverage** (`app/modules/optimizer/preferences.py`): al no existir área
  proyectada ni footprint en la UMM, el componente es **`DATA_REQUIRED`** (no se
  inventa cobertura; `test_coverage_is_data_required` lo fija).

## Propuesta de UMM 1.1 (deuda 10G)

Añadir al bloque `geometry`/`metrics` de la UMM (schema ≥ 1.1) dos campos
numéricos opcionales:

| Campo | Tipo | Significado | Fuente |
|---|---|---|---|
| `survey_area_m2` | float | Área del terreno a cubrir proyectada en el plano horizontal | Grid: `polygon.area` proyectado (UTM/local, ya usado en `corridor_area = poly.area`); Corridor: `corridor_area_m2` del engine |
| `covered_area_m2` | float | Área realmente cubierta por los footprints (GSD × footprint por foto, unión aproximada) | `planning/core` fotogrametría (footprint w×h ya disponible) |

### Regla de cálculo (respetando "no duplicar fórmulas")

1. El **engine** (grid/corridor) ya produce el área proyectada; el builder debe
   **copiarlo** al UMM, no recalcularlo.
2. El **footprint** (`footprint_width_m`/`height_m`) ya lo calcula la
   fotogrametría; `covered_area_m2` = `min(survey_area_m2, n_fotos × w × h)`
   como aproximación documentada (sin intersección exacta en 10G).
3. `score coverage = min(1, covered_area_m2 / survey_area_m2)` solo cuando ambos
   campos existen; si falta cualquiera, **sigue DATA_REQUIRED** (nunca inventar).

### Impacto

- UMM 1.0 queda intacta (no se añade campo → los fixtures/adapters de export no
  cambian). El cambio es **aditivo y opcional** en 1.1.
- `mission.builder` deja de descartar `corridor_area_m2` (fix puntual al migrar a 1.1).
- Backwards-compatible: `parse_mission_blob` acepta 1.0 sin los campos.

**Sin implementar en 10F** — solo spec. Implementación en 10G.