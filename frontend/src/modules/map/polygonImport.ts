import JSZip from 'jszip';
import shp from 'shpjs';

export interface ImportedPolygon {
  points: { lng: number; lat: number }[];
}

function coordsToPoints(
  coords: number[][],
): { lng: number; lat: number }[] {
  return coords.map((c) => ({ lng: c[0], lat: c[1] }));
}

function parseGeoJSON(text: string): ImportedPolygon[] {
  const gj = JSON.parse(text);
  const features = gj.type === 'FeatureCollection' ? gj.features : [gj];
  const results: ImportedPolygon[] = [];
  for (const f of features) {
    if (!f.geometry) continue;
    const g = f.geometry;
    if (g.type === 'Polygon') {
      results.push({ points: coordsToPoints(g.coordinates[0]) });
    } else if (g.type === 'MultiPolygon') {
      for (const poly of g.coordinates) {
        results.push({ points: coordsToPoints(poly[0]) });
      }
    }
  }
  return results;
}

function parseKML(text: string): ImportedPolygon[] {
  const doc = new DOMParser().parseFromString(text, 'text/xml');
  const placemarks = doc.querySelectorAll('Placemark');
  const results: ImportedPolygon[] = [];
  for (const pm of placemarks) {
    const coordsEl = pm.querySelector('Polygon outerBoundaryIs LinearRing coordinates, Polygon coordinates');
    if (!coordsEl) continue;
    const raw = coordsEl.textContent || '';
    const points = raw.trim().split(/\s+/).map((triplet) => {
      const [lng, lat] = triplet.split(',').map(Number);
      return { lng, lat };
    }).filter((p) => !isNaN(p.lng) && !isNaN(p.lat));
    if (points.length >= 3) results.push({ points });
  }
  return results;
}

async function parseKMZ(buffer: ArrayBuffer): Promise<ImportedPolygon[]> {
  const zip = await JSZip.loadAsync(buffer);
  const kmlFile = Object.keys(zip.files).find((f) => f.endsWith('.kml'));
  if (!kmlFile) throw new Error('No KML file found inside KMZ');
  const text = await zip.files[kmlFile].async('text');
  return parseKML(text);
}

function parseCSV(text: string): ImportedPolygon[] {
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  if (lines.length < 2) return [];
  const header = lines[0].toLowerCase();
  const cols = header.split(/[,;\t|]+/);
  const latIdx = cols.findIndex((c) => /^lat/i.test(c));
  const lonIdx = cols.findIndex((c) => /^l?on/i.test(c) || /^lng/i.test(c) || /^lon/i.test(c) || /^long/i.test(c));
  if (latIdx === -1 || lonIdx === -1) return [];
  const points: { lng: number; lat: number }[] = [];
  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(/[,;\t|]+/);
    const lat = parseFloat(parts[latIdx]);
    const lon = parseFloat(parts[lonIdx]);
    if (!isNaN(lat) && !isNaN(lon)) points.push({ lng: lon, lat });
  }
  if (points.length >= 3) return [{ points }];
  return [];
}

function parseTXT(text: string): ImportedPolygon[] {
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  if (lines.length < 3) return [];
  const points: { lng: number; lat: number }[] = [];
  for (const line of lines) {
    const parts = line.split(/[,;\t\s|]+/).filter(Boolean);
    if (parts.length >= 2) {
      const first = parseFloat(parts[0]);
      const second = parseFloat(parts[1]);
      if (!isNaN(first) && !isNaN(second)) {
        points.push({ lng: second, lat: first });
      }
    }
  }
  if (points.length >= 3) return [{ points }];
  return [];
}

async function parseShapefile(buffer: ArrayBuffer): Promise<ImportedPolygon[]> {
  const gj = await shp(buffer);
  const features = Array.isArray(gj) ? gj : (gj as any).features ?? [];
  const results: ImportedPolygon[] = [];
  for (const f of features) {
    const g = f.geometry || f;
    if (g.type === 'Polygon') {
      results.push({ points: coordsToPoints(g.coordinates[0]) });
    } else if (g.type === 'MultiPolygon') {
      for (const poly of g.coordinates) {
        results.push({ points: coordsToPoints(poly[0]) });
      }
    }
  }
  return results;
}

export async function importPolygonFromFile(file: File): Promise<ImportedPolygon[]> {
  const ext = file.name.split('.').pop()?.toLowerCase() || '';
  const buffer = await file.arrayBuffer();
  const text = await file.text().catch(() => '');

  if (ext === 'geojson' || ext === 'json') return parseGeoJSON(text);
  if (ext === 'kml') return parseKML(text);
  if (ext === 'kmz') return parseKMZ(buffer);
  if (ext === 'csv') {
    const csv = parseCSV(text);
    if (csv.length) return csv;
  }
  if (ext === 'txt') {
    const txt = parseTXT(text);
    if (txt.length) return txt;
  }
  if (ext === 'shp') return parseShapefile(buffer);
  if (ext === 'zip') {
    try {
      return await parseKMZ(buffer);
    } catch {}
  }
  const csv = parseCSV(text);
  if (csv.length) return csv;
  const txt = parseTXT(text);
  if (txt.length) return txt;
  try {
    return parseGeoJSON(text);
  } catch {}
  try {
    return parseKML(text);
  } catch {}
  throw new Error(`Unsupported format: .${ext}`);
}
