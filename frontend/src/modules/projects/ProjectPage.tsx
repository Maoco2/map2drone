import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import MapView from '@/modules/map/MapView';
import DrawingToolbar from '@/modules/map/DrawingToolbar';
import PropertiesPanel from '@/modules/planning/PropertiesPanel';
import { useProjectStore } from './store';
import { useMissionListStore } from '@/modules/missions/missionListStore';

export default function ProjectPage() {
  const { projectId } = useParams();
  const selectProject = useProjectStore((s) => s.selectProject);
  const fetchMissions = useMissionListStore((s) => s.fetchMissions);

  useEffect(() => {
    if (projectId) {
      selectProject(projectId);
    }
  }, [projectId, selectProject]);

  useEffect(() => {
    fetchMissions();
  }, [fetchMissions]);

  return (
    <div className="h-full w-full flex">
      <div className="flex-1 relative">
        <DrawingToolbar />
        <MapView />
      </div>
      <PropertiesPanel />
    </div>
  );
}
