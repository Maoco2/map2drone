# Fase 7 — Semántica de path mode / heading mode (bytes 7 y 15 del header LCHM)

Análisis y **resolución** de la discrepancia reportada por el usuario tras la
validación física en Litchi de los archivos de la Fase 6: el exportador
configuró `STRAIGHT` + `FOLLOW_PATH` pero Litchi mostró **"giros curvos"** y
**"rumbo personalizado"**.

> **RESUELTO (Fase 7, prueba controlada del usuario en Litchi).** El mapeo real
> es un **intercambio de campos** + valores distintos. La corrección está
> aplicada en el exportador, el parser, los tests y las herramientas; los
> archivos de Fase 6/7 se regeneraron y verifican contra el archivo físico del
> usuario.

## 1. Antecedentes: clasificación de los fixtures A/B/C

Los fixtures `Mission (3).lchm` (A), `Mission (3) (1).lchm` (B) y
`Mission (3) (2).lchm` (C) son **la misma misión** (10 wps con lat/lon/alt/speed
idénticos) y difieren solo en los bytes 7 y 15 del header (además de los valores
de heading por waypoint).

| Fixture | byte[7] | byte[15] | Clasificación (análisis inverso, NO verificado físicamente) |
|---------|---------|----------|-------------------------------------------------------------|
| A | `0x00` | `0x01` | CURVED_TURNS + FOLLOW_PATH |
| B | `0x03` | `0x00` | STRAIGHT + CUSTOM_POI |
| C | `0x03` | `0x01` | STRAIGHT + FOLLOW_PATH |

Todos los waypoints de A/B/C tienen `curvesize(m) = 0.0` (según el CSV de Litchi),
`rotationdir = 0`, `gimbalmode = 2`, `gimbalpitchangle = -90`, `speed = 4.1`,
`photo_timeinterval = 5.0`, `photo_distinterval = 20.6`.

**Nota metodológica**: la clasificación A/B/C proviene de un análisis inverso de
los bytes (sin observación física en la app Litchi). No hay evidencia de que el
usuario haya creado estos fixtures con opciones conocidas y verificadas
visualmente; por tanto NO son verdad de campo para la semántica de los bytes.

## 2. Evidencia física (Fase 6 — Litchi)

Archivos generados por Map2Drone (pipeline real del API) con `STRAIGHT` +
`FOLLOW_PATH` → `byte[7]=0x03`, `byte[15]=0x01`. Al importarlos, **Litchi mostró
"giros curvos" y "rumbo personalizado"**.

Estos archivos son byte-idénticos al fixture C en cabecera (byte 7=03, byte
15=01). Por tanto, **si el fixture C fuera realmente STRAIGHT + FOLLOW_PATH,
Litchi debería haber mostrado "giros rectos" y "rumbo siguiendo camino"** — lo
cual contradice la clasificación de los fixtures.

## 3. Hipótesis

1. **H1 — Mapeo invertido / campos intercambiados**: la semántica de los bytes es
   la opuesta a la clasificada, y los **campos** están intercambiados:
   - `byte[7]` = heading mode: `0x00` = FOLLOW_PATH, `0x03` = CUSTOM_POI
   - `byte[15]` = path mode: `0x00` = STRAIGHT, `0x01` = CURVED_TURNS
   - En ese caso el fixture A sería CURVED+FOLLOW, B STRAIGHT+CUSTOM, C
     CURVED+CUSTOM, y nuestros archivos de Fase 6 (03,01) mostrarían correctamente
     "giros curvos"+"rumbo personalizado" (¡lo cual coincide con la observación!).
2. **H2 — Etiqueta vs comportamiento**: Litchi muestra una etiqueta distinta pero
   el comportamiento real (giros rectos al volar, rumbo siguiendo el camino)
   coincide con la intención. La etiqueta no refleja el byte.
3. **H3 — Campo adicional**: el display de Litchi depende de otro campo además de
   los bytes 7/15 (p. ej. valores de heading por waypoint, campos UNKNOWN).

**La H1 es la más consistente con la observación física**: la matriz controlada
la confirmó sin ambigüedad (ver §5).

## 4. Matriz controlada (generada)

`tools/fase7_path_heading_test.py` genera 4 archivos con la **misma misión**
(5 wps, coords del fixture A, speed 4.1, alt 60, captura TIME=5) y cambiando
SOLO los bytes 7 y 15:

| Archivo | byte[7] | byte[15] |
|---------|---------|----------|
| `lchm_byte_00_01.lchm` | 0x00 | 0x01 |
| `lchm_byte_03_01.lchm` | 0x03 | 0x01 |
| `lchm_byte_00_00.lchm` | 0x00 | 0x00 |
| `lchm_byte_03_00.lchm` | 0x03 | 0x00 |

Verificación con `tools/lchm_byte_diff.py` (todos los pares): la diferencia
binaria es exactamente los offsets 7 y/o 15; **no hay ningún otro byte distinto**.

Regeneración:
```
python tools/fase7_path_heading_test.py   (desde backend/, o con el venv activo)
```

## 5. Resultado de la prueba física (realizada por el usuario)

El usuario importó los 4 archivos en Litchi y reportó:

| Archivo | byte[7] | byte[15] | Litchi mostró |
|---------|---------|----------|---------------|
| `lchm_byte_00_00.lchm` | 0x00 | 0x00 | recto + seguir camino |
| `lchm_byte_00_01.lchm` | 0x00 | 0x01 | giros curvos + seguir camino |
| `lchm_byte_03_00.lchm` | 0x03 | 0x00 | recto + personalizado (POI) |
| `lchm_byte_03_01.lchm` | 0x03 | 0x01 | giros curvos + personalizado (POI) |

**Conclusión — H1 confirmada:**
- `byte[7]` = **heading mode**: `0x00` = FOLLOW_PATH (seguir camino), `0x03` = CUSTOM_POI (personalizado)
- `byte[15]` = **path mode**: `0x00` = STRAIGHT (recto), `0x01` = CURVED_TURNS (giros curvos)

Los valores del análisis inverso original estaban asignados a los **campos
invertidos** (path en 7, heading en 15) y con **valores erróneos**; ambos
aspectos se corrigen juntos.

## 6. Acciones aplicadas (H1 confirmada)

- **`backend/app/modules/export/litchi_lchm.py`**:
  - `LchmPathMode.CURVED_TURNS = 0x01`, `STRAIGHT = 0x00` (byte 15).
  - `LchmHeadingMode.CUSTOM_POI = 0x03`, `FOLLOW_PATH = 0x00` (byte 7).
  - `_build_header_clean` escribe heading en el byte 7 y path en el 15.
  - `LchmHeaderParser` lee byte 7 → heading, byte 15 → path.
  - Exportador: en `CURVED_TURNS`, radio `0.0` en primer/último waypoint y
    `curve_size` en los interiores; flag `+7` = `0x01` en waypoints impares
    interiores (patrón del archivo físico del usuario).
- **`backend/tests/test_litchi_lchm.py`**: fixtures A=CURVED_TURNS+FOLLOW_PATH,
  B=STRAIGHT+CUSTOM_POI, C=CURVED_TURNS+CUSTOM_POI; tests de bytes
  (`offset 7` = heading 00→03, `offset 15` = path 00→01); test `lchm_diff_output`.
- **`tools/fase7_path_heading_test.py`**: filenames = bytes reales
  (00_00, 00_01, 03_00, 03_01) con el mapeo confirmado.
- Archivos de Fase 6 regenerados → `00/00` (STRAIGHT+FOLLOW_PATH → "recto +
  seguir camino").
- Archivo Fase 7b `area_grid_74_time5_curve.lchm` generado y verificado contra
  el archivo físico del usuario (única diferencia: redondeo f32 del radio y
  sentinels del trailer reescritos por Litchi).

## 7. Estado

| Componente | Estado |
|------------|--------|
| Exportador (enums byte 7/15) | **CORREGIDO** (campos intercambiados, H1 confirmada) |
| Radio de giro (`+36`) | **SOPORTADO** (mapea `ExportWaypoint.curve_size`) |
| Prueba controlada (4 archivos) | Resultados del usuario registrados (§5) |
| Herramienta de regeneración | `tools/fase7_path_heading_test.py` |
| Pruebas (pytest) | `test_litchi_lchm.py` 44 OK; suite total 193 OK (2 fallos pre-existentes de shapefile) |
| Docs | Actualizadas (`litchi-lchm.md`, `litchi-lchm-validation.md`) |
| Compatibilidad global | `LITCHI VALIDATED` (wps/geometría/velocidad/captura + path/heading + radio) |

**Cuestión abierta**: la semántica de negocio exacta del flag `+7` del registro
(alternancia en waypoints impares) no se ha verificado con una prueba de
comportamiento en vuelo/Litchi (p. ej., si Litchi lo usa para mostrar el radio).