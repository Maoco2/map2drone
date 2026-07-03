import { useProjectStore } from '@/modules/projects/store';

export default function StatusBar() {
  const { projects } = useProjectStore();

  return (
    <div
      className="h-7 flex items-center px-4 text-xs shrink-0 border-t"
      style={{
        backgroundColor: 'var(--color-panel)',
        borderColor: 'var(--color-border)',
        color: 'var(--color-text-secondary)',
      }}
    >
      <span>{projects.length} projects</span>
      <span className="mx-3">|</span>
      <span>Map2Drone v0.1.0</span>
      <span className="mx-3">|</span>
      <span id="coordinate-display">Lat: -- Lon: --</span>
    </div>
  );
}
