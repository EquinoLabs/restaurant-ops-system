import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from '../../features/authentication/AuthContext';
import { LoginForm } from '../../features/authentication/LoginForm';
import { MenuAdminView } from '../../features/menu-admin/MenuAdminView';
import { StaffOrdersView } from '../../features/staff-orders/StaffOrdersView';
import { ProtectedRoute } from '../../routes/ProtectedRoute';
import { NotFoundView } from '../../features/public-menu/NotFoundView';
import '../../index.css';

export const BusinessAdminApp: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginForm />} />
          
          <Route path="/admin" element={<Navigate to="/admin/menu" replace />} />
          <Route
            path="/admin/menu"
            element={
              <ProtectedRoute>
                <MenuAdminView />
              </ProtectedRoute>
            }
          />

          <Route path="/staff" element={<Navigate to="/staff/orders" replace />} />
          <Route
            path="/staff/orders"
            element={
              <ProtectedRoute>
                <StaffOrdersView />
              </ProtectedRoute>
            }
          />

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

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BusinessAdminApp />
  </React.StrictMode>
);
