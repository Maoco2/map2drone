import { create } from 'zustand';

type Tab = 'projects' | 'basemap' | 'missions' | 'export' | 'optimizer';

interface SidebarState {
  activeTab: Tab;
  setActiveTab: (tab: Tab) => void;
}

export const useSidebarStore = create<SidebarState>((set) => ({
  activeTab: 'projects',
  setActiveTab: (activeTab) => set({ activeTab }),
}));
