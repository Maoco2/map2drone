# Ingeniería inversa controlada de captura fotográfica LCHM (Fase 3)

> **SUPERSEDED by Fase 4/5.** El análisis de archivos LCHM reales (M1–M6/V1/V2)
> corrigió dos conclusiones de esta Fase 3: (1) `photo_timeinterval` **SÍ se
> serializa** (f32 BE global en `settings_start + 10`) y (2) `photo_distinterval`
> es un **campo de configuración independiente** (no derivado de `speed × time`).
> Ver `litchi-lchm-trailer-analysis.md` (Phase 4 y Phase 5). Este documento queda
> como registro histórico de la fase experimental.

Determina **experimentalmente** cómo Litchi almacena la configuración de captura fotográfica dentro del trailer LCHM. Esta fase NO modifica el exportador de producción; solo produce evidencia.

Confianza: **CONFIRMED** = comparación controlada con valor de referencia exacto; **PROBABLE** = evidencia parcial/consistente; **UNKNOWN** = sin evidencia suficiente. Nunca se marca CONFIRMED una hipótesis sin comparación controlada.

## Resumen de hallazgos

| Hallazgo | Confianza |
|----------|-----------|
| El trailer almacena `photo_distinterval` por waypoint (rel 212 + i×8, primer f32) | **CONFIRMED** (10/10 vs CSV A) |
| `photo_timeinterval` NO está almacenado en el trailer (búsqueda exhaustiva negativa) | **UNKNOWN / ausente** |
| En el CSV de Litchi, `photo_timeinterval = floor(photo_distinterval / speed, 1 decimal)` | **CONFIRMED** (7/7 CSVs independientes) |
| `photo_distinterval` NO es `speed × time` (20.6 vs 20.5 en A) | **CONTRADICE** la hipótesis speed×time |
| Los pares `[dist][?]` del trailer: campo B desconocido | **UNKNOWN** |

## 1. Assetos analizados

| Archivo | Fuente | Nº wps | speed | alt | timeint | distint |
|---------|--------|--------|-------|-----|---------|---------|
| `Mission (3).lchm` (A) | Litchi (Downloads) | 10 | 4.1 | 60.0 | 5.0 | 20.6 |
| `Mission (3) (1).lchm` (B) | Litchi (Downloads) | 10 | 4.1 | 60.0 | (misma misión) | 20.6 |
| `Mission (3) (2).lchm` (C) | Litchi (Downloads) | 10 | 4.1 | 60.0 | (misma misión) | 20.6 |
| `test_area_grid_litchi.lchm` | Map2Drone | 74 | 6.8 | 100.0 | — (sin trailer) | — |
| `test_linear_corridor_litchi.lchm` | Map2Drone | 15 | 6.8 | 100.0 | — (sin trailer) | — |
| `test_small_litchi.lchm` | Map2Drone | 5 | 4.1 | 60.0 | — (sin trailer) | — |

Además, 7 CSVs reales de Litchi en `C:\Users\usuario\Downloads` con distintos configs de foto (ver §4).

> **OJO**: A, B y C son la **misma misión** (solo cambian path mode, heading mode y heading). Por eso sus trailers son idénticos 298/298. **No constituyen variación de intervalo**; no se pueden usar para concluir cómo cambia el trailer con el intervalo.

## 2. Evidencia: photo_distinterval en el trailer (CONFIRMED)

En los fixtures, trailer rel **212–291** contiene 10 pares `[f32][f32]` (8 B por waypoint, en el orden de los registros). El **primer f32** coincide exactamente con la columna `photo_distinterval` del CSV A en **10/10 waypoints**:

| wp | trailer f32 A | CSV distint | ¿coincide? |
|----|---------------|-------------|------------|
| 0 | 20.6 | 20.6 | ✓ |
| 1 | 20.6 | 20.6 | ✓ |
| 2 | 20.6 | 20.6 | ✓ |
| 3 | 20.6 | 20.6 | ✓ |
| 4 | −1.0 | −1.0 | ✓ |
| 5 | 20.6 | 20.6 | ✓ |
| 6 | 20.6 | 20.6 | ✓ |
| 7 | 20.6 | 20.6 | ✓ |
| 8 | −1.0 | −1.0 | ✓ |
| 9 | −1.0 | −1.0 | ✓ |

`−1.0` (0xBF800000) es el centinela "sin intervalo". Valor observado `20.6` = `0x41A4CCCD`.

**Posición**: `trailer_rel = 212 + i*8`, `abs = trailer_start + trailer_rel`.

**Campo B** (segundo f32): 0.0 / −1.0, no correlaciona con `photo_timeinterval` (5.0) ni con patrón claro. El bloque wp9 campo B es un subnormal (3.5e-44) que solapa con el terminador `00 19 00 00 00 09` (rel 290+). **UNKNOWN**.

## 3. Evidencia: photo_timeinterval NO está en el trailer

Búsqueda exhaustiva en el archivo completo de A (y en el trailer) de **1.0, 2.0, 3.0, 4.0, 5.0, 6.0 y 3.6** como:

- float32 BE y LE
- float64 BE y LE
- int32 / int16 BE y LE
- fixed-point ×100 (BE y LE)

**Resultado**: ninguna representación de 5.0 (0x40A00000) ni de 3.6 (0x40666666) aparece en el trailer ni en los registros. Los falsos positivos (p. ej. "2.0" en f32 LE) provienen de bytes del gimbal/heading y se descartan.

**Conclusión**: no hay evidencia de que `photo_timeinterval` se serialice en el LCHM. En el modelo de Litchi, **la distancia es el parámetro primario almacenado**; el tiempo es derivado (ver §4).

## 4. Relación tiempo–distancia–velocidad (CONFIRMED en CSV)

Análisis de 7 CSVs reales de Litchi (misiones distintas, speeds 4.1–8.2 m/s, distint 17.5–30.0, timeint 3.6/5.0):

| CSV | speed | distint | distint/speed | floor(dist/speed,1) | csv timeint | match |
|-----|-------|---------|---------------|---------------------|-------------|-------|
| Mission.csv | 6.8 | 25.0 | 3.6765 | 3.6 | 3.6 | ✓ |
| Mission (1).csv | 8.2 | 30.0 | 3.6585 | 3.6 | 3.6 | ✓ |
| Mission (2).csv | 4.8 | 17.5 | 3.6458 | 3.6 | 3.6 | ✓ |
| Mission (3).csv | 4.1 | 20.6 | 5.0244 | 5.0 | 5.0 | ✓ |
| CALLE 15.csv | 4.8 | 17.5 | 3.6458 | 3.6 | 3.6 | ✓ |
| CARRERA 1.csv | 4.8 | 17.5 | 3.6458 | 3.6 | 3.6 | ✓ |
| CARRERA 1 (1).csv | 4.8 | 17.5 | 3.6458 | 3.6 | 3.6 | ✓ |

**7/7 coinciden** con `photo_timeinterval = floor(photo_distinterval / speed, 1 decimal)` (truncamiento, no redondeo; `round1` falla en Mission.csv y Mission (1).csv).

**Relación inversa con speed×time**: en A, `speed × time = 4.1 × 5.0 = 20.5`, pero el valor almacenado es **20.6**. La hipótesis `photo_distinterval = speed × photo_timeinterval` **NO se cumple** (diferencia 0.1; en las demás CSVs 0.22–0.52). Por tanto:

- El usuario fija la **distancia** de captura (o Litchi la calcula con otra regla) y el **tiempo se deriva** para el CSV.
- `photo_distinterval` NO es una simple multiplicación speed×time redondeada.

**Interpretación propuesta (PROBABLE)**: Litchi persiste la distancia de disparo (m) por waypoint en el trailer; el tiempo mostrado en el CSV es `floor(dist/speed, 1)`. Se necesita confirmación con LCHM reales de distinta velocidad (4 y 8 m/s, §6).

## 5. Matriz experimental (plantilla para M1–M6)

Misiones M1–M6: misma geometría/config, cambiando **solo** `photo_timeinterval` 1–6 s. Columnas requeridas:

| Archivo | Speed | Time Int | Expected Dist (s×t) | Stored distinterval | Diff | timeinterval detected | Bytes changed |
|---------|-------|----------|---------------------|---------------------|------|------------------------|---------------|
| M1 | 4.1 | 1 | 4.1 | ? | ? | ? | ? |
| M2 | 4.1 | 2 | 8.2 | ? | ? | ? | ? |
| M3 | 4.1 | 3 | 12.3 | ? | ? | ? | ? |
| M4 | 4.1 | 4 | 16.4 | ? | ? | ? | ? |
| M5 | 4.1 | 5 | 20.5 | ? | ? | ? | ? |
| M6 | 4.1 | 6 | 24.6 | ? | ? | ? | ? |

**Herramienta lista**: `tools/lchm_photo_matrix.py` produce esta tabla automáticamente cuando existan los archivos reales:

```
python tools/lchm_photo_matrix.py --csv M1.csv M1.lchm M2.lchm ...
```

Regla: si `stored_distance ≈ speed × interval` para **todas** las pruebas (1,2,3,4,5,6 s) → **CONFIRMED**; si no, documentar el método de redondeo real.

## 6. Control de velocidad (pendiente)

Repetir con `interval = 2 s` a `speed = 4 m/s` y `speed = 8 m/s` para determinar si `photo_distinterval` cambia con speed (depende de tiempo×velocidad) o permanece (Litchi almacena distancia directamente). **No hay fixtures con estos datos todavía.**

## 7. Regla de redondeo / intervalos comerciales

- Litchi (y apps comerciales) aceptan intervalos en **segundos enteros** 1–6. Map2Drone NO debe emitir 5.1/5.2/5.3.
- `CaptureIntervalEngine.recommended_interval_s` ya es `Optional[int]` (entero) — ver `backend/app/core/photogrammetry/capture_interval.py:44`.
- **NO implementar todavía** el redondeo ni la escritura de foto en el LCHM.

## 8. Decisión y estado (según §15 de la tarea)

Dado que el entorno NO permite ejecutar Litchi y no se dispone de archivos reales M1–M6:

- `photo_distinterval`: **CONFIRMED** (ubicación en el trailer, valor 20.6, 10/10).
- `photo_timeinterval`: **UNKNOWN** (sin evidencia de serialización).
- Estado documentado: **"Additional real Litchi-generated fixtures required."**
- NO se simulan archivos, NO se implementa nada.

## 9. Pipeline conceptual (Fase 4, NO implementar)

```
CaptureIntervalEngine.recommended_interval_s (int)
        ↓ integer rounding (ya int; no 5.1)
LchmPhotoCaptureOptions { photo_distinterval_m? }
        ↓
LchmTrailerSerializer   (escribe bloques rel 212+i×8)
```

> El LCHM almacena distancia, no tiempo. Si se confirma `dist = speed × int_seconds` en Fase 4 con fixtures reales, se elegirá entre escribir `dist` derivado o el valor directo según la evidencia. Hasta entonces, nada se serializa.

## 10. Referencias

- `tools/lchm_byte_diff.py` — diff byte a byte (abs/rel, f32/f64, agrupado).
- `tools/lchm_photo_matrix.py` — matriz experimental M1–M6.
- `lchm_trailer_photo_blocks()` en `litchi_lchm.py` — lector read-only del bloque de fotos del trailer.
- `docs/export/litchi-lchm-trailer-analysis.md` — análisis general del trailer.