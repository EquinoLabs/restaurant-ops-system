import React, { useState, useEffect, useCallback } from 'react';
import { PlatformAdminUser } from '@roms/shared-types';
import {
  fetchPlatformAdmins,
  fetchPlatformOperators,
  grantPlatformAdmin,
  revokePlatformAdmin,
  revokePlatformOperator,
  suspendPlatformUser,
  reactivatePlatformUser,
} from '@roms/api-client';
import { useAuth } from '@roms/api-client';
import { UserMe } from '@roms/shared-types';
import { AddOperatorModal } from './AddOperatorModal';
import { PlatformOwnerTransferModal } from './PlatformOwnerTransferModal';

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

  const [activeTab, setActiveTab] = useState<'admins' | 'operators'>('admins');
  const [admins, setAdmins] = useState<PlatformAdminUser[]>([]);
  const [operators, setOperators] = useState<PlatformAdminUser[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [ownerNotInitialized, setOwnerNotInitialized] = useState<boolean>(false);
  const [permissionDenied, setPermissionDenied] = useState<boolean>(false);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Modals state
  const [isAddOperatorOpen, setIsAddOperatorOpen] = useState(false);
  const [isOwnerTransferOpen, setIsOwnerTransferOpen] = useState(false);

  // Confirmation dialog state
  const [selectedUser, setSelectedUser] = useState<PlatformAdminUser | null>(null);
  const [actionType, setActionType] = useState<
    'grant' | 'revoke' | 'revoke_operator' | 'suspend' | 'reactivate' | null
  >(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadDirectory = useCallback(async () => {
    if (!token || isOperator) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      setOwnerNotInitialized(false);
      setPermissionDenied(false);

      const [adminsData, operatorsData] = await Promise.all([
        fetchPlatformAdmins(token),
        fetchPlatformOperators(token).catch(() => []),
      ]);
      setAdmins(adminsData);
      setOperators(operatorsData);
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
        setError(err.message || 'Failed to load platform directory.');
      }
    } finally {
      setLoading(false);
    }
  }, [token, isOperator]);

  useEffect(() => {
    loadDirectory();
  }, [loadDirectory]);

  const handleOpenConfirmModal = (
    user: PlatformAdminUser,
    type: 'grant' | 'revoke' | 'revoke_operator' | 'suspend' | 'reactivate'
  ) => {
    if ((type === 'revoke' || type === 'suspend') && currentUser && currentUser.id === user.id) {
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

    if ((actionType === 'revoke' || actionType === 'suspend') && currentUser && currentUser.id === selectedUser.id) {
      setActionError('Self-modification of administrative status or account suspension is prohibited.');
      return;
    }

    if (selectedUser.platform_role === 'owner' && (actionType === 'revoke' || actionType === 'suspend')) {
      setActionError('The active Platform Owner cannot be demoted or suspended. Use Owner Transfer.');
      return;
    }

    try {
      setIsSubmitting(true);
      setActionError(null);
      setActionSuccess(null);

      if (actionType === 'grant') {
        await grantPlatformAdmin(selectedUser.id, token);
        setActionSuccess(`Platform administrator privileges granted to '${selectedUser.email}'.`);
      } else if (actionType === 'revoke') {
        await revokePlatformAdmin(selectedUser.id, token);
        setActionSuccess(`Platform administrator privileges revoked from '${selectedUser.email}'.`);
      } else if (actionType === 'revoke_operator') {
        await revokePlatformOperator(selectedUser.id, token);
        setActionSuccess(`Operator privileges revoked from '${selectedUser.email}'.`);
      } else if (actionType === 'suspend') {
        await suspendPlatformUser(selectedUser.id, token);
        setActionSuccess(`User account '${selectedUser.email}' has been suspended.`);
      } else if (actionType === 'reactivate') {
        await reactivatePlatformUser(selectedUser.id, token);
        setActionSuccess(`User account '${selectedUser.email}' has been reactivated.`);
      }

      handleCloseModal();
      await loadDirectory();
    } catch (err: any) {
      setActionError(err.message || `Failed to execute ${actionType} action.`);
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

  const allEligibleCandidates = [...admins, ...operators];

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/60 border border-slate-800 p-6 rounded-2xl">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <svg className="w-6 h-6 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            Users & Governance Control Plane
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Manage SaaS super-administrators, platform operators, account suspensions, and owner transfer.
          </p>
        </div>

        <div className="flex items-center flex-wrap gap-2.5">
          {isCurrentOwner && (
            <button
              onClick={() => setIsOwnerTransferOpen(true)}
              className="px-3 py-2 rounded-xl bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/40 text-xs font-bold transition flex items-center space-x-1.5"
            >
              <svg className="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
              <span>Transfer Ownership</span>
            </button>
          )}

          <button
            onClick={() => setIsAddOperatorOpen(true)}
            className="px-3 py-2 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-bold transition flex items-center space-x-1.5"
          >
            <svg className="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            <span>Add Operator</span>
          </button>

          <button
            onClick={loadDirectory}
            disabled={loading}
            className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition flex items-center space-x-1.5 disabled:opacity-50"
          >
            <svg className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Segmented Sub-tab Navigation */}
      <div className="flex border-b border-slate-800 space-x-6 text-xs font-bold">
        <button
          onClick={() => setActiveTab('admins')}
          className={`pb-3 transition relative flex items-center space-x-2 ${
            activeTab === 'admins' ? 'text-indigo-400' : 'text-slate-400 hover:text-white'
          }`}
        >
          <span>Platform Administrators</span>
          <span className="px-1.5 py-0.2 rounded-full bg-slate-800 text-[10px]">
            {admins.length}
          </span>
          {activeTab === 'admins' && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500 rounded-full" />
          )}
        </button>

        <button
          onClick={() => setActiveTab('operators')}
          className={`pb-3 transition relative flex items-center space-x-2 ${
            activeTab === 'operators' ? 'text-amber-400' : 'text-slate-400 hover:text-white'
          }`}
        >
          <span>Platform Operators</span>
          <span className="px-1.5 py-0.2 rounded-full bg-slate-800 text-[10px]">
            {operators.length}
          </span>
          {activeTab === 'operators' && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-amber-500 rounded-full" />
          )}
        </button>
      </div>

      {/* Global Alerts */}
      {ownerNotInitialized && (
        <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-2xl text-amber-300 text-xs flex items-start justify-between gap-3 shadow-lg">
          <div>
            <div className="font-bold text-amber-200">Platform Governance Offline (Zero-Owner State)</div>
            <p className="mt-0.5 text-amber-300/90 leading-relaxed">
              Platform Owner has not been initialized. Ordinary role-governance endpoints fail closed with HTTP 503.
            </p>
          </div>
          <button onClick={() => setOwnerNotInitialized(false)} className="text-amber-400 hover:text-amber-300 font-bold p-1">✕</button>
        </div>
      )}

      {permissionDenied && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl text-rose-300 text-xs flex items-start justify-between gap-3 shadow-lg">
          <div>
            <div className="font-bold text-rose-200">Permission Denied</div>
            <p className="mt-0.5 text-rose-300/90 leading-relaxed">{error}</p>
          </div>
          <button onClick={() => setPermissionDenied(false)} className="text-rose-400 hover:text-rose-300 font-bold p-1">✕</button>
        </div>
      )}

      {actionSuccess && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-xs font-medium flex items-center justify-between">
          <span>{actionSuccess}</span>
          <button onClick={() => setActionSuccess(null)} className="text-emerald-400 hover:text-emerald-300 ml-4 font-bold">✕</button>
        </div>
      )}

      {error && !ownerNotInitialized && !permissionDenied && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs font-medium flex items-center justify-between">
          <div>
            <div className="font-bold">Error Loading Administrator Directory</div>
            <div>{error}</div>
          </div>
          <button onClick={loadDirectory} className="px-3 py-1 bg-red-500/20 hover:bg-red-500/30 text-red-300 font-semibold rounded-lg text-xs">
            Retry
          </button>
        </div>
      )}

      {/* Directory Table */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        {loading ? (
          <div className="p-12 text-center text-slate-400 text-sm flex flex-col items-center space-y-3">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
            <span>{activeTab === 'admins' ? 'Loading platform administrator directory...' : 'Loading platform operator directory...'}</span>
          </div>
        ) : (activeTab === 'admins' ? admins : operators).length === 0 ? (
          <div className="p-12 text-center text-slate-400 text-sm">
            No platform {activeTab === 'admins' ? 'administrators' : 'operators'} found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900 border-b border-slate-800 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                <tr>
                  <th className="py-3.5 px-6">User / Account</th>
                  <th className="py-3.5 px-6">Account Status</th>
                  <th className="py-3.5 px-6">Privileges</th>
                  <th className="py-3.5 px-6">Created</th>
                  <th className="py-3.5 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {(activeTab === 'admins' ? admins : operators).map((user) => {
                  const isSelf = Boolean(currentUser && currentUser.id === user.id);
                  const isOwner = user.platform_role === 'owner';
                  const roleInfo = getPlatformRoleInfo(user);

                  return (
                    <tr key={user.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-4 px-6">
                        <div className="flex items-center space-x-3">
                          <div className={`w-9 h-9 rounded-xl border flex items-center justify-center font-bold text-sm ${
                            roleInfo.badgeClasses
                          }`}>
                            {user.display_name ? user.display_name.charAt(0).toUpperCase() : user.email.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <div className="font-bold text-white text-sm">{user.display_name || 'Staff User'}</div>
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
                        <div className="flex items-center justify-end space-x-2">
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
                          ) : isOwner ? (
                            <span className="px-2.5 py-1 rounded-lg bg-purple-500/10 text-purple-300 border border-purple-500/20 text-[11px] font-semibold">
                              Platform Owner
                            </span>
                          ) : (
                            <>
                              {/* Suspension Toggle Button */}
                              {user.status === 'active' ? (
                                <button
                                  onClick={() => handleOpenConfirmModal(user, 'suspend')}
                                  className="px-2.5 py-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-xs font-semibold transition"
                                  title="Suspend account access"
                                >
                                  Suspend
                                </button>
                              ) : (
                                <button
                                  onClick={() => handleOpenConfirmModal(user, 'reactivate')}
                                  className="px-2.5 py-1.5 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-semibold transition"
                                  title="Reactivate suspended account"
                                >
                                  Reactivate
                                </button>
                              )}

                              {/* Role Modification Button */}
                              {activeTab === 'admins' ? (
                                user.is_platform_admin ? (
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
                                )
                              ) : (
                                <button
                                  onClick={() => handleOpenConfirmModal(user, 'revoke_operator')}
                                  className="px-3 py-1.5 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold text-xs transition-colors"
                                >
                                  Revoke Operator
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Confirmation Dialog */}
      {selectedUser && actionType && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-md w-full p-6 shadow-2xl text-slate-100 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-800">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                {actionType === 'revoke' && 'Confirm Privilege Revocation'}
                {actionType === 'grant' && 'Confirm Privilege Grant'}
                {actionType === 'suspend' && 'Confirm Account Suspension'}
                {actionType === 'reactivate' && 'Confirm Account Reactivation'}
                {actionType === 'revoke_operator' && 'Confirm Operator Revocation'}
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

            <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 space-y-1">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Target Account</div>
              <div className="font-bold text-white text-sm">{selectedUser.display_name}</div>
              <div className="text-slate-400 font-mono text-xs">{selectedUser.email}</div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              {actionType === 'revoke' && (
                'Are you sure you want to revoke platform administrator privileges from this user? They will lose access to the SaaS control plane, tenant management, and platform audit logs.'
              )}
              {actionType === 'grant' && (
                'Are you sure you want to grant platform administrator privileges to this user? They will gain full super-administrator control over all SaaS tenants, outlets, and platform settings.'
              )}
              {actionType === 'suspend' && (
                'Suspending this account will immediately revoke all portal and operational access for this user.'
              )}
              {actionType === 'reactivate' && (
                'Reactivating this account will restore standard login and permitted platform capabilities.'
              )}
              {actionType === 'revoke_operator' && (
                'Revoking platform operator privileges removes their access to the internal operations console.'
              )}
            </p>

            <div className="pt-3 border-t border-slate-800 flex justify-end space-x-3">
              <button
                type="button"
                onClick={handleCloseModal}
                disabled={isSubmitting}
                className="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 text-xs font-semibold hover:bg-slate-800 transition disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmAction}
                disabled={isSubmitting}
                className={`px-4 py-2 rounded-xl text-white text-xs font-bold transition flex items-center space-x-2 ${
                  actionType === 'suspend' || actionType === 'revoke' || actionType === 'revoke_operator'
                    ? 'bg-rose-600 hover:bg-rose-500'
                    : 'bg-indigo-600 hover:bg-indigo-500'
                }`}
              >
                {isSubmitting && (
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                )}
                <span>
                  {isSubmitting
                    ? 'Processing...'
                    : actionType === 'revoke' || actionType === 'revoke_operator'
                    ? 'Confirm Revoke'
                    : actionType === 'grant'
                    ? 'Confirm Grant'
                    : actionType === 'suspend'
                    ? 'Confirm Suspend'
                    : 'Confirm Reactivate'}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Operator Modal */}
      <AddOperatorModal
        isOpen={isAddOperatorOpen}
        onClose={() => setIsAddOperatorOpen(false)}
        onSuccess={() => {
          setActionSuccess('Operator successfully provisioned.');
          loadDirectory();
        }}
        token={token}
      />

      {/* Platform Owner Transfer Modal */}
      <PlatformOwnerTransferModal
        isOpen={isOwnerTransferOpen}
        onClose={() => setIsOwnerTransferOpen(false)}
        onSuccess={() => {
          setActionSuccess('Platform Ownership successfully transferred.');
          loadDirectory();
        }}
        token={token}
        candidates={allEligibleCandidates}
      />
    </div>
  );
};
