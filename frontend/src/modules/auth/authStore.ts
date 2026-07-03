import { create } from 'zustand';
import type { User } from '@/shared/types/project';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  setAuth: (user: User, token: string) => void;
  logout: () => void;
}

function loadPersisted(): { user: User | null; token: string | null } {
  try {
    const token = localStorage.getItem('token');
    const user = localStorage.getItem('user');
    if (token && user) {
      return { token, user: JSON.parse(user) };
    }
  } catch {}
  return { user: null, token: null };
}

const persisted = loadPersisted();

export const useAuthStore = create<AuthState>((set) => ({
  user: persisted.user,
  token: persisted.token,
  isAuthenticated: !!persisted.token && !!persisted.user,
  setAuth: (user, token) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
    set({ user, token, isAuthenticated: true });
  },
  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    set({ user: null, token: null, isAuthenticated: false });
  },
}));
