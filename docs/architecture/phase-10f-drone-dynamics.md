# 10F — Diseño Drone Dynamics (Punto 6, auditoría 10F)

**Fecha:** 2026-08-18 · **Estado:** solo diseño (enum + plumbing existen;
`DRONE_PROFILE` sin poblar desde DB en 10F).

## Estado actual confirmado

- `DroneDynamicsProvenance` (enum) ya existe en
  `app/modules/mission/models.py:222`: `DEFAULT | USER | DRONE_PROFILE`.
- `DroneFlightDynamicsProfile.provenance` default = `DEFAULT` (no inventar datos).
- `builder._drone_dynamics_profile(req)` (línea 148) lee `turn_radius.drone_dynamics`
  del request y, si el dict incluye `source`, mapea `DroneDynamicsProvenance(source)`.
  Si no hay dict → perfil `DEFAULT`.
- **Gap**: el builder **nunca puebla `DRONE_PROFILE`** a partir de la fila de
  `Drone` en DB. Un request sin `drone_dynamics` explícito produce siempre
  `DEFAULT`, aunque el dron tenga parámetros de fabricante (`max_speed_ms`,
  `flight_time_min`, …).

## Diseño para 10G (no implementado en 10F)

### Cadena de resolución de `provenance` (primera coincidencia)

1. **`USER`** — el request trae `turn_radius.drone_dynamics` (el usuario ajustó
   explícitamente los parámetros dinámicos). `source` omitido → USER (comportamiento
   actual).
2. **`DRONE_PROFILE`** — no hay override de usuario **y** el dron seleccionado
   (`db.query(Drone)`) tiene valores de dinámica (p. ej. `max_speed_ms`,
   `flight_time_min`, o un campo futuro `max_lateral_acceleration_ms2`).
   `_drone_dynamics_profile(req, drone)` poblaría el perfil desde la fila.
3. **`DEFAULT`** — ni override de usuario ni datos de fabricante → fallback
   conservador (sin inventar).

### Reglas

- **No duplicar**: los valores vienen de la fila de `Drone` (o del request USER);
  el builder solo los copia al perfil, no recalcula.
- El `turn_radius` config del request **no debe sobrescribir** un `DRONE_PROFILE`
  salvo `USER`: la cadena es USER → DRONE_PROFILE → DEFAULT.
- Cambio mínimo en `build_universal_mission`: pasar `drone` a
  `_drone_dynamics_profile` y emitir `DRONE_PROFILE` cuando aplique.

### Impacto

- `DroneFlightDynamicsProfile` y el enum no cambian de forma (compatibles).
- Los fixtures/adapters de export y UMM 1.0 intactos (el campo es
  opcional/nullable y ya existe en el modelo).
- El score de turn (10E) sigue consumiendo `provenance` solo como metadato de
  trazabilidad; el cambio de 10G no altera las funciones de utilidad.

**Sin implementar en 10F** — el punto 6 de la auditoría queda como diseño/deuda
10G para no tocar el builder fuera del alcance operacional de la integración.