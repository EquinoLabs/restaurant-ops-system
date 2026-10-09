import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from '../../features/authentication/AuthContext';
import { PlatformLoginForm } from '../../features/authentication/PlatformLoginForm';
import { PlatformAdminView } from '../../features/platform-admin/PlatformAdminView';
import { RequirePlatformAdmin } from '../../routes/RequirePlatformAdmin';
import { NotFoundView } from '../../features/public-menu/NotFoundView';
import '../../index.css';

export const PlatformAdminApp: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<PlatformLoginForm />} />
          <Route path="/" element={<Navigate to="/platform" replace />} />

          <Route
            path="/platform"
            element={
              <RequirePlatformAdmin>
                <PlatformAdminView />
              </RequirePlatformAdmin>
            }
          />
          <Route
            path="*"
            element={
              <NotFoundView message="The platform administrative page you requested does not exist." />
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <PlatformAdminApp />
  </React.StrictMode>
);
