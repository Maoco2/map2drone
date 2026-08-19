import { describe, expect, it, vi, beforeEach } from 'vitest';
import { useOptimizerStore, buildVariables, buildConstraints } from './optimizerStore';
import { api } from '@/shared/utils/api';
import { useDrawStore } from '@/modules/map/drawStore';
import { useMissionStore } from '@/modules/missions/planningStore';
import type { OptimizerSolveResponse } from '@/shared/types/project';

vi.mock('@/shared/utils/api', () => ({
  api: {
    optimizer: {
      solve: vi.fn(),
    },
  },
}));

const mockedSolve = vi.mocked(api.optimizer.solve);

function solveResponse(overrides: Partial<OptimizerSolveResponse> = {}): OptimizerSolveResponse {
  return {
    status: 'OPTIMAL',
    message: 'Best mission found',
    best_candidate: {
      label: 'candidate-1',
      variable_values: { altitude_m: 100, speed_mps: 7 },
      mission: {
        schema_version: '1.0',
        mission_type: 'grid',
        created_at: '',
        coordinate_reference: 'WGS84',
        parameters: {},
        waypoints: [],
        segments: [],
        metrics: {
          total_distance_m: 1000,
          estimated_time_sec: 600,
          straight_distance_m: 900,
          transition_distance_m: 50,
          turn_distance_m: 50,
          straight_time_s: 500,
          transition_time_s: 30,
          turn_time_s: 70,
          turn_source: 'overhead',
          battery_count: 1,
          gsd_cm: 2.5,
          footprint_width_m: 100,
          footprint_height_m: 80,
          line_spacing_m: 40,
          photo_spacing_m: 15,
          num_lines: 4,
          photo_count: 30,
          flight_distance_m: 1000,
          flight_time_s: 600,
          straight_flight_time_s: 500,
          line_count: 4,
          waypoint_count: 12,
        },
      },
      score: { total_score: 0.9 },
    },
    best_score: { total_score: 0.9 },
    alternatives: [],
    stats: { total: 20, evaluated: 20, valid: 18, invalid: 2, rejected: 0 },
    warnings: [],
    ...overrides,
  };
}

function addPolygon() {
  useDrawStore.getState().addFeature({
    id: 'poly1',
    type: 'rectangle',
    completed: true,
    points: [
      { lng: -3.6, lat: 37.0 },
      { lng: -3.5, lat: 37.1 },
    ],
  });
}

function addCenterline() {
  useDrawStore.getState().addFeature({
    id: 'line1',
    type: 'polyline',
    completed: true,
    points: [
      { lng: -3.6, lat: 37.0 },
      { lng: -3.5, lat: 37.1 },
    ],
  });
}

beforeEach(() => {
  useOptimizerStore.getState().reset();
  useDrawStore.getState().clearAll();
  useMissionStore.getState().clear();
  useMissionStore.getState().setMissionVariant('grid');
  useMissionStore.getState().setDroneId('drone-1');
  mockedSolve.mockReset();
});

describe('optimizerStore', () => {
  it('defaults to altitude and speed range variables', () => {
    const s = useOptimizerStore.getState();
    const altitude = s.vars.find((v) => v.name === 'altitude_m');
    const speed = s.vars.find((v) => v.name === 'speed_mps');
    const turn = s.vars.find((v) => v.name === 'turn_radius_m');
    expect(altitude?.enabled).toBe(true);
    expect(altitude?.mode).toBe('range');
    expect(speed?.enabled).toBe(true);
    expect(speed?.mode).toBe('range');
    expect(turn?.enabled).toBe(false);
    expect(s.maxCandidates).toBe(200);
  });

  it('updates a variable field and a constraint', () => {
    useOptimizerStore.getState().setVarField('altitude_m', { minValue: 60 });
    useOptimizerStore.getState().setConstraint('max_gsd', '3');
    const s = useOptimizerStore.getState();
    expect(s.vars.find((v) => v.name === 'altitude_m')?.minValue).toBe(60);
    expect(s.constraints.max_gsd).toBe('3');
  });

  it('buildVariables converts modes to declarations', () => {
    let s = useOptimizerStore.getState();
    s.setVarField('altitude_m', { mode: 'fixed', fixedValue: 100 });
    s.setVarField('front_overlap', { enabled: true, mode: 'candidate_values', candidatesText: '70, 75, 80' });
    s.setVarField('side_overlap', { enabled: true, mode: 'range', minValue: 60, maxValue: 80, step: 5 });
    s = useOptimizerStore.getState();
    const decls = buildVariables(s.vars);
    const altitude = decls.find((d) => d.name === 'altitude_m');
    expect(altitude).toEqual({ name: 'altitude_m', mode: 'fixed', value: 100 });
    const front = decls.find((d) => d.name === 'front_overlap');
    expect(front).toEqual({ name: 'front_overlap', mode: 'candidate_values', values: [70, 75, 80] });
    const side = decls.find((d) => d.name === 'side_overlap');
    expect(side).toEqual({ name: 'side_overlap', mode: 'range', min_value: 60, max_value: 80, step: 5 });
  });

  it('buildConstraints drops empty and non-numeric values', () => {
    const c = buildConstraints({ max_gsd: '3', max_altitude: '', min_speed: 'abc', max_battery_count: '2' });
    expect(c).toEqual({ max_gsd: 3, max_battery_count: 2 });
  });

  it('solves a grid mission with variables and constraints', async () => {
    mockedSolve.mockResolvedValue(solveResponse());
    addPolygon();
    useOptimizerStore.getState().setConstraint('max_gsd', '3');
    await useOptimizerStore.getState().solve();
    const body = mockedSolve.mock.calls[0][0];
    expect(body.grid!.polygon.type).toBe('Polygon');
    expect(body.grid!.drone_id).toBe('drone-1');
    expect(body.grid!.overlap_frontal).toBe(75);
    expect(body.variables!.variables.map((v: any) => v.name)).toEqual(['altitude_m', 'speed_mps']);
    expect(body.constraints).toEqual({ max_gsd: 3 });
    expect(body.max_candidates).toBe(200);
    const s = useOptimizerStore.getState();
    expect(s.result?.status).toBe('OPTIMAL');
    expect(s.running).toBe(false);
  });

  it('solves a corridor mission', async () => {
    mockedSolve.mockResolvedValue(solveResponse({ status: 'FEASIBLE' }));
    useMissionStore.getState().setMissionVariant('corridor');
    useMissionStore.getState().setWidthLeft(50);
    useMissionStore.getState().setWidthRight(50);
    addCenterline();
    await useOptimizerStore.getState().solve();
    const body = mockedSolve.mock.calls[0][0];
    expect(body.corridor!.centerline.type).toBe('LineString');
    expect(body.corridor!.width_left).toBe(50);
    expect(body.grid).toBeUndefined();
  });

  it('does not call the API when no polygon is drawn', async () => {
    await useOptimizerStore.getState().solve();
    expect(mockedSolve).not.toHaveBeenCalled();
    expect(useOptimizerStore.getState().error).toContain('polygon');
  });

  it('stores the error when the solve fails', async () => {
    mockedSolve.mockRejectedValue(new Error('boom'));
    addPolygon();
    await useOptimizerStore.getState().solve();
    const s = useOptimizerStore.getState();
    expect(s.error).toBe('boom');
    expect(s.result).toBeNull();
    expect(s.running).toBe(false);
  });
});