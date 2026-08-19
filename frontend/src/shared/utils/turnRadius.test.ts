import { describe, expect, it } from 'vitest';
import type { GridResult, TurnRadiusMode, TurnRadiusPlanResult } from '@/shared/types/project';
import {
  buildSnapshot,
  buildTurnRadiusConfig,
  effectiveSpeed,
  factsFromGrid,
  isTurnRadiusStale,
  missionTypeLabel,
  TURN_STATUS_STYLE,
  type TurnInputs,
} from './turnRadius';

const INPUTS: TurnInputs = {
  mode: 'AUTO',
  manualRadius: 12,
  speedOverride: 0,
  safetyFactor: 1.25,
  clearance: 4,
  maxLatAccel: 4.5,
  minRadius: 2,
  maxRadius: 50,
};

const FACTS = {
  recommendedSpeed: 6.8,
  lineSpacing: 100,
  widthLeft: 100,
  widthRight: 100,
  missionVariant: 'grid' as const,
};

function grid(overrides: Partial<GridResult> = {}): GridResult {
  return {
    waypoints: [
      { latitude: 37, longitude: -3.5, altitude: 100, heading: 90 },
      { latitude: 37.001, longitude: -3.497, altitude: 100, heading: 270 },
    ],
    total_distance: 1000,
    estimated_time_sec: 100,
    photo_count: 10,
    battery_count: 1,
    gsd: 2,
    footprint_width: 50,
    footprint_height: 40,
    line_spacing: 100,
    photo_spacing: 10,
    recommended_speed_ms: 6.8,
    ...overrides,
  };
}

describe('effectiveSpeed', () => {
  it('uses the recommended speed when no override is set', () => {
    expect(effectiveSpeed(INPUTS, 6.8)).toBe(6.8);
  });
  it('uses the override when set', () => {
    expect(effectiveSpeed({ ...INPUTS, speedOverride: 5.2 }, 6.8)).toBe(5.2);
  });
});

describe('missionTypeLabel', () => {
  it('maps grid/corridor variants', () => {
    expect(missionTypeLabel('grid')).toBe('AREA_GRID');
    expect(missionTypeLabel('corridor')).toBe('LINEAR_CORRIDOR');
  });
});

describe('buildTurnRadiusConfig', () => {
  it('returns undefined for NONE', () => {
    expect(buildTurnRadiusConfig({ ...INPUTS, mode: 'NONE' }, 6.8, {
      mission_type: 'AREA_GRID',
      line_spacing: 100,
    })).toBeUndefined();
  });

  it('builds a full AUTO config', () => {
    const cfg = buildTurnRadiusConfig(INPUTS, 6.8, {
      mission_type: 'AREA_GRID',
      line_spacing: 100,
    });
    expect(cfg).toMatchObject({
      mode: 'AUTO',
      mission_type: 'AREA_GRID',
      speed_ms: 6.8,
      line_spacing_m: 100,
      safety_factor: 1.25,
      max_lateral_acceleration_ms2: 4.5,
      min_turn_radius_m: 2,
      max_turn_radius_m: 50,
      turn_clearance_m: 4,
    });
    expect(cfg?.manual_radius_m).toBeUndefined();
  });

  it('includes manual_radius_m for MANUAL', () => {
    const cfg = buildTurnRadiusConfig({ ...INPUTS, mode: 'MANUAL' }, 6.8, {
      mission_type: 'AREA_GRID',
      line_spacing: 100,
    });
    expect(cfg?.mode).toBe('MANUAL');
    expect(cfg?.manual_radius_m).toBe(12);
  });

  it('omits speed_ms and line_spacing_m when unknown (0)', () => {
    const cfg = buildTurnRadiusConfig(INPUTS, 0, {
      mission_type: 'AREA_GRID',
      line_spacing: 0,
    });
    expect(cfg?.speed_ms).toBeUndefined();
    expect(cfg?.line_spacing_m).toBeUndefined();
  });

  it('uses the speed override when present', () => {
    const cfg = buildTurnRadiusConfig({ ...INPUTS, speedOverride: 5.2 }, 6.8, {
      mission_type: 'AREA_GRID',
      line_spacing: 100,
    });
    expect(cfg?.speed_ms).toBe(5.2);
  });

  it('includes flight_lines_geojson for corridors', () => {
    const flightLines = { type: 'FeatureCollection', features: [] } as GeoJSON.FeatureCollection;
    const cfg = buildTurnRadiusConfig(INPUTS, 6.8, {
      mission_type: 'LINEAR_CORRIDOR',
      line_spacing: 50,
      flight_lines_geojson: flightLines,
    });
    expect(cfg?.flight_lines_geojson).toBe(flightLines);
  });
});

describe('isTurnRadiusStale', () => {
  it('is stale when there is no snapshot', () => {
    expect(isTurnRadiusStale(null, INPUTS, FACTS)).toBe(true);
  });

  it('is fresh when inputs match the snapshot', () => {
    const snap = buildSnapshot(INPUTS, FACTS);
    expect(isTurnRadiusStale(snap, INPUTS, FACTS)).toBe(false);
  });

  it('becomes stale when the mode changes', () => {
    const snap = buildSnapshot(INPUTS, FACTS);
    expect(isTurnRadiusStale(snap, { ...INPUTS, mode: 'MANUAL' }, FACTS)).toBe(true);
  });

  it('becomes stale when the manual radius changes', () => {
    const snap = buildSnapshot({ ...INPUTS, mode: 'MANUAL' }, FACTS);
    expect(isTurnRadiusStale(snap, { ...INPUTS, mode: 'MANUAL', manualRadius: 20 }, FACTS)).toBe(true);
  });

  it('becomes stale when the speed changes', () => {
    const snap = buildSnapshot(INPUTS, FACTS);
    expect(isTurnRadiusStale(snap, { ...INPUTS, speedOverride: 5 }, FACTS)).toBe(true);
  });

  it('becomes stale when the line spacing changes', () => {
    const snap = buildSnapshot(INPUTS, FACTS);
    expect(isTurnRadiusStale(snap, INPUTS, { ...FACTS, lineSpacing: 30 })).toBe(true);
  });

  it('becomes stale when the corridor width changes', () => {
    const snap = buildSnapshot(INPUTS, FACTS);
    expect(isTurnRadiusStale(snap, INPUTS, { ...FACTS, widthLeft: 150 })).toBe(true);
  });

  it('becomes stale when the mission variant changes', () => {
    const snap = buildSnapshot(INPUTS, FACTS);
    expect(isTurnRadiusStale(snap, INPUTS, { ...FACTS, missionVariant: 'corridor' })).toBe(true);
  });

  it('becomes stale when safety factor, clearance or acceleration changes', () => {
    const snap = buildSnapshot(INPUTS, FACTS);
    expect(isTurnRadiusStale(snap, { ...INPUTS, safetyFactor: 1.5 }, FACTS)).toBe(true);
    expect(isTurnRadiusStale(snap, { ...INPUTS, clearance: 6 }, FACTS)).toBe(true);
    expect(isTurnRadiusStale(snap, { ...INPUTS, maxLatAccel: 3 }, FACTS)).toBe(true);
  });
});

describe('TURN_STATUS_STYLE', () => {
  it('provides a label and color for every backend status', () => {
    for (const status of ['VALID', 'CONSTRAINED', 'INVALID', 'NONE'] as const) {
      const style = TURN_STATUS_STYLE[status];
      expect(style.label.length).toBeGreaterThan(0);
      expect(style.color).toMatch(/^#[0-9a-f]{6}$/i);
    }
    // Distinct colors so the user can tell valid / constrained / invalid apart.
    const colors = new Set((['VALID', 'CONSTRAINED', 'INVALID'] as const).map((s) => TURN_STATUS_STYLE[s].color));
    expect(colors.size).toBe(3);
  });
});

describe('factsFromGrid', () => {
  it('extracts speed, spacing and widths from the grid result', () => {
    const facts = factsFromGrid(grid(), 'grid', 120, 80);
    expect(facts).toMatchObject({
      recommendedSpeed: 6.8,
      lineSpacing: 100,
      widthLeft: 120,
      widthRight: 80,
      missionVariant: 'grid',
    });
  });

  it('defaults to zeros when there is no grid result', () => {
    const facts = factsFromGrid(null, 'corridor', 100, 100);
    expect(facts.recommendedSpeed).toBe(0);
    expect(facts.lineSpacing).toBe(0);
  });
});