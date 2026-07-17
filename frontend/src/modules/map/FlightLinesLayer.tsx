import { Source, Layer } from 'react-map-gl/maplibre';
import type { LayerProps } from 'react-map-gl/maplibre';
import { useMissionStore } from '@/modules/missions/planningStore';
import { useMemo } from 'react';

const scanLineLayer: LayerProps = {
  id: 'flight-scan-lines',
  type: 'line',
  filter: ['==', ['get', 'type'], 'scan'],
  paint: {
    'line-color': '#00e676',
    'line-width': 2,
    'line-opacity': 0.8,
  },
};

const giroLineLayer: LayerProps = {
  id: 'flight-giro-lines',
  type: 'line',
  filter: ['==', ['get', 'type'], 'giro'],
  paint: {
    'line-color': '#ff9100',
    'line-width': 1.5,
    'line-dasharray': [2, 2],
    'line-opacity': 0.6,
  },
};

const waypointCircleLayer: LayerProps = {
  id: 'flight-waypoints-circle',
  type: 'circle',
  filter: ['==', ['get', 'type'], 'waypoint'],
  paint: {
    'circle-radius': ['case', ['>=', ['get', 'index'], 100], 14, 11],
    'circle-color': '#1a5276',
    'circle-stroke-width': 1.5,
    'circle-stroke-color': '#ffffff',
  },
};

const waypointLabelLayer: LayerProps = {
  id: 'flight-waypoints-label',
  type: 'symbol',
  filter: ['==', ['get', 'type'], 'waypoint'],
  layout: {
    'text-field': ['to-string', ['get', 'index']],
    'text-font': ['Noto Sans Bold'],
    'text-size': 11,
    'text-anchor': 'center',
    'text-allow-overlap': true,
    'text-ignore-placement': true,
  },
  paint: {
    'text-color': '#ffffff',
  },
};

const waypointAltLayer: LayerProps = {
  id: 'flight-waypoints-alt',
  type: 'symbol',
  filter: ['==', ['get', 'type'], 'waypoint'],
  layout: {
    'text-field': ['concat', ['to-string', ['get', 'altitude']], 'm'],
    'text-font': ['Noto Sans Regular'],
    'text-size': 9,
    'text-anchor': 'top',
    'text-offset': [0, 1.5],
    'text-allow-overlap': true,
    'text-ignore-placement': true,
  },
  paint: {
    'text-color': '#f1c40f',
    'text-halo-color': '#000000',
    'text-halo-width': 2,
  },
};

const photoTriggerLayer: LayerProps = {
  id: 'flight-photo-triggers',
  type: 'circle',
  filter: ['==', ['get', 'type'], 'photo_trigger'],
  paint: {
    'circle-radius': 2,
    'circle-color': '#ffab00',
    'circle-opacity': 0.6,
  },
};

export default function FlightLinesLayer() {
  const geoJSON = useMissionStore((s) => s.flightLinesGeoJSON);

  const data = useMemo(() => {
    if (!geoJSON) return { type: 'FeatureCollection', features: [] } as GeoJSON.FeatureCollection;
    return geoJSON;
  }, [geoJSON]);

  if (!geoJSON) return null;

  return (
    <Source id="flight-lines" type="geojson" data={data}>
      <Layer {...scanLineLayer} />
      <Layer {...giroLineLayer} />
      <Layer {...waypointCircleLayer} />
      <Layer {...waypointLabelLayer} />
      <Layer {...waypointAltLayer} />
      <Layer {...photoTriggerLayer} />
    </Source>
  );
}
