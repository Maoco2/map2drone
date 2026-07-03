import { useMapStore } from '@/modules/map/store';

const BASEMAPS = [
  { id: 'osm' as const, label: 'OpenStreetMap', desc: 'Topográfico con curvas de nivel' },
  { id: 'satellite' as const, label: 'Satélite', desc: 'Imagen satelital ESRI' },
  { id: 'hybrid' as const, label: 'Híbrido', desc: 'Satélite + calles y etiquetas' },
];

export default function LayerPanel() {
  const { basemap, setBasemap } = useMapStore();

  return (
    <div className="space-y-1">
      {BASEMAPS.map((b) => (
        <button
          key={b.id}
          onClick={() => setBasemap(b.id)}
          className="w-full flex items-center gap-2 px-3 py-2 rounded text-xs text-left transition-colors"
          style={{
            backgroundColor: basemap === b.id ? 'var(--color-surface)' : 'transparent',
            color: 'var(--color-text)',
          }}
        >
          <span
            className="w-3 h-3 rounded-full shrink-0 border"
            style={{
              backgroundColor: basemap === b.id ? '#4f8cff' : 'transparent',
              borderColor: basemap === b.id ? '#4f8cff' : 'var(--color-border)',
            }}
          />
          <div>
            <div className="font-medium">{b.label}</div>
            <div className="text-[10px] opacity-60">{b.desc}</div>
          </div>
        </button>
      ))}
    </div>
  );
}
