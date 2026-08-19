# 10F — Análisis del split LCHM > 99 waypoints (Punto 4, auditoría 10F)

**Fecha:** 2026-08-18 · **Estado:** análisis 4A completado · split automático
4B **NO implementado** en 10F (el readiness lo reporta como `split_required`).

## Contexto confirmado

- `LCHM_MAX_WAYPOINTS = 99` en `app/modules/export/litchi_lchm.py` (header fijo:
  `waypoint_count` como i32; los fixtures físicos del usuario lo confirman).
- `LchmValidator`/`LchmExporter.validate` **rechaza** misiones con más de 99
  waypoints (nunca emite un archivo corrupto). El readiness (`check_mission_readiness`)
  lo traduce a **BLOCKED + `split_required`** y el endpoint `/export/umm/{fmt}`
  responde 400.
- Los grid reales a baja altitud superan 99 con facilidad (p. ej. 210 WP a
  altitud 100 m sobre el polígono estándar) → el split es un caso operativo normal.

## Análisis 4A: cómo se dividiría una misión en varios LCHM

### Invariantes

1. **Orden**: los waypoints se agrupan en chunks consecutivos respetando el
   orden de vuelo; un LCHM nunca reordena puntos.
2. **Capacidad**: cada chunk ≤ 99 waypoints (respetar `LCHM_MAX_WAYPOINTS`).
3. **Continuidad fotográfica**: la captura (trailer `photo_capture`) vive en el
   chunk; Litchi ejecuta misión a misión, por lo que la captura continua entre
   chunks depende del operador (documentar: intervalo por foto en cada chunk).

### Estrategia propuesta

- Dividir en `ceil(n / 99)` chunks; los primeros `n-1` con 99 y el último con el
  resto. Alternativa útil: partir en **líneas de vuelo completas** (boundaries de
  `flight_lines_geojson`) para minimizar cortes en medio de una línea — el
  footer/heading no se recalcula en el corte porque cada waypoint lleva su
  heading propio.
- Cada chunk exporta su propio LCHM con el **mismo** header/trailer config
  (path_mode, heading_mode, photo_capture). No hay estado global compartido entre
  archivos en el formato.
- Nombres: `project_01.lchm`, `project_02.lchm`, … (o `_part1`).
- El `metrics.waypoint_count` / `photo_count` del UMM original describe la misión
  completa; el readiness debe reportar `parts = ceil(n/99)`.

### Qué NO se hace (para no mentir)

- No se reparte la captura como si fuera continua entre archivos: Litchi trata
  cada misión como un vuelo. Se documenta el límite operativo, no se oculta.
- No se inventan waypoints de retorno al home por corte (el operador decide).

## Estado

- **4A** (análisis): hecho — este documento.
- **4B** (implementación): **NO** — deuda 10G. El panel muestra BLOCKED +
  `split_required` y bloquea el botón de descarga (Caso B E2E lo verifica).

## Decisión de gate

El gate 12 (readiness) pasa porque el split se **detecta y se bloquea** antes de
generar un archivo; el split automático no es prerrequisito de 10F (es deuda 10G).