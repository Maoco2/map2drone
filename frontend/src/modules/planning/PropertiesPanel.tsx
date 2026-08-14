import { useCallback, useMemo, useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/utils/api';
import { useDrawStore, nextId } from '@/modules/map/drawStore';
import type { DrawFeature } from '@/modules/map/drawStore';
import { useMapStore } from '@/modules/map/store';
import { useMissionStore } from '@/modules/missions/planningStore';
import { useSidebarStore } from '@/app/layouts/sidebarStore';
import { useProjectStore } from '@/modules/projects/store';
import { useMissionListStore } from '@/modules/missions/missionListStore';
import type { Drone, Camera } from '@/shared/types/project';
import { computeLiveCapture } from '@/shared/utils/captureInterval';
import CaptureIntervalCard from './CaptureIntervalCard';
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
    missionVariant, widthLeft, widthRight,
    setDroneId, setAltitude, setOverlapFrontal, setOverlapLateral,
    setGridResult, setGenerating, setError, setAltitudeMode,
    setMissionVariant, setWidthLeft, setWidthRight,
  } = useMissionStore();
  const selectedProjectId = useProjectStore((s) => s.selectedProjectId);
  const fetchMissions = useMissionListStore((s) => s.fetchMissions);

  const [selectedMfr, setSelectedMfr] = useState('');
  const [gridType, setGridType] = useState<'simple' | 'cross'>('simple');
  const [importingFile, setImportingFile] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [captureSnapshot, setCaptureSnapshot] = useState<{
    altitude: number;
    overlapFrontal: number;
    overlapLateral: number;
    droneId: string;
    altitudeMode: string;
    missionVariant: string;
  } | null>(null);
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

  const drone = useMemo(() => drones?.find((d: Drone) => d.id === droneId), [drones, droneId]);
  const camera = useMemo(
    () => cameras?.find((c: Camera) => c.id === drone?.camera_id),
    [cameras, drone],
  );

  // Lightweight live mirror of the backend capture-interval engine (no GIS calls).
  const liveCapture = useMemo(() => {
    if (!camera || !drone) return null;
    return computeLiveCapture({
      altitude: Number(altitude),
      camera,
      drone,
      frontOverlap: Number(overlapFrontal),
      terrainFollow: altitudeMode === 'ground',
    });
  }, [camera, drone, altitude, overlapFrontal, altitudeMode]);

  // Right after Generate the backend block is authoritative (it applies the
  // terrain-follow conservative minimum footprint). Once any input that feeds
  // the capture interval changes, the backend block is stale -> live mirror.
  const backendCapture = useMemo(() => {
    if (!gridResult?.capture_interval || !captureSnapshot) return null;
    const same =
      Number(altitude) === captureSnapshot.altitude &&
      Number(overlapFrontal) === captureSnapshot.overlapFrontal &&
      Number(overlapLateral) === captureSnapshot.overlapLateral &&
      (droneId ?? '') === captureSnapshot.droneId &&
      altitudeMode === captureSnapshot.altitudeMode &&
      missionVariant === captureSnapshot.missionVariant;
    return same ? gridResult.capture_interval : null;
  }, [gridResult, captureSnapshot, altitude, overlapFrontal, overlapLateral, droneId, altitudeMode, missionVariant]);

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
    if (!droneId) return;
    const drone = drones?.find((d: Drone) => d.id === droneId);
    if (!drone || !drone.camera_id) {
      setError('Selected drone has no associated camera');
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      if (missionVariant === 'corridor') {
        let lineFeature = features
          .filter((f) => f.type === 'polyline' && f.completed && f.points.length >= 2)
          .pop();
        if (!lineFeature) {
          const currentFeature = useDrawStore.getState().currentFeature;
          if (currentFeature && currentFeature.type === 'polyline' && currentFeature.points.length >= 2) {
            const committed = { ...currentFeature, completed: true };
            useDrawStore.getState().addFeature(committed);
            useDrawStore.getState().setCurrentFeature(null);
            lineFeature = committed;
          }
        }
        if (!lineFeature) {
          setError('Draw the corridor centerline first using the Polyline tool');
          setGenerating(false);
          return;
        }
        const centerline: GeoJSON.LineString = {
          type: 'LineString',
          coordinates: lineFeature.points.map((p) => [p.lng, p.lat]),
        };
        const result = await api.planning.corridor({
          centerline,
          width_left: Number(widthLeft),
          width_right: Number(widthRight),
          altitude: Number(altitude),
          overlap_frontal: Number(overlapFrontal),
          overlap_lateral: Number(overlapLateral),
          drone_id: droneId,
          project_id: selectedProjectId || undefined,
          altitude_mode: altitudeMode,
        });
        setGridResult(result);
        setCaptureSnapshot({
          altitude: Number(altitude),
          overlapFrontal: Number(overlapFrontal),
          overlapLateral: Number(overlapLateral),
          droneId: droneId ?? '',
          altitudeMode,
          missionVariant,
        });
        fetchMissions();
        return;
      }

      if (!lastFeature || !polygonPoints) return;
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
      setCaptureSnapshot({
        altitude: Number(altitude),
        overlapFrontal: Number(overlapFrontal),
        overlapLateral: Number(overlapLateral),
        droneId: droneId ?? '',
        altitudeMode,
        missionVariant,
      });
      fetchMissions();
    } catch (err: any) {
      setError(err.message || 'Mission generation failed');
    } finally {
      setGenerating(false);
    }
  }, [drones, droneId, altitude, overlapFrontal, overlapLateral, lastFeature, polygonPoints, selectedProjectId, gridType, altitudeMode, missionVariant, widthLeft, widthRight, features, setGridResult, setGenerating, setError, fetchMissions]);

  const handleOpenExport = useCallback(() => {
    useSidebarStore.getState().setActiveTab('export');
  }, []);

  const handleImportFile = useCallback(async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase() || '';
    const allowed = ['geojson', 'json', 'kml', 'kmz', 'shp', 'gpkg'];
    if (!allowed.includes(ext)) {
      setError(`Unsupported format: .${ext}`);
      return;
    }
    setImportingFile(true);
    setError(null);
    try {
      const parsed = await api.planning.corridorParse(file);
      const coords = parsed.centerline?.coordinates ?? [];
      const pts = coords.map((c) => ({ lng: Number(c[0]), lat: Number(c[1]) }));
      if (pts.length < 2) {
        setError('No centerline found in the file');
        return;
      }
      const drawStore = useDrawStore.getState();
      for (const f of drawStore.features) {
        if (f.type === 'polyline') drawStore.removeFeature(f.id);
      }
      drawStore.addFeature({
        id: nextId(),
        type: 'polyline',
        points: pts,
        completed: true,
      });
      setGridResult(null);
      const map = useMapStore.getState().mapRef;
      if (map) {
        const lngs = pts.map((p) => p.lng);
        const lats = pts.map((p) => p.lat);
        map.fitBounds(
          [[Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]],
          { padding: 80, duration: 800 },
        );
      }
    } catch (err: any) {
      setError(err.message || 'Corridor import failed');
    } finally {
      setImportingFile(false);
    }
  }, [setGridResult, setError]);

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
          <div className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>Mission Type</div>
          <div className="flex gap-2">
            <button
              onClick={() => setMissionVariant('grid')}
              className={`flex-1 py-1.5 text-xs rounded font-medium border transition-colors ${
                missionVariant === 'grid'
                  ? 'text-white'
                  : 'opacity-70 hover:opacity-100'
              }`}
              style={{
                backgroundColor: missionVariant === 'grid' ? '#4f8cff' : 'var(--color-surface)',
                borderColor: 'var(--color-border)',
                color: missionVariant === 'grid' ? '#fff' : 'var(--color-text)',
              }}
            >
              Area Grid
            </button>
            <button
              onClick={() => setMissionVariant('corridor')}
              className={`flex-1 py-1.5 text-xs rounded font-medium border transition-colors ${
                missionVariant === 'corridor'
                  ? 'text-white'
                  : 'opacity-70 hover:opacity-100'
              }`}
              style={{
                backgroundColor: missionVariant === 'corridor' ? '#4f8cff' : 'var(--color-surface)',
                borderColor: 'var(--color-border)',
                color: missionVariant === 'corridor' ? '#fff' : 'var(--color-text)',
              }}
            >
              Linear Corridor
            </button>
          </div>
        </div>

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

        {missionVariant === 'corridor' && (
          <div className="space-y-2">
            <div className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>Corridor Width</div>
            {field('Width Left (m)', widthLeft, setWidthLeft, { min: 1, max: 10000, step: 1 })}
            {field('Width Right (m)', widthRight, setWidthRight, { min: 1, max: 10000, step: 1 })}
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={importingFile}
              className="w-full py-1.5 text-xs rounded font-medium border transition-colors disabled:opacity-40 hover:opacity-90"
              style={{
                backgroundColor: 'var(--color-surface)',
                borderColor: 'var(--color-border)',
                color: 'var(--color-text)',
              }}
            >
              {importingFile ? 'Importing...' : '📂 Import centerline file'}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              hidden
              accept=".geojson,.json,.kml,.kmz,.shp,.gpkg"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleImportFile(f);
                e.target.value = '';
              }}
            />
            <div className="text-[10px] px-1 leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
              Import shows the centerline on the map (KML, KMZ, GeoPackage, GeoJSON, Shapefile)
              and zooms to it — the flight plan is generated only when you press Generate. You can
              also draw it with the <b>Polyline</b> tool (〰 icon, above Measure).
            </div>
          </div>
        )}

        {missionVariant === 'grid' && (
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
        )}

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

        {missionVariant === 'corridor' ? (
          <div className="text-xs space-y-1" style={{ color: 'var(--color-text-secondary)' }}>
            <div>
              Centerline:{' '}
              {features.filter((f) => f.type === 'polyline' && f.completed && f.points.length >= 2).length > 0
                ? 'drawn'
                : useDrawStore.getState().currentFeature?.type === 'polyline' && (useDrawStore.getState().currentFeature?.points.length ?? 0) >= 2
                  ? 'in progress'
                  : 'not drawn yet'}
            </div>
          </div>
        ) : (
          <div className="text-xs space-y-1" style={{ color: 'var(--color-text-secondary)' }}>
            <div>Polygon: {polygonPoints ? `${polygonPoints.length} vertices` : 'none drawn'}</div>
            {polygonArea && (
              <div>
                Area: <span className="font-mono">{polygonArea.m2.toFixed(0)} m²</span>
                {' '}(<span className="font-mono">{polygonArea.ha.toFixed(2)} ha</span>)
              </div>
            )}
          </div>
        )}

        <button
          onClick={handleGenerate}
          disabled={generating || (missionVariant === 'corridor' ? !droneId : (!lastFeature || !droneId))}
          className="w-full py-2 text-xs rounded font-medium text-white transition-opacity disabled:opacity-40 hover:opacity-90"
          style={{ backgroundColor: '#4f8cff' }}
        >
          {generating ? 'Generating...' : missionVariant === 'corridor' ? 'Generate Corridor' : `Generate ${gridType === 'cross' ? 'Cross ' : ''}Grid`}
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
              {gridResult.corridor_length_m != null && (
                <div className="flex justify-between"><span>Corridor length:</span><span className="font-mono">{gridResult.corridor_length_m.toFixed(0)} m</span></div>
              )}
              {gridResult.corridor_area_m2 != null && (
                <div className="flex justify-between"><span>Corridor area:</span><span className="font-mono">{gridResult.corridor_area_m2.toFixed(0)} m²</span></div>
              )}
              {(gridResult as any).import_source && (
                <div className="flex justify-between"><span>Source:</span><span className="font-mono">{(gridResult as any).import_format} · {(gridResult as any).import_source}</span></div>
              )}
              <div className="flex justify-between"><span>Distance:</span><span className="font-mono">{gridResult.total_distance.toFixed(0)} m</span></div>
              <div className="flex justify-between"><span>Photos:</span><span className="font-mono">{gridResult.photo_count}</span></div>
              <div className="flex justify-between"><span>Speed:</span><span className="font-mono">{gridResult.recommended_speed_ms?.toFixed(1)} m/s</span></div>
              <div className="flex justify-between"><span>Time:</span><span className="font-mono">{Math.round(gridResult.estimated_time_sec / 60)} min</span></div>
              <div className="flex justify-between"><span>Batteries:</span><span className="font-mono">{gridResult.battery_count}</span></div>
              <div className="flex justify-between"><span>Waypoints:</span><span className="font-mono">{gridResult.waypoints.length}</span></div>
              {gridResult.geometry && (
                <div className="text-[10px] pt-1" style={{ color: 'var(--color-text-secondary)' }}>
                  CRS: {gridResult.geometry.crs_name} (EPSG:{gridResult.geometry.epsg_out})
                </div>
              )}
            </div>

            {gridResult.warnings && gridResult.warnings.length > 0 && (
              <div className="text-[10px] p-2 rounded space-y-1" style={{ color: '#f57c00', backgroundColor: 'rgba(245,124,0,0.1)' }}>
                {gridResult.warnings.map((w, i) => (
                  <div key={i}>⚠ {w}</div>
                ))}
              </div>
            )}

            {(backendCapture || liveCapture) && (
              <CaptureIntervalCard
                result={backendCapture ?? liveCapture!.result}
                gsd={backendCapture ? gridResult.gsd : liveCapture!.gsd}
                footprintLengthM={backendCapture ? gridResult.footprint_height : liveCapture!.footprintLength}
                frontOverlap={backendCapture ? (backendCapture.required_front_overlap ?? Number(overlapFrontal)) : Number(overlapFrontal)}
                lateralOverlap={Number(overlapLateral)}
              />
            )}

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
