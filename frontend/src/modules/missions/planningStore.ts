import { create } from 'zustand';
import type { Waypoint, GridResult } from '@/shared/types/project';

interface MissionState {
  gridResult: GridResult | null;
  generating: boolean;
  error: string | null;
  flightLinesGeoJSON: GeoJSON.FeatureCollection | null;
  corridorPolygon: GeoJSON.Polygon | null;
  corridorWarnings: string[];
  droneId: string;
  altitude: number;
  overlapFrontal: number;
  overlapLateral: number;
  altitudeMode: string;
  waypointMode: string;
  photoSpacing: number;
  missionVariant: 'grid' | 'corridor';
  widthLeft: number;
  widthRight: number;

  setDroneId: (id: string) => void;
  setAltitude: (alt: number) => void;
  setOverlapFrontal: (val: number) => void;
  setOverlapLateral: (val: number) => void;
  setAltitudeMode: (mode: string) => void;
  setGridResult: (result: GridResult | null) => void;
  setGenerating: (v: boolean) => void;
  setError: (err: string | null) => void;
  setMissionVariant: (v: 'grid' | 'corridor') => void;
  setWidthLeft: (w: number) => void;
  setWidthRight: (w: number) => void;
  clear: () => void;
}

function waypointsToFeatures(waypoints: Waypoint[]): GeoJSON.Feature[] {
  return waypoints.map((wp, i) => ({
    type: 'Feature',
    id: `wp_${i}`,
    geometry: { type: 'Point', coordinates: [wp.longitude, wp.latitude] },
    properties: { index: i + 1, altitude: wp.altitude, heading: wp.heading, type: 'waypoint' },
  }));
}

export const useMissionStore = create<MissionState>((set) => ({
  gridResult: null,
  generating: false,
  error: null,
  flightLinesGeoJSON: null,
  corridorPolygon: null,
  corridorWarnings: [],
  droneId: '',
  altitude: 100,
  overlapFrontal: 75,
  overlapLateral: 65,
  altitudeMode: 'takeoff',
  waypointMode: 'photo',
  photoSpacing: 0,
  missionVariant: 'grid',
  widthLeft: 100,
  widthRight: 100,

  setDroneId: (id) => set({ droneId: id }),
  setAltitude: (alt) => set({ altitude: alt }),
  setOverlapFrontal: (val) => set({ overlapFrontal: val }),
  setOverlapLateral: (val) => set({ overlapLateral: val }),
  setAltitudeMode: (mode) => set({ altitudeMode: mode }),
  setGridResult: (result) => {
    if (!result) {
      set({ gridResult: null, flightLinesGeoJSON: null, corridorPolygon: null, corridorWarnings: [] });
      return;
    }
    // Backend is the single source of truth for flight lines and photo points;
    // the frontend only visualizes them (it no longer reconstructs geometry).
    const lines: GeoJSON.Feature[] = [];
    const flightLines =
      result.flight_lines_geojson ?? result.geometry?.flight_lines_geojson;
    if (flightLines?.features?.length) {
      flightLines.features.forEach((f, i) => {
        lines.push({
          type: 'Feature',
          id: `fl_${i}`,
          geometry: f.geometry,
          properties: { type: 'scan' },
        });
      });
    }

    const points: GeoJSON.Feature[] = waypointsToFeatures(result.waypoints);

    const photoTriggers: GeoJSON.Feature[] = (result.photo_points ?? [])
      .filter((p) => p.capture)
      .map((p) => ({
        type: 'Feature',
        id: `pt_${p.index}`,
        geometry: { type: 'Point', coordinates: [p.longitude, p.latitude] },
        properties: { type: 'photo_trigger' },
      }));

    const fc: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: [...lines, ...points, ...photoTriggers],
    };

    set({
      gridResult: result,
      flightLinesGeoJSON: fc,
      corridorPolygon: result.geometry?.polygon_geojson ?? null,
      corridorWarnings: result.warnings ?? [],
      waypointMode: result.waypoint_mode || 'photo',
      photoSpacing: result.photo_spacing,
    });
  },
  setGenerating: (v) => set({ generating: v }),
  setError: (err) => set({ error: err }),
  setMissionVariant: (v) => set({ missionVariant: v }),
  setWidthLeft: (w) => set({ widthLeft: w }),
  setWidthRight: (w) => set({ widthRight: w }),
  clear: () =>
    set({
      gridResult: null,
      generating: false,
      error: null,
      flightLinesGeoJSON: null,
      corridorPolygon: null,
      corridorWarnings: [],
      altitudeMode: 'takeoff',
      waypointMode: 'photo',
      photoSpacing: 0,
    }),
}));
