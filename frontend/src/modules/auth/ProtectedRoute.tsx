import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from './authStore';

export default function ProtectedRoute() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (!isAuthenticated) return <Navigate to="/" replace />;
  return <Outlet />;
}
