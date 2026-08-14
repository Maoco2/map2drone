import { describe, expect, it } from 'vitest';
import {
  STATUS_ERROR,
  STATUS_INCOMPATIBLE,
  STATUS_VALID,
  STATUS_WARNING,
  buildCopyConfigText,
  calcGsd,
  computeCaptureInterval,
  computeLiveCapture,
  computeMinimumPlausibleAgl,
} from './captureInterval';
import type { Camera, Drone, CaptureIntervalResult } from '@/shared/types/project';

function forIdealInterval(idealS: number) {
  const speed = 1.0;
  const overlap = 80.0;
  const footprint = idealS / (1 - overlap / 100);
  return { footprint, overlap, speed };
}

const CASES: Array<[number, number | null, string]> = [
  [0.5, null, STATUS_INCOMPATIBLE],
  [0.9, null, STATUS_INCOMPATIBLE],
  [1.0, 1, STATUS_VALID],
  [1.2, 1, STATUS_VALID],
  [1.9, 1, STATUS_WARNING],
  [2.0, 2, STATUS_VALID],
  [2.1, 2, STATUS_VALID],
  [3.8, 3, STATUS_WARNING],
  [4.0, 4, STATUS_VALID],
  [4.9, 4, STATUS_VALID],
  [5.6, 5, STATUS_VALID],
  [6.0, 6, STATUS_VALID],
];

describe('computeCaptureInterval (mirror of backend engine)', () => {
  it.each(CASES)('ideal %ss -> recommended %s, status %s', (ideal, expectedRec, expectedStatus) => {
    const { footprint, overlap, speed } = forIdealInterval(ideal);
    const res = computeCaptureInterval(footprint, overlap, speed);
    expect(res.status).toBe(expectedStatus);
    expect(res.recommended_interval_s ?? null).toBe(expectedRec);
  });

  it.each(CASES.map((c) => c[0]))('keeps effective overlap >= required for ideal %ss', (ideal) => {
    const { footprint, overlap, speed } = forIdealInterval(ideal);
    const res = computeCaptureInterval(footprint, overlap, speed);
    if (res.status === STATUS_VALID || res.status === STATUS_WARNING) {
      expect(res.effective_front_overlap).not.toBeUndefined();
      expect((res.effective_front_overlap ?? 0) >= overlap - 1e-9).toBe(true);
    }
  });

  it.each(CASES.map((c) => c[0]))('always recommends an integer >= 1s for ideal %ss', (ideal) => {
    const { footprint, overlap, speed } = forIdealInterval(ideal);
    const res = computeCaptureInterval(footprint, overlap, speed);
    if (res.recommended_interval_s != null) {
      expect(Number.isInteger(res.recommended_interval_s)).toBe(true);
      expect(res.recommended_interval_s).toBeGreaterThanOrEqual(1);
    }
  });

  it('spec example: footprint 20 m, overlap 75%, speed 2 m/s -> 2 s', () => {
    const res = computeCaptureInterval(20, 75, 2);
    expect(res.status).toBe(STATUS_VALID);
    expect(res.required_photo_spacing_m).toBeCloseTo(5.0);
    expect(res.ideal_interval_s).toBeCloseTo(2.5);
    expect(res.recommended_interval_s).toBe(2);
    expect(res.actual_photo_spacing_m).toBeCloseTo(4.0);
    expect(res.effective_front_overlap).toBeCloseTo(80.0);
  });

  it('chooses the largest valid integer, never rounds up (2.5 -> 2, 5.6 -> 5)', () => {
    const a = computeCaptureInterval(20, 75, 2);
    expect(a.recommended_interval_s).toBe(2);
    const { footprint, overlap, speed } = forIdealInterval(5.6);
    expect(computeCaptureInterval(footprint, overlap, speed).recommended_interval_s).toBe(5);
  });

  it('INCOMPATIBLE when even 1 s fails, with maximum speed for 1 s', () => {
    const { footprint, overlap, speed } = forIdealInterval(0.5);
    const res = computeCaptureInterval(footprint, overlap, speed);
    expect(res.status).toBe(STATUS_INCOMPATIBLE);
    expect(res.recommended_interval_s).toBeUndefined();
    expect(res.maximum_speed_for_1s).toBeCloseTo(0.5);
  });

  it('ERROR on invalid inputs', () => {
    expect(computeCaptureInterval(0, 75, 2).status).toBe(STATUS_ERROR);
    expect(computeCaptureInterval(20, 75, 0).status).toBe(STATUS_ERROR);
    expect(computeCaptureInterval(20, 100, 2).status).toBe(STATUS_ERROR);
    expect(computeCaptureInterval(20, 0, 2).status).toBe(STATUS_ERROR);
    expect(computeCaptureInterval(20, 75, -1).status).toBe(STATUS_ERROR);
  });
});

describe('calcGsd / computeLiveCapture', () => {
  it('calcGsd matches backend formula', () => {
    expect(calcGsd(100, 12, 3.27)).toBeCloseTo((100 * 3.27) / (12 * 10), 6);
  });

  it('computeLiveCapture mirrors backend shutter-limited speed', () => {
    const camera: Camera = {
      id: 'c1',
      name: 'Test',
      sensor_width_mm: 17.3,
      sensor_height_mm: 13.0,
      image_width_px: 5280,
      image_height_px: 3956,
      focal_length_mm: 12,
      pixel_size_um: 3.27,
      shutter_speed_s: 0.001,
      shutter_type: 'electronic',
    };
    const drone: Drone = {
      id: 'd1',
      name: 'Test',
      manufacturer: 'T',
      weight_kg: 1,
      max_speed_ms: 21,
      flight_time_min: 45,
      max_altitude_m: 5000,
      camera_id: 'c1',
    };
    const live = computeLiveCapture({ altitude: 100, camera, drone, frontOverlap: 75 });
    const gsd = calcGsd(100, 12, 3.27);
    expect(live.gsd).toBeCloseTo(gsd, 6);
    // electronic shutter factor 0.5
    const vShutter = (gsd / 100) / (2 * 0.001) * 0.5;
    expect(live.speedMps).toBeCloseTo(Math.min(vShutter, 21), 3);
    expect(live.result.recommended_interval_s).toBeGreaterThanOrEqual(1);
  });
});

describe('computeMinimumPlausibleAgl (terrain-follow conservative rule)', () => {
  it('constant terrain keeps the nominal AGL', () => {
    expect(computeMinimumPlausibleAgl(100, [600, 600, 600])).toBeCloseTo(100);
  });

  it('terrain rising above the reference reduces the minimum AGL', () => {
    expect(computeMinimumPlausibleAgl(100, [600, 620, 640])).toBeCloseTo(60);
  });

  it('terrain falling below the reference keeps the nominal AGL', () => {
    expect(computeMinimumPlausibleAgl(100, [640, 620, 600])).toBeCloseTo(100);
  });

  it('no elevations falls back to the requested AGL', () => {
    expect(computeMinimumPlausibleAgl(100, [])).toBeCloseTo(100);
    expect(computeMinimumPlausibleAgl(100, undefined, 80)).toBeCloseTo(80);
  });

  it('all-zero elevations (DEM unavailable) fall back to the requested AGL', () => {
    expect(computeMinimumPlausibleAgl(100, [0, 0, 0])).toBeCloseTo(100);
  });

  it('never dips below the 1 m floor', () => {
    expect(computeMinimumPlausibleAgl(50, [600, 900])).toBeCloseTo(1);
  });

  it('shrinks the live footprint/interval vs nominal (mirrors backend)', () => {
    const camera: Camera = {
      id: 'c1',
      name: 'Test',
      sensor_width_mm: 13.2,
      sensor_height_mm: 8.8,
      image_width_px: 5472,
      image_height_px: 3648,
      focal_length_mm: 8.8,
      pixel_size_um: 2.41,
      shutter_speed_s: 0.001,
      shutter_type: 'electronic',
    };
    const drone: Drone = {
      id: 'd1',
      name: 'Test',
      manufacturer: 'T',
      weight_kg: 1,
      max_speed_ms: 21,
      flight_time_min: 45,
      max_altitude_m: 5000,
      camera_id: 'c1',
    };
    const nominal = computeLiveCapture({ altitude: 100, camera, drone, frontOverlap: 75 });
    const conservative = computeLiveCapture({
      altitude: 100,
      camera,
      drone,
      frontOverlap: 75,
      terrainFollow: true,
      groundElevations: [600, 620, 640],
    });
    expect(conservative.footprintLength).toBeLessThan(nominal.footprintLength);
    expect((conservative.result.recommended_interval_s ?? Infinity)).toBeLessThanOrEqual(
      nominal.result.recommended_interval_s ?? Infinity,
    );
  });

  it('exposes the assumed conservative AGL on the result when terrain-follow is on', () => {
    const camera: Camera = {
      id: 'c1',
      name: 'Test',
      sensor_width_mm: 13.2,
      sensor_height_mm: 8.8,
      image_width_px: 5472,
      image_height_px: 3648,
      focal_length_mm: 8.8,
      pixel_size_um: 2.41,
      shutter_speed_s: 0.001,
      shutter_type: 'electronic',
    };
    const drone: Drone = {
      id: 'd1',
      name: 'Test',
      manufacturer: 'T',
      weight_kg: 1,
      max_speed_ms: 21,
      flight_time_min: 45,
      max_altitude_m: 5000,
      camera_id: 'c1',
    };
    const terrain = computeLiveCapture({
      altitude: 100,
      camera,
      drone,
      frontOverlap: 75,
      terrainFollow: true,
      groundElevations: [600, 620, 640],
    });
    expect(terrain.result.terrain_follow).toBe(true);
    expect(terrain.result.planned_agl_m).toBe(100);
    expect(terrain.result.assumed_agl_m).toBeCloseTo(60);
    expect(terrain.assumedAglM).toBeCloseTo(60);
    expect(terrain.terrainFollow).toBe(true);
    expect(terrain.result.assumed_footprint_length_m).toBeCloseTo(terrain.footprintLength);

    // without elevation data (live mirror) it falls back to the requested AGL
    const fallback = computeLiveCapture({
      altitude: 100,
      camera,
      drone,
      frontOverlap: 75,
      terrainFollow: true,
    });
    expect(fallback.result.terrain_follow).toBe(true);
    expect(fallback.result.assumed_agl_m).toBeCloseTo(100);

    // non-terrain leaves the assumption off
    const plain = computeLiveCapture({ altitude: 100, camera, drone, frontOverlap: 75 });
    expect(plain.result.terrain_follow).toBe(false);
    expect(plain.result.assumed_agl_m).toBeCloseTo(100);
  });
});

describe('buildCopyConfigText', () => {
  it('uses the recommended integer interval, never the ideal decimal', () => {
    const res = computeCaptureInterval(20, 75, 2);
    const text = buildCopyConfigText({ result: res, gsd: 2.72, frontOverlap: 75, lateralOverlap: 65 });
    expect(text).toContain('Map2Drone — Configuración de captura');
    expect(text).toContain('Intervalo: 2 segundos');
    expect(text).not.toContain('Intervalo: 2.5');
    expect(text).toContain('Velocidad: 2.0 m/s');
  });

  it('exposes the conservative assumed AGL when terrain-follow is active', () => {
    const res: CaptureIntervalResult = {
      status: STATUS_VALID,
      required_photo_spacing_m: 15.0,
      ideal_interval_s: 3.0,
      recommended_interval_s: 3,
      actual_photo_spacing_m: 15.0,
      effective_front_overlap: 80,
      required_front_overlap: 75,
      speed_mps: 5.0,
      planned_agl_m: 100,
      terrain_follow: true,
      assumed_agl_m: 60,
      assumed_footprint_length_m: 59.9,
    };
    const text = buildCopyConfigText({ result: res, frontOverlap: 75, lateralOverlap: 65 });
    expect(text).toContain('Altitud planificada: 100 m');
    expect(text).toContain('Seguimiento de terreno: activado');
    expect(text).toContain('AGL conservador asumido: 60.0 m');
    expect(text).toContain('Huella fotográfica: 59.9 m');
  });
});
