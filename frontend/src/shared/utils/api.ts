import { QueryClient } from '@tanstack/react-query';
import type { Project, Mission, Drone, Camera, GridResult, TokenResponse, User, ExportFormat } from '@/shared/types/project';

const API_BASE = '/api/v1';

function getToken(): string | null {
  try { return localStorage.getItem('token'); } catch { return null; }
}

function clearAuth() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  window.location.href = '/';
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  try {
    const res = await fetch(`${API_BASE}${url}`, {
      headers,
      signal: controller.signal,
      ...init,
    });
    if (!res.ok) {
      if (res.status === 401) clearAuth();
      const body = await res.text().catch(() => '');
      let detail = `API error: ${res.status}`;
      try { const j = JSON.parse(body); detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail) || detail; } catch {}
      throw new Error(detail);
    }
    return res.json();
  } catch (err: any) {
    if (err.name === 'AbortError') throw new Error('Request timed out (30s)');
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchBlob(url: string, init?: RequestInit): Promise<Blob> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120000);
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (init?.body) headers['Content-Type'] = 'application/json';
  try {
    const res = await fetch(`${API_BASE}${url}`, {
      headers,
      signal: controller.signal,
      ...init,
    });
    if (!res.ok) {
      if (res.status === 401) clearAuth();
      const body = await res.text().catch(() => '');
      let detail = `API error: ${res.status}`;
      try { const j = JSON.parse(body); detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail) || detail; } catch {}
      throw new Error(detail);
    }
    return res.blob();
  } catch (err: any) {
    if (err.name === 'AbortError') throw new Error('Request timed out (120s)');
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}

export const api = {
  auth: {
    register: (data: { full_name: string; email: string; password: string; country: string; city: string; phone: string; gender: string; profession: string }) =>
      fetchJson<TokenResponse>('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
    login: (data: { email: string; password: string }) =>
      fetchJson<TokenResponse>('/auth/login', { method: 'POST', body: JSON.stringify(data) }),
    me: () => fetchJson<User>('/auth/me'),
  },
  projects: {
    list: () => fetchJson<Project[]>('/projects'),
    get: (id: string) => fetchJson<Project>(`/projects/${id}`),
    create: (data: Partial<Project>) =>
      fetchJson<Project>('/projects', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Partial<Project>) =>
      fetchJson<Project>(`/projects/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: string) => fetchJson<void>(`/projects/${id}`, { method: 'DELETE' }),
  },
  missions: {
    list: (projectId: string) => fetchJson<Mission[]>(`/projects/${projectId}/missions`),
    get: (id: string) => fetchJson<Mission>(`/missions/${id}`),
    create: (projectId: string, data: { name: string; mission_type?: string; polygon_geojson?: string; waypoints_json?: string; parameters_json?: string; grid_result_json?: string }) =>
      fetchJson<Mission>(`/projects/${projectId}/missions`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    update: (id: string, data: Partial<Mission>) =>
      fetchJson<Mission>(`/missions/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    delete: (id: string) => fetchJson<void>(`/missions/${id}`, { method: 'DELETE' }),
  },
  drones: {
    list: () => fetchJson<Drone[]>('/drones'),
  },
  cameras: {
    list: () => fetchJson<Camera[]>('/cameras'),
  },
  planning: {
    grid: (data: {
      polygon: GeoJSON.Polygon;
      altitude: number;
      overlap_frontal: number;
      overlap_lateral: number;
      camera_id?: string;
      drone_id: string;
      project_id?: string;
      home_latitude?: number;
      home_longitude?: number;
      rotation_deg?: number;
      grid_type?: string;
      altitude_mode?: string;
    }) => fetchJson<GridResult>('/planning/grid', { method: 'POST', body: JSON.stringify(data) }),
    gsd: (data: { altitude: number; camera_id: string }) =>
      fetchJson<{ gsd: number; footprint_width: number; footprint_height: number }>('/planning/gsd', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },
  export: {
    listFormats: () =>
      fetchJson<ExportFormat[]>('/export/formats'),

    format: (fmt: string, data: any) =>
      fetchBlob(`/export/${fmt}`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    multi: (data: any) =>
      fetchBlob('/export/multi', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

  },
};

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 2, staleTime: 30000 },
  },
});
