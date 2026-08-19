import type {
  GridResult,
  TurnRadiusConfig,
  TurnRadiusMode,
  TurnStatus,
} from '@/shared/types/project';

export const DEFAULT_SAFETY_FACTOR = 1.25;
export const DEFAULT_CLEARANCE_M = 4.0;
export const DEFAULT_MAX_LAT_ACCEL_MS2 = 4.5;
export const DEFAULT_MIN_RADIUS_M = 2.0;
export const DEFAULT_MAX_RADIUS_M = 50.0;

export interface TurnInputs {
  mode: TurnRadiusMode;
  manualRadius: number;
  speedOverride: number;
  safetyFactor: number;
  clearance: number;
  maxLatAccel: number;
  minRadius: number;
  maxRadius: number;
}

export interface PlanFacts {
  recommendedSpeed: number;
  lineSpacing: number;
  widthLeft: number;
  widthRight: number;
  missionVariant: 'grid' | 'corridor';
}

export interface TurnSnapshot {
  mode: TurnRadiusMode;
  manualRadius: number;
  speed: number;
  lineSpacing: number;
  widthLeft: number;
  widthRight: number;
  missionVariant: string;
  safetyFactor: number;
  clearance: number;
  maxLatAccel: number;
  minRadius: number;
  maxRadius: number;
}

export function effectiveSpeed(inputs: TurnInputs, recommendedSpeed: number): number {
  return inputs.speedOverride > 0 ? inputs.speedOverride : recommendedSpeed;
}

export function missionTypeLabel(variant: 'grid' | 'corridor'): 'AREA_GRID' | 'LINEAR_CORRIDOR' {
  return variant === 'corridor' ? 'LINEAR_CORRIDOR' : 'AREA_GRID';
}

export function buildTurnRadiusConfig(
  inputs: TurnInputs,
  recommendedSpeed: number,
  plan: {
    mission_type: 'AREA_GRID' | 'LINEAR_CORRIDOR';
    line_spacing: number;
    flight_lines_geojson?: GeoJSON.FeatureCollection;
  },
): TurnRadiusConfig | undefined {
  if (inputs.mode === 'NONE') return undefined;
  const cfg: TurnRadiusConfig = {
    mode: inputs.mode,
    mission_type: plan.mission_type,
    safety_factor: inputs.safetyFactor,
    max_lateral_acceleration_ms2: inputs.maxLatAccel,
    min_turn_radius_m: inputs.minRadius,
    max_turn_radius_m: inputs.maxRadius,
    turn_clearance_m: inputs.clearance,
  };
  const speed = effectiveSpeed(inputs, recommendedSpeed);
  if (speed > 0) cfg.speed_ms = round3(speed);
  if (plan.line_spacing > 0) cfg.line_spacing_m = round3(plan.line_spacing);
  if (inputs.mode === 'MANUAL') cfg.manual_radius_m = inputs.manualRadius;
  if (plan.flight_lines_geojson) cfg.flight_lines_geojson = plan.flight_lines_geojson;
  return cfg;
}

export function buildSnapshot(inputs: TurnInputs, facts: PlanFacts): TurnSnapshot {
  return {
    mode: inputs.mode,
    manualRadius: inputs.manualRadius,
    speed: round3(effectiveSpeed(inputs, facts.recommendedSpeed)),
    lineSpacing: round3(facts.lineSpacing),
    widthLeft: facts.widthLeft,
    widthRight: facts.widthRight,
    missionVariant: facts.missionVariant,
    safetyFactor: inputs.safetyFactor,
    clearance: inputs.clearance,
    maxLatAccel: inputs.maxLatAccel,
    minRadius: inputs.minRadius,
    maxRadius: inputs.maxRadius,
  };
}

export function isTurnRadiusStale(
  snapshot: TurnSnapshot | null,
  inputs: TurnInputs,
  facts: PlanFacts,
): boolean {
  if (!snapshot) return true;
  const cur = buildSnapshot(inputs, facts);
  return (
    snapshot.mode !== cur.mode ||
    snapshot.manualRadius !== cur.manualRadius ||
    snapshot.speed !== cur.speed ||
    snapshot.lineSpacing !== cur.lineSpacing ||
    snapshot.widthLeft !== cur.widthLeft ||
    snapshot.widthRight !== cur.widthRight ||
    snapshot.missionVariant !== cur.missionVariant ||
    snapshot.safetyFactor !== cur.safetyFactor ||
    snapshot.clearance !== cur.clearance ||
    snapshot.maxLatAccel !== cur.maxLatAccel ||
    snapshot.minRadius !== cur.minRadius ||
    snapshot.maxRadius !== cur.maxRadius
  );
}

export function factsFromGrid(
  grid: GridResult | null,
  variant: 'grid' | 'corridor',
  widthLeft: number,
  widthRight: number,
): PlanFacts {
  return {
    recommendedSpeed: grid?.recommended_speed_ms ?? 0,
    lineSpacing: grid?.line_spacing ?? 0,
    widthLeft,
    widthRight,
    missionVariant: variant,
  };
}

export const TURN_STATUS_STYLE: Record<
  TurnStatus,
  { color: string; label: string }
> = {
  VALID: { color: '#00c853', label: 'VÁLIDO' },
  CONSTRAINED: { color: '#ff9100', label: 'LIMITADO POR ESPACIO' },
  INVALID: { color: '#e53935', label: 'INVALIDO' },
  NONE: { color: '#9e9e9e', label: 'SIN GIROS' },
};

export const DEFAULT_TURN_INPUTS: TurnInputs = {
  mode: 'NONE',
  manualRadius: 12,
  speedOverride: 0,
  safetyFactor: DEFAULT_SAFETY_FACTOR,
  clearance: DEFAULT_CLEARANCE_M,
  maxLatAccel: DEFAULT_MAX_LAT_ACCEL_MS2,
  minRadius: DEFAULT_MIN_RADIUS_M,
  maxRadius: DEFAULT_MAX_RADIUS_M,
};

function round3(v: number): number {
  return Math.round(v * 1000) / 1000;
}
