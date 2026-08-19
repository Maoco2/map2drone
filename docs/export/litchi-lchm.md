# Exportador Litchi LCHM (`litchi_lchm`)

Exporta la misión universal como archivo binario `.lchm` compatible con Litchi, a partir de fixtures reales de Litchi como referencia golden.

- **Formato**: binario, `application/octet-stream`
- **Extensión**: `<nombre_sanitizado>_litchi.lchm`
- **Compatibilidad**: `reverse_engineered` + `LITCHI VALIDATED` — nº de waypoints, geometría, velocidad, captura (TIME/DISTANCE/NONE), **path mode / heading mode** (bytes 7 y 15) y **radio de giro** confirmados físicamente en Litchi (Fases 6 y 7). Ver `docs/export/litchi-lchm-fase7-path-heading.md`.
- **Estado**: completo

## Estructura del archivo

El archivo emitido está compuesto por una cabecera de **44 bytes** seguida de **N registros de waypoint de 56 bytes** cada uno. Cuando se configura captura fotográfica (`options.photo_capture`), se añade además el **trailer** confirmado en Fase 4/5 (bloques de altitud, ajustes de captura, distancia por waypoint y bytes finales) — ver `docs/export/litchi-lchm-trailer-analysis.md` (Phase 5). Sin `photo_capture` la exportación es solo `cabecera + registros`.

Todos los campos multi-byte son **big-endian**.

### Cabecera (44 bytes)

| Campo | Offset | Tamaño | Tipo | Valor | Estado | Evidencia |
|------|--------|--------|------|-------|--------|-----------|
| Magic | 0 | 4 | bytes | `"lchm"` | Conocido | Fixtures |
| (reservado) | 4 | 3 | — | `0x000000` | Desconocido | Fixtures |
| Heading mode | 7 | 1 | u8 | `0x00` FOLLOW_PATH / `0x03` CUSTOM_POI | Conocido (Fase 7, confirmado físicamente) | Matriz controlada en Litchi |
| (reservado) | 8 | 3 | — | `0x000000` | Desconocido | Fixtures |
| (constante) | 11 | 1 | u8 | `0x01` | Conocido | Fixtures |
| (reservado) | 12 | 3 | — | `0x000000` | Desconocido | Fixtures |
| Path mode | 15 | 1 | u8 | `0x00` STRAIGHT / `0x01` CURVED_TURNS | Conocido (Fase 7, confirmado físicamente) | Matriz controlada en Litchi |
| (constante) | 16 | 4 | f32 | `8.0` | Conocido | Fixtures |
| (constante) | 20 | 4 | f32 | `15.0` | Conocido | Fixtures |
| (reservado) | 24 | 4 | — | `0x00000000` | Desconocido | Fixtures |
| (constante) | 28 | 4 | u32 | `0x00120000` | Conocido | Fixtures |
| (reservado) | 32 | 11 | — | `0x0000…` | Desconocido | Fixtures |
| Nº waypoints | 43 | 1 | u8 | `N` | Conocido | Fixtures (0x0A = 10) |

### Registro de waypoint (56 bytes, desde offset 44)

| Campo | Offset | Tamaño | Tipo | Valor | Estado | Evidencia |
|------|--------|--------|------|-------|--------|-----------|
| Altitud | +0 | 4 | f32 | `altitude` (m) | Conocido | Coincide con CSV |
| Flag | +4 | 4 | i32 | `0` | Parcialmente conocido | Fixtures (0/1) |
| Heading | +8 | 4 | f32 | `heading` (grados) | Conocido | Coincide con CSV |
| Velocidad | +12 | 4 | f32 | `speed` (m/s) | Conocido | Coincide con CSV |
| (reservado) | +16 | 4 | i32 | `0` | Desconocido | Fixtures |
| Latitud | +20 | 8 | f64 | `latitude` | Conocido | Coincide con CSV |
| Longitud | +28 | 8 | f64 | `longitude` | Conocido | Coincide con CSV |
| Radio de giro | +36 | 4 | f32 | `curve_size` (m) | Conocido (Fase 7b) | Archivo físico del usuario |
| Gimbal mode | +40 | 4 | i32 | `2` | Conocido | Fixtures |
| Gimbal pitch | +44 | 4 | i32 | `-90` | Conocido | Fixtures |
| (reservado) | +48 | 4 | i32 | `0` | Desconocido | Fixtures |
| (reservado) | +52 | 4 | i32 | `0` | Desconocido | Fixtures |

**Notas Fase 7**:
- `byte[7]` del header = **heading mode** (`0x00` FOLLOW_PATH, `0x03` CUSTOM_POI); `byte[15]` = **path mode** (`0x00` STRAIGHT, `0x01` CURVED_TURNS). Confirmado con la matriz controlada en Litchi (ver `litchi-lchm-fase7-path-heading.md`).
- En `CURVED_TURNS`, el campo `+36` (radio de giro) se escribe como `curve_size` en los waypoints interiores y `0.0` en el primero/último. El último byte del flag `+4` (`+7`) se escribe `0x01` en los waypoints impares interiores (patrón observado en el archivo físico del usuario; semántica de negocio pendiente de verificación de comportamiento).

## Parámetros de configuración

La misión universal admite opciones de exportación (enviadas en `options` del request):

| Opción | Valores | Por defecto |
|--------|---------|-------------|
| `path_mode` | `STRAIGHT` (Recto), `CURVED_TURNS` (Curvo) | `STRAIGHT` |
| `heading_mode` | `FOLLOW_PATH` (Seguir camino), `CUSTOM_POI` (Personalizado) | `FOLLOW_PATH` |
| `photo_capture` | `{mode: NONE\|TIME\|DISTANCE, time_interval_s?, distance_interval_m?}` | ausente (sin trailer) |

`photo_capture.mode`:
- `TIME` — `photo_timeinterval` = entero (segundos) en `settings_start + 10`. Si se da `distance_interval_m` se conserva en los bloques de distancia (nunca derivado de `speed × time`).
- `DISTANCE` — `photo_distinterval` por waypoint en `settings_start + 106 + i*8`; `photo_timeinterval` = 0.
- `NONE` — `photo_timeinterval` = 0.0 y `photo_distinterval` = `-1.0` (representación observada en los fixtures).

La conversión del intervalo científico (`CaptureIntervalEngine.recommended_interval_s`) al valor entero de Litchi se hace en `normalize_litchi_time_interval()` (Litchi Export Adapter); el motor universal no se modifica.

## Funcionalidad no implementada

- **Campos UNKNOWN** (flag `+4`, reservado `+36`, segundo f32 de cada bloque de foto, resto de la plantilla de ajustes): se escriben como `0` y se documentan como desconocidos. Nunca se rellenan con información inventada.
- **Acciones de cámara/gimbal por waypoint**: no se serializan en esta versión (advertencia `actions_lost`).