import { useCallback, useRef } from 'react';
import type { MapLayerMouseEvent } from 'react-map-gl/maplibre';
import { useMapStore } from './store';
import { useDrawStore, nextId } from './drawStore';

export function useDrawTools() {
  const snapEnabledRef = useRef(false);

  const handleMapClick = useCallback((e: MapLayerMouseEvent) => {
    const activeTool = useMapStore.getState().activeTool;
    if (!activeTool || activeTool === 'pan') return;

    const map = useMapStore.getState().mapRef;
    if (!map) return;

    if (activeTool === 'delete') {
      const features = map.queryRenderedFeatures(e.point, { layers: ['draw-fill', 'draw-line', 'draw-point'] });
      if (features && features.length > 0) {
        const id = features[0].id || features[0].properties?.id;
        if (id) useDrawStore.getState().removeFeature(id as string);
      }
      return;
    }

    const lngLat = e.lngLat;
    let lng = lngLat.lng;
    let lat = lngLat.lat;

    if (snapEnabledRef.current) {
      const snapDistance = 0.0001;
      for (const feat of useDrawStore.getState().features) {
        if (!feat.completed) continue;
        for (const pt of feat.points) {
          if (Math.abs(pt.lat - lat) < snapDistance && Math.abs(pt.lng - lng) < snapDistance) {
            lng = pt.lng;
            lat = pt.lat;
            break;
          }
        }
      }
    }

    const point = { lng, lat };

    if (activeTool === 'measure') {
      const current = useDrawStore.getState().currentFeature;
      if (!current || current.completed) {
        useDrawStore.getState().setCurrentFeature({
          id: nextId(),
          type: 'line',
          points: [point, point],
          completed: false,
        });
        useDrawStore.getState().setDrawMode('drawing');
      } else {
        useDrawStore.getState().addFeature({
          ...current,
          points: [current.points[0], point],
          completed: true,
          properties: { measure: true },
        });
        useDrawStore.getState().setCurrentFeature(null);
        useDrawStore.getState().setDrawMode('none');
      }
      return;
    }

    if (activeTool === 'waypoint') {
      useDrawStore.getState().addFeature({
        id: nextId(),
        type: 'waypoint',
        points: [point],
        completed: true,
      });
      return;
    }

    const current = useDrawStore.getState().currentFeature;
    if (!current || current.completed) {
      const newFeature = {
        id: nextId(),
        type: activeTool as 'polygon' | 'rectangle' | 'line',
        points: [point],
        completed: false,
      };
      useDrawStore.getState().setCurrentFeature(newFeature);
      useDrawStore.getState().setDrawMode('drawing');

      if (activeTool === 'rectangle' || activeTool === 'circle') {
        useDrawStore.getState().setCurrentFeature({
          ...newFeature,
          points: [point, point],
        });
      }
      return;
    }

    if (activeTool === 'rectangle' || activeTool === 'circle') {
      useDrawStore.getState().addFeature({
        ...current,
        points: [...current.points.slice(0, 1), point],
        completed: true,
      });
      useDrawStore.getState().setCurrentFeature(null);
      useDrawStore.getState().setDrawMode('none');
    } else if (activeTool === 'line') {
      useDrawStore.getState().setCurrentFeature({
        ...current,
        points: [...current.points, point],
      });
    } else if (activeTool === 'polygon') {
      useDrawStore.getState().setCurrentFeature({
        ...current,
        points: [...current.points, point],
      });
    }
  }, []);

  const handleMapDblClick = useCallback((_e: MapLayerMouseEvent) => {
    const activeTool = useMapStore.getState().activeTool;
    if (!activeTool || activeTool === 'pan') return;

    const current = useDrawStore.getState().currentFeature;
    if (!current || current.completed) return;

    if (activeTool === 'polygon' || activeTool === 'line') {
      if (current.points.length >= 2) {
        const completedFeature = { ...current, completed: true };
        useDrawStore.getState().setCurrentFeature(null);
        useDrawStore.getState().addFeature(completedFeature);
        useDrawStore.getState().setDrawMode('none');
      }
    }
  }, []);

  const handleMapMouseMove = useCallback((e: MapLayerMouseEvent) => {
    const activeTool = useMapStore.getState().activeTool;
    const drawMode = useDrawStore.getState().drawMode;
    const current = useDrawStore.getState().currentFeature;

    if (!activeTool || activeTool === 'pan') {
      useMapStore.getState().setCursor('default');
      return;
    }

    if (activeTool === 'polygon' || activeTool === 'rectangle' || activeTool === 'circle' || activeTool === 'line' || activeTool === 'waypoint' || activeTool === 'measure') {
      useMapStore.getState().setCursor('crosshair');
    } else if (activeTool === 'delete') {
      useMapStore.getState().setCursor('pointer');
    } else {
      useMapStore.getState().setCursor('default');
    }

    if (drawMode === 'drawing' && current && !current.completed) {
      if (activeTool === 'measure') {
        useDrawStore.getState().setCurrentFeature({
          ...current,
          points: [current.points[0], { lng: e.lngLat.lng, lat: e.lngLat.lat }],
        });
      } else if (activeTool === 'rectangle') {
        const pts = current.points;
        if (pts.length >= 1) {
          useDrawStore.getState().setCurrentFeature({
            ...current,
            points: [pts[0], { lng: e.lngLat.lng, lat: e.lngLat.lat }],
          });
        }
      } else if (activeTool === 'circle') {
        const first = current.points[0];
        if (first) {
          useDrawStore.getState().setCurrentFeature({
            ...current,
            points: [first, { lng: e.lngLat.lng, lat: e.lngLat.lat }],
          });
        }
      }
    }
  }, []);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    const current = useDrawStore.getState().currentFeature;
    const selectedId = useDrawStore.getState().selectedFeatureId;

    if (e.key === 'Escape' && current && !current.completed) {
      useDrawStore.getState().setCurrentFeature(null);
      useDrawStore.getState().setDrawMode('none');
      useMapStore.getState().setActiveTool(null);
    }
    if (e.key === 'Enter' && current && !current.completed) {
      if (current.points.length >= 2) {
        if (current.type === 'line' || current.type === 'polygon') {
          useDrawStore.getState().addFeature({ ...current, completed: true });
          useDrawStore.getState().setCurrentFeature(null);
          useDrawStore.getState().setDrawMode('none');
        }
      }
    }
    if (e.key === 'Delete' && selectedId) {
      useDrawStore.getState().removeFeature(selectedId);
      useDrawStore.getState().setSelectedFeatureId(null);
    }
  }, []);

  return { handleMapClick, handleMapDblClick, handleMapMouseMove, handleKeyDown };
}
