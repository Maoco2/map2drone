# Análisis del trailer Litchi LCHM (~298 bytes)

Análisis **diferencial** del trailer presente en los fixtures de Litchi (`Mission (3).lchm` = A, `Mission (3) (1).lchm` = B, `Mission (3) (2).lchm` = C) tras los registros de waypoint.

> **Advertencia metodológica crítica**: A, B y C son la **misma misión** (10 waypoints con lat/lon/alt/speed idénticos) y difieren **solo** en el byte de path mode (offset 7), el byte de heading mode (offset 15) y los valores de heading. Por tanto, **el trailer idéntico 298/298 entre A/B/C NO demuestra que el trailer sea invariante**; solo demuestra que no cambia con el path/heading mode ni con el heading. Para confirmar hipótesis se necesitan misiones con parámetros distintos (ver sección "Experimentos futuros").

Confianza: **CONFIRMED** = verificado por comparación controlada con valor de referencia exacto; **PROBABLE** = evidencia parcial/consistente; **UNKNOWN** = sin evidencia suficiente. Nunca se marca CONFIRMED una hipótesis sin comparación controlada.

## Método

- Offset del trailer: `44 + N×56` (para N=10 → 604). Fixtures: trailer de 298 bytes.
- Herramienta: `lchm_trailer_diff(files)` en `litchi_lchm.py` (comparación byte a byte y agrupación de regiones variables).
- Referencias: CSV de Litchi `Mission (3).csv` (coincide con A: wp0 lat=3.5871270, alt=60.0, speed=4.1, timeint=5.0, distint=20.6).

## Vista general (trailer de A, 298 bytes)

```
rel   0-   5: 00 00 00 00 00 00                        (6 bytes cero)
rel   6- 105: 10 bloques de 10 bytes  [alt_f32][0xFFFFFFFF][0x0000]
rel 106- 297: ajustes de misión (192 bytes)
```

### Sección 1: bloques por waypoint (rel 6–105)

10 bloques de 10 bytes, uno por waypoint, en el orden de los registros:

| Bloque | rel | alt f32 (BE) | rest (hex) |
|--------|-----|--------------|------------|
| wp00 | 6–15 | 60.0 | `ffffffff0000` |
| wp01 | 16–25 | 59.0 | `ffffffff0000` |
| wp02 | 26–35 | 58.0 | `ffffffff0000` |
| wp03 | 36–45 | 57.6 | `ffffffff0000` |
| wp04 | 46–55 | 56.9 | `ffffffff0000` |
| wp05 | 56–65 | 57.4 | `ffffffff0000` |
| wp06 | 66–75 | 58.4 | `ffffffff0000` |
| wp07 | 76–85 | 58.9 | `ffffffff0000` |
| wp08 | 86–95 | 59.5 | `ffffffff0000` |
| wp09 | 96–105 | 60.6 | `ffffffff0000` |

| offset | tamaño | valor | comportamiento | hipótesis | confianza |
|--------|--------|-------|----------------|-----------|-----------|
| 6 + i×10 | 4 | altitud del waypoint i | = altitud del registro i | espejo por waypoint de la altitud | CONFIRMED (igual exacto a los 10 registros) |
| 10 + i×10 | 4 | `0xFFFFFFFF` | constante | centinela/sentinel (-1) | PROBABLE |
| 14 + i×10 | 2 | `0x0000` | constante | padding/flag | UNKNOWN |

### Sección 2: ajustes (rel 106–297)

Datos mixtos. Valores reconocibles:

| rel | bytes (hex) | interpretación | comportamiento | hipótesis | confianza |
|-----|-------------|----------------|----------------|-----------|-----------|
| 106–109 | `00 5c 00 00` | u32=6029312 / u16 0x005C=92 | constante en A/B/C | cabecera de sección | UNKNOWN |
| 110–113 | `00 08 00 00` | u32=524288 | constante | cabecera de sección | UNKNOWN |
| 138–141 | `00 00 c7 c3` / `c7 c3 50 00` | f32 -100000.0 (c7c35000, desalineado) | constante | sentinela de altitud POI | PROBABLE |
| 146–153 | `41 f0 00 00` = 30.0 | f32 30.0 | constante | ? | UNKNOWN |
| 166–169 | `42 48 00 00` = 50.0 | f32 50.0 | constante | ? | UNKNOWN |
| 174–177 | `3f 80 00 00` = 1.0 | f32 1.0 | constante | ? | UNKNOWN |
| 202–205 | `00 c7 c3 50` | f32 -100000.0 (c7c35000, desalineado) | constante | sentinela de altitud POI | PROBABLE |

### Sección 3: fotos por waypoint (rel 212–291) — HALLAZGO CLAVE

10 registros de 8 bytes `[f32 foto_distinterval][f32 ?]` (uno por waypoint):

| rec | rel | f32 A | f32 B | CSV distint (A) | CSV timeint (A) |
|-----|-----|-------|-------|-----------------|-----------------|
| wp0 | 212–219 | 20.6 | 0.0 | 20.6 | 5.0 |
| wp1 | 220–227 | 20.6 | 0.0 | 20.6 | 5.0 |
| wp2 | 228–235 | 20.6 | 0.0 | 20.6 | 5.0 |
| wp3 | 236–243 | 20.6 | -1.0 | 20.6 | 5.0 |
| wp4 | 244–251 | -1.0 | 0.0 | -1.0 | -1.0 |
| wp5 | 252–259 | 20.6 | 0.0 | 20.6 | 5.0 |
| wp6 | 260–267 | 20.6 | 0.0 | 20.6 | 5.0 |
| wp7 | 268–275 | 20.6 | -1.0 | 20.6 | 5.0 |
| wp8 | 276–283 | -1.0 | -1.0 | -1.0 | -1.0 |
| wp9 | 284–291 | -1.0 | 0.0 | -1.0 | -1.0 |

| offset | tamaño | valor | comportamiento | hipótesis | confianza |
|--------|--------|-------|----------------|-----------|-----------|
| 212 + i×8 | 4 | 20.6 / -1.0 | = `photo_distinterval` del CSV, 10/10 coinciden | almacena photo_distinterval por waypoint | CONFIRMED (coincide 10/10 con CSV A) |
| 216 + i×8 | 4 | 0.0 / -1.0 | no coincide con `photo_timeinterval` (5.0) ni con un patrón claro | campo B desconocido | UNKNOWN |

> **No se encontró `0x40A00000` (5.0) en todo el trailer** → no hay evidencia de que el trailer almacene `photo_timeinterval`. (En el CSV todos los wps con distint=20.6 tienen timeint=5.0, pero el trailer guarda 0.0/-1.0 en ese campo B.)

### Final (rel 292–297)

| offset | tamaño | bytes | comportamiento | hipótesis | confianza |
|--------|--------|-------|----------------|-----------|-----------|
| 292–297 | 6 | `00 19 00 00 00 09` | constante | terminador/checksum | UNKNOWN |

## Conclusiones por campo del registro

### Flag `+4` (registro)

| wp | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|----|---|---|---|---|---|---|---|---|---|---|
| flag | 0 | 0 | 1 | 1 | 1 | 0 | 1 | 1 | 0 | 0 |

- Idéntico en A, B y C → no depende de path mode, heading mode ni heading.
- No correlaciona con `photo_distinterval` ni `photo_timeinterval` del CSV (wp4 tiene distint=-1 pero flag=1; wp0 tiene distint=20.6 pero flag=0).
- No correlaciona con f36 (wp3: flag 1, f36 20.38; wp4: flag 1, f36 4.855; wp5: flag 0, f36 4.855).
- **Hipótesis**: indicador de acción/foto u otro modo por waypoint. **Confianza: UNKNOWN** — sin comparación controlada. Se serializa como 0 (ver `docs/export/litchi-lchm.md`).

### Campo `+36` (registro)

| wp | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|----|---|---|---|---|---|---|---|---|---|---|
| f36 | 0.000 | 13.772 | 16.792 | 20.382 | 4.855 | 4.855 | 20.414 | 17.041 | 13.856 | 0.000 |

- Idéntico en A, B y C → no depende de path/heading mode ni heading.
- **Patrón simétrico en el boustrophedon**: wp1≈wp8 (13.77≈13.86), wp2≈wp7 (16.79≈17.04), wp3≈wp6 (20.38≈20.41), wp4=wp5 (4.855 exacto) → valor geométrico por posición.
- **NO coincide** con la distancia haversine entre waypoints consecutivos (55.6/67.7/82.0/129.0/20.0/128.5/82.2/68.7/56.0 m) ni con distancias proyectadas locales (55.7/67.8/82.1/129.1/20.0/128.6/82.3/68.8/56.0 m).
- **Hipótesis**: distancia a un punto de referencia geométrico (p. ej. punto de giro, perpendicular a la línea) o un valor de curva. **Confianza: UNKNOWN** — sin comparación controlada con misiones de geometría distinta. Se serializa como 0 con la nota "currently serialized as zero because no evidence establishes another value."

## Decisión de implementación

- **El trailer se emite cuando se configura captura fotográfica** (Fase 5,
  `options.photo_capture` en el exporter → `LchmTrailerSerializer`). Sin
  `photo_capture` el exporter mantiene el comportamiento previo (sin trailer).
- `photo_timeinterval`/`photo_distinterval` se serializan conforme a la
  estructura confirmada (ver "Phase 5" abajo).
- No confundir: el **intervalo recomendado de Map2Drone** (p. ej. 5.1 s) vs el
  **intervalo comercial entero 1–6 s** de Litchi. La conversión es específica
  del exporter (Litchi Export Adapter) y NO contamina `CaptureIntervalEngine`.

## Experimentos futuros (para elevar confianza)

1. **Distancia**: generar en Litchi 2–3 misiones idénticas variando `photo_distinterval` (p. ej. 10, 20, 30 m) y ver si los bytes rel 212–291 cambian (confirmaría CONFIRMED y el mapeo 1:1 por waypoint).
2. **Tiempo**: generar misiones con `photo_timeinterval` 1 s / 2 s / 3 s y buscar el byte que cambia (no encontrado en fixtures actuales; posiblemente no se serializa o está en otra zona).
3. **Geometría**: misiones con otro número de waypoints y otra distribución (el trailer parece tener secciones por waypoint: 10 bloques + 10 recs de 8 B → 10 waypoints; verificar que el tamaño del trailer escala con N o es fijo).
4. **Flag +4 / f36**: comparar contra misiones con acciones de cámara (foto/video por waypoint) y con POI, para determinar su significado.

## Herramientas relacionadas

- `tools/lchm_inspector.py` — inspección (`inspect`, `--hex`) de cualquier `.lchm`, con offsets de trailer.
- `lchm_trailer_diff(files)` en `litchi_lchm.py` — comparación diferencial de trailers.
- `lchm_trailer_photo_blocks()` en `litchi_lchm.py` — lector read-only del bloque de fotos del trailer.
- `tools/lchm_photo_matrix.py` — analizador de matriz de captura fotográfica (Phase 4).
- `tools/lchm_byte_diff.py` — diff byte a byte (abs/rel, f32/f64, agrupado).
- Fixtures: `backend/tests/fixtures/litchi/`. Generadas: `tools/lchm_exports/`.

## Phase 4 preparation

Infraestructura lista para analizar NUEVOS archivos LCHM reales generados por
Litchi cuando estén disponibles. **Sin cambios de comportamiento**: no se escribe
`photo_distinterval`, no se modifica `LchmTrailerSerializer`,
`CaptureIntervalEngine`, Grid ni Corridor Engine.

Estado (sin suposiciones de fórmula):

| Variable | Estado |
|----------|--------|
| `photo_distinterval` | **CONFIRMED as stored field** (trailer rel `212 + i*8`, primer f32) |
| `photo_timeinterval` | **NOT IDENTIFIED** (sin campo independiente; no aparece como bytes) |
| `photo_distinterval = speed × interval` | NO confirmado (A: 20.6 vs 20.5 esperado) |
| distance generation formula | **UNKNOWN** |
| rounding rule | **UNKNOWN** |
| `time = floor(distance / speed, 1)` en CSV | CONFIRMED (7/7 CSVs) pero es la variable *mostrada*, no la regla interna |

`tools/lchm_photo_matrix.py` proporciona por archivo:
- extracción de **todos** los waypoints (rel `212 + i×8`), respetando el centinela `−1.0`;
- conteo valid/sentinel; estadística min/max/mean/median ignorando centinelas; valores únicos
  (detecta si Litchi usa una distancia global o distancias distintas por waypoint);
- velocidad desde el campo LCHM real (sin inventar), y `derived_time = floor(dist/speed, 1)`;
- comparación por pares (dist anterior/nueva, diferencia, % de cambio);
- byte diff con `absolute_offset`, `trailer_relative_offset`, `section`, old/new hex,
  old/new float32, agrupación, y marca **"candidate photo_distinterval change"**
  cuando el cambio cae dentro del primer f32 de `212 + i*8` (sin declarar funcionalidad nueva).

Criterio para declarar una fórmula CONFIRMED (Phase 4+): debe explicar **≥3 valores de
intervalo distintos** y preferiblemente **≥2 velocidades distintas**; nunca con un
único archivo. La conversión Litchi será específica del exporter; no contaminar
`CaptureIntervalEngine`.

Ejecución con fixtures existentes:
```
python tools/lchm_photo_matrix.py backend/tests/fixtures/litchi/Mission\ \(3\).lchm
python tools/lchm_photo_matrix.py --combined --diff <M1.lchm> <M2.lchm> ...
```

## Phase 4 — Análisis de LCHM reales (M1–M6, V1–V2)

Fuentes: `C:\Users\usuario\Downloads\M1.lchm` … `M6.lchm`, `V1.lchm`, `V2.lchm`,
`pruebas.lchm` (65 waypoints, CURVED_TURNS, FOLLOW_PATH, trailer 1288 B) y el CSV
`pruebas.csv`. M-series y V-series comparten la MISMA geometría y el MISMO
`photo_distinterval` (20.5) — no forman una matriz de distancia distinta.

**El trailer escala con el número de waypoints** (sección 1 = 10 B/waypoint):

```
rel 0..5            : 6 bytes cero
section1 rel 6..    : n_wp × 10 B  (espejo de altitudes)
settings_start      : 6 + n_wp × 10
settings_start + 10 : photo_timeinterval f32 (GLOBAL, un solo valor)
settings_start + 106: bloques por waypoint: [photo_distinterval f32][otro f32], 8 B/wp
```

Para 10 waypoints: settings=106, timeinterval@116, dist@212 (fixture A). Para 65
waypoints: settings=656, timeinterval@666, dist@762.

### Hallazgos confirmados

1. **`photo_timeinterval` SÍ se serializa** (Fase 3 decía NOT IDENTIFIED — se corrige):
   f32 big-endian GLOBAL en `settings_start + 10`. M1→M6 difieren **exclusivamente**
   en rel 666-669: `3f800000`=1.0, `40000000`=2.0, `40400000`=3.0, `40800000`=4.0,
   `40a00000`=5.0, `40c00000`=6.0. El fixture A (10 wp) tenía `0.0` en ese campo
   (captura por distancia) — por eso la búsqueda exhaustiva de 5.0 en Fase 3 falló.

2. **`photo_distinterval` por waypoint en `settings_start + 106 + i*8`** (primer f32),
   centinela `-1.0` cuando no hay foto. Match 100% contra el CSV `pruebas.csv`
   (37 válidos / 28 centinelas).

3. **`photo_distinterval ≠ speed × interval`** en los datos reales:
   - M1..M6 (speed 6.8, interval 1..6): dist = 20.5 constante, NO 6.8/13.6/20.4/27.2/34.0/40.8.
   - V1 (speed 4.0, interval 6): dist = 20.5, NO 24.0.
   - V2 (speed 8.0, interval 6): dist = 20.5, NO 48.0.
   La distancia es un campo almacenado independiente; no es función de la velocidad
   ni del intervalo de tiempo en estos archivos.

4. **No hay suficiente evidencia para una fórmula de generación de distancia.**
   Todos los archivos reales comparten el mismo `photo_distinterval` (20.5), así que
   el criterio de ≥3 intervalos de distancia distintos NO se cumple. Estado
   `photo_distinterval` = CONFIRMED as stored field, pero la fórmula de generación
   = UNKNOWN. `photo_timeinterval` = CONFIRMED as stored field (global f32 en
   `settings_start+10`), con formato exacto conocido.

### Ejecución documentada (resultados clave)

```
python tools/lchm_photo_matrix.py --combined --timeinterval M1.lchm M2.lchm ... V2.lchm
```
- Todas: speed 6.80 (M) / 4.00 / 8.00 (V), 65 wp, trailer@3684, dist 20.50 (37/28).
- photo_timeinterval: M1=1.0 … M6=6.0, V1=V2=6.0.
- derived_time(floor1): M=3.0 (20.5/6.8), V1=5.1, V2=2.5.
- v×t nunca coincide con dist (confirmado por la columna `match?` = no en 8/8).

## Phase 5 — Serialización de captura fotográfica (TIME / DISTANCE / NONE)

**Estado final de los campos** (consolidado en la Fase 5):

| Variable | Estado |
|----------|--------|
| `photo_timeinterval` | **CONFIRMED as stored field** — f32 BE global en `settings_start + 10`; entero en segundos |
| `photo_distinterval` | **CONFIRMED as stored field** — f32 BE por waypoint en `settings_start + 106 + i*8`; centinela `-1.0` (0xBF800000) sin foto |
| Relación time/dist | **INDEPENDENT CONFIGURATION FIELDS** — cada uno se configura y se almacena por separado |
| Fórmula de generación de distancia | **NO DERIVATION ESTABLISHED** — ningún archivo real permite derivarla (todos comparten dist 20.5) |

**Arquitectura** (Litchi-specific; `CaptureIntervalEngine` NO se toca):

```
CaptureIntervalEngine → recommended_interval_s (int)
        → Litchi Export Adapter → LchmPhotoCaptureOptions
        → LchmTrailerSerializer → trailer LCHM
```

`normalize_litchi_time_interval(interval_s)`: mapea el intervalo recomendado
(segundos, posiblemente decimal) al entero que Litchi acepta. **No redondea
hacia arriba** (conservador: 5.3 s → 5 s; un valor mayor aumentaría el spacing
real por encima de lo garantizado por el motor). La decisión floor/round/ceil
queda **aislada en esta función** para poder revisarse con la política del
motor y los requisitos de Map2Drone. El intervalo recomendado del motor ya es
entero; esta función centraliza la política de conversión.

**Reglas de serialización:**

- `TIME` — escribe `photo_timeinterval` en `settings_start + 10`. Si se
  proporciona `distance_interval_m` se conserva en los bloques de distancia
  (nunca se deriva de `speed × time`).
- `DISTANCE` — escribe `photo_distinterval` en `settings_start + 106 + i*8`
  por waypoint; respeta el centinela `-1.0`; fuerza `photo_timeinterval` a 0.
- `NONE` — ambos a 0 / centinela: `photo_timeinterval` = 0.0 y
  `photo_distinterval` = `-1.0` (representación observada en los fixtures).

**Estructura final del trailer** (trailer-relative):

```
rel 0..5                          : 6 bytes cero
rel 6..(6 + N*10)                 : N bloques de 10 B [alt f32 BE][0xFFFFFFFF][0x0000]
settings_start = 6 + N*10         : región de ajustes (106 B, plantilla constante)
settings_start + 10               : photo_timeinterval f32 BE (modo TIME)
settings_start + 106              : N bloques de 8 B [photo_distinterval f32][otro f32 UNKNOWN]
fin (settings_start + 106 + N*8)  : 6 bytes `00 00 00 00 09 00`
```

El segundo f32 de cada bloque de foto es **UNKNOWN**; se escribe `0.0` como
constante documentada (valor más común observado), sin interpretación
semántica. Los campos UNKNOWN restantes (padding de cabecera, flag +4, f36 del
registro, resto de la plantilla de 106 B) se mantienen intactos con sus
constantes documentadas — nunca se rellenan con información inventada.

**UI (frontend, panel LCHM)** — radios "Sin captura de fotos / Intervalo de
tiempo / Intervalo de distancia":
- TIME muestra "Intervalo recomendado: X.X s" (científico, ideal) y "Intervalo
  Litchi: Y s" (entero) — mantenidos separados.
- DISTANCE muestra "Distancia entre fotos: X m" (no se asume 20.5 por defecto;
  el usuario la escribe).

**Fixtures reales** (copiados a `backend/tests/fixtures/litchi/real/`): M1–M6
(timeint 1.0–6.0), V1/V2 (timeint 6.0), todos con dist 20.5 (37/28) y trailer
1288 B. Usados como referencias golden en `test_lchm_photo_capture.py` junto
con pruebas de round-trip, Area Grid 74 wp TIME=5 y Linear Corridor 15 wp
TIME=5.

## Fase 6 — Validación real (archivos generados por Map2Drone)

Archivos generados con `tools/fase6_generate.py` a través del pipeline real del
API (motor de planificación → `_build_mission` → exportador LCHM; sin edición
manual, sin reconstrucción desde fixtures). Destino: `tools/lchm_exports/fase6/`.

| Archivo | Waypoints | Captura | Validación estructural |
|---|---|---|---|
| `area_grid_74_time5.lchm` | 74 | TIME=5 | timeint 5.00, dist centinela |
| `linear_corridor_15_time5.lchm` | 15 | TIME=5 | timeint 5.00, dist centinela |
| `area_grid_dist_20_5.lchm` | 74 | DISTANCE=20.5 | timeint 0.00, dist 20.50 ×74 |
| `area_grid_none.lchm` | 74 | NONE | timeint 0.00, dist centinela ×74 |
| `area_grid_time1..6.lchm` | 74 | TIME=1..6 | timeint 1.00..6.00 |

La validación geométrica (planificado vs. parseado, `tools/fase6_validate.py`)
confirma **PASS** en A–D: count, lat/lon (Δ=0), altitud, heading, speed, gimbal,
path/heading mode.

**Validación física (Fase 6, app Litchi)** — `LITCHI VALIDATED`: Litchi abrió los
archivos y mostró nº de waypoints correcto (74/15), velocidad 6.8 m/s y captura
TIME 1–6 s / DISTANCE 20.5 m / NONE. La **discrepancia de Fase 6** ("giros
curvos" y "rumbo personalizado" para archivos configurados STRAIGHT +
FOLLOW_PATH) quedó **resuelta en Fase 7** con la matriz controlada en Litchi:
`byte[7]` = heading mode (`0x00` FOLLOW_PATH, `0x03` CUSTOM_POI) y `byte[15]` =
path mode (`0x00` STRAIGHT, `0x01` CURVED_TURNS). Exportador, parser y tests
corregidos; los archivos regenerados escriben `00/00` para STRAIGHT+FOLLOW_PATH.
Ver `litchi-lchm-fase7-path-heading.md`.

**Hallazgo 5.3 → 5 (pendiente de decisión de política):** el motor científico
produce intervalos con decimales (p. ej. 5.3 s) y `normalize_litchi_time_interval`
los convierte al entero que Litchi acepta. La política actual es **floor**
(conservador: 5.3 s → 5 s), aislada en `normalize_litchi_time_interval()`. Tras
la validación física debe evaluarse si la política correcta según el objetivo
fotogramétrico es `floor`, `round` o `ceil`. **NO modificar
`CaptureIntervalEngine` en esta fase.**