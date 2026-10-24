import React from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { PlatformShell, PlatformTab } from '../features/platform-admin/PlatformShell';

function getTabFromPath(path: string): PlatformTab {
  if (path.startsWith('/platform/businesses') || path.startsWith('/platform/outlets')) return 'businesses';
  if (path.startsWith('/platform/plans')) return 'plans';
  if (path.startsWith('/platform/subscriptions')) return 'subscriptions';
  if (path.startsWith('/platform/admins') || path.startsWith('/platform/team')) return 'admins';
  if (path.startsWith('/platform/approvals')) return 'approvals';
  if (path.startsWith('/platform/audit-logs')) return 'audit-logs';
  return 'dashboard';
}

export const PlatformLayout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const activeTab = getTabFromPath(location.pathname);

  const handleTabChange = (tab: PlatformTab) => {
    if (tab === 'dashboard') {
      navigate('/platform/dashboard');
    } else {
      navigate(`/platform/${tab}`);
    }
  };

  return (
    <PlatformShell activeTab={activeTab} onTabChange={handleTabChange}>
      <Outlet />
    </PlatformShell>
  );
};

export default PlatformLayout;
