import { useNavigate } from 'react-router-dom';
import { useProjectStore } from '@/modules/projects/store';
import { useThemeStore } from '@/shared/hooks/useTheme';
import { useAuthStore } from '@/modules/auth/authStore';
import { useSidebarStore } from './sidebarStore';
import ProjectTree from '@/modules/projects/ProjectTree';
import LayerPanel from './LayerPanel';
import MissionPanel from '@/modules/missions/MissionPanel';
import ExportPanel from '@/modules/export/ExportPanel';
import AdSlot from '@/shared/components/AdSlot';

type Tab = 'projects' | 'basemap' | 'missions' | 'export';

export default function Sidebar() {
  const { activeTab, setActiveTab } = useSidebarStore();
  const { isDark, toggle } = useThemeStore();
  const { projects, selectedProjectId, selectProject } = useProjectStore();
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: 'projects', label: 'Projects', icon: '📁' },
    { id: 'basemap', label: 'Basemap', icon: '🗺️' },
    { id: 'missions', label: 'Missions', icon: '✈️' },
    { id: 'export', label: 'Export', icon: '📤' },
  ];

  return (
    <aside
      className="w-72 flex flex-col border-r shrink-0"
      style={{
        backgroundColor: 'var(--color-panel)',
        borderColor: 'var(--color-border)',
      }}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--color-border)' }}>
        <div className="flex items-center gap-2">
          <img src="/icon-map2drone.png" alt="Map2Drone" className="w-6 h-6" />
          <span className="font-semibold text-sm">Map2Drone</span>
        </div>
        <button
          onClick={toggle}
          className="text-xs px-2 py-1 rounded"
          style={{ backgroundColor: 'var(--color-surface)' }}
        >
          {isDark ? '☀️' : '🌙'}
        </button>
      </div>

      <div className="flex border-b" style={{ borderColor: 'var(--color-border)' }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className="flex-1 py-2 text-xs font-medium transition-colors"
            style={{
              backgroundColor: activeTab === t.id ? 'var(--color-surface)' : 'transparent',
              color: activeTab === t.id ? 'var(--color-text)' : 'var(--color-text-secondary)',
              borderBottom: activeTab === t.id ? '2px solid #4f8cff' : '2px solid transparent',
            }}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {activeTab === 'projects' && <ProjectTree />}
        {activeTab === 'basemap' && <LayerPanel />}
        {activeTab === 'missions' && <MissionPanel />}
        {activeTab === 'export' && <ExportPanel />}
      </div>
      <AdSlot slotId="sidebar-banner" format="horizontal" className="px-2 py-1" />
      <div className="flex items-center justify-between px-4 py-2 border-t text-xs"
        style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}>
        <span className="truncate">{user?.full_name || user?.email}</span>
        <button
          onClick={() => { logout(); navigate('/'); }}
          className="text-xs px-2 py-1 rounded hover:bg-red-100 hover:text-red-600 transition-colors"
        >
          Salir
        </button>
      </div>
    </aside>
  );
}
