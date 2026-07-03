import { useCallback, useRef } from 'react';
import { useMapStore } from './store';
import { useDrawStore, nextId } from './drawStore';
import { useMissionStore } from '@/modules/missions/planningStore';
import { importPolygonFromFile } from './polygonImport';

const TOOLS = [
  { id: 'pan', icon: '✋', label: 'Pan' },
  { id: 'polygon', icon: '⬡', label: 'Polygon' },
  { id: 'rectangle', icon: '⬜', label: 'Rectangle' },
  { id: 'circle', icon: '⭕', label: 'Circle' },

  { id: 'measure', icon: '📏', label: 'Measure' },
  { id: 'delete', icon: '🗑️', label: 'Delete' },
  { id: 'snap', icon: '⚡', label: 'Snap' },
  { id: 'import', icon: '📂', label: 'Import Polygon' },
  { id: 'clear', icon: '🗙', label: 'Clear All' },
];

export default function DrawingToolbar() {
  const { activeTool, setActiveTool } = useMapStore();
  const features = useDrawStore((s) => s.features);
  const clearAll = useDrawStore((s) => s.clearAll);
  const addFeature = useDrawStore((s) => s.addFeature);
  const clearPlanning = useMissionStore((s) => s.clear);
  const {
    droneId, altitude, overlapFrontal, overlapLateral,
  } = useMissionStore();
  const fileRef = useRef<HTMLInputElement>(null);

  const handleClick = useCallback((toolId: string) => {
    if (toolId === 'import') {
      fileRef.current?.click();
      return;
    }
    if (toolId === 'clear') {
      clearAll();
      clearPlanning();
      setActiveTool(null);
      return;
    }
    setActiveTool(activeTool === toolId ? null : toolId);
  }, [activeTool, setActiveTool, clearAll, clearPlanning]);

  const handleFile = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const polys = await importPolygonFromFile(file);
      if (!polys.length) return;
      clearAll();
      let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity;
      for (const p of polys) {
        addFeature({
          id: nextId(),
          type: 'polygon',
          points: p.points,
          completed: true,
        });
        for (const pt of p.points) {
          if (pt.lng < minLng) minLng = pt.lng;
          if (pt.lng > maxLng) maxLng = pt.lng;
          if (pt.lat < minLat) minLat = pt.lat;
          if (pt.lat > maxLat) maxLat = pt.lat;
        }
      }
      const map = useMapStore.getState().mapRef;
      if (map && isFinite(minLng) && isFinite(minLat)) {
        map.fitBounds(
          [[minLng, minLat], [maxLng, maxLat]],
          { padding: 80, duration: 800 },
        );
      }
    } catch (err) {
      alert(`Error importing polygon: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
    e.target.value = '';
  }, [clearAll, addFeature]);

  return (
    <div
      className="absolute left-3 top-3 z-10 flex flex-col gap-1 p-1.5 rounded-lg shadow-lg border"
      style={{
        backgroundColor: 'var(--color-panel)',
        borderColor: 'var(--color-border)',
      }}
    >
      {TOOLS.map((t) => (
        <button
          key={t.id}
          onClick={() => handleClick(t.id)}
          className="w-8 h-8 flex items-center justify-center rounded text-sm transition-colors"
          style={{
            backgroundColor: activeTool === t.id ? '#4f8cff' : 'transparent',
            color: activeTool === t.id ? '#fff' : 'var(--color-text)',
          }}
          title={t.label}
        >
          {t.icon}
        </button>
      ))}
      <input
        ref={fileRef}
        type="file"
        accept=".geojson,.json,.kml,.kmz,.csv,.txt,.shp,.zip"
        onChange={handleFile}
        className="hidden"
      />
    </div>
  );
}
