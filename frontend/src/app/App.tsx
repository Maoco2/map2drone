import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import ProjectPage from '@/modules/projects/ProjectPage';
import LandingPage from '@/modules/auth/LandingPage';
import PrivacyPage from '@/modules/privacy/PrivacyPage';
import ProtectedRoute from '@/modules/auth/ProtectedRoute';
import { AdsenseProvider } from '@/shared/adsense/AdsenseContext';
import CookieConsent from '@/shared/components/CookieConsent';

export default function App() {
  return (
    <AdsenseProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<MainLayout />}>
              <Route path="/projects" element={<ProjectPage />} />
              <Route path="/projects/:projectId" element={<ProjectPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <CookieConsent />
      </BrowserRouter>
    </AdsenseProvider>
  );
}
