import { create } from 'zustand';
import { api } from '@/shared/utils/api';
import type {
  OptimizationConstraints,
  OptimizerApplyResponse,
  OptimizerSolveRequest,
  OptimizerSolveResponse,
  OptimizerVariableDeclaration,
  OptimizerVariableMode,
} from '@/shared/types/project';
import { useMissionStore } from '@/modules/missions/planningStore';
import { useDrawStore } from '@/modules/map/drawStore';
import { useTurnRadiusStore } from '@/modules/planning/turnRadiusStore';
import { buildTurnRadiusConfig, missionTypeLabel } from '@/shared/utils/turnRadius';
import { useProjectStore } from '@/modules/projects/store';
import { buildOptimizerRequest } from './optimizerRequest';

export const OPTIMIZABLE_VARIABLES = [
  { name: 'altitude_m', label: 'Altitude (m)', unit: 'm' },
  { name: 'speed_mps', label: 'Speed (m/s)', unit: 'm/s' },
  { name: 'front_overlap', label: 'Front overlap', unit: '%' },
  { name: 'side_overlap', label: 'Side overlap', unit: '%' },
  { name: 'photo_interval_s', label: 'Photo interval', unit: 's' },
  { name: 'turn_radius_m', label: 'Turn radius', unit: 'm' },
] as const;

export interface OptimizerVarEditor {
  name: string;
  enabled: boolean;
  mode: OptimizerVariableMode;
  fixedValue: number;
  minValue: number;
  maxValue: number;
  step: number;
  candidatesText: string;
}

export const CONSTRAINT_KEYS: { key: keyof OptimizationConstraints; label: string }[] = [
  { key: 'min_altitude', label: 'Min altitude (m)' },
  { key: 'max_altitude', label: 'Max altitude (m)' },
  { key: 'min_speed', label: 'Min speed (m/s)' },
  { key: 'max_speed', label: 'Max speed (m/s)' },
  { key: 'min_gsd', label: 'Min GSD (cm/px)' },
  { key: 'max_gsd', label: 'Max GSD (cm/px)' },
  { key: 'preferred_gsd', label: 'Preferred GSD (cm/px)' },
  { key: 'min_overlap_front', label: 'Min front overlap %' },
  { key: 'max_overlap_front', label: 'Max front overlap %' },
  { key: 'preferred_overlap_front', label: 'Preferred front overlap %' },
  { key: 'min_overlap_side', label: 'Min side overlap %' },
  { key: 'max_overlap_side', label: 'Max side overlap %' },
  { key: 'preferred_overlap_side', label: 'Preferred side overlap %' },
  { key: 'max_flight_time', label: 'Max flight time (min)' },
  { key: 'max_battery_count', label: 'Max batteries' },
  { key: 'max_photo_count', label: 'Max photos' },
  { key: 'preferred_turn_radius', label: 'Preferred turn radius (m)' },
];

function defaultVars(): OptimizerVarEditor[] {
  const defs: Record<string, OptimizerVarEditor> = {
    altitude_m: { name: 'altitude_m', enabled: true, mode: 'range', fixedValue: 100, minValue: 80, maxValue: 120, step: 10, candidatesText: '80,90,100,110,120' },
    speed_mps: { name: 'speed_mps', enabled: true, mode: 'range', fixedValue: 7, minValue: 5, maxValue: 9, step: 1, candidatesText: '5,6,7,8,9' },
    front_overlap: { name: 'front_overlap', enabled: false, mode: 'range', fixedValue: 75, minValue: 70, maxValue: 85, step: 5, candidatesText: '70,75,80,85' },
    side_overlap: { name: 'side_overlap', enabled: false, mode: 'range', fixedValue: 65, minValue: 60, maxValue: 80, step: 5, candidatesText: '60,65,70,75,80' },
    photo_interval_s: { name: 'photo_interval_s', enabled: false, mode: 'range', fixedValue: 2, minValue: 1, maxValue: 5, step: 1, candidatesText: '1,2,3,4,5' },
    turn_radius_m: { name: 'turn_radius_m', enabled: false, mode: 'fixed', fixedValue: 12, minValue: 5, maxValue: 30, step: 1, candidatesText: '5,10,15,20,25,30' },
  };
  return OPTIMIZABLE_VARIABLES.map((v) => defs[v.name]);
}

function defaultConstraints(): Record<string, string> {
  return {
    min_altitude: '',
    max_altitude: '',
    min_speed: '',
    max_speed: '',
    min_gsd: '',
    max_gsd: '',
    preferred_gsd: '',
    min_overlap_front: '',
    max_overlap_front: '',
    preferred_overlap_front: '',
    min_overlap_side: '',
    max_overlap_side: '',
    preferred_overlap_side: '',
    max_flight_time: '',
    max_battery_count: '',
    max_photo_count: '',
    preferred_turn_radius: '',
  };
}

export function buildVariables(vars: OptimizerVarEditor[]): OptimizerVariableDeclaration[] {
  return vars
    .filter((v) => v.enabled)
    .map((v) => {
      if (v.mode === 'fixed') return { name: v.name, mode: 'fixed', value: v.fixedValue };
      if (v.mode === 'candidate_values') {
        const values = v.candidatesText
          .split(',')
          .map((s) => Number(s.trim()))
          .filter((n) => Number.isFinite(n));
        return { name: v.name, mode: 'candidate_values', values };
      }
      return { name: v.name, mode: 'range', min_value: v.minValue, max_value: v.maxValue, step: v.step };
    });
}

export function buildConstraints(raw: Record<string, string>): OptimizationConstraints | undefined {
  const out: Record<string, number> = {};
  for (const [key, val] of Object.entries(raw)) {
    if (val.trim() === '') continue;
    const n = Number(val);
    if (Number.isFinite(n)) out[key] = n;
  }
  return Object.keys(out).length ? (out as OptimizationConstraints) : undefined;
}

interface OptimizerState {
  vars: OptimizerVarEditor[];
  constraints: Record<string, string>;
  maxCandidates: number;
  result: OptimizerSolveResponse | null;
  running: boolean;
  error: string | null;
  lastSolveRequest: OptimizerSolveRequest | null;
  applyResult: OptimizerApplyResponse | null;
  applying: boolean;
  applyError: string | null;

  setVarField: (name: string, patch: Partial<OptimizerVarEditor>) => void;
  setConstraint: (key: string, value: string) => void;
  setMaxCandidates: (n: number) => void;
  clearResult: () => void;
  reset: () => void;
  solve: () => Promise<void>;
  applyWinner: () => Promise<void>;
  clearApply: () => void;
}

export const useOptimizerStore = create<OptimizerState>((set, get) => ({
  vars: defaultVars(),
  constraints: defaultConstraints(),
  maxCandidates: 200,
  result: null,
  running: false,
  error: null,
  lastSolveRequest: null,
  applyResult: null,
  applying: false,
  applyError: null,

  setVarField: (name, patch) =>
    set({ vars: get().vars.map((v) => (v.name === name ? { ...v, ...patch } : v)) }),

  setConstraint: (key, value) =>
    set({ constraints: { ...get().constraints, [key]: value } }),

  setMaxCandidates: (maxCandidates) => set({ maxCandidates }),

  clearResult: () => set({ result: null, error: null, lastSolveRequest: null }),

  clearApply: () => set({ applyResult: null, applyError: null }),

  reset: () =>
    set({
      vars: defaultVars(),
      constraints: defaultConstraints(),
      maxCandidates: 200,
      result: null,
      running: false,
      error: null,
      lastSolveRequest: null,
      applyResult: null,
      applying: false,
      applyError: null,
    }),

  solve: async () => {
    const ms = useMissionStore.getState();
    const tr = useTurnRadiusStore.getState();
    const turnRadiusConfig = buildTurnRadiusConfig(
      {
        mode: tr.mode,
        manualRadius: tr.manualRadius,
        speedOverride: tr.speedOverride,
        safetyFactor: tr.safetyFactor,
        clearance: tr.clearance,
        maxLatAccel: tr.maxLatAccel,
        minRadius: tr.minRadius,
        maxRadius: tr.maxRadius,
      },
      0,
      { mission_type: missionTypeLabel(ms.missionVariant), line_spacing: 0 },
    );
    const base = buildOptimizerRequest({
      variant: ms.missionVariant,
      droneId: ms.droneId,
      altitude: ms.altitude,
      overlapFrontal: ms.overlapFrontal,
      overlapLateral: ms.overlapLateral,
      altitudeMode: ms.altitudeMode,
      gridType: 'simple',
      widthLeft: ms.widthLeft,
      widthRight: ms.widthRight,
      projectId: useProjectStore.getState().selectedProjectId || undefined,
      turnRadius: turnRadiusConfig ?? undefined,
      features: useDrawStore.getState().features,
    });
    if (!base) {
      set({
        running: false,
        error:
          ms.missionVariant === 'corridor'
            ? 'Draw the corridor centerline first using the Polyline tool'
            : 'Draw the area polygon first',
      });
      return;
    }
    const variables = buildVariables(get().vars);
    const constraints = buildConstraints(get().constraints);
    const request: OptimizerSolveRequest = {
      ...base,
      ...(variables.length ? { variables: { variables } } : {}),
      ...(constraints ? { constraints } : {}),
      max_candidates: get().maxCandidates,
    };
    set({ running: true, error: null });
    try {
      const res = await api.optimizer.solve(request);
      set({ result: res, running: false, lastSolveRequest: request });
    } catch (err: any) {
      set({ running: false, error: err.message || 'Optimization failed' });
    }
  },

  applyWinner: async () => {
    const { result, lastSolveRequest } = get();
    const winner = result?.best_candidate;
    if (!winner || !lastSolveRequest) {
      set({ applyError: 'Optimize first to obtain a winner mission' });
      return;
    }
    set({ applying: true, applyError: null });
    try {
      const res = await api.optimizer.apply({
        solve_request: lastSolveRequest,
        winner: winner.mission,
        winner_variable_values: winner.variable_values,
        project_id: useProjectStore.getState().selectedProjectId || null,
      });
      set({ applyResult: res, applying: false });
    } catch (err: any) {
      set({ applying: false, applyError: err.message || 'Apply failed' });
    }
  },
}));