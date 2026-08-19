# Validación real del exportador Litchi LCHM

Documento de **validación de campo**: misiones generadas por Map2Drone, exportadas como `.lchm` e importadas en la aplicación **Litchi** (iOS/Android) para verificar la compatibilidad real, no solo la estructura de bytes.

> **Estado de esta fase**: `LITCHI VALIDATED`. Las misiones de la Fase 6 (grid 74 wps, corredor 15 wps, captura TIME/DISTANCE/NONE) se generaron con el pipeline real del API y se importaron físicamente en Litchi. **Litchi abrió los archivos y mostró: nº de waypoints correcto (74/15), velocidad 6.8 m/s correcta, y las opciones de captura TIME 1–6 s / DISTANCE 20.5 m / NONE correctas.**

> **Fase 7 resuelta** (ver `litchi-lchm-fase7-path-heading.md`): la semántica de los bytes de path mode / heading mode quedó **confirmada físicamente** mediante la matriz controlada. Se corrigió el **mapeo de campos** (heading mode en byte `7`, path mode en byte `15`) y se añadió soporte para el **radio de giro** (campo `+36` del registro de waypoint). Ver §"Fase 7 — Resolución".

## Cómo ejecutar la validación en Litchi

1. Generar/exportar las misiones (ver sección "Misiones de prueba").
2. Copiar los archivos `.lchm` al dispositivo (aplicación Litchi → Misión → Importar, o carpeta de importación de Litchi).
3. En Litchi: **Importar misión** desde archivo local.
4. Verificar cada parámetro de la tabla contra lo que Litchi muestra en el editor.

## Checklist (misiones)

| # | Misión | Archivo | Waypoints | Path Mode | Heading Mode | Reconocida | Se abre | Nº wps OK | Geometría OK |
|---|--------|---------|-----------|-----------|--------------|------------|---------|-----------|--------------|
| A | Área Grid (74 wps) | `tools/lchm_exports/fase6/area_grid_74_time5.lchm` | 74 | STRAIGHT | FOLLOW_PATH | OK | OK | OK (74) | OK |
| B | Corredor lineal (15 wps) | `tools/lchm_exports/fase6/linear_corridor_15_time5.lchm` | 15 | STRAIGHT | FOLLOW_PATH | OK | OK | OK (15) | OK |
| C | Area Grid DISTANCE | `tools/lchm_exports/fase6/area_grid_dist_20_5.lchm` | 74 | STRAIGHT | FOLLOW_PATH | OK | OK | OK (74) | OK |
| D | Area Grid NONE | `tools/lchm_exports/fase6/area_grid_none.lchm` | 74 | STRAIGHT | FOLLOW_PATH | OK | OK | OK (74) | OK |
| E | Area Grid TIME=1..6 | `tools/lchm_exports/fase6/area_grid_time1..6.lchm` | 74 | STRAIGHT | FOLLOW_PATH | OK | OK | OK (74) | OK |

### Metadatos de la ejecución manual

- **Fecha de validación**: Fase 6 (validación física en Litchi).
- **Versión Map2Drone**: fase 6 (pipeline real del API).
- **Versión Litchi (app)**: según dispositivo del usuario.
- **Dispositivo / plataforma**: según dispositivo del usuario.
- **Modelo de drone**: DJI Mavic 3 Enterprise (perfil usado en la planificación).

## Tabla de parámetros (Map2Drone vs Litchi vs Resultado)

| Parámetro | Valor Map2Drone (exportado) | Valor Litchi (leído) | Resultado |
|-----------|-----------------------------|----------------------|-----------|
| Nº waypoints | 74 / 15 | 74 / 15 | OK |
| Latitud / Longitud wp0 | 3.5871270 / -76.4855905 (grid 74); según misión | coincide con la planificación | OK |
| Altitud (m) | según misión (100 m AGL) | coincide | OK |
| Orden de waypoints | secuencial | coincide | OK |
| Heading (°) | según misión (grid: 90/270 alternados) | coincide | OK |
| Velocidad (m/s) | 6.81 (grid/corredor) | 6.8 | OK |
| Gimbal pitch (°) | -90 | coincide | OK |
| Gimbal mode | 2 | coincide | OK |
| Path mode | STRAIGHT | **recto (giros rectos)** | OK (tras corrección Fase 7) |
| Heading mode | FOLLOW_PATH | **seguir camino** | OK (tras corrección Fase 7) |
| Captura TIME | 1–6 s | 1–6 s | OK |
| Captura DISTANCE | 20.5 m | 20.5 m | OK |
| Captura NONE | — | sin captura | OK |

## Fase 7 — Resolución (bytes 7 y 15 + radio de giro)

### Resultado de la matriz controlada (prueba física en Litchi)

El usuario importó los 4 archivos de prueba y reportó:

| Archivo (`tools/lchm_exports/fase7/`) | byte[7] | byte[15] | Litchi mostró |
|---------|---------|----------|---------------|
| `lchm_byte_00_00.lchm` | 0x00 | 0x00 | recto + seguir camino |
| `lchm_byte_00_01.lchm` | 0x00 | 0x01 | giros curvos + seguir camino |
| `lchm_byte_03_00.lchm` | 0x03 | 0x00 | recto + personalizado (POI) |
| `lchm_byte_03_01.lchm` | 0x03 | 0x01 | giros curvos + personalizado (POI) |

**Conclusión (H1 confirmada):**
- `byte[7]` = **heading mode**: `0x00` = **FOLLOW_PATH** (seguir camino), `0x03` = **CUSTOM_POI** (personalizado)
- `byte[15]` = **path mode**: `0x00` = **STRAIGHT** (recto), `0x01` = **CURVED_TURNS** (giros curvos)

**Corrección aplicada** en `backend/app/modules/export/litchi_lchm.py`:
- Se intercambió el **mapeo de campos**: el modo de heading se escribe en el byte `7` y el de path en el byte `15` (el análisis inverso inicial los tenía asignados a la inversa, con valores erróneos).
- Enums: `LchmPathMode.CURVED_TURNS = 0x01`, `STRAIGHT = 0x00`; `LchmHeadingMode.CUSTOM_POI = 0x03`, `FOLLOW_PATH = 0x00`.
- Parser y serializer actualizados en ambos sentidos; tests de fixtures A/B/C y de bytes actualizados.
- **Esto explica la observación de Fase 6**: los archivos STRAIGHT+FOLLOW_PATH (configurado) se escribían con bytes `03/01`, que Litchi interpreta como CUSTOM+CURVED — exactamente lo que el usuario vio ("giros curvos" + "personalizado"). Los archivos regenerados ahora escriben `00/00` → Litchi muestra "recto + seguir camino".

### Radio de giro (campo +36 del registro)

Al configurar `CURVED_TURNS` con `curve_size` por waypoint, el radio se serializa en el **campo `+36` (f32, big-endian) de cada registro** (en metros). Patrón observado en el archivo físico del usuario `area_grid_74_time5_curve.lchm` y replicado por el exportador:
- Primer y último waypoint: radio `0.0` (no tienen giro).
- Waypoints interiores: `curve_size` (radio en m).
- El flag `+7` del registro alterna (`0x01` en waypoints impares interiores) como marca de giro.

El exportador ahora mapea `ExportWaypoint.curve_size` → `+36`. Ver `litchi-lchm-fase7-path-heading.md` §Fase 7b.

### Archivos de verificación

- `tools/lchm_exports/fase7b/area_grid_74_time5_curve.lchm` — generado por Map2Drone (CURVED_TURNS + CUSTOM_POI + radius 12.637 m).
- Comparado contra el archivo del usuario (`C:\Users\usuario\Downloads\area_grid_74_time5_curve.lchm`): los únicos bytes distintos son el redondeo f32 del radio (12.6367 vs 12.6370) y los sentinels del trailer que Litchi reescribió al re-exportar. **Cabecera, flag alternado y radios idénticos.**

## Resultado estructural (verificado con parser + lchm_inspector, sin app Litchi)

| Comprobación | Resultado | Herramienta |
|--------------|-----------|-------------|
| Magic `lchm` | OK | `lchm_inspector.py` / parser |
| Header 44 B, path/heading mode | OK (bytes escritos) | `lchm_inspector.py` |
| Nº waypoints = registros (N × 56 B) | OK | parser + round-trip |
| Coordenadas wp0..wpN | OK | parser |
| Altitudes, headings, speed, gimbal | OK | parser + round-trip |
| Trailer | emitido (captura) | `lchm_inspector.py` |
| `photo_timeinterval`/`photo_distinterval` | OK (TIME/DISTANCE/NONE) | parser |

## Limitaciones y advertencias

- **Compatibilidad**: `LITCHI VALIDATED` para nº de waypoints, geometría, velocidad, captura (TIME/DISTANCE/NONE) y, tras Fase 7, también para **path mode / heading mode** (confirmado con la matriz controlada) y **radio de giro** (verificado contra el archivo físico del usuario).
- El flag `+7` del registro y su alternancia (`0x01` en waypoints impares interiores) están replicados según el archivo físico observado; su semántica de negocio exacta (p. ej. si Litchi lo usa para "mostrar radio") queda como **cuestión abierta** pendiente de una prueba de comportamiento en el dispositivo.
- Los archivos de prueba de Fase 6 se generaron con el esquema `header + N×56` (con trailer de captura). Litchi puede exigir campos adicionales para ciertas funciones; el análisis del trailer está en `docs/export/litchi-lchm-trailer-analysis.md`.
- Esta validación NO debe confundirse con el formato `.csv` de Litchi (es un formato distinto).