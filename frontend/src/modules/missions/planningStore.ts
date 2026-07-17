import { create } from 'zustand';
import type { Waypoint, GridResult } from '@/shared/types/project';

interface MissionState {
  gridResult: GridResult | null;
  generating: boolean;
  error: string | null;
  flightLinesGeoJSON: GeoJSON.FeatureCollection | null;
  droneId: string;
  altitude: number;
  overlapFrontal: number;
  overlapLateral: number;
  altitudeMode: string;
  waypointMode: string;
  photoSpacing: number;

  setDroneId: (id: string) => void;
  setAltitude: (alt: number) => void;
  setOverlapFrontal: (val: number) => void;
  setOverlapLateral: (val: number) => void;
  setAltitudeMode: (mode: string) => void;
  setGridResult: (result: GridResult | null) => void;
  setGenerating: (v: boolean) => void;
  setError: (err: string | null) => void;
  clear: () => void;
}

function headingDiff(a: number, b: number): number {
  let d = Math.abs(a - b) % 360;
  if (d > 180) d = 360 - d;
  return d;
}

function interpolatePhotoPoints(
  waypoints: Waypoint[],
  photoSpacing: number,
  isInterval: boolean,
): GeoJSON.Feature[] {
  if (!isInterval || photoSpacing <= 0) return [];
  const points: GeoJSON.Feature[] = [];
  const R = 6371000;
  function distMeters(a: Waypoint, b: Waypoint): number {
    const dLat = ((b.latitude - a.latitude) * Math.PI) / 180;
    const dLng = ((b.longitude - a.longitude) * Math.PI) / 180;
    const lat1 = (a.latitude * Math.PI) / 180;
    const lat2 = (b.latitude * Math.PI) / 180;
    const sinDLat = Math.sin(dLat / 2);
    const sinDLng = Math.sin(dLng / 2);
    const h = sinDLat * sinDLat + Math.cos(lat1) * Math.cos(lat2) * sinDLng * sinDLng;
    return 2 * R * Math.asin(Math.sqrt(h));
  }
  for (let i = 0; i < waypoints.length - 1; i++) {
    const a = waypoints[i];
    const b = waypoints[i + 1];
    if (headingDiff(a.heading, b.heading) > 45) continue;
    const segLen = distMeters(a, b);
    const steps = Math.floor(segLen / photoSpacing);
    for (let s = 1; s <= steps; s++) {
      const frac = (s * photoSpacing) / segLen;
      const lat = a.latitude + (b.latitude - a.latitude) * frac;
      const lng = a.longitude + (b.longitude - a.longitude) * frac;
      points.push({
        type: 'Feature',
        id: `pt_${i}_${s}`,
        geometry: { type: 'Point', coordinates: [lng, lat] },
        properties: { type: 'photo_trigger' },
      });
    }
  }
  return points;
}

export const useMissionStore = create<MissionState>((set) => ({
  gridResult: null,
  generating: false,
  error: null,
  flightLinesGeoJSON: null,
  droneId: '',
  altitude: 100,
  overlapFrontal: 75,
  overlapLateral: 65,
  altitudeMode: 'takeoff',
  waypointMode: 'photo',
  photoSpacing: 0,

  setDroneId: (id) => set({ droneId: id }),
  setAltitude: (alt) => set({ altitude: alt }),
  setOverlapFrontal: (val) => set({ overlapFrontal: val }),
  setOverlapLateral: (val) => set({ overlapLateral: val }),
  setAltitudeMode: (mode) => set({ altitudeMode: mode }),
  setGridResult: (result) => {
    if (!result) {
      set({ gridResult: null, flightLinesGeoJSON: null });
      return;
    }
    const lines: GeoJSON.Feature[] = [];
    const waypoints = result.waypoints;
    const isInterval = result.waypoint_mode === 'vertex' || result.waypoint_mode === 'terrain';

    for (let i = 0; i < waypoints.length - 1; i++) {
      const wp1 = waypoints[i];
      const wp2 = waypoints[i + 1];
      const coords: [number, number][] = [
        [wp1.longitude, wp1.latitude],
        [wp2.longitude, wp2.latitude],
      ];
      const diff = headingDiff(wp1.heading, wp2.heading);
      if (diff > 1 && diff < 179) {
        continue;
      }
      const isGiro = diff > 90;
      lines.push({
        type: 'Feature',
        id: `fl_${i}`,
        geometry: { type: 'LineString', coordinates: coords },
        properties: { type: isGiro ? 'giro' : 'scan' },
      });
    }

    const points: GeoJSON.Feature[] = waypoints.map((wp, i) => ({
      type: 'Feature',
      id: `wp_${i}`,
      geometry: { type: 'Point', coordinates: [wp.longitude, wp.latitude] },
      properties: { index: i + 1, altitude: wp.altitude, heading: wp.heading, type: 'waypoint' },
    }));

    const photoTriggers = interpolatePhotoPoints(waypoints, result.photo_spacing, isInterval);

    const fc: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: [...lines, ...points, ...photoTriggers],
    };

    set({
      gridResult: result,
      flightLinesGeoJSON: fc,
      waypointMode: result.waypoint_mode || 'photo',
      photoSpacing: result.photo_spacing,
    });
  },
  setGenerating: (v) => set({ generating: v }),
  setError: (err) => set({ error: err }),
  clear: () =>
    set({
      gridResult: null,
      generating: false,
      error: null,
      flightLinesGeoJSON: null,
      altitudeMode: 'takeoff',
      waypointMode: 'photo',
      photoSpacing: 0,
    }),
}));
