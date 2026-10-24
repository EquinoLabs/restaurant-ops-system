import React from 'react';
import { useAuth } from '@roms/api-client';
import { PlatformApprovals } from './PlatformApprovals';

export const ApprovalsPage: React.FC = () => {
  const { token } = useAuth();
  return <PlatformApprovals token={token} />;
};

export default ApprovalsPage;
