import type { Camera, CaptureIntervalResult, CaptureIntervalStatus, Drone } from '@/shared/types/project';

/**
 * Live capture-interval calculations.
 *
 * Lightweight mirror of the backend CaptureIntervalEngine
 * (backend/app/core/photogrammetry/capture_interval.py) used for instant,
 * no-GIS updates when the user changes altitude / overlap / speed inputs.
 * The backend response remains the authoritative source of truth on Generate.
 *
 * IMPORTANT: the operational `recommended_interval_s` is ALWAYS an integer
 * number of seconds; `ideal_interval_s` is informational only. No `round()`
 * is ever applied to the ideal value.
 */

export const STATUS_VALID: CaptureIntervalStatus = 'VALID';
export const STATUS_WARNING: CaptureIntervalStatus = 'WARNING';
export const STATUS_INCOMPATIBLE: CaptureIntervalStatus = 'INCOMPATIBLE';
export const STATUS_ERROR: CaptureIntervalStatus = 'ERROR';

const DEFAULT_MIN_INTERVAL_S = 1.0;
const DEFAULT_MAX_INTERVAL_S = 60.0;
const WARNING_RATIO = 1.25;
const EPS = 1e-9;

export function calcGsd(altitudeM: number, focalLengthMm: number, pixelSizeUm: number): number {
  return (altitudeM * pixelSizeUm) / (focalLengthMm * 10);
}

/** Returns [footprintWidthM, footprintLengthM] (cm/px * pixels / 100). */
export function calcFootprint(gsdCmPx: number, imageWidthPx: number, imageHeightPx: number): [number, number] {
  return [(gsdCmPx * imageWidthPx) / 100, (gsdCmPx * imageHeightPx) / 100];
}

/** Mirrors backend `recommended_speed_ms` (shutter-limited, capped by drone). */
export function calcRecommendedSpeedMps(gsdCmPx: number, camera: Camera, droneMaxSpeedMs?: number): number {
  const gsdM = gsdCmPx / 100;
  const shutterSpeedS = camera.shutter_speed_s ?? 0.001;
  const factor = camera.shutter_type === 'mechanical' ? 1.0 : 0.5;
  const vShutter = gsdM / (2.0 * shutterSpeedS) * factor;
  return droneMaxSpeedMs ? Math.min(vShutter, droneMaxSpeedMs) : vShutter;
}

export function computeCaptureInterval(
  footprintLengthM: number,
  frontOverlap: number,
  flightSpeedMps: number,
): CaptureIntervalResult {
  const requiredFrontOverlap = Number.isFinite(frontOverlap) ? frontOverlap : 0;
  const speedMps = Number.isFinite(flightSpeedMps) ? flightSpeedMps : 0;

  const invalid =
    !Number.isFinite(footprintLengthM) ||
    footprintLengthM <= 0 ||
    !Number.isFinite(flightSpeedMps) ||
    flightSpeedMps <= 0 ||
    !Number.isFinite(frontOverlap) ||
    !(frontOverlap > 0 && frontOverlap < 100);

  if (invalid) {
    return {
      status: STATUS_ERROR,
      required_photo_spacing_m: 0,
      required_front_overlap: requiredFrontOverlap,
      speed_mps: speedMps,
    };
  }

  const requiredPhotoSpacingM = footprintLengthM * (1 - frontOverlap / 100);
  const idealIntervalS = requiredPhotoSpacingM / flightSpeedMps;

  const top = Math.floor(DEFAULT_MAX_INTERVAL_S / 1);
  const bottom = Math.ceil(DEFAULT_MIN_INTERVAL_S / 1);

  let recommended: number | undefined;
  for (let k = top; k >= bottom; k--) {
    const candidate = k;
    if (candidate * flightSpeedMps <= requiredPhotoSpacingM * (1 + EPS)) {
      recommended = candidate;
      break;
    }
  }

  if (recommended === undefined) {
    return {
      status: STATUS_INCOMPATIBLE,
      required_photo_spacing_m: requiredPhotoSpacingM,
      ideal_interval_s: idealIntervalS,
      recommended_interval_s: undefined,
      actual_photo_spacing_m: undefined,
      effective_front_overlap: undefined,
      required_front_overlap: frontOverlap,
      speed_mps: flightSpeedMps,
      maximum_speed_for_1s: requiredPhotoSpacingM / DEFAULT_MIN_INTERVAL_S,
    };
  }

  const actualPhotoSpacingM = recommended * flightSpeedMps;
  const effectiveFrontOverlap = 1 - actualPhotoSpacingM / footprintLengthM;
  const status = idealIntervalS / recommended > WARNING_RATIO ? STATUS_WARNING : STATUS_VALID;

  return {
    status,
    required_photo_spacing_m: requiredPhotoSpacingM,
    ideal_interval_s: idealIntervalS,
    recommended_interval_s: recommended,
    actual_photo_spacing_m: actualPhotoSpacingM,
    effective_front_overlap: effectiveFrontOverlap * 100,
    required_front_overlap: frontOverlap,
    speed_mps: flightSpeedMps,
    maximum_speed_for_1s: undefined,
  };
}

export interface LiveCapture {
  result: CaptureIntervalResult;
  gsd: number;
  footprintWidth: number;
  footprintLength: number;
  speedMps: number;
}

/**
 * Chain of camera -> footprint -> speed -> capture interval, mirroring the
 * backend planning engine. Single shared helper for Area Grid, Linear Corridor
 * and the capture card (no per-variant duplication).
 */
export function computeLiveCapture(opts: {
  altitude: number;
  camera: Camera;
  drone?: Drone;
  frontOverlap: number;
}): LiveCapture {
  const gsd = calcGsd(opts.altitude, opts.camera.focal_length_mm, opts.camera.pixel_size_um);
  const [footprintWidth, footprintLength] = calcFootprint(gsd, opts.camera.image_width_px, opts.camera.image_height_px);
  const speedMps = calcRecommendedSpeedMps(gsd, opts.camera, opts.drone?.max_speed_ms);
  const result = computeCaptureInterval(footprintLength, opts.frontOverlap, speedMps);
  return { result, gsd, footprintWidth, footprintLength, speedMps };
}

/** Clipboard text for the "COPIAR CONFIGURACIÓN" button (operational values only). */
export function buildCopyConfigText(opts: {
  result: CaptureIntervalResult;
  gsd?: number;
  frontOverlap?: number;
  lateralOverlap?: number;
  footprintLengthM?: number;
}): string {
  const { result } = opts;
  const kmh = (v: number) => v * 3.6;
  const lines: string[] = ['Map2Drone — Configuración de captura'];

  const speed = result.speed_mps ?? 0;
  lines.push(`Velocidad: ${speed.toFixed(1)} m/s`);

  if (result.status === STATUS_INCOMPATIBLE && result.maximum_speed_for_1s != null) {
    const maxKph = kmh(result.maximum_speed_for_1s);
    lines.push(`Intervalo: no compatible con la velocidad actual`);
    lines.push(
      `Para mantener el ${(result.required_front_overlap ?? 0).toFixed(0)} % de overlap utilizando captura cada 1 segundo, la velocidad máxima recomendada es ${result.maximum_speed_for_1s.toFixed(1)} m/s (${maxKph.toFixed(1)} km/h).`,
    );
  } else if (result.recommended_interval_s != null) {
    lines.push(
      `Intervalo: ${result.recommended_interval_s} ${result.recommended_interval_s === 1 ? 'segundo' : 'segundos'}`,
    );
    if (result.actual_photo_spacing_m != null) {
      lines.push(`Espaciado entre fotos: ${result.actual_photo_spacing_m.toFixed(1)} m`);
    }
  }

  if (opts.frontOverlap != null) lines.push(`Overlap frontal: ${opts.frontOverlap.toFixed(0)} %`);
  if (opts.lateralOverlap != null) lines.push(`Overlap lateral: ${opts.lateralOverlap.toFixed(0)} %`);
  if (opts.gsd != null) lines.push(`GSD: ${opts.gsd.toFixed(2)} cm/px`);
  if (opts.footprintLengthM != null) lines.push(`Huella fotográfica: ${opts.footprintLengthM.toFixed(1)} m`);

  lines.push(`Estado: ${result.status}`);
  return lines.join('\n');
}
