import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from '@roms/api-client';
import { PlatformLoginForm } from './features/authentication/PlatformLoginForm';
import { RequirePlatformAdmin } from './routes/RequirePlatformAdmin';
import { PlatformLayout } from './routes/PlatformLayout';
import { DashboardPage } from './features/platform-admin/DashboardPage';
import { BusinessDirectoryPage } from './features/platform-admin/BusinessDirectoryPage';
import { BusinessDetailPage } from './features/platform-admin/BusinessDetailPage';
import { OutletDetailPage } from './features/platform-admin/OutletDetailPage';
import { PlansPage } from './features/platform-admin/PlansPage';
import { SubscriptionsOverviewPage } from './features/platform-admin/SubscriptionsOverviewPage';
import { AdminsPage } from './features/platform-admin/AdminsPage';
import { AuditLogsPage } from './features/platform-admin/AuditLogsPage';
import { NotFoundPage } from './components/errors/NotFoundPage';

export const PlatformAdminApp: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/platform/dashboard" replace />} />
          <Route path="/platform-admin.html" element={<Navigate to="/platform/dashboard" replace />} />
          <Route path="/login" element={<PlatformLoginForm />} />
          <Route path="/platform/login" element={<PlatformLoginForm />} />
          <Route path="/dashboard" element={<Navigate to="/platform/dashboard" replace />} />
          <Route path="/businesses" element={<Navigate to="/platform/businesses" replace />} />
          <Route path="/plans" element={<Navigate to="/platform/plans" replace />} />
          <Route path="/subscriptions" element={<Navigate to="/platform/subscriptions" replace />} />
          <Route path="/admins" element={<Navigate to="/platform/admins" replace />} />
          <Route path="/team" element={<Navigate to="/platform/admins" replace />} />
          <Route path="/audit-logs" element={<Navigate to="/platform/audit-logs" replace />} />

          <Route
            path="/platform"
            element={
              <RequirePlatformAdmin>
                <PlatformLayout />
              </RequirePlatformAdmin>
            }
          >
            <Route index element={<Navigate to="/platform/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="businesses" element={<BusinessDirectoryPage />} />
            <Route path="businesses/:businessId" element={<BusinessDetailPage />} />
            <Route path="outlets/:outletId" element={<OutletDetailPage />} />
            <Route path="plans" element={<PlansPage />} />
            <Route path="subscriptions" element={<SubscriptionsOverviewPage />} />
            <Route path="admins" element={<AdminsPage />} />
            <Route path="team" element={<Navigate to="/platform/admins" replace />} />
            <Route path="audit-logs" element={<AuditLogsPage />} />
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default PlatformAdminApp;
