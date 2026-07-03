import { useEffect, useCallback } from 'react';
import { api } from '@/shared/utils/api';
import { useExportStore, buildExportData } from './exportStore';
import { useMissionStore } from '@/modules/missions/planningStore';

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ExportPanel() {
  const {
    formats, selectedFormats, projectName, status, progress, error,
    setFormats, toggleFormat, selectAll, deselectAll,
    setProjectName, setStatus, setProgress, setError, reset,
  } = useExportStore();
  const gridResult = useMissionStore((s) => s.gridResult);

  useEffect(() => {
    api.export.listFormats().then(setFormats).catch(() => {});
  }, [setFormats]);

  const handleExport = useCallback(async () => {
    if (!gridResult || selectedFormats.length === 0) return;
    setStatus('exporting');
    setProgress(0);
    setError(null);

    try {
      const data = {
        ...buildExportData(gridResult, projectName),
        altitude_mode: useMissionStore.getState().altitudeMode,
        drone_name: useMissionStore.getState().droneId,
      };

      if (selectedFormats.length === 1) {
        const blob = await api.export.format(selectedFormats[0], data);
        const fmt = formats.find((f) => f.id === selectedFormats[0]);
        downloadBlob(blob, `${projectName}${fmt?.extension || '.dat'}`);
      } else {
        const blob = await api.export.multi({ ...data, formats: selectedFormats });
        downloadBlob(blob, `${projectName}_map2drone.zip`);
      }

      setProgress(100);
      setStatus('done');
    } catch (err: any) {
      setError(err.message || 'Export failed');
      setStatus('error');
    }
  }, [gridResult, selectedFormats, projectName, formats, setStatus, setProgress, setError]);

  return (
    <div className="space-y-3 p-3" style={{ color: 'var(--color-text)' }}>
      <div className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
        Universal Mission Export Engine
      </div>

      <div className="space-y-1">
        <label className="text-xs block" style={{ color: 'var(--color-text-secondary)' }}>
          Project name
        </label>
        <input
          type="text"
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          className="w-full px-2 py-1.5 text-xs rounded border"
          style={{
            backgroundColor: 'var(--color-surface)',
            borderColor: 'var(--color-border)',
            color: 'var(--color-text)',
          }}
        />
      </div>

      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
            Formats ({selectedFormats.length}/{formats.length})
          </span>
          <div className="flex gap-2">
            <button onClick={selectAll} className="text-[10px] underline opacity-60 hover:opacity-100">All</button>
            <button onClick={deselectAll} className="text-[10px] underline opacity-60 hover:opacity-100">None</button>
          </div>
        </div>
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {formats.map((fmt) => {
            const sel = selectedFormats.includes(fmt.id);
            return (
              <button
                key={fmt.id}
                onClick={() => toggleFormat(fmt.id)}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs text-left border transition-colors"
                style={{
                  backgroundColor: sel ? 'var(--color-surface)' : 'transparent',
                  borderColor: sel ? '#4f8cff' : 'var(--color-border)',
                  color: 'var(--color-text)',
                }}
              >
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: sel ? '#4f8cff' : 'transparent', border: '1px solid var(--color-border)' }}
                />
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{fmt.name}</div>
                  <div className="text-[10px] opacity-60 truncate">{fmt.description}</div>
                </div>
                <span className="text-[10px] opacity-40 font-mono">{fmt.extension}</span>
              </button>
            );
          })}
        </div>
      </div>

      {error && (
        <div className="text-xs p-2 rounded" style={{ backgroundColor: 'rgba(255,0,0,0.1)', color: '#ff4444' }}>
          {error}
        </div>
      )}

      {status === 'exporting' && (
        <div className="space-y-1">
          <div className="text-xs opacity-60">Exporting... {progress}%</div>
          <div
            className="h-1.5 rounded-full overflow-hidden"
            style={{ backgroundColor: 'var(--color-border)' }}
          >
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${progress}%`, backgroundColor: '#4f8cff' }}
            />
          </div>
        </div>
      )}

      <button
        onClick={handleExport}
        disabled={status === 'exporting' || !gridResult || selectedFormats.length === 0}
        className="w-full py-2 text-xs rounded font-medium text-white transition-opacity disabled:opacity-40 hover:opacity-90"
        style={{ backgroundColor: '#00c853' }}
      >
        {status === 'exporting'
          ? 'Exporting...'
          : selectedFormats.length === 0
            ? 'Select at least one format'
            : selectedFormats.length === 1
              ? `Export ${formats.find((f) => f.id === selectedFormats[0])?.name || ''}`
              : `Export ${selectedFormats.length} formats as ZIP`
          }
      </button>

      {status === 'done' && (
        <div className="text-xs text-center" style={{ color: '#00c853' }}>
          Export completed successfully
        </div>
      )}
    </div>
  );
}
