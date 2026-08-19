# 10F — Matriz de compatibilidad de exporters (Punto 5, auditoría 10F)

**Fecha:** 2026-08-18 · Fuente: `factory.list_exporters()` (datos vivos de
`compatibility_info`, no duplicados aquí).

## Matriz

| id | Nombre | Ext | Categoría | Uso operativo | Limitaciones clave |
|---|---|---|---|---|---|
| `litchi` | Litchi CSV | `.csv` | **proprietary** | Vuelo en app Litchi Mission Hub (licencia) | Intervalo TIME entero (floor, solo en el adaptador Litchi); requiere la app de pago |
| `litchi_lchm` | Litchi LCHM | `.lchm` | **reverse_engineered** | Vuelo en app Litchi | **Máx. 99 waypoints** → `split_required`; verificar importación por versión |
| `dji_wpml` | DJI WPML | `.wpml` | **reverse_engineered** | DJI Pilot 2 | Spec no pública; puede cambiar/rechazar; verificar versión |
| `dji_kmz` | DJI KMZ | `.kmz` | **reverse_engineered** | DJI Pilot 2 (mission.wpml + waylines.wpml + manifest) | Ídem WPML |
| `qgc` | QGroundControl Plan | `.plan` | **official** | QGroundControl → ArduPilot/PX4 | Comportamiento real según firmware |
| `mission_planner` | Mission Planner | `.waypoints` | **official** | ArduPilot / MP (QGC WPL 110) | Documentado por ArduPilot |
| `mavlink` | MAVLink Mission | `.mavlink` | **reverse_engineered** | Referencia/software propio | JSON MISSION_ITEM_INT propio; **no importable** por GCS |
| `mavlink_binary` | MAVLink Binary | `.bin` | **reverse_engineered** | Referencia/software propio | Sin framing/checksum MAVLink v2; **no es** .mavlink válido |
| `kml` | KML | `.kml` | **gis_only** | Visualización GIS (Google Earth) | **No es misión de vuelo** |
| `kmz` | KMZ (Google Earth) | `.kmz` | **gis_only** | Visualización GIS | **No es misión de vuelo** |
| `geojson` | GeoJSON | `.geojson` | **gis_only** | GIS / análisis | **No es misión de vuelo** |
| `gpx` | GPX | `.gpx` | **gis_only** | Navegación/GIS | **No es misión de vuelo** |

## Categorías

- **proprietary**: especificación publicada por el fabricante para terceros, pero
  el ecosistema (app) es de pago/cerrado.
- **reverse_engineered**: estructura reconstruida por la comunidad; sin garantía
  de versiones futuras.
- **official**: formato documentado oficialmente (QGC, ArduPilot, OGC para GIS).
- **gis_only**: representación geográfica; **no generan una misión ejecutable**.

## Uso en el readiness (10F)

`check_mission_readiness(mission, fmt)` ejecuta el **exporter real**
(`validate`/`get_warnings`) para cada formato y traduce el resultado a
READY / WARNING / BLOCKED. El panel 10F muestra el diagnóstico de `litchi_lchm`
del winner y **descarga solo el LCHM** del winner aplicado; los formatos
gis_only/mavlink quedan excluidos de "volar esto" por diseño (su categoría lo
indica en la UI de export existente).

## Regla respetada

El exporter sigue siendo **responsable de la validación final**; el readiness
consume su resultado (no duplica lógica). `from_universal_mission` es la única
fuente de transformación UMM → `MissionExportData` (sin recálculo).