import { describe, expect, it, vi, beforeEach } from 'vitest';
import { useTurnRadiusStore } from './turnRadiusStore';
import { api } from '@/shared/utils/api';
import type { GridResult, TurnRadiusPlanResult } from '@/shared/types/project';

vi.mock('@/shared/utils/api', () => ({
  api: {
    planning: {
      turnRadius: vi.fn(),
    },
  },
}));

const mockedTurnRadius = vi.mocked(api.planning.turnRadius);

function planResult(overrides: Partial<TurnRadiusPlanResult> = {}): TurnRadiusPlanResult {
  return {
    mission_type: 'AREA_GRID',
    mode: 'AUTO',
    status: 'VALID',
    radius_m: 12.6,
    turn_count: 2,
    turns: [],
    per_waypoint_curve_size: {},
    warnings: [],
    explanation: '',
    geometry: { type: 'FeatureCollection', features: [] },
    epsg: 32630,
    crs_name: 'WGS84 / UTM zone 30N',
    ...overrides,
  };
}

function grid(overrides: Partial<GridResult> = {}): GridResult {
  return {
    waypoints: [
      { latitude: 37, longitude: -3.5, altitude: 100, heading: 90 },
      { latitude: 37.001, longitude: -3.497, altitude: 100, heading: 270 },
      { latitude: 37.002, longitude: -3.5, altitude: 100, heading: 90 },
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

beforeEach(() => {
  useTurnRadiusStore.getState().reset();
  mockedTurnRadius.mockReset();
});

describe('turnRadiusStore', () => {
  it('resets to defaults', () => {
    const s = useTurnRadiusStore.getState();
    expect(s.mode).toBe('NONE');
    expect(s.result).toBeNull();
    expect(s.snapshot).toBeNull();
    expect(s.manualRadius).toBe(12);
  });

  it('updates mode and manual radius', () => {
    useTurnRadiusStore.getState().setMode('MANUAL');
    useTurnRadiusStore.getState().setManualRadius(20);
    const s = useTurnRadiusStore.getState();
    expect(s.mode).toBe('MANUAL');
    expect(s.manualRadius).toBe(20);
  });

  it('hydrates the result from the grid response', () => {
    const g = grid({ turn_radius_result: planResult(), turn_radius_warnings: ['a'] });
    useTurnRadiusStore.getState().hydrateFromGrid(g, 'grid');
    const s = useTurnRadiusStore.getState();
    expect(s.result?.radius_m).toBe(12.6);
    expect(s.warnings).toEqual(['a']);
    expect(s.snapshot).not.toBeNull();
    expect(mockedTurnRadius).not.toHaveBeenCalled();
  });

  it('clears on hydrate when the grid has no result', () => {
    useTurnRadiusStore.getState().hydrateFromGrid(grid(), 'grid');
    const s = useTurnRadiusStore.getState();
    expect(s.result).toBeNull();
    expect(s.snapshot).toBeNull();
  });

  it('clears on hydrate with a null grid', () => {
    useTurnRadiusStore.getState().setMode('AUTO');
    useTurnRadiusStore.getState().hydrateFromGrid(null, 'grid');
    const s = useTurnRadiusStore.getState();
    expect(s.result).toBeNull();
    expect(s.snapshot).toBeNull();
    expect(s.mode).toBe('AUTO');
  });

  it('recomputes with the correct AUTO payload', async () => {
    mockedTurnRadius.mockResolvedValue({ turn_radius_result: planResult() });
    useTurnRadiusStore.getState().setMode('AUTO');
    await useTurnRadiusStore.getState().recompute(grid(), 'grid');
    const body = mockedTurnRadius.mock.calls[0][0];
    expect(body.mission_type).toBe('AREA_GRID');
    expect(body.line_spacing).toBe(100);
    expect(body.recommended_speed_ms).toBe(6.8);
    expect(body.turn_radius.mode).toBe('AUTO');
    expect(body.turn_radius.speed_ms).toBe(6.8);
    const s = useTurnRadiusStore.getState();
    expect(s.result?.radius_m).toBe(12.6);
    expect(s.snapshot?.speed).toBe(6.8);
    expect(s.loading).toBe(false);
  });

  it('recomputes with the manual radius', async () => {
    mockedTurnRadius.mockResolvedValue({ turn_radius_result: planResult({ mode: 'MANUAL', radius_m: 20 }) });
    useTurnRadiusStore.getState().setMode('MANUAL');
    useTurnRadiusStore.getState().setManualRadius(20);
    await useTurnRadiusStore.getState().recompute(grid(), 'grid');
    const body = mockedTurnRadius.mock.calls[0][0];
    expect(body.turn_radius.mode).toBe('MANUAL');
    expect(body.turn_radius.manual_radius_m).toBe(20);
    expect(useTurnRadiusStore.getState().result?.radius_m).toBe(20);
  });

  it('does not call the API when mode is NONE', async () => {
    useTurnRadiusStore.getState().setMode('NONE');
    await useTurnRadiusStore.getState().recompute(grid(), 'grid');
    expect(mockedTurnRadius).not.toHaveBeenCalled();
    const s = useTurnRadiusStore.getState();
    expect(s.result).toBeNull();
    expect(s.snapshot).toBeNull();
  });

  it('sends corridor geometry for corridor recompute', async () => {
    mockedTurnRadius.mockResolvedValue({ turn_radius_result: planResult({ mission_type: 'LINEAR_CORRIDOR' }) });
    const flightLines = { type: 'FeatureCollection', features: [] } as GeoJSON.FeatureCollection;
    const g = grid({
      geometry: {
        polygon_geojson: { type: 'Polygon', coordinates: [] } as any,
        flight_lines_geojson: flightLines,
        epsg_out: 32630,
        crs_name: 'WGS84',
        transformation: '',
      },
    });
    useTurnRadiusStore.getState().setMode('AUTO');
    await useTurnRadiusStore.getState().recompute(g, 'corridor');
    const body = mockedTurnRadius.mock.calls[0][0];
    expect(body.mission_type).toBe('LINEAR_CORRIDOR');
    expect(body.flight_lines_geojson).toBe(flightLines);
    expect(body.turn_radius.flight_lines_geojson).toBe(flightLines);
  });

  it('stores the error when recompute fails', async () => {
    mockedTurnRadius.mockRejectedValue(new Error('boom'));
    useTurnRadiusStore.getState().setMode('AUTO');
    await useTurnRadiusStore.getState().recompute(grid(), 'grid');
    const s = useTurnRadiusStore.getState();
    expect(s.error).toBe('boom');
    expect(s.result).toBeNull();
    expect(s.snapshot).toBeNull();
  });
});