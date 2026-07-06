import { useCallback, useMemo, useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/utils/api';
import { useDrawStore } from '@/modules/map/drawStore';
import type { DrawFeature } from '@/modules/map/drawStore';
import { useMissionStore } from '@/modules/missions/planningStore';
import { useSidebarStore } from '@/app/layouts/sidebarStore';
import { useProjectStore } from '@/modules/projects/store';
import { useMissionListStore } from '@/modules/missions/missionListStore';
import type { Drone, Camera } from '@/shared/types/project';
import AdSlot from '@/shared/components/AdSlot';

function getPolygonPoints(f: DrawFeature): { lng: number; lat: number }[] {
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
    const a = Math.sin(dLat / 2) ** 2 + Math.cos((center.lat * Math.PI) / 180) * Math.cos((edge.lat * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
    const radius = R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const pts: { lng: number; lat: number }[] = [];
    const cosLat = Math.cos((center.lat * Math.PI) / 180);
    for (let angle = 0; angle <= 360; angle += 10) {
      const rad = (angle * Math.PI) / 180;
      pts.push({
        lng: center.lng + (radius / R) * (180 / Math.PI) * Math.sin(rad) / cosLat,
        lat: center.lat + (radius / R) * (180 / Math.PI) * Math.cos(rad),
      });
    }
    return pts;
  }
  return f.points;
}

function polygonAreaM2(points: { lng: number; lat: number }[]): number {
  if (points.length < 3) return 0;
  const lats = points.map((p) => p.lat);
  const lngs = points.map((p) => p.lng);
  const centerLat = (Math.min(...lats) + Math.max(...lats)) / 2;
  const degToM = 111320;
  const cosLat = Math.cos((centerLat * Math.PI) / 180);
  const pts = points.map((p) => ({
    x: (p.lng - (Math.min(...lngs) + Math.max(...lngs)) / 2) * degToM * cosLat,
    y: (p.lat - centerLat) * degToM,
  }));
  let area = 0;
  const n = pts.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    area += pts[i].x * pts[j].y - pts[j].x * pts[i].y;
  }
  return Math.abs(area) / 2;
}

export default function PropertiesPanel() {
  const { data: drones } = useQuery({ queryKey: ['drones'], queryFn: api.drones.list });
  const { data: cameras } = useQuery({ queryKey: ['cameras'], queryFn: api.cameras.list });

  const features = useDrawStore((s) => s.features);
  const {
    droneId, altitude, overlapFrontal, overlapLateral,
    gridResult, generating, error, altitudeMode,
    setDroneId, setAltitude, setOverlapFrontal, setOverlapLateral,
    setGridResult, setGenerating, setError, setAltitudeMode,
  } = useMissionStore();
  const selectedProjectId = useProjectStore((s) => s.selectedProjectId);
  const fetchMissions = useMissionListStore((s) => s.fetchMissions);

  const [selectedMfr, setSelectedMfr] = useState('');
  const [gridType, setGridType] = useState<'simple' | 'cross'>('simple');
  const manufacturers = useMemo(() => {
    if (!drones) return [];
    return [...new Set(drones.map((d: Drone) => d.manufacturer))].sort();
  }, [drones]);
  const filteredDrones = useMemo(() => {
    if (!drones) return [];
    if (!selectedMfr) return [];
    return drones.filter((d: Drone) => d.manufacturer === selectedMfr);
  }, [drones, selectedMfr]);

  const lastFeature = features.filter(
    (f) => (f.type === 'polygon' || f.type === 'rectangle' || f.type === 'circle') && f.completed && f.points.length >= 2
  ).pop();

  const polygonPoints = useMemo(() => {
    if (!lastFeature) return null;
    return getPolygonPoints(lastFeature);
  }, [lastFeature]);

  const polygonArea = useMemo(() => {
    if (!polygonPoints) return null;
    const areaM2 = polygonAreaM2(polygonPoints);
    return { m2: areaM2, ha: areaM2 / 10000 };
  }, [polygonPoints]);

  const handleGenerate = useCallback(async () => {
    if (!droneId || !lastFeature || !polygonPoints) return;
    const drone = drones?.find((d: Drone) => d.id === droneId);
    if (!drone || !drone.camera_id) {
      setError('Selected drone has no associated camera');
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      const coords = polygonPoints.map((p) => [p.lng, p.lat]);
      coords.push([polygonPoints[0].lng, polygonPoints[0].lat]);
      const polygon: GeoJSON.Polygon = {
        type: 'Polygon',
        coordinates: [coords],
      };
      const baseReq: any = {
        polygon,
        altitude: Number(altitude),
        overlap_frontal: Number(overlapFrontal),
        overlap_lateral: Number(overlapLateral),
        drone_id: droneId,
        project_id: selectedProjectId || undefined,
        grid_type: gridType,
        altitude_mode: altitudeMode,
      };
      const result = await api.planning.grid(baseReq);
      setGridResult(result);
      fetchMissions();
    } catch (err: any) {
      setError(err.message || 'Grid generation failed');
    } finally {
      setGenerating(false);
    }
  }, [drones, droneId, altitude, overlapFrontal, overlapLateral, lastFeature, polygonPoints, selectedProjectId, gridType, altitudeMode, setGridResult, setGenerating, setError, fetchMissions]);

  const handleOpenExport = useCallback(() => {
    useSidebarStore.getState().setActiveTab('export');
  }, []);

  const field = (label: string, value: string | number, onChange: (v: any) => void, opts?: { min?: number; max?: number; step?: number }) => (
    <div className="flex items-center gap-2">
      <label className="text-xs shrink-0 w-28" style={{ color: 'var(--color-text-secondary)' }}>
        {label}
      </label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.valueAsNumber || 0)}
        className="flex-1 px-2 py-1 text-xs rounded border outline-none"
        style={{
          backgroundColor: 'var(--color-surface)',
          borderColor: 'var(--color-border)',
          color: 'var(--color-text)',
        }}
        {...opts}
      />
    </div>
  );

  return (
    <aside
      className="w-72 flex flex-col border-l shrink-0 overflow-y-auto"
      style={{
        backgroundColor: 'var(--color-panel)',
        borderColor: 'var(--color-border)',
      }}
    >
      <div className="px-4 py-3 border-b text-xs font-semibold" style={{ borderColor: 'var(--color-border)' }}>
        Mission Properties
      </div>

      <div className="p-3 space-y-3">
        <div className="space-y-2">
          <div className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>Aeronave</div>
          <select
            value={selectedMfr}
            onChange={(e) => {
              setSelectedMfr(e.target.value);
              setDroneId('');
            }}
            className="w-full px-2 py-1.5 text-xs rounded border outline-none"
            style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
          >
            <option value="">Select manufacturer</option>
            {manufacturers.map((mfr: string) => (
              <option key={mfr} value={mfr}>{mfr}</option>
            ))}
          </select>
          <select
            value={droneId}
            onChange={(e) => setDroneId(e.target.value)}
            className="w-full px-2 py-1.5 text-xs rounded border outline-none"
            style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
            disabled={!selectedMfr}
          >
            <option value="">Select model</option>
            {filteredDrones.map((d: Drone) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
          {droneId && drones && (() => {
            const d = drones.find((x: Drone) => x.id === droneId);
            return d && d.camera_id ? (
              <div className="text-xs px-1" style={{ color: 'var(--color-text-secondary)' }}>
                Camera: {cameras?.find((c: Camera) => c.id === d.camera_id)?.name ?? d.camera_id}
              </div>
            ) : null;
          })()}
        </div>

        <div className="space-y-2">
          <div className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>Flight Parameters</div>
          {field('Altitude (m)', altitude, setAltitude, { min: 10, max: 500, step: 5 })}
          {field('Overlap Frontal %', overlapFrontal, setOverlapFrontal, { min: 50, max: 95, step: 1 })}
          {field('Overlap Lateral %', overlapLateral, setOverlapLateral, { min: 30, max: 90, step: 1 })}
        </div>

        <div className="space-y-2">
          <div className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>Grid Options</div>
          <div className="flex gap-2">
            <button
              onClick={() => setGridType('simple')}
              className={`flex-1 py-1.5 text-xs rounded font-medium border transition-colors ${
                gridType === 'simple'
                  ? 'text-white'
                  : 'opacity-70 hover:opacity-100'
              }`}
              style={{
                backgroundColor: gridType === 'simple' ? '#4f8cff' : 'var(--color-surface)',
                borderColor: 'var(--color-border)',
                color: gridType === 'simple' ? '#fff' : 'var(--color-text)',
              }}
            >
              Simple Grid
            </button>
            <button
              onClick={() => setGridType('cross')}
              className={`flex-1 py-1.5 text-xs rounded font-medium border transition-colors ${
                gridType === 'cross'
                  ? 'text-white'
                  : 'opacity-70 hover:opacity-100'
              }`}
              style={{
                backgroundColor: gridType === 'cross' ? '#4f8cff' : 'var(--color-surface)',
                borderColor: 'var(--color-border)',
                color: gridType === 'cross' ? '#fff' : 'var(--color-text)',
              }}
            >
              Cross Grid
            </button>
          </div>
        </div>

        <div className="space-y-2">
          <div className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>Altitude Mode</div>
          <div className="flex gap-2">
            <button
              onClick={() => setAltitudeMode('takeoff')}
              className={`flex-1 py-1.5 text-xs rounded font-medium border transition-colors ${
                altitudeMode === 'takeoff' ? 'text-white' : 'opacity-70 hover:opacity-100'
              }`}
              style={{
                backgroundColor: altitudeMode === 'takeoff' ? '#4f8cff' : 'var(--color-surface)',
                borderColor: 'var(--color-border)',
                color: altitudeMode === 'takeoff' ? '#fff' : 'var(--color-text)',
              }}
            >
              Takeoff
            </button>
            <button
              onClick={() => setAltitudeMode('ground')}
              className={`flex-1 py-1.5 text-xs rounded font-medium border transition-colors ${
                altitudeMode === 'ground' ? 'text-white' : 'opacity-70 hover:opacity-100'
              }`}
              style={{
                backgroundColor: altitudeMode === 'ground' ? '#4f8cff' : 'var(--color-surface)',
                borderColor: 'var(--color-border)',
                color: altitudeMode === 'ground' ? '#fff' : 'var(--color-text)',
              }}
            >
              Ground (AGL)
            </button>
          </div>
        </div>

        <div className="text-xs space-y-1" style={{ color: 'var(--color-text-secondary)' }}>
          <div>Polygon: {polygonPoints ? `${polygonPoints.length} vertices` : 'none drawn'}</div>
          {polygonArea && (
            <div>
              Area: <span className="font-mono">{polygonArea.m2.toFixed(0)} m²</span>
              {' '}(<span className="font-mono">{polygonArea.ha.toFixed(2)} ha</span>)
            </div>
          )}
        </div>

        <button
          onClick={handleGenerate}
          disabled={generating || !lastFeature || !droneId}
          className="w-full py-2 text-xs rounded font-medium text-white transition-opacity disabled:opacity-40 hover:opacity-90"
          style={{ backgroundColor: '#4f8cff' }}
        >
          {generating ? 'Generating...' : `Generate ${gridType === 'cross' ? 'Cross ' : ''}Grid`}
        </button>

        {error && (
          <div className="text-xs p-2 rounded" style={{ color: '#ff5252', backgroundColor: 'rgba(255,82,82,0.1)' }}>
            {error}
          </div>
        )}

        {gridResult && (
          <>
            <div className="space-y-1.5 p-2 rounded text-xs" style={{ backgroundColor: 'var(--color-surface)' }}>
              <div className="font-medium mb-1" style={{ color: 'var(--color-text-secondary)' }}>Grid Results</div>
              <div className="flex justify-between"><span>GSD:</span><span className="font-mono">{gridResult.gsd.toFixed(2)} cm/px</span></div>
              <div className="flex justify-between"><span>Footprint:</span><span className="font-mono">{gridResult.footprint_width.toFixed(1)} x {gridResult.footprint_height.toFixed(1)} m</span></div>
              <div className="flex justify-between"><span>Line spacing:</span><span className="font-mono">{gridResult.line_spacing.toFixed(1)} m</span></div>
              <div className="flex justify-between"><span>Photo spacing:</span><span className="font-mono">{gridResult.photo_spacing.toFixed(1)} m</span></div>
              <div className="flex justify-between"><span>Distance:</span><span className="font-mono">{gridResult.total_distance.toFixed(0)} m</span></div>
              <div className="flex justify-between"><span>Photos:</span><span className="font-mono">{gridResult.photo_count}</span></div>
              <div className="flex justify-between"><span>Speed:</span><span className="font-mono">{gridResult.recommended_speed_ms?.toFixed(1)} m/s</span></div>
              <div className="flex justify-between"><span>Time:</span><span className="font-mono">{Math.round(gridResult.estimated_time_sec / 60)} min</span></div>
              <div className="flex justify-between"><span>Batteries:</span><span className="font-mono">{gridResult.battery_count}</span></div>
              <div className="flex justify-between"><span>Waypoints:</span><span className="font-mono">{gridResult.waypoints.length}</span></div>
            </div>

            <button
              onClick={handleOpenExport}
              className="w-full py-2 text-xs rounded font-medium text-white transition-opacity hover:opacity-90"
              style={{ backgroundColor: '#00c853' }}
            >
              Export (all formats)
            </button>

            <AdSlot slotId="properties-rectangle" format="rectangle" className="py-2" />
          </>
        )}
      </div>
    </aside>
  );
}
