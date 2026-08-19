import { useEffect, useMemo } from 'react';
import type { TurnStatus } from '@/shared/types/project';
import { useMissionStore } from '@/modules/missions/planningStore';
import { useTurnRadiusStore } from './turnRadiusStore';
import {
  TURN_STATUS_STYLE,
  factsFromGrid,
  isTurnRadiusStale,
  type TurnInputs,
} from '@/shared/utils/turnRadius';

function statusColor(status: TurnStatus | undefined): string {
  return TURN_STATUS_STYLE[status ?? 'NONE'].color;
}

export default function TurnRadiusPanel() {
  const gridResult = useMissionStore((s) => s.gridResult);
  const missionVariant = useMissionStore((s) => s.missionVariant);
  const widthLeft = useMissionStore((s) => s.widthLeft);
  const widthRight = useMissionStore((s) => s.widthRight);

  const {
    mode, manualRadius, speedOverride, safetyFactor, clearance, maxLatAccel, minRadius, maxRadius,
    result, warnings, loading, error, snapshot, advancedOpen, sourceGrid,
    setMode, setManualRadius, setSpeedOverride, setSafetyFactor, setClearance,
    setMaxLatAccel, setMinRadius, setMaxRadius, setAdvancedOpen,
    clearResult, hydrateFromGrid, recompute,
  } = useTurnRadiusStore();

  const inputs: TurnInputs = {
    mode, manualRadius, speedOverride, safetyFactor, clearance, maxLatAccel, minRadius, maxRadius,
  };
  const facts = useMemo(
    () => factsFromGrid(gridResult, missionVariant, widthLeft, widthRight),
    [gridResult, missionVariant, widthLeft, widthRight],
  );
  const stale = mode !== 'NONE' && isTurnRadiusStale(snapshot, inputs, facts);
  const hasResult = result !== null && result.status !== 'NONE';
  const status = result?.status as TurnStatus | undefined;
  const statusStyle = TURN_STATUS_STYLE[status ?? 'NONE'];
  const advancedParams = result?.turns?.[0]?.metadata;

  useEffect(() => {
    if (!gridResult) return;
    if (mode === 'NONE') {
      if (sourceGrid !== null || result !== null || snapshot !== null) clearResult();
      return;
    }
    if (sourceGrid !== gridResult) {
      if (gridResult.turn_radius_result) {
        hydrateFromGrid(gridResult, missionVariant);
      } else {
        recompute(gridResult, missionVariant);
      }
      return;
    }
    if (!isTurnRadiusStale(snapshot, inputs, facts)) return;
    const t = setTimeout(() => {
      recompute(gridResult, missionVariant);
    }, 350);
    return () => clearTimeout(t);
  }, [
    mode, manualRadius, speedOverride, safetyFactor, clearance, maxLatAccel, minRadius, maxRadius,
    snapshot, sourceGrid, result, gridResult, missionVariant, widthLeft, widthRight,
    hydrateFromGrid, recompute, clearResult,
  ]);

  const row = (label: string, value: string) => (
    <div className="flex justify-between gap-2 text-xs">
      <span style={{ color: 'var(--color-text-secondary)' }}>{label}</span>
      <span className="font-mono">{value}</span>
    </div>
  );

  return (
    <div
      className="space-y-2 p-2 rounded text-xs"
      style={{
        backgroundColor: 'var(--color-surface)',
        border: hasResult ? `1px solid ${statusStyle.color}44` : '1px solid var(--color-border)',
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="font-semibold" style={{ color: 'var(--color-text)' }}>
          TURN RADIUS
        </div>
        {hasResult && (
          <span
            className="px-1.5 py-px rounded text-[9px] font-semibold shrink-0"
            style={{ color: '#fff', backgroundColor: statusStyle.color }}
          >
            {statusStyle.label}
          </span>
        )}
      </div>

      <div className="flex gap-1">
        {(['AUTO', 'MANUAL', 'NONE'] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`flex-1 py-1.5 text-xs rounded font-medium border transition-colors ${
              mode === m ? 'text-white' : 'opacity-70 hover:opacity-100'
            }`}
            style={{
              backgroundColor: mode === m ? '#4f8cff' : 'transparent',
              borderColor: 'var(--color-border)',
              color: mode === m ? '#fff' : 'var(--color-text)',
            }}
          >
            {m}
          </button>
        ))}
      </div>

      {mode === 'MANUAL' && (
        <div className="flex items-center gap-2">
          <label className="text-xs shrink-0 w-28" style={{ color: 'var(--color-text-secondary)' }}>
            Radio manual (m)
          </label>
          <input
            type="number"
            min={0}
            step={0.5}
            value={Number.isFinite(manualRadius) ? manualRadius : ''}
            onChange={(e) => setManualRadius(Number(e.target.value) || 0)}
            className="flex-1 px-2 py-1 text-xs rounded border outline-none"
            style={{
              backgroundColor: 'var(--color-surface)',
              borderColor: 'var(--color-border)',
              color: 'var(--color-text)',
            }}
          />
        </div>
      )}

      {mode === 'AUTO' && gridResult && (
        <div className="text-[10px] px-1 leading-snug" style={{ color: 'var(--color-text-secondary)' }}>
          Radio calculado desde la separación entre líneas y la velocidad
          {facts.recommendedSpeed > 0 ? ` recomendada (${facts.recommendedSpeed.toFixed(1)} m/s)` : ''}.
          Puedes forzar otra velocidad en Información avanzada.
        </div>
      )}

      <button
        onClick={() => setAdvancedOpen(!advancedOpen)}
        className="w-full text-left text-[10px] font-medium underline opacity-70 hover:opacity-100"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        {advancedOpen ? '▾ Ocultar información avanzada' : '▸ Información avanzada'}
      </button>

      {advancedOpen && (
        <div className="space-y-1.5 pt-0.5">
          {row('Velocidad (m/s)', speedOverride > 0 ? speedOverride.toFixed(1) : 'recomendada')}
          <div className="flex items-center gap-2">
            <label className="text-xs shrink-0 w-28" style={{ color: 'var(--color-text-secondary)' }}>
              Velocidad
            </label>
            <input
              type="number"
              min={0}
              step={0.1}
              value={speedOverride || ''}
              placeholder="recomendada"
              onChange={(e) => setSpeedOverride(Number(e.target.value) || 0)}
              className="flex-1 px-2 py-1 text-xs rounded border outline-none"
              style={{
                backgroundColor: 'var(--color-surface)',
                borderColor: 'var(--color-border)',
                color: 'var(--color-text)',
              }}
            />
          </div>
          {row('Factor de seguridad', safetyFactor.toFixed(2))}
          {row('Distancia de seguridad (m)', clearance.toFixed(1))}
          {row('Acel. lateral máx. (m/s²)', maxLatAccel.toFixed(2))}
          {row('Radio mín. / máx. (m)', `${minRadius.toFixed(1)} / ${maxRadius.toFixed(1)}`)}
          <div className="text-[10px] pt-1 leading-snug" style={{ color: 'var(--color-text-secondary)' }}>
            Parámetros de ingeniería configurables. No son especificaciones de ningún fabricante;
            verifique los límites reales de su aeronave.
          </div>
        </div>
      )}

      {loading && (
        <div className="text-[10px] px-1" style={{ color: 'var(--color-text-secondary)' }}>
          Calculando radio de giro...
        </div>
      )}

      {error && (
        <div className="text-[10px] p-1.5 rounded" style={{ color: '#ff5252', backgroundColor: 'rgba(255,82,82,0.1)' }}>
          {error}
        </div>
      )}

      {stale && !loading && hasResult && (
        <div className="text-[10px] px-1" style={{ color: '#f57c00' }}>
          ⚠ Parámetros modificados: recalculando...
        </div>
      )}

      {hasResult && result && (
        <div className="space-y-1.5 pt-1">
          <div className="flex items-baseline gap-2">
            <div className="text-2xl font-bold font-mono" style={{ color: statusStyle.color }}>
              {result.radius_m.toFixed(1)}
            </div>
            <div className="text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
              m radio de giro
              <br />({result.turn_count} giro{result.turn_count === 1 ? '' : 's'})
            </div>
          </div>
          {result.turns[0] && (
            <div className="space-y-1">
              {row('Ángulo de giro', `${result.turns[0].turn_angle_deg.toFixed(0)}°`)}
              {row('Extensión antes/después', `${result.turns[0].extension_before_m.toFixed(1)} / ${result.turns[0].extension_after_m.toFixed(1)} m`)}
              {row('Distancia de seguridad', `${result.turns[0].clearance_m.toFixed(1)} m`)}
              {row('Velocidad de giro', `${result.turns[0].turn_speed_ms.toFixed(1)} m/s`)}
            </div>
          )}

          {result.status === 'CONSTRAINED' && (
            <div className="text-[10px] leading-snug px-1" style={{ color: '#f57c00' }}>
              El radio está limitado por el espacio disponible entre líneas. El valor mostrado
              es el máximo que cabe con la separación y la distancia de seguridad actuales.
            </div>
          )}

          {advancedParams && (
            <div className="space-y-1 pt-0.5">
              <div className="text-[10px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                Parámetros de cálculo
              </div>
              {row('Radio dinámico', `${result.turns[0].dynamic_radius_m.toFixed(1)} m`)}
              {row('Radio seguro', `${result.turns[0].safe_radius_m.toFixed(1)} m`)}
              {row('Radio disponible', `${result.turns[0].available_radius_m.toFixed(1)} m`)}
              {typeof advancedParams.a_lat_ms2 === 'number' && row('Acel. lateral (a_lat)', `${advancedParams.a_lat_ms2.toFixed(2)} m/s²`)}
              {typeof advancedParams.safety_factor === 'number' && row('Factor de seguridad', `${advancedParams.safety_factor.toFixed(2)}`)}
            </div>
          )}
        </div>
      )}

      {!hasResult && mode !== 'NONE' && !loading && gridResult && (
        <div className="text-[10px] px-1 leading-snug" style={{ color: 'var(--color-text-secondary)' }}>
          Sin giros entre líneas (menos de dos líneas de vuelo) o resultado no disponible.
        </div>
      )}

      {(warnings.length > 0 || (result?.warnings?.length ?? 0) > 0) && (
        <div className="text-[10px] p-1.5 rounded space-y-1" style={{ color: '#f57c00', backgroundColor: 'rgba(245,124,0,0.1)' }}>
          {[...(result?.warnings ?? []), ...warnings].map((w, i) => (
            <div key={i}>⚠ {w}</div>
          ))}
        </div>
      )}
    </div>
  );
}