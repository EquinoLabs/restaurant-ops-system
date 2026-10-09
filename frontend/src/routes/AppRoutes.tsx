import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { PublicMenuView } from '../features/public-menu/PublicMenuView';
import { NotFoundView } from '../features/public-menu/NotFoundView';
import { LoginForm } from '../features/authentication/LoginForm';
import { MenuAdminView } from '../features/menu-admin/MenuAdminView';
import { ProtectedRoute } from './ProtectedRoute';

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Public QR Code Menu Route */}
      <Route path="/m/:publicSlug" element={<PublicMenuView />} />

      {/* Staff Authentication Route */}
      <Route path="/login" element={<LoginForm />} />

      {/* Administrative Dashboard Routes */}
      <Route path="/admin" element={<Navigate to="/admin/menu" replace />} />
      <Route
        path="/admin/menu"
        element={
          <ProtectedRoute>
            <MenuAdminView />
          </ProtectedRoute>
        }
      />

      {/* Unmapped URL 404 Page */}
      <Route
        path="*"
        element={
          <NotFoundView message="The page or link you opened does not exist. Please check the URL or scan a valid restaurant QR code." />
        }
      />
    </Routes>
  );
};
