import { useEffect, useCallback, useRef } from 'react';
import { api } from '@/shared/utils/api';
import { useExportStore, buildExportData, COMPAT_COLORS } from './exportStore';
import { useMissionStore } from '@/modules/missions/planningStore';
import { useTurnRadiusStore } from '@/modules/planning/turnRadiusStore';
import { buildTurnRadiusConfig, missionTypeLabel } from '@/shared/utils/turnRadius';
import type { Drone } from '@/shared/types/project';

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
    formats, selectedFormats, projectName, status, progress, error, checks,
    lchmPathMode, lchmHeadingMode, lchmPhotoMode, lchmPhotoDistance,
    setFormats, setChecks, toggleFormat, selectAll, deselectAll,
    setProjectName, setStatus, setProgress, setError, reset,
    setLchmPathMode, setLchmHeadingMode, setLchmPhotoMode, setLchmPhotoDistance,
  } = useExportStore();
  const gridResult = useMissionStore((s) => s.gridResult);
  const lchmSelected = selectedFormats.includes('litchi_lchm');

  useEffect(() => {
    api.export.listFormats().then(setFormats).catch(() => {});
  }, [setFormats]);

  const dronesRef = useRef<Drone[] | null>(null);

  const buildPayload = useCallback(async () => {
    if (!gridResult) return null;
    if (!dronesRef.current) {
      try {
        dronesRef.current = await api.drones.list();
      } catch {
        dronesRef.current = [];
      }
    }
    const droneId = useMissionStore.getState().droneId;
    const drone = dronesRef.current.find((d) => d.id === droneId);
    const ci = gridResult.capture_interval;
    let photoCapture: Record<string, unknown> | undefined;
    if (lchmPhotoMode === 'TIME') {
      const rec = ci?.recommended_interval_s;
      if (rec != null) {
        photoCapture = { mode: 'TIME', time_interval_s: rec };
      }
    } else if (lchmPhotoMode === 'DISTANCE') {
      const dist = parseFloat(lchmPhotoDistance);
      if (Number.isFinite(dist) && dist > 0) {
        photoCapture = { mode: 'DISTANCE', distance_interval_m: dist };
      }
    }
    const trState = useTurnRadiusStore.getState();
    const variant = useMissionStore.getState().missionVariant;
    const turnRadius = trState.mode !== 'NONE'
      ? buildTurnRadiusConfig(
          {
            mode: trState.mode,
            manualRadius: trState.manualRadius,
            speedOverride: trState.speedOverride,
            safetyFactor: trState.safetyFactor,
            clearance: trState.clearance,
            maxLatAccel: trState.maxLatAccel,
            minRadius: trState.minRadius,
            maxRadius: trState.maxRadius,
          },
          gridResult.recommended_speed_ms ?? 0,
          {
            mission_type: missionTypeLabel(variant),
            line_spacing: gridResult.line_spacing ?? 0,
            flight_lines_geojson: variant === 'corridor' ? gridResult.geometry?.flight_lines_geojson : undefined,
          },
        )
      : undefined;
    return {
      ...buildExportData(gridResult, projectName, {
        path_mode: lchmPathMode,
        heading_mode: lchmHeadingMode,
        photo_capture: photoCapture,
        turn_radius: turnRadius,
      }),
      altitude_mode: useMissionStore.getState().altitudeMode,
      drone_name: drone?.name ?? droneId,
    };
  }, [gridResult, projectName, lchmPathMode, lchmHeadingMode, lchmPhotoMode, lchmPhotoDistance]);

  useEffect(() => {
    if (!gridResult || selectedFormats.length === 0) return;
    let cancelled = false;
    buildPayload().then((p) => {
      if (cancelled || !p) return;
      return api.export.check({ ...p, formats: selectedFormats });
    }).then((items) => {
      if (!cancelled && items) setChecks(items);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [gridResult, selectedFormats, projectName, buildPayload, setChecks]);

  const handleExport = useCallback(async () => {
    if (!gridResult || selectedFormats.length === 0) return;
    setStatus('exporting');
    setProgress(0);
    setError(null);

    try {
      const data = await buildPayload();
      if (!data) throw new Error('No mission data');

      if (selectedFormats.length === 1) {
        const blob = await api.export.format(selectedFormats[0], data);
        const fmt = formats.find((f) => f.id === selectedFormats[0]);
        const filename = selectedFormats[0] === 'litchi_lchm'
          ? `${projectName.replace(/[^A-Za-z0-9_.\- ]/g, '_').trim().replace(/[\s_]+/g, '_').toLowerCase()}_litchi.lchm`
          : `${projectName}${fmt?.extension || '.dat'}`;
        downloadBlob(blob, filename);
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
  }, [gridResult, selectedFormats, projectName, formats, buildPayload, setStatus, setProgress, setError]);

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
        <div className="space-y-1 max-h-60 overflow-y-auto">
          {formats.map((fmt) => {
            const sel = selectedFormats.includes(fmt.id);
            const compat = fmt.compatibility;
            const compatColor = compat ? (COMPAT_COLORS[compat.category] || '#9e9e9e') : '#9e9e9e';
            const check = checks[fmt.id];
            const warnings = sel && check ? check.warnings : [];
            return (
              <div
                key={fmt.id}
                className="w-full rounded text-xs text-left border transition-colors"
                style={{
                  backgroundColor: sel ? 'var(--color-surface)' : 'transparent',
                  borderColor: sel ? '#4f8cff' : 'var(--color-border)',
                  color: 'var(--color-text)',
                }}
              >
                <button
                  onClick={() => toggleFormat(fmt.id)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 text-left"
                >
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: sel ? '#4f8cff' : 'transparent', border: '1px solid var(--color-border)' }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="font-medium truncate">{fmt.name}</span>
                      {compat && (
                        <span
                          className="px-1 py-px rounded text-[9px] font-semibold shrink-0"
                          style={{ color: '#fff', backgroundColor: compatColor }}
                        >
                          {compat.label}
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] opacity-60 truncate">{fmt.description}</div>
                  </div>
                  <span className="text-[10px] opacity-40 font-mono">{fmt.extension}</span>
                </button>
                {sel && compat?.description && (
                  <div
                    className="px-2 pb-1 pt-0 text-[10px] leading-snug"
                    style={{ color: 'var(--color-text-secondary)' }}
                  >
                    {compat.description}
                  </div>
                )}
                {sel && warnings.length > 0 && (
                  <div className="px-2 pb-2 space-y-1">
                    {warnings.map((w, wi) => (
                      <div
                        key={`${fmt.id}-${w.code}-${wi}`}
                        className="flex gap-1.5 text-[10px] leading-snug rounded px-1.5 py-1"
                        style={{
                          backgroundColor: w.code === 'not_a_mission' || w.code === 'no_mavlink_framing'
                            ? 'rgba(229,57,53,0.15)'
                            : 'rgba(255,145,0,0.15)',
                          color: w.code === 'not_a_mission' || w.code === 'no_mavlink_framing'
                            ? '#ff6b6b'
                            : '#ffb74d',
                        }}
                      >
                        <span className="shrink-0">⚠</span>
                        <span>{w.message}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {lchmSelected && (
        <div className="space-y-2 rounded border p-2" style={{ borderColor: 'var(--color-border)' }}>
          <div className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
            Litchi LCHM options
          </div>
          <div className="space-y-1">
            <label className="text-xs block" style={{ color: 'var(--color-text-secondary)' }}>
              Path mode
            </label>
            <select
              value={lchmPathMode}
              onChange={(e) => setLchmPathMode(e.target.value)}
              className="w-full px-2 py-1.5 text-xs rounded border"
              style={{
                backgroundColor: 'var(--color-surface)',
                borderColor: 'var(--color-border)',
                color: 'var(--color-text)',
              }}
            >
              <option value="STRAIGHT">Recto (Straight)</option>
              <option value="CURVED_TURNS">Curvo (Curved turns)</option>
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs block" style={{ color: 'var(--color-text-secondary)' }}>
              Heading mode
            </label>
            <select
              value={lchmHeadingMode}
              onChange={(e) => setLchmHeadingMode(e.target.value)}
              className="w-full px-2 py-1.5 text-xs rounded border"
              style={{
                backgroundColor: 'var(--color-surface)',
                borderColor: 'var(--color-border)',
                color: 'var(--color-text)',
              }}
            >
              <option value="FOLLOW_PATH">Seguir camino (Follow path)</option>
              <option value="CUSTOM_POI">Personalizado (Custom / POI)</option>
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs block" style={{ color: 'var(--color-text-secondary)' }}>
              Photo capture
            </label>
            <div className="space-y-1">
              {[
                ['NONE', 'Sin captura de fotos'],
                ['TIME', 'Intervalo de tiempo'],
                ['DISTANCE', 'Intervalo de distancia'],
              ].map(([value, label]) => (
                <label
                  key={value}
                  className="flex items-center gap-2 text-xs rounded px-2 py-1 border"
                  style={{
                    backgroundColor: lchmPhotoMode === value ? 'rgba(79,140,255,0.12)' : 'transparent',
                    borderColor: lchmPhotoMode === value ? '#4f8cff' : 'var(--color-border)',
                    color: 'var(--color-text)',
                  }}
                >
                  <input
                    type="radio"
                    name="lchmPhotoMode"
                    value={value}
                    checked={lchmPhotoMode === value}
                    onChange={() => setLchmPhotoMode(value)}
                  />
                  {label}
                </label>
              ))}
            </div>
            {lchmPhotoMode === 'TIME' && (
              <div className="space-y-0.5 pt-1 text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
                <div>
                  Intervalo recomendado:{' '}
                  <span className="font-mono" style={{ color: 'var(--color-text)' }}>
                    {gridResult?.capture_interval?.ideal_interval_s != null
                      ? `${gridResult.capture_interval.ideal_interval_s.toFixed(1)} s`
                      : '—'}
                  </span>{' '}
                  (científico)
                </div>
                <div>
                  Intervalo Litchi:{' '}
                  <span className="font-mono" style={{ color: 'var(--color-text)' }}>
                    {gridResult?.capture_interval?.recommended_interval_s != null
                      ? `${gridResult.capture_interval.recommended_interval_s} s`
                      : '—'}
                  </span>{' '}
                  (entero)
                </div>
              </div>
            )}
            {lchmPhotoMode === 'DISTANCE' && (
              <div className="space-y-1 pt-1">
                <label className="text-[10px] block" style={{ color: 'var(--color-text-secondary)' }}>
                  Distancia entre fotos (m)
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  value={lchmPhotoDistance}
                  onChange={(e) => setLchmPhotoDistance(e.target.value)}
                  placeholder="p. ej. 20.5"
                  className="w-full px-2 py-1.5 text-xs rounded border"
                  style={{
                    backgroundColor: 'var(--color-surface)',
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text)',
                  }}
                />
              </div>
            )}
          </div>
          <div className="text-[10px] leading-snug" style={{ color: 'var(--color-text-secondary)' }}>
            Nota: el intervalo científico de captura se calcula aparte; Litchi usa el intervalo
            entero de tiempo o la distancia por foto seleccionados.
          </div>
        </div>
      )}

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

      <div
        className="text-[10px] leading-snug rounded p-2 space-y-1"
        style={{ color: '#ffb74d', backgroundColor: 'rgba(255,145,0,0.12)' }}
      >
        <div className="flex gap-1.5">
          <span className="shrink-0">⚠</span>
          <span>
            Este plan es una propuesta de cálculo automático. Verifique las condiciones reales
            de vuelo, obstáculos, restricciones de espacio aéreo y normativa aeronáutica local
            antes de volar. El operador es responsable de la seguridad de personas, bienes y del
            cumplimiento de la ley.
          </span>
        </div>
      </div>
    </div>
  );
}
