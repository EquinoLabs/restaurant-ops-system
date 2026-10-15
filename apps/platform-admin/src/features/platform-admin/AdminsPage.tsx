import React from 'react';
import { useAuth } from '@roms/api-client';
import { PlatformAdminManagement } from './PlatformAdminManagement';

export const AdminsPage: React.FC = () => {
  const { token } = useAuth();
  return <PlatformAdminManagement token={token} />;
};

export default AdminsPage;
