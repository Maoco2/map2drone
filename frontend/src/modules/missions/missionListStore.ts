import { create } from 'zustand';
import type { Mission } from '@/shared/types/project';
import { api } from '@/shared/utils/api';
import { useProjectStore } from '@/modules/projects/store';

interface MissionListState {
  missions: Mission[];
  selectedMissionId: string | null;
  loading: boolean;
  fetchMissions: () => Promise<void>;
  selectMission: (id: string | null) => void;
  renameMission: (id: string, name: string) => Promise<void>;
  deleteMission: (id: string) => Promise<void>;
}

export const useMissionListStore = create<MissionListState>((set, get) => ({
  missions: [],
  selectedMissionId: null,
  loading: false,

  fetchMissions: async () => {
    const projectId = useProjectStore.getState().selectedProjectId;
    if (!projectId) {
      set({ missions: [], loading: false });
      return;
    }
    set({ loading: true });
    try {
      const missions = await api.missions.list(projectId);
      set({ missions, loading: false });
    } catch {
      set({ loading: false });
    }
  },

  selectMission: (id) => set({ selectedMissionId: id }),

  renameMission: async (id, name) => {
    await api.missions.update(id, { name });
    const missions = get().missions.map((m) => (m.id === id ? { ...m, name } : m));
    set({ missions });
  },

  deleteMission: async (id) => {
    await api.missions.delete(id);
    const missions = get().missions.filter((m) => m.id !== id);
    set({ missions, selectedMissionId: get().selectedMissionId === id ? null : get().selectedMissionId });
  },
}));
