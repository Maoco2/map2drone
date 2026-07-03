import { create } from 'zustand';

export interface DrawPoint {
  id?: string;
  lng: number;
  lat: number;
}

export interface DrawFeature {
  id: string;
  type: 'polygon' | 'rectangle' | 'circle' | 'line' | 'waypoint';
  points: DrawPoint[];
  properties?: Record<string, any>;
  completed: boolean;
}

interface DrawStore {
  features: DrawFeature[];
  currentFeature: DrawFeature | null;
  drawMode: 'none' | 'drawing' | 'editing';
  snapEnabled: boolean;
  hoveredFeatureId: string | null;
  selectedFeatureId: string | null;

  addFeature: (feature: DrawFeature) => void;
  updateFeature: (id: string, updates: Partial<DrawFeature>) => void;
  removeFeature: (id: string) => void;
  setCurrentFeature: (feature: DrawFeature | null) => void;
  setDrawMode: (mode: 'none' | 'drawing' | 'editing') => void;
  toggleSnap: () => void;
  setHoveredFeatureId: (id: string | null) => void;
  setSelectedFeatureId: (id: string | null) => void;
  clearAll: () => void;
  toGeoJSON: () => GeoJSON.FeatureCollection;
}

let featureCounter = 0;
function nextId() {
  featureCounter += 1;
  return `draw_${featureCounter}`;
}

export const useDrawStore = create<DrawStore>((set, get) => ({
  features: [],
  currentFeature: null,
  drawMode: 'none',
  snapEnabled: false,
  hoveredFeatureId: null,
  selectedFeatureId: null,

  addFeature: (feature) =>
    set((s) => ({ features: [...s.features, feature] })),

  updateFeature: (id, updates) =>
    set((s) => ({
      features: s.features.map((f) => (f.id === id ? { ...f, ...updates } : f)),
    })),

  removeFeature: (id) =>
    set((s) => ({
      features: s.features.filter((f) => f.id !== id),
    })),

  setCurrentFeature: (feature) => set({ currentFeature: feature }),

  setDrawMode: (mode) => set({ drawMode: mode }),

  toggleSnap: () => set((s) => ({ snapEnabled: !s.snapEnabled })),

  setHoveredFeatureId: (id) => set({ hoveredFeatureId: id }),

  setSelectedFeatureId: (id) => set({ selectedFeatureId: id }),

  clearAll: () => set({ features: [], currentFeature: null }),

  toGeoJSON: () => {
    const { features } = get();
    return {
      type: 'FeatureCollection',
      features: features
        .filter((f) => f.completed && f.points.length >= (f.type === 'waypoint' ? 1 : 2))
        .map((f) => {
          let geometry: GeoJSON.Geometry;
          switch (f.type) {
            case 'polygon':
              geometry = {
                type: 'Polygon',
                coordinates: [[...f.points.map((p) => [p.lng, p.lat]), [f.points[0].lng, f.points[0].lat]]],
              };
              break;
            case 'rectangle':
              if (f.points.length >= 2) {
                const [p1, p2] = [f.points[0], f.points[1]];
                geometry = {
                  type: 'Polygon',
                  coordinates: [[
                    [p1.lng, p1.lat],
                    [p2.lng, p1.lat],
                    [p2.lng, p2.lat],
                    [p1.lng, p2.lat],
                    [p1.lng, p1.lat],
                  ]],
                };
              } else {
                geometry = { type: 'Point', coordinates: [0, 0] };
              }
              break;
            case 'circle': {
              if (f.points.length >= 2) {
                const [center, edge] = [f.points[0], f.points[1]];
                const R = 6371000;
                const dLat = ((edge.lat - center.lat) * Math.PI) / 180;
                const dLon = ((edge.lng - center.lng) * Math.PI) / 180;
                const a = Math.sin(dLat / 2) ** 2 + Math.cos((center.lat * Math.PI) / 180) * Math.cos((edge.lat * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
                const radius = R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
                const points: number[][] = [];
                for (let angle = 0; angle <= 360; angle += 10) {
                  const rad = (angle * Math.PI) / 180;
                  const lat = center.lat + (radius / R) * (180 / Math.PI) * Math.cos(rad);
                  const lon = center.lng + (radius / R) * (180 / Math.PI) * Math.sin(rad) / Math.cos((center.lat * Math.PI) / 180);
                  points.push([lon, lat]);
                }
                geometry = { type: 'Polygon', coordinates: [points] };
              } else {
                geometry = { type: 'Point', coordinates: [0, 0] };
              }
              break;
            }
            case 'line':
              geometry = {
                type: 'LineString',
                coordinates: f.points.map((p) => [p.lng, p.lat]),
              };
              break;
            case 'waypoint':
              geometry = {
                type: 'Point',
                coordinates: [f.points[0].lng, f.points[0].lat],
              };
              break;
            default:
              geometry = { type: 'Point', coordinates: [0, 0] };
          }
          return {
            type: 'Feature',
            id: f.id,
            geometry,
            properties: { type: f.type, ...f.properties },
          };
        }),
    };
  },
}));

export { nextId };
