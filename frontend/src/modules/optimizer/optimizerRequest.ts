import type { DrawFeature } from '@/modules/map/drawStore';
import type { OptimizerSolveRequest } from '@/shared/types/project';

export function getPolygonPoints(f: DrawFeature): { lng: number; lat: number }[] {
  if (f.type === 'rectangle' && f.points.length >= 2) {
    const [p1, p2] = [f.points[0], f.points[1]];
    return [
      { lng: p1.lng, lat: p1.lat },
      { lng: p2.lng, lat: p1.lat },
      { lng: p2.lng, lat: p2.lat },
      { lng: p1.lng, lat: p2.lat },
    ];
  }
  if (f.type === 'circle' && f.points.length >= 2) {
    const [center, edge] = [f.points[0], f.points[1]];
    const R = 6371000;
    const dLat = ((edge.lat - center.lat) * Math.PI) / 180;
    const dLon = ((edge.lng - center.lng) * Math.PI) / 180;
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos((center.lat * Math.PI) / 180) * Math.cos((edge.lat * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
    const radius = R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const pts: { lng: number; lat: number }[] = [];
    const cosLat = Math.cos((center.lat * Math.PI) / 180);
    for (let angle = 0; angle <= 360; angle += 10) {
      const rad = (angle * Math.PI) / 180;
      pts.push({
        lng: center.lng + ((radius / R) * (180 / Math.PI) * Math.sin(rad)) / cosLat,
        lat: center.lat + (radius / R) * (180 / Math.PI) * Math.cos(rad),
      });
    }
    return pts;
  }
  return f.points;
}

export interface OptimizerRequestState {
  variant: 'grid' | 'corridor';
  droneId: string;
  altitude: number;
  overlapFrontal: number;
  overlapLateral: number;
  altitudeMode: string;
  gridType: 'simple' | 'cross';
  widthLeft: number;
  widthRight: number;
  projectId?: string;
  turnRadius?: any;
  features: DrawFeature[];
}

export function buildOptimizerRequest(state: OptimizerRequestState): OptimizerSolveRequest | null {
  const {
    variant, droneId, altitude, overlapFrontal, overlapLateral,
    altitudeMode, gridType, widthLeft, widthRight, projectId, turnRadius,
  } = state;

  if (!droneId) return null;
  const turn = turnRadius ? { turn_radius: turnRadius } : {};

  if (variant === 'corridor') {
    const line = state.features
      .filter((f) => f.type === 'polyline' && f.completed && f.points.length >= 2)
      .pop();
    if (!line) return null;
    const centerline: GeoJSON.LineString = {
      type: 'LineString',
      coordinates: line.points.map((p) => [p.lng, p.lat]),
    };
    return {
      corridor: {
        centerline,
        width_left: Number(widthLeft),
        width_right: Number(widthRight),
        altitude: Number(altitude),
        overlap_frontal: Number(overlapFrontal),
        overlap_lateral: Number(overlapLateral),
        drone_id: droneId,
        project_id: projectId || undefined,
        altitude_mode: altitudeMode,
        ...turn,
      },
    };
  }

  const area = state.features
    .filter(
      (f) => (f.type === 'polygon' || f.type === 'rectangle' || f.type === 'circle') &&
        f.completed && f.points.length >= 2,
    )
    .pop();
  if (!area) return null;
  const points = getPolygonPoints(area);
  const coords = points.map((p) => [p.lng, p.lat]);
  coords.push([points[0].lng, points[0].lat]);
  const polygon: GeoJSON.Polygon = { type: 'Polygon', coordinates: [coords] };
  return {
    grid: {
      polygon,
      altitude: Number(altitude),
      overlap_frontal: Number(overlapFrontal),
      overlap_lateral: Number(overlapLateral),
      drone_id: droneId,
      project_id: projectId || undefined,
      grid_type: gridType,
      altitude_mode: altitudeMode,
      ...turn,
    },
  };
}