import { Source, Layer, Marker } from 'react-map-gl/maplibre';
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

function WaypointMarker({ feature }: { feature: GeoJSON.Feature }) {
  const coords = (feature.geometry as GeoJSON.Point).coordinates;
  const props = feature.properties as Record<string, any>;
  const index = props.index;
  const altitude = props.altitude;
  const radius = index >= 100 ? 14 : 11;

  return (
    <Marker longitude={coords[0]} latitude={coords[1]}>
      <div style={{ position: 'relative', width: 0, height: 0 }}>
        <div
          style={{
            position: 'absolute',
            left: -radius,
            top: -radius,
            width: radius * 2,
            height: radius * 2,
            borderRadius: '50%',
            backgroundColor: '#1a5276',
            border: '1.5px solid #ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 11,
            fontWeight: 700,
            color: '#ffffff',
            fontFamily: 'Arial, sans-serif',
          }}
        >
          {index}
        </div>
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: radius + 2,
            transform: 'translateX(-50%)',
            whiteSpace: 'nowrap',
            fontSize: 9,
            fontWeight: 600,
            color: '#f1c40f',
            fontFamily: 'Arial, sans-serif',
            textShadow: '0 0 2px #000, 0 0 2px #000',
            pointerEvents: 'none',
          }}
        >
          {altitude}m
        </div>
      </div>
    </Marker>
  );
}

export default function FlightLinesLayer() {
  const geoJSON = useMissionStore((s) => s.flightLinesGeoJSON);

  const data = useMemo(() => {
    if (!geoJSON) return { type: 'FeatureCollection', features: [] } as GeoJSON.FeatureCollection;
    return geoJSON;
  }, [geoJSON]);

  const waypointFeatures = useMemo(() => {
    if (!geoJSON) return [];
    return geoJSON.features.filter((f) => f.properties?.type === 'waypoint');
  }, [geoJSON]);

  if (!geoJSON) return null;

  return (
    <>
      <Source id="flight-lines" type="geojson" data={data}>
        <Layer {...scanLineLayer} />
        <Layer {...giroLineLayer} />
        <Layer {...photoTriggerLayer} />
      </Source>
      {waypointFeatures.map((f) => (
        <WaypointMarker key={f.id} feature={f} />
      ))}
    </>
  );
}
