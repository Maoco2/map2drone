import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import StatusBar from './StatusBar';

export default function MainLayout() {
  return (
    <div className="h-full w-full flex flex-col" style={{ backgroundColor: 'var(--color-surface)' }}>
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 relative overflow-hidden">
          <Outlet />
        </main>
      </div>
      <StatusBar />
    </div>
  );
}
