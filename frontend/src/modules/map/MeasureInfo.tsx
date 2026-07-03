import { useDrawStore } from './drawStore';
import { useMapStore } from './store';

function haversine(
  a: { lng: number; lat: number },
  b: { lng: number; lat: number },
): number {
  const R = 6371000;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLon = ((b.lng - a.lng) * Math.PI) / 180;
  const sDLat = Math.sin(dLat / 2);
  const sDLon = Math.sin(dLon / 2);
  const a2 =
    sDLat * sDLat +
    Math.cos((a.lat * Math.PI) / 180) *
      Math.cos((b.lat * Math.PI) / 180) *
      sDLon * sDLon;
  return R * 2 * Math.atan2(Math.sqrt(a2), Math.sqrt(1 - a2));
}

export default function MeasureInfo() {
  const features = useDrawStore((s) => s.features);
  const currentFeature = useDrawStore((s) => s.currentFeature);
  const activeTool = useMapStore((s) => s.activeTool);

  if (activeTool !== 'measure') return null;

  const completedMeasures = features.filter(
    (f) => f.completed && f.properties?.measure && f.type === 'line' && f.points.length >= 2,
  );

  const drawing =
    currentFeature && !currentFeature.completed && currentFeature.type === 'line' && currentFeature.points.length >= 2;

  return (
    <div style={{
      position: 'absolute',
      top: 10,
      right: 10,
      background: '#fff',
      border: '1px solid #ccc',
      borderRadius: 6,
      padding: '10px 14px',
      fontSize: 14,
      fontFamily: 'sans-serif',
      boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
      zIndex: 10,
      minWidth: 180,
    }}>
      <div style={{ fontWeight: 600, marginBottom: 6, color: '#e53935' }}>Measure</div>
      {drawing && (
        <div style={{ marginBottom: 4 }}>
          <span style={{ color: '#888' }}>Drawing: </span>
          <span style={{ fontWeight: 500 }}>{haversine(currentFeature.points[0], currentFeature.points[1]).toFixed(2)} m</span>
        </div>
      )}
      {completedMeasures.length === 0 && !drawing && (
        <div style={{ color: '#888' }}>Click two points to measure</div>
      )}
      {completedMeasures.map((m, i) => (
        <div key={m.id} style={{ marginBottom: 2 }}>
          <span style={{ color: '#888' }}>Line {i + 1}: </span>
          <span style={{ fontWeight: 500 }}>{haversine(m.points[0], m.points[1]).toFixed(2)} m</span>
        </div>
      ))}
    </div>
  );
}
