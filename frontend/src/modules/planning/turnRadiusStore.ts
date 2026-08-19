import { create } from 'zustand';
import { api } from '@/shared/utils/api';
import type {
  GridResult,
  TurnRadiusMode,
  TurnRadiusPlanResult,
  TurnRadiusRecomputeRequest,
} from '@/shared/types/project';
import { useMissionStore } from '@/modules/missions/planningStore';
import {
  buildSnapshot,
  buildTurnRadiusConfig,
  DEFAULT_TURN_INPUTS,
  factsFromGrid,
  missionTypeLabel,
  type PlanFacts,
  type TurnInputs,
  type TurnSnapshot,
} from '@/shared/utils/turnRadius';

interface TurnRadiusState extends TurnInputs {
  result: TurnRadiusPlanResult | null;
  warnings: string[];
  loading: boolean;
  error: string | null;
  snapshot: TurnSnapshot | null;
  sourceGrid: GridResult | null;
  advancedOpen: boolean;

  setMode: (mode: TurnRadiusMode) => void;
  setManualRadius: (v: number) => void;
  setSpeedOverride: (v: number) => void;
  setSafetyFactor: (v: number) => void;
  setClearance: (v: number) => void;
  setMaxLatAccel: (v: number) => void;
  setMinRadius: (v: number) => void;
  setMaxRadius: (v: number) => void;
  setAdvancedOpen: (v: boolean) => void;
  clearResult: () => void;
  hydrateFromGrid: (grid: GridResult | null, variant: 'grid' | 'corridor') => void;
  recompute: (grid: GridResult, variant: 'grid' | 'corridor') => Promise<void>;
  reset: () => void;
}

export const useTurnRadiusStore = create<TurnRadiusState>((set, get) => ({
  ...DEFAULT_TURN_INPUTS,
  result: null,
  warnings: [],
  loading: false,
  error: null,
  snapshot: null,
  sourceGrid: null,
  advancedOpen: false,

  setMode: (mode) => set({ mode }),
  setManualRadius: (manualRadius) => set({ manualRadius }),
  setSpeedOverride: (speedOverride) => set({ speedOverride }),
  setSafetyFactor: (safetyFactor) => set({ safetyFactor }),
  setClearance: (clearance) => set({ clearance }),
  setMaxLatAccel: (maxLatAccel) => set({ maxLatAccel }),
  setMinRadius: (minRadius) => set({ minRadius }),
  setMaxRadius: (maxRadius) => set({ maxRadius }),
  setAdvancedOpen: (advancedOpen) => set({ advancedOpen }),
  clearResult: () =>
    set({ result: null, warnings: [], snapshot: null, sourceGrid: null, loading: false, error: null }),

  hydrateFromGrid: (grid, variant) => {
    if (!grid) {
      set({ result: null, warnings: [], snapshot: null, sourceGrid: null, loading: false, error: null });
      return;
    }
    const ms = useMissionStore.getState();
    const facts = factsFromGrid(grid, variant, ms.widthLeft, ms.widthRight);
    const tr = grid.turn_radius_result;
    set({
      result: tr ?? null,
      warnings: grid.turn_radius_warnings ?? [],
      snapshot: tr ? buildSnapshot(get(), facts) : null,
      sourceGrid: grid,
      loading: false,
      error: null,
    });
  },

  recompute: async (grid, variant) => {
    const { mode } = get();
    if (mode === 'NONE') {
      set({ result: null, warnings: [], snapshot: null, sourceGrid: null, loading: false, error: null });
      return;
    }
    const ms = useMissionStore.getState();
    const facts: PlanFacts = factsFromGrid(grid, variant, ms.widthLeft, ms.widthRight);
    const flightLines =
      variant === 'corridor' ? grid.geometry?.flight_lines_geojson : undefined;
    const cfg = buildTurnRadiusConfig(get(), facts.recommendedSpeed, {
      mission_type: missionTypeLabel(variant),
      line_spacing: facts.lineSpacing,
      flight_lines_geojson: flightLines,
    });
    if (!cfg) {
      set({ result: null, warnings: [], snapshot: null, sourceGrid: null, loading: false, error: null });
      return;
    }
    set({ loading: true, error: null });
    try {
      const body: TurnRadiusRecomputeRequest = {
        mission_type: missionTypeLabel(variant),
        waypoints: grid.waypoints,
        line_spacing: facts.lineSpacing,
        recommended_speed_ms: facts.recommendedSpeed,
        turn_radius: cfg,
        flight_lines_geojson: flightLines,
      };
      const res = await api.planning.turnRadius(body);
      set({
        result: res.turn_radius_result ?? null,
        warnings: res.turn_radius_warnings ?? [],
        snapshot: buildSnapshot(get(), facts),
        sourceGrid: grid,
        loading: false,
      });
    } catch (err: any) {
      set({
        loading: false,
        error: err.message || 'Turn radius computation failed',
        result: null,
        warnings: [],
        snapshot: null,
        sourceGrid: null,
      });
    }
  },

  reset: () => set({ ...DEFAULT_TURN_INPUTS, result: null, warnings: [], loading: false, error: null, snapshot: null, sourceGrid: null, advancedOpen: false }),
}));
