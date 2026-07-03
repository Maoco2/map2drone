import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProjectStore } from './store';
import { api } from '@/shared/utils/api';
import { useDrawStore } from '@/modules/map/drawStore';
import { useMissionStore } from '@/modules/missions/planningStore';

export default function ProjectTree() {
  const { projects, selectedProjectId, selectProject, addProject, deleteProject, fetchProjects, loading } = useProjectStore();
  const navigate = useNavigate();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setError('');
    try {
      const proj = await addProject(name.trim());
      useDrawStore.getState().clearAll();
      useMissionStore.getState().clear();
      navigate(`/projects/${proj.id}`);
      setName('');
      setShowForm(false);
    } catch (err: any) {
      setError(err?.message || 'Failed to create project');
    }
  };

  const handleRename = async (id: string) => {
    if (!editName.trim()) return;
    try {
      await api.projects.update(id, { name: editName.trim() });
      await fetchProjects();
    } catch {}
    setEditingId(null);
  };

  return (
    <div>
      {loading && (
        <p className="text-xs px-2 py-4 text-center" style={{ color: 'var(--color-text-secondary)' }}>
          Loading...
        </p>
      )}

      {!loading && projects.length === 0 && !showForm && (
        <p className="text-xs px-2 py-4 text-center" style={{ color: 'var(--color-text-secondary)' }}>
          No projects yet
        </p>
      )}

      <div className="space-y-0.5">
        {projects.map((p) => (
          <div
            key={p.id}
            className="flex items-center gap-1 px-2 py-1.5 rounded transition-colors group"
            style={{
              backgroundColor: selectedProjectId === p.id ? 'var(--color-surface)' : 'transparent',
              borderLeft: selectedProjectId === p.id ? '3px solid #4f8cff' : '3px solid transparent',
            }}
          >
            {editingId === p.id ? (
              <input
                autoFocus
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleRename(p.id);
                  if (e.key === 'Escape') setEditingId(null);
                }}
                onBlur={() => handleRename(p.id)}
                className="flex-1 px-1.5 py-0.5 text-xs rounded border outline-none"
                style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <button
                onClick={() => { useDrawStore.getState().clearAll(); useMissionStore.getState().clear(); selectProject(p.id); navigate(`/projects/${p.id}`); }}
                className="flex-1 text-left text-xs font-medium truncate"
                style={{ color: 'var(--color-text)' }}
                title="Open project"
              >
                {p.name}
              </button>
            )}

            <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={() => { setEditingId(p.id); setEditName(p.name); }}
                className="px-1 py-0.5 rounded text-xs hover:bg-blue-100 hover:text-blue-600 transition-colors"
                title="Edit name"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                  <path d="M11.013 1.427a1.75 1.75 0 0 1 2.474 0l1.086 1.086a1.75 1.75 0 0 1 0 2.474l-8.61 8.61c-.21.21-.47.364-.756.445l-3.251.93a.75.75 0 0 1-.927-.928l.929-3.25a1.75 1.75 0 0 1 .445-.758l8.61-8.61Z" />
                </svg>
              </button>
              <button
                onClick={async () => { if (confirm('Delete project?')) await deleteProject(p.id); }}
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
      </div>

      {showForm && (
        <div className="p-2 space-y-2 border-t mt-2" style={{ borderColor: 'var(--color-border)' }}>
          {error && (
            <div className="text-xs p-1.5 rounded bg-red-50 text-red-600">{error}</div>
          )}
          <input
            autoFocus
            value={name}
            onChange={(e) => { setName(e.target.value); setError(''); }}
            placeholder="Project name"
            className="w-full px-2 py-1.5 text-xs rounded border outline-none"
            style={{
              backgroundColor: 'var(--color-surface)',
              borderColor: 'var(--color-border)',
              color: 'var(--color-text)',
            }}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
          />
          <div className="flex gap-1">
            <button
              onClick={handleCreate}
              className="flex-1 py-1 text-xs rounded text-white"
              style={{ backgroundColor: '#4f8cff' }}
            >
              Create
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="px-3 py-1 text-xs rounded"
              style={{ backgroundColor: 'var(--color-surface)' }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {!showForm && (
        <button
          onClick={() => setShowForm(true)}
          className="w-full mt-2 py-1.5 text-xs rounded font-medium transition-colors hover:opacity-80 text-white"
          style={{ backgroundColor: '#4f8cff' }}
        >
          + New Project
        </button>
      )}
    </div>
  );
}
