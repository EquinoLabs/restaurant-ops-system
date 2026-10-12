import React, { useState, useEffect, useCallback } from 'react';
import { PlatformAdminUser } from '../../types/platform';
import { fetchPlatformAdmins, grantPlatformAdmin, revokePlatformAdmin } from '../../api/client';
import { useAuth } from '../authentication/AuthContext';
import { UserMe } from '../../types/auth';

interface PlatformAdminManagementProps {
  token: string | null;
}

export function getPlatformRoleInfo(user: PlatformAdminUser): { label: string; badgeClasses: string } {
  const normalizedRole = user.platform_role?.trim().toLowerCase();
  if (normalizedRole === 'owner') {
    return {
      label: 'Platform Owner',
      badgeClasses: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
    };
  }
  if (normalizedRole === 'admin') {
    return {
      label: 'Platform Admin',
      badgeClasses: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30',
    };
  }
  if (normalizedRole === 'operator') {
    return {
      label: 'Platform Operator',
      badgeClasses: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    };
  }
  // Legacy compatibility: platform_role is null/undefined and is_platform_admin is true
  if ((user.platform_role === null || user.platform_role === undefined) && user.is_platform_admin) {
    return {
      label: 'Platform Admin (Legacy)',
      badgeClasses: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
    };
  }
  return {
    label: 'Standard User',
    badgeClasses: 'bg-slate-800 text-slate-400 border-slate-700',
  };
}

export const PlatformAdminManagement: React.FC<PlatformAdminManagementProps> = ({ token }) => {
  let currentUser: UserMe | null = null;
  try {
    const auth = useAuth();
    currentUser = auth.user;
  } catch {
    currentUser = null;
  }

  const isOperator = currentUser?.platform_role === 'operator';
  const isCurrentOwner = Boolean(currentUser && currentUser.platform_role?.toLowerCase() === 'owner');

  const [admins, setAdmins] = useState<PlatformAdminUser[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [ownerNotInitialized, setOwnerNotInitialized] = useState<boolean>(false);
  const [permissionDenied, setPermissionDenied] = useState<boolean>(false);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Modal & Action state
  const [selectedUser, setSelectedUser] = useState<PlatformAdminUser | null>(null);
  const [actionType, setActionType] = useState<'grant' | 'revoke' | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadAdmins = useCallback(async () => {
    if (!token || isOperator) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      setOwnerNotInitialized(false);
      setPermissionDenied(false);
      const data = await fetchPlatformAdmins(token);
      setAdmins(data);
    } catch (err: any) {
      if (
        err.status === 503 ||
        err.code === 'PLATFORM_OWNER_NOT_INITIALIZED' ||
        err.message?.includes('Platform Owner has not been initialized')
      ) {
        setOwnerNotInitialized(true);
        setError(err.message || 'Platform Owner has not been initialized. Governance operations are unavailable.');
      } else if (
        err.status === 403 ||
        err.message?.includes('Forbidden') ||
        err.message?.includes('privileges are required')
      ) {
        setPermissionDenied(true);
        setError(err.message || 'Platform administrator privileges are required to view this directory.');
      } else {
        setError(err.message || 'Failed to load platform administrator directory.');
      }
    } finally {
      setLoading(false);
    }
  }, [token, isOperator]);

  useEffect(() => {
    loadAdmins();
  }, [loadAdmins]);

  const handleOpenConfirmModal = (user: PlatformAdminUser, type: 'grant' | 'revoke') => {
    if (type === 'revoke' && currentUser && currentUser.id === user.id) {
      return;
    }
    setSelectedUser(user);
    setActionType(type);
    setActionError(null);
  };

  const handleCloseModal = () => {
    if (isSubmitting) return;
    setSelectedUser(null);
    setActionType(null);
    setActionError(null);
  };

  const handleConfirmAction = async () => {
    if (!token || !selectedUser || !actionType) return;
    if (actionType === 'revoke' && currentUser && currentUser.id === selectedUser.id) {
      setActionError('Platform administrators cannot revoke their own privileges.');
      return;
    }
    if (!isCurrentOwner) {
      setActionError('Permission denied: Only Platform Owners may modify administrator privileges.');
      return;
    }
    try {
      setIsSubmitting(true);
      setActionError(null);
      setActionSuccess(null);

      if (actionType === 'revoke') {
        await revokePlatformAdmin(selectedUser.id, token);
        setActionSuccess(`Platform administrator privileges revoked from '${selectedUser.email}'.`);
      } else {
        await grantPlatformAdmin(selectedUser.id, token);
        setActionSuccess(`Platform administrator privileges granted to '${selectedUser.email}'.`);
      }

      handleCloseModal();
      await loadAdmins();
    } catch (err: any) {
      if (
        err.status === 503 ||
        err.code === 'PLATFORM_OWNER_NOT_INITIALIZED' ||
        err.message?.includes('Platform Owner has not been initialized')
      ) {
        setOwnerNotInitialized(true);
        setActionError('Platform Owner has not been initialized. Governance operations are unavailable (HTTP 503).');
      } else if (err.status === 403) {
        setActionError(err.message || 'Permission denied: Only Platform Owners may modify administrator privileges (HTTP 403).');
      } else {
        setActionError(err.message || `Failed to ${actionType} administrator privileges.`);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // Direct navigation guard for Platform Operators
  if (isOperator) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-8 text-center max-w-xl mx-auto space-y-4 my-8 shadow-xl">
        <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-400 mx-auto flex items-center justify-center">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <div>
          <h3 className="text-base font-bold text-white">Access Restricted: Platform Operator</h3>
          <p className="text-xs text-slate-400 mt-2 leading-relaxed">
            Platform Operators do not have administrative directory access. Access to the platform team management directory is restricted to Platform Owners and Platform Admins.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/60 border border-slate-800 p-6 rounded-2xl">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <svg className="w-6 h-6 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            Platform Administrators
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Manage SaaS control plane access, super-administrator accounts, and privilege revocation.
          </p>
        </div>

        <button
          onClick={loadAdmins}
          disabled={loading}
          className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-colors flex items-center justify-center space-x-2 self-start sm:self-auto disabled:opacity-50"
        >
          <svg className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>Refresh Directory</span>
        </button>
      </div>

      {/* Global Alerts */}
      {ownerNotInitialized && (
        <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-2xl text-amber-300 text-xs flex items-start justify-between gap-3 shadow-lg">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <div className="font-bold text-amber-200">Platform Governance Offline (Zero-Owner State)</div>
              <p className="mt-0.5 text-amber-300/90 leading-relaxed">
                Platform Owner has not been initialized. Ordinary role-governance endpoints fail closed with HTTP 503 Service Unavailable. Commercial and operations routes remain active.
              </p>
            </div>
          </div>
          <button onClick={() => setOwnerNotInitialized(false)} className="text-amber-400 hover:text-amber-300 font-bold p-1">
            ✕
          </button>
        </div>
      )}

      {permissionDenied && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl text-rose-300 text-xs flex items-start justify-between gap-3 shadow-lg">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
            </svg>
            <div>
              <div className="font-bold text-rose-200">Permission Denied</div>
              <p className="mt-0.5 text-rose-300/90 leading-relaxed">
                {error || 'Platform administrator privileges are required to view this directory (HTTP 403).'}
              </p>
            </div>
          </div>
          <button onClick={() => setPermissionDenied(false)} className="text-rose-400 hover:text-rose-300 font-bold p-1">
            ✕
          </button>
        </div>
      )}

      {actionSuccess && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-xs font-medium flex items-center justify-between">
          <span>{actionSuccess}</span>
          <button onClick={() => setActionSuccess(null)} className="text-emerald-400 hover:text-emerald-300 ml-4 font-bold">
            ✕
          </button>
        </div>
      )}

      {error && !ownerNotInitialized && !permissionDenied && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs font-medium flex items-center justify-between">
          <div>
            <div className="font-bold">Error Loading Administrator Directory</div>
            <div>{error}</div>
          </div>
          <button
            onClick={loadAdmins}
            className="px-3 py-1 bg-red-500/20 hover:bg-red-500/30 text-red-300 font-semibold rounded-lg text-xs"
          >
            Retry
          </button>
        </div>
      )}

      {/* Admin List / Directory Card */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        {loading ? (
          <div className="p-12 text-center text-slate-400 text-sm flex flex-col items-center space-y-3">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
            <span>Loading platform administrator directory...</span>
          </div>
        ) : admins.length === 0 ? (
          <div className="p-12 text-center text-slate-400 text-sm">
            No platform administrators found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900 border-b border-slate-800 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                <tr>
                  <th className="py-3.5 px-6">User / Account</th>
                  <th className="py-3.5 px-6">Status</th>
                  <th className="py-3.5 px-6">Privileges</th>
                  <th className="py-3.5 px-6">Granted / Registered</th>
                  <th className="py-3.5 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {admins.map((user) => {
                  const isSelf = Boolean(currentUser && currentUser.id === user.id);
                  const roleInfo = getPlatformRoleInfo(user);
                  return (
                    <tr key={user.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-4 px-6">
                        <div className="flex items-center space-x-3">
                          <div className="w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 font-bold text-sm">
                            {user.display_name ? user.display_name.charAt(0).toUpperCase() : user.email.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <div className="font-bold text-white text-sm">{user.display_name || 'Administrator'}</div>
                            <div className="text-slate-400 font-mono text-[11px]">{user.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className="py-4 px-6">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide border ${
                            user.status === 'active'
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : 'bg-red-500/10 text-red-400 border-red-500/20'
                          }`}
                        >
                          {user.status}
                        </span>
                      </td>
                      <td className="py-4 px-6">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide border ${roleInfo.badgeClasses}`}
                        >
                          {roleInfo.label}
                        </span>
                      </td>
                      <td className="py-4 px-6 text-slate-400 text-[11px]">
                        {user.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}
                      </td>
                      <td className="py-4 px-6 text-right">
                        {isSelf ? (
                          <span
                            className="inline-flex items-center px-3 py-1.5 rounded-xl bg-slate-800 text-slate-500 border border-slate-700 text-xs font-semibold cursor-not-allowed select-none"
                            title="You cannot revoke your own administrator privileges"
                          >
                            Current User (Self)
                          </span>
                        ) : !isCurrentOwner ? (
                          <span
                            className="inline-flex items-center px-3 py-1.5 rounded-xl bg-slate-800/80 text-slate-500 border border-slate-700/60 text-xs font-semibold cursor-not-allowed select-none"
                            title="Privilege modifications require Platform Owner authorization"
                          >
                            Requires Owner
                          </span>
                        ) : user.is_platform_admin ? (
                          <button
                            onClick={() => handleOpenConfirmModal(user, 'revoke')}
                            className="px-3 py-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 font-semibold text-xs transition-colors"
                          >
                            Revoke Access
                          </button>
                        ) : (
                          <button
                            onClick={() => handleOpenConfirmModal(user, 'grant')}
                            className="px-3 py-1.5 rounded-xl bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-semibold text-xs transition-colors"
                          >
                            Grant Access
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      {selectedUser && actionType && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-md w-full p-6 shadow-2xl text-slate-100 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-800">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                {actionType === 'revoke' ? (
                  <>
                    <svg className="w-5 h-5 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    Confirm Privilege Revocation
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                    Confirm Privilege Grant
                  </>
                )}
              </h3>
              <button
                onClick={handleCloseModal}
                disabled={isSubmitting}
                className="text-slate-400 hover:text-white p-1 disabled:opacity-50"
              >
                ✕
              </button>
            </div>

            {actionError && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs font-medium">
                {actionError}
              </div>
            )}

            <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 space-y-2">
              <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Target User Account</div>
              <div className="font-bold text-white text-sm">{selectedUser.display_name || 'Administrator'}</div>
              <div className="text-slate-400 font-mono text-xs">{selectedUser.email}</div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              {actionType === 'revoke'
                ? "Are you sure you want to revoke platform administrator privileges from this user? They will lose access to the SaaS control plane, tenant management, and platform audit logs."
                : "Are you sure you want to grant platform administrator privileges to this user? They will gain full super-administrator control over all SaaS tenants, outlets, and platform settings."}
            </p>

            <div className="pt-3 border-t border-slate-800 flex justify-end space-x-3">
              <button
                type="button"
                onClick={handleCloseModal}
                disabled={isSubmitting}
                className="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 text-xs font-semibold hover:bg-slate-800 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmAction}
                disabled={isSubmitting}
                className={`px-4 py-2 rounded-xl text-white text-xs font-bold transition-colors disabled:opacity-50 flex items-center space-x-2 ${
                  actionType === 'revoke'
                    ? 'bg-rose-600 hover:bg-rose-700'
                    : 'bg-indigo-600 hover:bg-indigo-700'
                }`}
              >
                {isSubmitting && (
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                )}
                <span>
                  {isSubmitting
                    ? 'Processing...'
                    : actionType === 'revoke'
                    ? 'Confirm Revoke'
                    : 'Confirm Grant'}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
