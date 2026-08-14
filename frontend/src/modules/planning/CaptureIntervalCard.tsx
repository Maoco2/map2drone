import { useCallback, useState } from 'react';
import type { CaptureIntervalResult } from '@/shared/types/project';
import {
  STATUS_ERROR,
  STATUS_INCOMPATIBLE,
  STATUS_VALID,
  STATUS_WARNING,
  buildCopyConfigText,
} from '@/shared/utils/captureInterval';

const STATUS_STYLE: Record<string, { color: string; label: string }> = {
  [STATUS_VALID]: { color: '#00c853', label: 'CONFIGURACIÓN COMPATIBLE' },
  [STATUS_WARNING]: { color: '#ff9100', label: 'COMPATIBLE CON AJUSTE' },
  [STATUS_INCOMPATIBLE]: { color: '#e53935', label: 'INCOMPATIBLE' },
  [STATUS_ERROR]: { color: '#e53935', label: 'ERROR' },
};

interface CaptureIntervalCardProps {
  result: CaptureIntervalResult;
  gsd?: number;
  footprintLengthM?: number;
  frontOverlap?: number;
  lateralOverlap?: number;
}

export default function CaptureIntervalCard({
  result,
  gsd,
  footprintLengthM,
  frontOverlap,
  lateralOverlap,
}: CaptureIntervalCardProps) {
  const [copied, setCopied] = useState(false);
  const status = STATUS_STYLE[result.status] ?? STATUS_STYLE[STATUS_ERROR];
  const speed = result.speed_mps ?? 0;

  const handleCopy = useCallback(async () => {
    const text = buildCopyConfigText({ result, gsd, frontOverlap, lateralOverlap, footprintLengthM });
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // clipboard unavailable — ignore
    }
  }, [result, gsd, frontOverlap, lateralOverlap, footprintLengthM]);

  const row = (label: string, value: string) => (
    <div className="flex justify-between gap-2 text-xs">
      <span style={{ color: 'var(--color-text-secondary)' }}>{label}</span>
      <span className="font-mono">{value}</span>
    </div>
  );

  return (
    <div
      className="space-y-1.5 p-2 rounded text-xs"
      style={{ backgroundColor: 'var(--color-surface)', border: `1px solid ${status.color}44` }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="font-semibold" style={{ color: 'var(--color-text)' }}>
          CAPTURA DE FOTOGRAFÍAS
        </div>
        <span
          className="px-1.5 py-px rounded text-[9px] font-semibold shrink-0"
          style={{ color: '#fff', backgroundColor: status.color }}
        >
          {status.label}
        </span>
      </div>

      {result.recommended_interval_s != null ? (
        <>
          <div className="flex items-baseline gap-2">
            <div className="text-3xl font-bold font-mono" style={{ color: status.color }}>
              {result.recommended_interval_s}s
            </div>
            <div className="text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
              intervalo captura
              <br />recomendado
            </div>
          </div>
          {row('Velocidad', `${speed.toFixed(1)} m/s`)}
          {result.assumed_footprint_length_m != null && (
            row('Huella fotográfica', `${result.assumed_footprint_length_m.toFixed(1)} m`)
          )}
          {result.required_photo_spacing_m != null && (
            row('Espaciado requerido', `${result.required_photo_spacing_m.toFixed(1)} m`)
          )}
          {result.actual_photo_spacing_m != null && (
            row('Espaciado real', `${result.actual_photo_spacing_m.toFixed(1)} m`)
          )}
          {result.effective_front_overlap != null && (
            row(
              'Overlap frontal',
              `${result.effective_front_overlap.toFixed(1)} % (req. ${(result.required_front_overlap ?? 0).toFixed(0)} %)`,
            )
          )}
          {result.ideal_interval_s != null && (
            row('Intervalo ideal (info)', `${result.ideal_interval_s.toFixed(1)} s`)
          )}
        </>
      ) : result.status === STATUS_INCOMPATIBLE ? (
        <div
          className="text-[10px] leading-snug rounded p-2"
          style={{ color: '#ff6b6b', backgroundColor: 'rgba(229,57,53,0.1)' }}
        >
          {result.maximum_speed_for_1s != null ? (
            <>
              Para mantener el {Math.round(result.required_front_overlap ?? 0)} % de overlap
              utilizando captura cada 1 segundo, la velocidad máxima recomendada es{' '}
              <b>{result.maximum_speed_for_1s.toFixed(1)} m/s</b> (
              {(result.maximum_speed_for_1s * 3.6).toFixed(1)} km/h). Reduzca la velocidad de vuelo
              o aumente la altitud para obtener un intervalo compatible.
            </>
          ) : (
            'No es posible configurar un intervalo de captura con la velocidad actual.'
          )}
        </div>
      ) : (
        <div className="text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
          Parámetros de captura no válidos.
        </div>
      )}

      {result.terrain_follow && (
        <div
          className="pt-1.5 space-y-1 border-t"
          style={{ borderColor: 'var(--color-border)' }}
        >
          <div className="text-[9px] font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
            CÁLCULO CONSERVADOR · TERRENO
          </div>
          {result.planned_agl_m != null && row('Altitud planificada', `${result.planned_agl_m.toFixed(0)} m`)}
          {result.assumed_agl_m != null && (
            row('AGL conservador asumido', `${result.assumed_agl_m.toFixed(1)} m`)
          )}
          <div className="text-[9px] leading-snug" style={{ color: 'var(--color-text-secondary)' }}>
            AGL usado para el cálculo fotogramétrico conservador — puede ser menor
            que la altitud nominal de vuelo para garantizar el overlap frontal sobre el relieve.
          </div>
        </div>
      )}

      <button
        onClick={handleCopy}
        className="w-full py-1.5 text-[10px] rounded font-semibold border transition-colors opacity-80 hover:opacity-100"
        style={{
          backgroundColor: status.color,
          borderColor: status.color,
          color: '#fff',
        }}
      >
        {copied ? 'CONFIGURACIÓN COPIADA' : 'COPIAR CONFIGURACIÓN'}
      </button>
    </div>
  );
}