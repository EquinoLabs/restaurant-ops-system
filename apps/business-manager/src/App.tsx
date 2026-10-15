import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from '@roms/api-client';
import { LoginForm } from './features/authentication/LoginForm';
import { MenuAdminView } from './features/menu-admin/MenuAdminView';
import { StaffOrdersView } from './features/staff-orders/StaffOrdersView';
import { KDSView } from './features/kds/KDSView';
import { SubscriptionSummaryView } from './features/subscription/SubscriptionSummaryView';
import { TablesManagerView } from './features/tables/TablesManagerView';
import { ProtectedRoute } from './routes/ProtectedRoute';
import { NotFoundView } from '@roms/ui';

export const BusinessManagerApp: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/admin/menu" replace />} />
          <Route path="/login" element={<LoginForm />} />

          {/* Menu Management */}
          <Route path="/admin" element={<Navigate to="/admin/menu" replace />} />
          <Route
            path="/admin/menu"
            element={
              <ProtectedRoute>
                <MenuAdminView />
              </ProtectedRoute>
            }
          />

          {/* Dining Table Management */}
          <Route
            path="/admin/tables"
            element={
              <ProtectedRoute>
                <TablesManagerView />
              </ProtectedRoute>
            }
          />

          {/* Kitchen Display System */}
          <Route
            path="/admin/kds"
            element={
              <ProtectedRoute>
                <KDSView />
              </ProtectedRoute>
            }
          />

          {/* Business Owner Subscription Inspection */}
          <Route
            path="/admin/subscription"
            element={
              <ProtectedRoute>
                <SubscriptionSummaryView />
              </ProtectedRoute>
            }
          />

          {/* Staff POS Order Management */}
          <Route path="/staff" element={<Navigate to="/staff/orders" replace />} />
          <Route
            path="/staff/orders"
            element={
              <ProtectedRoute>
                <StaffOrdersView />
              </ProtectedRoute>
            }
          />

          {/* 404 Fallback */}
          <Route
            path="*"
            element={
              <NotFoundView message="The administrative page you requested does not exist." />
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default BusinessManagerApp;
