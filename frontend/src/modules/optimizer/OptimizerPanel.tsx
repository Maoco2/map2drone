import { useEffect, useState } from 'react';
import { useOptimizerStore, OPTIMIZABLE_VARIABLES, CONSTRAINT_KEYS, type OptimizerVarEditor } from './optimizerStore';
import { api } from '@/shared/utils/api';
import type {
  OptimizerSolveResponse, OptimizerCandidate, OptimizerVariableMode, ScoreComponentDetail,
  OptimizerApplyResponse, ExportReadinessItem,
} from '@/shared/types/project';

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

const MODES: { id: OptimizerVariableMode; label: string }[] = [
  { id: 'range', label: 'Range' },
  { id: 'candidate_values', label: 'Values' },
  { id: 'fixed', label: 'Fixed' },
];

const inputStyle: React.CSSProperties = {
  backgroundColor: 'var(--color-surface)',
  borderColor: 'var(--color-border)',
  color: 'var(--color-text)',
};

function numField(
  value: number,
  onChange: (v: number) => void,
  opts?: { min?: number; max?: number; step?: number },
) {
  return (
    <input
      type="number"
      value={value}
      onChange={(e) => onChange(e.target.valueAsNumber || 0)}
      className="w-full px-2 py-1 text-xs rounded border outline-none"
      style={inputStyle}
      {...opts}
    />
  );
}

function VariableRow({ v }: { v: OptimizerVarEditor }) {
  const setVarField = useOptimizerStore((s) => s.setVarField);
  const meta = OPTIMIZABLE_VARIABLES.find((m) => m.name === v.name);
  const mode = v.mode;

  return (
    <div className="space-y-1.5 p-2 rounded" style={{ backgroundColor: 'var(--color-surface)' }}>
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={v.enabled}
          onChange={(e) => setVarField(v.name, { enabled: e.target.checked })}
        />
        <label className="text-xs font-medium flex-1" style={{ color: 'var(--color-text)' }}>
          {meta?.label}
        </label>
        <select
          value={mode}
          onChange={(e) => setVarField(v.name, { mode: e.target.value as OptimizerVariableMode })}
          disabled={!v.enabled}
          className="px-1.5 py-1 text-[10px] rounded border outline-none disabled:opacity-40"
          style={inputStyle}
        >
          {MODES.map((m) => (
            <option key={m.id} value={m.id}>{m.label}</option>
          ))}
        </select>
      </div>
      {v.enabled && (
        <div className="space-y-1">
          {mode === 'fixed' && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] w-14 shrink-0" style={{ color: 'var(--color-text-secondary)' }}>Value</span>
              {numField(v.fixedValue, (n) => setVarField(v.name, { fixedValue: n }))}
            </div>
          )}
          {mode === 'range' && (
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] w-14 shrink-0" style={{ color: 'var(--color-text-secondary)' }}>Min</span>
              {numField(v.minValue, (n) => setVarField(v.name, { minValue: n }))}
              <span className="text-[10px] w-10 shrink-0" style={{ color: 'var(--color-text-secondary)' }}>Max</span>
              {numField(v.maxValue, (n) => setVarField(v.name, { maxValue: n }))}
              <span className="text-[10px] w-7 shrink-0" style={{ color: 'var(--color-text-secondary)' }}>Step</span>
              {numField(v.step, (n) => setVarField(v.name, { step: n }), { min: 0.1, step: 0.1 })}
            </div>
          )}
          {mode === 'candidate_values' && (
            <input
              type="text"
              value={v.candidatesText}
              onChange={(e) => setVarField(v.name, { candidatesText: e.target.value })}
              placeholder="e.g. 80,90,100"
              className="w-full px-2 py-1 text-xs rounded border outline-none"
              style={inputStyle}
            />
          )}
        </div>
      )}
    </div>
  );
}

function formatVarValues(values: Record<string, number>): string {
  return Object.entries(values)
    .map(([k, val]) => `${k.replace('_', ' ')}: ${Number(val).toFixed(val % 1 === 0 ? 0 : 2)}`)
    .join(' · ');
}

function ScoreBreakdown({ details }: { details: ScoreComponentDetail[] }) {
  const statusColors: Record<string, string> = {
    SCORED: 'var(--color-text)',
    UNKNOWN: '#888',
    DATA_REQUIRED: '#f57c00',
  };
  if (!details.length) return null;
  return (
    <div className="space-y-0.5">
      <div className="text-[10px] font-medium uppercase" style={{ color: 'var(--color-text-secondary)' }}>
        Score breakdown
      </div>
      {details.map((d) => (
        <div key={d.component} className="flex items-center gap-2 text-[10px]">
          <span className="w-20 shrink-0 truncate" style={{ color: 'var(--color-text)' }}>{d.label}</span>
          <span className="flex-1" style={{ color: 'var(--color-text-secondary)' }}>
            {d.normalized_value != null ? (
              <>
                raw {d.raw_value != null ? Number(d.raw_value).toFixed(2) : '—'}
                {d.target != null && ` / target ${Number(d.target).toFixed(2)}`}
              </>
            ) : (
              d.message || d.status
            )}
          </span>
          <span className="shrink-0" style={{ color: statusColors[d.status] }}>
            {d.normalized_value != null ? Number(d.normalized_value).toFixed(3) : d.status}
          </span>
          {d.normalized_value != null && (
            <span className="w-12 shrink-0 text-right font-mono" style={{ color: '#4f8cff' }}>
              {(d.weight * (d.normalized_value ?? 0)).toFixed(3)}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function CandidateCard({ candidate, score, rank }: { candidate: OptimizerCandidate; score?: { total_score?: number; details?: ScoreComponentDetail[] } | null; rank: number }) {
  const m = candidate.mission?.metrics;
  return (
    <div className="p-2 rounded text-xs space-y-1" style={{ backgroundColor: 'var(--color-surface)' }}>
      <div className="flex justify-between items-center">
        <span className="font-medium" style={{ color: 'var(--color-text)' }}>
          {rank === 0 ? '★ Best' : `Alternative ${rank}`}
        </span>
        {score?.total_score != null && (
          <span className="font-mono" style={{ color: '#4f8cff' }}>{score.total_score.toFixed(3)}</span>
        )}
      </div>
      {candidate.label && <div className="text-[10px] font-mono" style={{ color: 'var(--color-text-secondary)' }}>{candidate.label}</div>}
      {candidate.variable_values && Object.keys(candidate.variable_values).length > 0 && (
        <div className="text-[10px] leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
          {formatVarValues(candidate.variable_values)}
        </div>
      )}
      {m && (
        <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
          <span>GSD: {m.gsd_cm.toFixed(2)} cm/px</span>
          <span>Photos: {m.photo_count}</span>
          <span>Time: {Math.round(m.estimated_time_sec / 60)} min</span>
          <span>Batteries: {m.battery_count}</span>
          <span>Distance: {m.total_distance_m.toFixed(0)} m</span>
          <span>Waypoints: {m.waypoint_count}</span>
        </div>
      )}
      {score?.details && <ScoreBreakdown details={score.details} />}
    </div>
  );
}

function ResultSection({ result }: { result: OptimizerSolveResponse }) {
  const [showAll, setShowAll] = useState(false);
  const statusColors: Record<string, string> = {
    OPTIMAL: '#00c853',
    FEASIBLE: '#4f8cff',
    CONSTRAINED: '#f57c00',
    NO_SOLUTION: '#ff5252',
  };
  return (
    <div className="space-y-2">
      <div className="p-2 rounded text-xs space-y-1" style={{ backgroundColor: 'var(--color-surface)' }}>
        <div className="flex items-center gap-2">
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold text-white" style={{ backgroundColor: statusColors[result.status] ?? '#888' }}>
            {result.status}
          </span>
          <span style={{ color: 'var(--color-text)' }}>{result.message}</span>
        </div>
        {result.stats && (
          <div className="text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
            {result.stats.evaluated ?? 0} evaluated · {result.stats.valid ?? 0} valid · {result.stats.invalid ?? 0} invalid
            {result.stats.rejected ? ` · ${result.stats.rejected} rejected` : ''}
          </div>
        )}
      </div>

      {result.best_candidate && (
        <CandidateCard candidate={result.best_candidate} score={result.best_score} rank={0} />
      )}

      {result.alternatives && result.alternatives.length > 0 && (
        <div className="space-y-1.5">
          <button
            onClick={() => setShowAll((s) => !s)}
            className="w-full py-1.5 text-xs rounded font-medium border transition-colors hover:opacity-90"
            style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
          >
            {showAll ? 'Hide' : 'Show'} alternatives ({result.alternatives.length})
          </button>
          {showAll && result.alternatives.map((a, i) => (
            <CandidateCard key={i} candidate={a} score={a.score} rank={i + 1} />
          ))}
        </div>
      )}

      {result.explanation && result.explanation.reasons.length > 0 && (
        <div className="p-2 rounded text-xs space-y-0.5" style={{ backgroundColor: 'var(--color-surface)' }}>
          <div className="font-medium text-[10px] uppercase" style={{ color: 'var(--color-text-secondary)' }}>Why this mission</div>
          {result.explanation.reasons.map((r, i) => (
            <div key={i} className="text-[10px]" style={{ color: 'var(--color-text)' }}>• {r}</div>
          ))}
        </div>
      )}

      {result.warnings && result.warnings.length > 0 && (
        <div className="text-[10px] p-2 rounded space-y-1" style={{ color: '#f57c00', backgroundColor: 'rgba(245,124,0,0.1)' }}>
          {result.warnings.map((w, i) => (
            <div key={i}>⚠ {w}</div>
          ))}
        </div>
      )}
    </div>
  );
}

function ApplyWinnerSection() {
  const {
    applyWinner, applying, applyError, applyResult, clearApply,
    result,
  } = useOptimizerStore();
  const [readiness, setReadiness] = useState<ExportReadinessItem[] | null>(null);
  const [readinessError, setReadinessError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportMsg, setExportMsg] = useState<string | null>(null);

  const winner = result?.best_candidate;

  useEffect(() => {
    if (!applyResult) {
      setReadiness(null);
      setReadinessError(null);
      setExportMsg(null);
      return;
    }
    let cancelled = false;
    api.export.checkUmm({ mission: applyResult.winner_mission, formats: ['litchi_lchm'] })
      .then((res) => { if (!cancelled) { setReadiness(res.items); setReadinessError(null); } })
      .catch((err: any) => { if (!cancelled) setReadinessError(err.message || 'Readiness check failed'); });
    return () => { cancelled = true; };
  }, [applyResult]);

  if (!applyResult) {
    return (
      <div className="space-y-2 p-2 rounded" style={{ backgroundColor: 'var(--color-surface)' }}>
        <button
          onClick={applyWinner}
          disabled={applying || !winner}
          className="w-full py-2 text-xs rounded font-medium text-white transition-opacity disabled:opacity-40 hover:opacity-90"
          style={{ backgroundColor: '#00c853' }}
        >
          {applying ? 'Applying winner…' : 'Apply winner mission'}
        </button>
        {!winner && (
          <div className="text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
            Optimize first, then apply the best candidate as a saved mission.
          </div>
        )}
        {applyError && (
          <div className="text-xs p-2 rounded" style={{ color: '#ff5252', backgroundColor: 'rgba(255,82,82,0.1)' }}>
            {applyError}
          </div>
        )}
      </div>
    );
  }

  const statusColors: Record<string, string> = {
    READY: '#00c853',
    WARNING: '#f57c00',
    BLOCKED: '#ff5252',
  };
  const readinessItem = readiness?.find((i) => i.id === 'litchi_lchm');

  return (
    <div className="space-y-2 p-2 rounded" style={{ backgroundColor: 'var(--color-surface)' }}>
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-medium uppercase" style={{ color: 'var(--color-text-secondary)' }}>
          Applied winner
        </div>
        <button
          onClick={clearApply}
          className="text-[10px] underline opacity-60 hover:opacity-100"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          Clear
        </button>
      </div>

      {applyResult.mission_id && (
        <div className="text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
          Mission saved: <span className="font-mono" style={{ color: 'var(--color-text)' }}>{applyResult.mission_id}</span>
        </div>
      )}

      {applyResult.modified_variables.length > 0 && (
        <div className="text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
          Modified variables:{' '}
          <span className="font-mono" style={{ color: '#4f8cff' }}>{applyResult.modified_variables.join(', ')}</span>
        </div>
      )}

      {applyResult.comparison.length > 0 && (
        <div className="space-y-0.5">
          <div className="text-[10px] font-medium uppercase" style={{ color: 'var(--color-text-secondary)' }}>
            Baseline vs winner
          </div>
          <div className="grid grid-cols-3 gap-x-2 text-[10px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>
            <span>Metric</span>
            <span className="text-right">Baseline</span>
            <span className="text-right">Winner</span>
          </div>
          {applyResult.comparison.map((row) => (
            <div key={row.metric} className="grid grid-cols-3 gap-x-2 text-[10px]">
              <span style={{ color: 'var(--color-text)' }}>{row.label}</span>
              <span className="text-right font-mono" style={{ color: 'var(--color-text-secondary)' }}>
                {row.baseline != null ? `${Number(row.baseline).toFixed(2)}${row.unit}` : '—'}
              </span>
              <span className="text-right font-mono" style={{ color: '#4f8cff' }}>
                {row.winner != null ? `${Number(row.winner).toFixed(2)}${row.unit}` : '—'}
              </span>
            </div>
          ))}
        </div>
      )}

      {applyResult.baseline_score?.total_score != null && applyResult.winner_score?.total_score != null && (
        <div className="text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
          Score:{' '}
          <span className="font-mono" style={{ color: 'var(--color-text)' }}>{applyResult.baseline_score.total_score.toFixed(3)}</span>
          <span className="opacity-60"> → </span>
          <span className="font-mono" style={{ color: '#00c853' }}>{applyResult.winner_score.total_score.toFixed(3)}</span>
        </div>
      )}

      {applyResult.verification?.verified === true && (
        <div className="text-[10px]" style={{ color: '#00c853' }}>
          ✓ Re-derived winner matches sent mission
        </div>
      )}
      {applyResult.verification?.verified === false && (
        <div className="text-[10px]" style={{ color: '#ff5252' }}>
          ✗ Winner mismatch detected
        </div>
      )}

      {applyResult.warnings.length > 0 && (
        <div className="text-[10px] space-y-0.5" style={{ color: '#f57c00' }}>
          {applyResult.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
        </div>
      )}

      <div className="space-y-1">
        <div className="text-[10px] font-medium uppercase" style={{ color: 'var(--color-text-secondary)' }}>
          Export readiness (Litchi LCHM)
        </div>
        {readinessError && (
          <div className="text-[10px]" style={{ color: '#ff5252' }}>{readinessError}</div>
        )}
        {readinessItem && (
          <div className="flex items-center gap-2">
            <span
              className="px-1.5 py-0.5 rounded text-[10px] font-semibold text-white"
              style={{ backgroundColor: statusColors[readinessItem.status] ?? '#888' }}
            >
              {readinessItem.status}
            </span>
            <div className="flex-1 space-y-0.5">
              {readinessItem.reasons.map((r, i) => (
                <div key={i} className="text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>{r}</div>
              ))}
              {readinessItem.codes.includes('split_required') && (
                <div className="text-[10px]" style={{ color: '#ffb74d' }}>
                  ⚠ Over 99 waypoints — split the mission into multiple LCHM files.
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <button
        onClick={async () => {
          setExporting(true);
          setExportMsg(null);
          try {
            const blob = await api.export.umm('litchi_lchm', { mission: applyResult.winner_mission });
            downloadBlob(blob, 'winner_litchi.lchm');
            setExportMsg('Downloaded winner LCHM');
          } catch (err: any) {
            setExportMsg(err.message || 'Export failed');
          } finally {
            setExporting(false);
          }
        }}
        disabled={exporting || (readinessItem?.status === 'BLOCKED' && readinessItem.codes.includes('split_required'))}
        className="w-full py-1.5 text-xs rounded font-medium border transition-opacity disabled:opacity-40 hover:opacity-90"
        style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
      >
        {exporting ? 'Exporting…' : 'Download winner LCHM'}
      </button>
      {exportMsg && (
        <div className="text-[10px]" style={{ color: readinessItem?.status === 'BLOCKED' ? '#ff5252' : '#00c853' }}>
          {exportMsg}
        </div>
      )}
    </div>
  );
}

export default function OptimizerPanel() {
  const {
    vars, constraints, maxCandidates, result, running, error,
    setConstraint, setMaxCandidates, clearResult, solve,
  } = useOptimizerStore();

  return (
    <div className="p-3 space-y-3">
      <div className="text-xs font-semibold" style={{ color: 'var(--color-text)' }}>
        Mission Optimizer
      </div>

      <div className="space-y-2">
        <div className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
          Optimize variables
        </div>
        {vars.map((v) => (
          <VariableRow key={v.name} v={v} />
        ))}
      </div>

      <div className="space-y-2">
        <div className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>Constraints</div>
        <div className="grid grid-cols-2 gap-1.5">
          {CONSTRAINT_KEYS.map((c) => (
            <div key={c.key} className="space-y-0.5">
              <label className="text-[10px] block truncate" style={{ color: 'var(--color-text-secondary)' }}>
                {c.label}
              </label>
              <input
                type="number"
                value={constraints[c.key] ?? ''}
                onChange={(e) => setConstraint(c.key, e.target.value)}
                placeholder="—"
                className="w-full px-2 py-1 text-xs rounded border outline-none"
                style={inputStyle}
              />
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <label className="text-xs shrink-0" style={{ color: 'var(--color-text-secondary)' }}>
          Max candidates
        </label>
        <input
          type="number"
          min={1}
          value={maxCandidates}
          onChange={(e) => setMaxCandidates(Math.max(1, e.target.valueAsNumber || 1))}
          className="flex-1 px-2 py-1 text-xs rounded border outline-none"
          style={inputStyle}
        />
      </div>

      <button
        onClick={solve}
        disabled={running}
        className="w-full py-2 text-xs rounded font-medium text-white transition-opacity disabled:opacity-40 hover:opacity-90"
        style={{ backgroundColor: '#4f8cff' }}
      >
        {running ? 'Optimizing…' : 'Optimize Mission'}
      </button>

      {error && (
        <div className="text-xs p-2 rounded" style={{ color: '#ff5252', backgroundColor: 'rgba(255,82,82,0.1)' }}>
          {error}
        </div>
      )}

      {result && (
        <>
          <ResultSection result={result} />
          <ApplyWinnerSection />
          <button
            onClick={clearResult}
            className="w-full py-1.5 text-xs rounded font-medium border transition-colors hover:opacity-90"
            style={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
          >
            Clear result
          </button>
        </>
      )}
    </div>
  );
}