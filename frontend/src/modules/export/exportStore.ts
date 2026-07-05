import { create } from 'zustand';
import type { ExportFormat, ExportWaypoint, GridResult } from '@/shared/types/project';

interface ExportState {
  formats: ExportFormat[];
  selectedFormats: string[];
  projectName: string;
  status: 'idle' | 'exporting' | 'done' | 'error';
  progress: number;
  error: string | null;

  setFormats: (fmts: ExportFormat[]) => void;
  toggleFormat: (id: string) => void;
  selectAll: () => void;
  deselectAll: () => void;
  setProjectName: (name: string) => void;
  setStatus: (s: 'idle' | 'exporting' | 'done' | 'error') => void;
  setProgress: (p: number) => void;
  setError: (e: string | null) => void;
  reset: () => void;
}

export const useExportStore = create<ExportState>((set, get) => ({
  formats: [],
  selectedFormats: [],
  projectName: 'Mission',
  status: 'idle',
  progress: 0,
  error: null,

  setFormats: (formats) => set({ formats }),
  toggleFormat: (id) => {
    const curr = get().selectedFormats;
    if (curr.includes(id)) {
      set({ selectedFormats: curr.filter((f) => f !== id) });
    } else {
      set({ selectedFormats: [...curr, id] });
    }
  },
  selectAll: () => {
    set({ selectedFormats: get().formats.map((f) => f.id) });
  },
  deselectAll: () => set({ selectedFormats: [] }),
  setProjectName: (projectName) => set({ projectName }),
  setStatus: (status) => set({ status }),
  setProgress: (progress) => set({ progress }),
  setError: (error) => set({ error }),
  reset: () => set({
    selectedFormats: [],
    status: 'idle',
    progress: 0,
    error: null,
  }),
}));

export function buildExportData(gridResult: GridResult, projectName: string) {
  return {
    project_name: projectName,
    waypoints: (gridResult.waypoints || []).map((wp) => ({
      latitude: wp.latitude,
      longitude: wp.longitude,
      altitude: wp.altitude,
      heading: wp.heading,
      speed: wp.speed,
      action_type: wp.action_type ?? -1,
      action_param: wp.action_param ?? 0,
    })),
    home_latitude: gridResult.waypoints?.[0]?.latitude ?? 0,
    home_longitude: gridResult.waypoints?.[0]?.longitude ?? 0,
    altitude: gridResult.waypoints?.[0]?.altitude ?? 100,
    speed: gridResult.recommended_speed_ms ?? 10,
    altitude_mode: 'takeoff',
    drone_name: '',
    total_distance: gridResult.total_distance ?? 0,
    estimated_time: gridResult.estimated_time_sec ?? 0,
    photo_count: gridResult.photo_count ?? 0,
    gsd: gridResult.gsd ?? 0,
    sweep_deg: gridResult.sweep_deg ?? 0,
    line_spacing: gridResult.line_spacing ?? 0,
    photo_spacing: gridResult.photo_spacing ?? 0,
    battery_count: gridResult.battery_count ?? 0,
  };
}
