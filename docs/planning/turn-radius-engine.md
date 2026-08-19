# Turn Radius Engine (Fase 8)

Independent turn-radius geometry engine for Map2Drone survey missions
(Area Grid and Linear Corridor). It computes recommended, calculated and
geometry-constrained turn radii, generates the turn geometry (circular arc),
validates feasibility and exposes results that export formats (notably LCHM)
consume.

The engine has **no knowledge of LCHM or any exporter** — it works with
speed, vehicle parameters, line separation, turn angle, clearance and space
constraints, in a projected metric CRS.

---

## Location

| Component | File |
| --- | --- |
| Data models | `backend/app/modules/planning/turn_radius/models.py` |
| Geometry helpers | `backend/app/modules/planning/turn_radius/geometry.py` |
| Engine | `backend/app/modules/planning/turn_radius/engine.py` |
| Planners (Grid / Corridor) | `backend/app/modules/planning/turn_radius/planners.py` |
| Export integration adapter | `backend/app/modules/planning/turn_radius/integration.py` |
| Package entry | `backend/app/modules/planning/turn_radius/__init__.py` |
| Tests | `backend/tests/test_turn_radius_{engine,planners,lchm_integration}.py` |

## Concepts

**Radii (in meters, always metric)**

* `dynamic_radius_m` — `R = v² / a_lat` from physics.
* `safe_radius_m` — `R_safe = R_dynamic × safety_factor` (engineering factor,
  default **1.25**, `>= 1`).
* `available_radius_m` — largest radius the space allows
  (analytic + optional geometric check).
* `radius_m` — the radius the mission actually uses:
  - AUTO + fits  → `safe_radius_m` (`VALID`)
  - AUTO + no fit → `available_radius_m` (`CONSTRAINED`, **never silently
    reduced**)
  - MANUAL → the requested `manual_radius_m` (warn unless invalid)
  - NONE → `0.0` (no curve)

**Status** — `VALID`, `CONSTRAINED`, `INVALID`, `NONE`.

**Modes** — `AUTO`, `MANUAL` (warnings, only blocks when the radius is
mathematically invalid), `NONE`.

## Formulas

| Quantity | Formula |
| --- | --- |
| Dynamic radius | `R_dynamic = v_turn² / a_lat` |
| Safe radius | `R_safe = R_dynamic × safety_factor` |
| U-turn width bound | `R_available ≤ (line_spacing − 2·clearance) / 2` |
| Length bound | `R_available ≤ available_length − clearance` |
| Arc length | `L = R × θ_rad` |
| Turn duration | `t = L / v_turn` |
| Turn extension (AUTO) | `extension = R` (engineering default, documented) |
| Photo capture in turn | `photo_capture_recommended_during_turn = False` |

Headings are **angles** (degrees clockwise from north). Metric math is always
done in UTM (zone chosen from the centroid, via `pyproj` + `shapely`); raw
EPSG:4326 degrees are never used for distances or radii.

### Turn geometry (circular arc)

For a turn starting at `P` with entry heading `h_in`:

* `dir_sign = +1` RIGHT (heading increases), `-1` LEFT.
* Center: `C = P + dir_sign·R·right_normal(h_in)` where
  `right_normal = (cos h, −sin h)` in (x=east, y=north).
* Arc point at turn fraction `t`: `P(t) = C + dir_sign·R·left_normal(h(t))`
  with `h(t) = h_in + dir_sign·turn_angle·t` and `left_normal = (−cos h, sin h)`.

`generate_turn_geometry` returns the arc, center and clearance buffer
(`arc.buffer(clearance)`), all in projected meters.

## Vehicle parameters — provenance

`DroneFlightDynamics` defaults are **conservative engineering defaults
(provenance `DEFAULT`)** and are never presented as manufacturer specs:

* `max_lateral_acceleration_ms2 = 4.5`
* `min_turn_radius_m = 2.0`, `max_turn_radius_m = 50.0`
* `preferred_turn_speed_ms = None` (AUTO → survey speed)
* `max_speed_ms = None`

Sources: `DEFAULT` (engineering), `USER` (user input), `DRONE_PROFILE`
(future per-model profiles). No DJI-specific dynamics are assumed.

## Validation

`validate_turn` returns `VALID` / `CONSTRAINED` / `INVALID`:

* `radius ≤ 0` → `INVALID`
* `radius < min_turn_radius` → `INVALID` (below vehicle minimum)
* `turn_angle` outside `(0, 180]` → `INVALID`
* `radius > max_turn_radius` → `CONSTRAINED` (warning)
* arc + clearance not inside the maneuver boundary → `CONSTRAINED`
  (with mitigation suggestions: reduce turn speed, enlarge maneuver area,
  extend the flight lines)

`CONSTRAINED` means the radius was geometry-constrained — the engine does
not silently reduce the safe radius; it reports both values and explains.

## Planners

Both planners reconstruct flight lines and call the engine once per
transition between consecutive lines.

* **`GridTurnPlanner`** — Area Grid. Reconstructs straight lines from
  waypoints by grouping consecutive waypoints whose heading matches within
  `HEADING_TOLERANCE_DEG` (1.5°). U-turns: `turn_angle = 180°`, direction
  from the side the next line lies on (`RIGHT` if
  `(entry_next − exit_current)·right_normal ≥ 0`). Line spacing comes from
  the grid response or, in the export path, from the reconstructed lines
  (conservative: tightest consecutive spacing).
* **`CorridorTurnPlanner`** — Linear Corridor. Uses the real
  `flight_lines_geojson` geometry; applies serpentine orientation (odd
  segments reversed), computes the actual turn angle from the traversal
  headings at each bend, and derives spacing from the corridor
  (`line_spacing` or actual offset distances). Supports symmetric and
  asymmetric corridors.

`TurnPlanResult.radius_m` is the uniform mission radius (minimum across
turns) and `per_waypoint_curve_size` maps global waypoint indices to curve
sizes (informational).

## LCHM integration (no exporter change)

The LCHM exporter is **not modified**. It already serialises
`wp.curve_size` into the record curve-radius field (`+36`, f32 BE) and forces
`0.0` on the first/last waypoint when `CURVED_TURNS`. The adapter
`apply_turn_radii(waypoints, options)` in `integration.py` computes the
mission radius with the engine and writes it into every waypoint's
`curve_size`, mirroring the observed physical file behaviour.

Configuration lives in `options["turn_radius"]`:

```json
{
  "mode": "AUTO",
  "mission_type": "AREA_GRID",
  "speed_ms": 6.8,
  "line_spacing_m": 51.1,
  "safety_factor": 1.25,
  "max_lateral_acceleration_ms2": 4.5,
  "min_turn_radius_m": 2.0,
  "max_turn_radius_m": 50.0,
  "turn_clearance_m": 4.0,
  "turn_extension_m": null,
  "manual_radius_m": 12.0
}
```

`_build_mission` (`backend/app/api/v1/endpoints.py`) invokes the adapter when
`options["turn_radius"]` is present, and stores the resulting plan under
`options["turn_radius_result"]` plus any warnings under
`options["turn_radius_warnings"]`.

## Worked examples

### Area Grid (physics default)

* `v = 6.8 m/s`, `a_lat = 4.5 m/s²`, `safety_factor = 1.25`
* `R_dynamic = 6.8²/4.5 = 10.28 m`, `R_safe = 12.84 m`
* spacing `100 m`, clearance `4 m` → `R_available = 46 m`
* `R_safe (12.84) ≤ R_available (46)` → **`VALID`, radius = 12.84 m**

### Area Grid (tight spacing → CONSTRAINED)

* Same speed/a_lat/safety → `R_safe = 12.84 m`
* spacing `26 m`, clearance `4 m` → `R_available = (26 − 8)/2 = 9 m`
* `R_safe > R_available` → **`CONSTRAINED`, radius = 9 m** with mitigation
  warnings (no silent reduction).

### Linear Corridor (90° bend)

Two flight lines meeting at a corner produce a real turn angle of 90°; the
engine uses the corridor geometry so the radius is validated against the
actual bend, not an assumed 180°.

### Regression vs the physical reference

`area_grid_74_time5_curve.lchm` (74 waypoints, CURVED + CUSTOM, speed
≈6.81 m/s) carries a median curve radius of ≈12.637 m on waypoints 1..72.
The regression test derives the implied lateral acceleration from that file
(`a_lat = v²/(R/1.25)` ≈ 4.59 m/s²) and asserts the engine reproduces the
observed radius — validating the formula against real data without
hardcoding 12.637.

## Fase 9 — frontend integration (API surface)

The engine is exposed to the frontend through three additions:

* `GridRequest.turn_radius` / `CorridorRequest.turn_radius` (optional config
  dict). When present, the grid/corridor responses carry the computed plan in
  `turn_radius_result` and any plan warnings in `turn_radius_warnings`.
* `POST /api/v1/planning/turn-radius` — live recompute for an existing flight
  plan. Body: `mission_type`, `waypoints`, `line_spacing`,
  `recommended_speed_ms`, `turn_radius` config and (for Linear Corridor) the
  real `flight_lines_geojson`. Returns `{turn_radius_result, turn_radius_warnings}`.
  It reuses the exact planner that computes the export radius, so the value
  shown in the planner always matches the value serialised into the LCHM.
* `TurnPlanResult.geometry` — a mission-level GeoJSON FeatureCollection
  merging every turn's arc / center / clearance buffer in EPSG:4326, each
  feature tagged `properties.kind` (`turn_arc`, `turn_center`,
  `clearance_buffer`) and `properties.turn`. The frontend renders this
  directly (it never recomputes turn geometry). Per-turn metadata also
  exposes `a_lat_ms2` and `safety_factor` for the advanced info panel.

`integration.compute_turn_radius_plan` is the non-mutating helper behind
both the planning endpoints and `apply_turn_radii` (export path), keeping a
single source of truth.

## Design decisions & limitations

* **No obstacle avoidance / terrain following / dynamic speed control** —
  out of scope for this phase; the engine is purely geometric.
* **No DJI-specific undocumented dynamics** — defaults are conservative
  engineering values with explicit provenance.
* **No new exporters** — LCHM consumes the engine's radius via
  `curve_size`; the exporter code is untouched.
* `turn_extension_m` AUTO equals one turn radius (a planning recommendation;
  LCHM does not carry it).
* The analytic spacing bound is exact for U-turns between parallel lines;
  the optional `boundary` geometric check applies to caller-supplied
  maneuver regions (not the survey footprint, since turns happen outside it).
* Performance is linear in the number of turns (no O(N²)); the geometric
  binary search is bounded (48 iterations).

## Acceptance

* `pytest` - full suite green (251 passed, 0 failed at time of writing,
  including 7 new tests for the recompute path and mission geometry).
* `ruff` - clean on all new files (pre-existing E402/E501 in
  `endpoints.py` untouched).
* `tsc --noEmit`, `npm run build` and `vitest run` - frontend green
  (83 tests, including turn-radius config/staleness/store tests).
* No commit made for this phase.
