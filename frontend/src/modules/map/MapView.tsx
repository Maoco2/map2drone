import { useMemo, useRef, useCallback, useEffect } from 'react';
import Map, { MapRef, NavigationControl, ScaleControl } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useMapStore } from './store';
import { useDrawTools } from './useDrawTools';
import DrawLayers from './DrawLayers';
import MeasureInfo from './MeasureInfo';
import FlightLinesLayer from './FlightLinesLayer';
import { useDrawStore } from './drawStore';
import type { StyleSpecification } from 'maplibre-gl';
import AdSlot from '@/shared/components/AdSlot';

export default function MapView() {
  const mapRef = useRef<MapRef>(null);
  const { viewState, setViewState, setMapRef, basemap } = useMapStore();

  const mapStyle = useMemo(() => {
    const rasterStyle = (tiles: string[], attribution: string): StyleSpecification => ({
      version: 8,
      glyphs: 'https://fonts.openmaptiles.org/{fontstack}/{range}.pbf',
      sources: { r: { type: 'raster', tiles, tileSize: 256, attribution } },
      layers: [{ id: 'r', type: 'raster', source: 'r', minzoom: 0, maxzoom: 22 }],
    });
    if (basemap === 'satellite') {
      return rasterStyle(
        ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
        '&copy; Esri',
      );
    }
    if (basemap === 'hybrid') {
      return {
        version: 8,
        glyphs: 'https://fonts.openmaptiles.org/{fontstack}/{range}.pbf',
        sources: {
          sat: {
            type: 'raster',
            tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
            tileSize: 256,
            attribution: '&copy; Esri',
          },
          labels: {
            type: 'raster',
            tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'],
            tileSize: 256,
            attribution: '&copy; Esri',
          },
        },
        layers: [
          { id: 'satellite-layer', type: 'raster', source: 'sat', minzoom: 0, maxzoom: 22 },
          { id: 'labels-layer', type: 'raster', source: 'labels', minzoom: 0, maxzoom: 22 },
        ],
      } as StyleSpecification;
    }
    return rasterStyle(
      ['https://tile.opentopomap.org/{z}/{x}/{y}.png'],
      '&copy; OpenTopoMap contributors',
    );
  }, [basemap]);
  const {
    handleMapClick,
    handleMapDblClick,
    handleMapMouseMove,
    handleKeyDown,
  } = useDrawTools();

  const geoFetched = useRef(false);

  useEffect(() => {
    if (mapRef.current) {
      setMapRef(mapRef.current);
    }
  }, [mapRef.current, setMapRef]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  useEffect(() => {
    if (geoFetched.current) return;
    geoFetched.current = true;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setViewState({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          zoom: 16,
        });
      },
      () => {},
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }, [setViewState]);

  const onClick = useCallback(
    (e: any) => {
      handleMapClick(e);
    },
    [handleMapClick],
  );

  const onDblClick = useCallback(
    (e: any) => {
      if (useMapStore.getState().activeTool && useMapStore.getState().activeTool !== 'pan') {
        e.originalEvent.preventDefault();
      }
      handleMapDblClick(e);
    },
    [handleMapDblClick],
  );

  const onMouseMove = useCallback(
    (e: any) => {
      const coord = document.getElementById('coordinate-display');
      if (coord && e.lngLat) {
        coord.textContent = `Lat: ${e.lngLat.lat.toFixed(6)} Lon: ${e.lngLat.lng.toFixed(6)}`;
      }
      handleMapMouseMove(e);
    },
    [handleMapMouseMove],
  );

  return (
    <Map
      ref={mapRef}
      {...viewState}
      onMove={(evt) => setViewState(evt.viewState)}
      mapStyle={mapStyle}
      style={{ width: '100%', height: '100%' }}
      onClick={onClick}
      onDblClick={onDblClick}
      onMouseMove={onMouseMove}
      attributionControl={false}
      doubleClickZoom={false}
    >
      <DrawLayers />
      <MeasureInfo />
      <FlightLinesLayer />
      <NavigationControl position="top-right" />
      <ScaleControl unit="metric" />
      <div className="absolute bottom-2 left-2 z-10">
        <AdSlot slotId="map-banner" format="horizontal" />
      </div>
    </Map>
  );
}
