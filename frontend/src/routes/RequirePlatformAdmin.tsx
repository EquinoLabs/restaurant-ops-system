import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../features/authentication/AuthContext';

interface RequirePlatformAdminProps {
  children: React.ReactNode;
}

export const RequirePlatformAdmin: React.FC<RequirePlatformAdminProps> = ({ children }) => {
  const { user, token, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-slate-300">
        <div className="flex flex-col items-center space-y-4">
          <div className="w-10 h-10 border-4 border-amber-500/20 border-t-amber-500 rounded-full animate-spin"></div>
          <p className="text-xs font-semibold">Verifying Platform Permissions...</p>
        </div>
      </div>
    );
  }

  if (!token || !user) {
    return <Navigate to="/login" replace />;
  }

  if (!user.is_platform_admin) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 text-center space-y-4 shadow-2xl">
          <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/30 text-red-400 flex items-center justify-center mx-auto">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h3 className="text-lg font-bold text-white">Platform Access Denied</h3>
          <p className="text-xs text-slate-400">
            You do not have Platform Administrator privileges. This control plane is restricted to internal ROMS system operators.
          </p>
          <a
            href="/admin/menu"
            className="inline-block px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs font-bold transition-colors"
          >
            Return to Business Admin
          </a>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};
