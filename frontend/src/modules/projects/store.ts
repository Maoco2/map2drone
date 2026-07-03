import { create } from 'zustand';
import type { Project } from '@/shared/types/project';
import { api } from '@/shared/utils/api';

interface ProjectStore {
  projects: Project[];
  selectedProjectId: string | null;
  loading: boolean;
  fetchProjects: () => Promise<void>;
  addProject: (name: string) => Promise<Project>;
  deleteProject: (id: string) => Promise<void>;
  selectProject: (id: string | null) => void;
}

export const useProjectStore = create<ProjectStore>((set, get) => ({
  projects: [],
  selectedProjectId: null,
  loading: false,

  fetchProjects: async () => {
    set({ loading: true });
    try {
      const projects = await api.projects.list();
      set({ projects, loading: false });
    } catch (err) {
      console.error('fetchProjects error:', err);
      set({ loading: false });
    }
  },

  addProject: async (name: string) => {
    const proj = await api.projects.create({ name });
    set((s) => ({ projects: [proj, ...s.projects], selectedProjectId: proj.id }));
    return proj;
  },

  deleteProject: async (id: string) => {
    await api.projects.delete(id);
    set((s) => ({
      projects: s.projects.filter((p) => p.id !== id),
      selectedProjectId: s.selectedProjectId === id ? null : s.selectedProjectId,
    }));
  },

  selectProject: (id) => set({ selectedProjectId: id }),
}));
