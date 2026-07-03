import { useCallback } from 'react';
import { api } from '@/shared/utils/api';
import { useDrawStore } from '@/modules/map/drawStore';
import { useMissionStore } from './planningStore';
import { useMapStore } from '@/modules/map/store';

export function useMissionLoader() {
  const setGridResult = useMissionStore((s) => s.setGridResult);
  const setDroneId = useMissionStore((s) => s.setDroneId);
  const setAltitude = useMissionStore((s) => s.setAltitude);
  const setOverlapFrontal = useMissionStore((s) => s.setOverlapFrontal);
  const setOverlapLateral = useMissionStore((s) => s.setOverlapLateral);
  const setAltitudeMode = useMissionStore((s) => s.setAltitudeMode);

  return useCallback(async (missionId: string) => {
    try {
      const mission = await api.missions.get(missionId);

      // Restore polygon in drawStore
      if (mission.polygon_geojson) {
        const poly = JSON.parse(mission.polygon_geojson);
        const coords = poly.coordinates[0];
        if (coords?.length >= 3) {
          const points = coords.slice(0, -1).map((c: number[]) => ({
            lng: c[0],
            lat: c[1],
          }));
          useDrawStore.getState().clearAll();
          const id = `draw_${Date.now()}`;
          useDrawStore.getState().addFeature({
            id,
            type: 'polygon',
            points,
            completed: true,
          });
          const map = useMapStore.getState().mapRef;
          if (map) {
            let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity;
            for (const pt of points) {
              if (pt.lng < minLng) minLng = pt.lng;
              if (pt.lng > maxLng) maxLng = pt.lng;
              if (pt.lat < minLat) minLat = pt.lat;
              if (pt.lat > maxLat) maxLat = pt.lat;
            }
            if (isFinite(minLng)) {
              map.fitBounds([[minLng, minLat], [maxLng, maxLat]], { padding: 80, duration: 800 });
            }
          }
        }
      }

      // Restore parameters
      if (mission.parameters_json) {
        const params = JSON.parse(mission.parameters_json);
        if (params.drone_id) setDroneId(params.drone_id);
        if (params.altitude) setAltitude(params.altitude);
        if (params.overlap_frontal) setOverlapFrontal(params.overlap_frontal);
        if (params.overlap_lateral) setOverlapLateral(params.overlap_lateral);
        if (params.altitude_mode) setAltitudeMode(params.altitude_mode);
      }

      // Restore grid result
      if (mission.grid_result_json) {
        const grid = JSON.parse(mission.grid_result_json);
        setGridResult(grid);
      }
    } catch (err) {
      console.error('Failed to load mission:', err);
    }
  }, [setGridResult, setDroneId, setAltitude, setOverlapFrontal, setOverlapLateral, setAltitudeMode]);
}
