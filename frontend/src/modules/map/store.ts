import { create } from 'zustand';
import type { MapRef } from 'react-map-gl/maplibre';

type Basemap = 'osm' | 'satellite' | 'hybrid';

interface MapStore {
  mapRef: MapRef | null;
  setMapRef: (ref: MapRef | null) => void;
  activeTool: string | null;
  setActiveTool: (tool: string | null) => void;
  cursor: 'default' | 'crosshair' | 'pointer';
  setCursor: (cursor: 'default' | 'crosshair' | 'pointer') => void;
  viewState: {
    latitude: number;
    longitude: number;
    zoom: number;
  };
  setViewState: (state: { latitude: number; longitude: number; zoom: number }) => void;
  basemap: Basemap;
  setBasemap: (bm: Basemap) => void;
}

export const useMapStore = create<MapStore>((set, get) => ({
  mapRef: null,
  setMapRef: (ref) => {
    set({ mapRef: ref });
    const cursor = get().cursor;
    if (ref) {
      const container = ref.getContainer();
      if (container) container.style.cursor = cursor;
    }
  },
  activeTool: null,
  setActiveTool: (tool) => set({ activeTool: tool }),
  cursor: 'default',
  setCursor: (cursor) => {
    set({ cursor });
    const ref = get().mapRef;
    if (ref) {
      const container = ref.getContainer();
      if (container) container.style.cursor = cursor;
    }
  },
  viewState: {
    latitude: 19.4326,
    longitude: -99.1332,
    zoom: 13,
  },
  setViewState: (viewState) => set({ viewState }),
  basemap: 'osm',
  setBasemap: (basemap) => set({ basemap }),
}));
