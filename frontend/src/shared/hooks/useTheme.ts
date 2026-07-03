import { create } from 'zustand';

interface ThemeStore {
  isDark: boolean;
  toggle: () => void;
}

export const useThemeStore = create<ThemeStore>((set) => ({
  isDark: true,
  toggle: () =>
    set((s) => {
      const next = !s.isDark;
      document.documentElement.classList.toggle('dark', next);
      return { isDark: next };
    }),
}));
