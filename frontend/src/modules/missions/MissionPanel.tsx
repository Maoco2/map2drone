import { useState, useEffect } from 'react';
import { useMissionListStore } from './missionListStore';
import { useProjectStore } from '@/modules/projects/store';
import { useDrawStore } from '@/modules/map/drawStore';
import { useMissionStore } from './planningStore';
import { useMissionLoader } from './useMissionLoader';
import AdSlot from '@/shared/components/AdSlot';

export default function MissionPanel() {
  const { missions, loading, fetchMissions, selectedMissionId, selectMission, renameMission, deleteMission } = useMissionListStore();
  const selectedProjectId = useProjectStore((s) => s.selectedProjectId);
  const clearAll = useDrawStore((s) => s.clearAll);
  const clearPlanning = useMissionStore((s) => s.clear);
  const loadMission = useMissionLoader();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');

  useEffect(() => {
    fetchMissions();
  }, [fetchMissions, selectedProjectId]);

  const handleSelect = async (id: string) => {
    selectMission(id);
    await loadMission(id);
  };

  const handleNewMission = () => {
    selectMission(null);
    clearAll();
    clearPlanning();
  };

  const handleRename = async (id: string) => {
    if (!editName.trim()) return;
    try {
      await renameMission(id, editName.trim());
    } catch {}
    setEditingId(null);
  };

  return (
    <div>
      <button
        onClick={handleNewMission}
        className="w-full mb-2 py-1.5 text-xs rounded font-medium text-white transition-colors hover:opacity-80"
        style={{ backgroundColor: '#4f8cff' }}
      >
        + New Mission
      </button>

      {loading && (
        <p className="text-xs px-2 py-4 text-center" style={{ color: 'var(--color-text-secondary)' }}>
          Loading...
        </p>
      )}

      {!loading && missions.length === 0 && (
        <p className="text-xs px-2 py-4 text-center" style={{ color: 'var(--color-text-secondary)' }}>
          No missions. Draw a polygon and generate a grid.
        </p>
      )}

      <div className="space-y-0.5">
        {missions.map((m) => (
          <div
            key={m.id}
            className="flex items-center gap-1 px-2 py-1.5 rounded transition-colors group"
            style={{
              backgroundColor: selectedMissionId === m.id ? 'var(--color-surface)' : 'transparent',
              borderLeft: selectedMissionId === m.id ? '3px solid #4f8cff' : '3px solid transparent',
            }}
          >
            {editingId === m.id ? (
              <input
                autoFocus
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleRename(m.id);
                  if (e.key === 'Escape') setEditingId(null);
                }}
                onBlur={() => handleRename(m.id)}
                className="flex-1 px-1.5 py-0.5 text-xs rounded border outline-none"
                style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <button
                onClick={() => handleSelect(m.id)}
                className="flex-1 text-left"
              >
                <div className="text-xs font-medium truncate">{m.name}</div>
                <div className="text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
                  {new Date(m.created_at).toLocaleDateString()}
                </div>
              </button>
            )}

            <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
              <button
                onClick={() => { setEditingId(m.id); setEditName(m.name); }}
                className="px-1 py-0.5 rounded text-xs hover:bg-blue-100 hover:text-blue-600 transition-colors"
                title="Edit name"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                  <path d="M11.013 1.427a1.75 1.75 0 0 1 2.474 0l1.086 1.086a1.75 1.75 0 0 1 0 2.474l-8.61 8.61c-.21.21-.47.364-.756.445l-3.251.93a.75.75 0 0 1-.927-.928l.929-3.25a1.75 1.75 0 0 1 .445-.758l8.61-8.61Z" />
                </svg>
              </button>
              <button
                onClick={async () => { if (confirm('Delete mission?')) await deleteMission(m.id); }}
                className="px-1 py-0.5 rounded text-xs hover:bg-red-100 hover:text-red-600 transition-colors"
                title="Delete"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                  <path fillRule="evenodd" d="M5 3.25V4H2.75a.75.75 0 0 0 0 1.5h.3l.815 8.15A1.5 1.5 0 0 0 5.357 15h5.286a1.5 1.5 0 0 0 1.492-1.35l.815-8.15h.3a.75.75 0 0 0 0-1.5H11v-.75A2.25 2.25 0 0 0 8.75 1h-1.5A2.25 2.25 0 0 0 5 3.25Zm2.25-.75a.75.75 0 0 0-.75.75V4h3v-.75a.75.75 0 0 0-.75-.75h-1.5ZM6.05 6a.75.75 0 0 1 .787.713l.275 5.5a.75.75 0 0 1-1.498.074l-.275-5.5A.75.75 0 0 1 6.05 6Zm3.9 0a.75.75 0 0 1 .712.787l-.275 5.5a.75.75 0 0 1-1.498-.074l.275-5.5a.75.75 0 0 1 .786-.713Z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
          </div>
        ))}
        <AdSlot slotId="missions-rectangle" format="rectangle" className="pt-2" />
      </div>
    </div>
  );
}
