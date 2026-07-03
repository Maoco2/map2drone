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

const waypointLayer: LayerProps = {
  id: 'flight-waypoints',
  type: 'circle',
  filter: ['==', ['get', 'type'], 'waypoint'],
  paint: {
    'circle-radius': 4,
    'circle-color': '#00e676',
    'circle-stroke-width': 1.5,
    'circle-stroke-color': '#ffffff',
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
      <Layer {...waypointLayer} />
      <Layer {...photoTriggerLayer} />
    </Source>
  );
}
