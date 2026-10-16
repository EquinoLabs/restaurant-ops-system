import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '@roms/api-client';
import { StateBlock } from '../components/ops-ui';

interface RequirePlatformAdminProps {
  children: React.ReactNode;
}

export const RequirePlatformAdmin: React.FC<RequirePlatformAdminProps> = ({ children }) => {
  const { user, token, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ops-canvas">
        <StateBlock variant="loading" title="Checking access" description="Verifying platform permissions…" />
      </div>
    );
  }

  if (!token || !user) {
    return <Navigate to="/login" replace />;
  }

  const isPlatformUser = Boolean(user.is_platform_admin || user.platform_role);
  if (!isPlatformUser) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ops-canvas p-4">
        <StateBlock
          variant="permission-denied"
          title="Platform access denied"
          description="You do not have Platform Administrator privileges. Contact the Platform Owner to request access."
          actionLabel="Return to Business Admin"
          onAction={() => {
            window.location.href = '/admin/menu';
          }}
        />
      </div>
    );
  }

  return <>{children}</>;
};
