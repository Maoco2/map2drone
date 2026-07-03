import { Source, Layer } from 'react-map-gl/maplibre';
import type { LayerProps } from 'react-map-gl/maplibre';
import { useDrawStore } from './drawStore';
import { useMemo } from 'react';

const fillLayer: LayerProps = {
  id: 'draw-fill',
  type: 'fill',
  paint: {
    'fill-color': '#4f8cff',
    'fill-opacity': 0.15,
  },
};

const lineLayer: LayerProps = {
  id: 'draw-line',
  type: 'line',
  paint: {
    'line-color': '#4f8cff',
    'line-width': 2,
    'line-opacity': 0.8,
  },
};

const outlineLayer: LayerProps = {
  id: 'draw-outline',
  type: 'line',
  paint: {
    'line-color': '#4f8cff',
    'line-width': 3,
    'line-opacity': 1,
  },
};

const pointLayer: LayerProps = {
  id: 'draw-point',
  type: 'circle',
  paint: {
    'circle-radius': 5,
    'circle-color': '#4f8cff',
    'circle-stroke-width': 2,
    'circle-stroke-color': '#ffffff',
  },
};

function featuresToGeoJSON(
  features: import('./drawStore').DrawFeature[],
  currentFeature: import('./drawStore').DrawFeature | null,
): GeoJSON.FeatureCollection {
  const fc: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] };

  for (const f of features) {
    if (!f.completed || f.points.length < (f.type === 'waypoint' ? 1 : 2)) continue;
    let geometry: GeoJSON.Geometry | null = null;

    switch (f.type) {
      case 'polygon': {
        const coords = f.points.map((p) => [p.lng, p.lat]);
        coords.push([f.points[0].lng, f.points[0].lat]);
        geometry = { type: 'Polygon', coordinates: [coords] };
        break;
      }
      case 'rectangle': {
        if (f.points.length < 2) break;
        const [p1, p2] = [f.points[0], f.points[1]];
        geometry = {
          type: 'Polygon',
          coordinates: [[
            [p1.lng, p1.lat],
            [p2.lng, p1.lat],
            [p2.lng, p2.lat],
            [p1.lng, p2.lat],
            [p1.lng, p1.lat],
          ]],
        };
        break;
      }
      case 'circle': {
        if (f.points.length < 2) break;
        const [center, edge] = [f.points[0], f.points[1]];
        const R = 6371000;
        const dLat = ((edge.lat - center.lat) * Math.PI) / 180;
        const dLon = ((edge.lng - center.lng) * Math.PI) / 180;
        const a = Math.sin(dLat / 2) ** 2 +
          Math.cos((center.lat * Math.PI) / 180) *
          Math.cos((edge.lat * Math.PI) / 180) *
          Math.sin(dLon / 2) ** 2;
        const radius = R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        const pts: number[][] = [];
        const cosLat = Math.cos((center.lat * Math.PI) / 180);
        for (let angle = 0; angle <= 360; angle += 10) {
          const rad = (angle * Math.PI) / 180;
          const lat = center.lat + (radius / R) * (180 / Math.PI) * Math.cos(rad);
          const lon = center.lng + (radius / R) * (180 / Math.PI) * Math.sin(rad) / cosLat;
          pts.push([lon, lat]);
        }
        geometry = { type: 'Polygon', coordinates: [pts] };
        break;
      }
      case 'line':
        if (f.points.length >= 2) {
          geometry = {
            type: 'LineString',
            coordinates: f.points.map((p) => [p.lng, p.lat]),
          };
        }
        break;
      case 'waypoint':
        geometry = { type: 'Point', coordinates: [f.points[0].lng, f.points[0].lat] };
        break;
    }

    if (geometry) {
      fc.features.push({
        type: 'Feature',
        id: f.id,
        geometry,
        properties: { type: f.type, id: f.id },
      });
    }
  }

  if (currentFeature && !currentFeature.completed) {
    const c = currentFeature;

    if (c.type === 'polygon' && c.points.length >= 2) {
      const coords = c.points.map((p) => [p.lng, p.lat]);
      coords.push([c.points[0].lng, c.points[0].lat]);
      fc.features.push({
        type: 'Feature',
        id: 'temp',
        geometry: { type: 'Polygon', coordinates: [coords] },
        properties: { type: 'polygon', temp: true },
      });
    }

    if (c.type === 'rectangle' && c.points.length >= 2) {
      const p1 = c.points[0];
      const p2 = c.points[1];
      fc.features.push({
        type: 'Feature', id: 'temp',
        geometry: {
          type: 'Polygon',
          coordinates: [[
            [p1.lng, p1.lat], [p2.lng, p1.lat],
            [p2.lng, p2.lat], [p1.lng, p2.lat],
            [p1.lng, p1.lat],
          ]],
        },
        properties: { type: 'rectangle', temp: true },
      });
    }

    if (c.type === 'circle' && c.points.length >= 2) {
      const [center, edge] = [c.points[0], c.points[1]];
      const R = 6371000;
      const dLat = ((edge.lat - center.lat) * Math.PI) / 180;
      const dLon = ((edge.lng - center.lng) * Math.PI) / 180;
      const a = Math.sin(dLat / 2) ** 2 +
        Math.cos((center.lat * Math.PI) / 180) *
        Math.cos((edge.lat * Math.PI) / 180) *
        Math.sin(dLon / 2) ** 2;
      const radius = R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
      const pts: number[][] = [];
      const cosLat = Math.cos((center.lat * Math.PI) / 180);
      for (let angle = 0; angle <= 360; angle += 10) {
        const rad = (angle * Math.PI) / 180;
        const lat = center.lat + (radius / R) * (180 / Math.PI) * Math.cos(rad);
        const lon = center.lng + (radius / R) * (180 / Math.PI) * Math.sin(rad) / cosLat;
        pts.push([lon, lat]);
      }
      fc.features.push({
        type: 'Feature', id: 'temp',
        geometry: { type: 'Polygon', coordinates: [pts] },
        properties: { type: 'circle', temp: true },
      });
    }

    if (c.type === 'line' && c.points.length >= 2) {
      fc.features.push({
        type: 'Feature', id: 'temp',
        geometry: {
          type: 'LineString',
          coordinates: c.points.map((p) => [p.lng, p.lat]),
        },
        properties: { type: 'line', temp: true },
      });
    }

    for (const pt of c.points) {
      fc.features.push({
        type: 'Feature',
        id: `v_${pt.lng}_${pt.lat}`,
        geometry: { type: 'Point', coordinates: [pt.lng, pt.lat] },
        properties: { type: 'vertex' },
      });
    }
  }

  return fc;
}

export default function DrawLayers() {
  const features = useDrawStore((s) => s.features);
  const currentFeature = useDrawStore((s) => s.currentFeature);

  const geoJSON = useMemo(
    () => featuresToGeoJSON(features, currentFeature),
    [features, currentFeature],
  );

  return (
    <Source id="draw" type="geojson" data={geoJSON}>
      <Layer {...fillLayer} />
      <Layer {...lineLayer} />
      <Layer {...pointLayer} />
      <Layer {...outlineLayer} />
    </Source>
  );
}
