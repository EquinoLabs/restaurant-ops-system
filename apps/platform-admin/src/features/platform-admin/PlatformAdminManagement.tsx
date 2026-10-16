import React, { useState, useEffect, useCallback } from 'react';
import { PlatformAdminUser, UserMe } from '@roms/shared-types';
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
import {
  ArrowLeftRight,
  Loader2,
  Plus,
  RefreshCw,
  ShieldAlert,
  X,
} from 'lucide-react';
import {
  Button,
  DataTable,
  RoleBadge,
  StatusBadge,
  type DataTableColumn,
} from '../../components/ops-ui';
import { AddOperatorModal } from './AddOperatorModal';
import { PlatformOwnerTransferModal } from './PlatformOwnerTransferModal';
import { formatCreatedAt } from './BusinessDirectory';

interface PlatformAdminManagementProps {
  token: string | null;
}

export function getPlatformRoleInfo(user: PlatformAdminUser): { label: string; badgeClasses: string } {
  const normalizedRole = user.platform_role?.trim().toLowerCase();
  if (normalizedRole === 'owner') {
    return {
      label: 'Platform Owner',
      badgeClasses: 'bg-ops-status-neutral-bg text-ops-status-neutral-text',
    };
  }
  if (normalizedRole === 'admin') {
    return {
      label: 'Platform Admin',
      badgeClasses: 'bg-ops-status-neutral-bg text-ops-status-neutral-text',
    };
  }
  if (normalizedRole === 'operator') {
    return {
      label: 'Platform Operator',
      badgeClasses: 'bg-ops-status-neutral-bg text-ops-status-neutral-text',
    };
  }
  if ((user.platform_role === null || user.platform_role === undefined) && user.is_platform_admin) {
    return {
      label: 'Platform Admin (Legacy)',
      badgeClasses: 'bg-ops-status-neutral-bg text-ops-status-neutral-text',
    };
  }
  return {
    label: 'Standard User',
    badgeClasses: 'bg-ops-status-neutral-bg text-ops-status-neutral-text',
  };
}

const rowActionButtonClasses = (tone: 'error' | 'accent' | 'neutral') =>
  `rounded px-2 py-1 text-xs font-medium transition-colors ${
    tone === 'error'
      ? 'text-ops-error hover:bg-ops-status-critical-bg'
      : tone === 'accent'
      ? 'text-ops-accent hover:bg-ops-canvas'
      : 'text-ops-text-secondary hover:bg-ops-canvas'
  }`;

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
      <div className="mx-auto my-8 max-w-xl rounded-md border border-ops-border bg-white p-8 text-center">
        <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-ops-canvas">
          <ShieldAlert className="h-5 w-5 text-ops-text-secondary" aria-hidden="true" />
        </div>
        <h3 className="text-base font-semibold text-ops-text-primary">
          Access Restricted: Platform Operator
        </h3>
        <p className="mt-2 text-sm leading-relaxed text-ops-text-secondary">
          Platform Operators do not have administrative directory access. Access to the platform
          team management directory is restricted to Platform Owners and Platform Admins.
        </p>
      </div>
    );
  }

  const allEligibleCandidates = [...admins, ...operators];
  const activeList = activeTab === 'admins' ? admins : operators;

  const columns: DataTableColumn<PlatformAdminUser>[] = [
    {
      key: 'name',
      header: 'Name',
      width: 'w-56',
      render: (user) => (
        <span className="whitespace-nowrap font-medium text-ops-text-primary">
          {user.display_name || 'Staff User'}
        </span>
      ),
    },
    {
      key: 'email',
      header: 'Email',
      width: 'w-64',
      render: (user) => (
        <span className="whitespace-nowrap text-ops-text-secondary">{user.email}</span>
      ),
    },
    {
      key: 'role',
      header: 'Role',
      width: 'w-52',
      render: (user) => <RoleBadge label={getPlatformRoleInfo(user).label} />,
    },
    {
      key: 'status',
      header: 'Status',
      width: 'w-28',
      render: (user) =>
        user.status === 'active' ? (
          <StatusBadge tone="active" label="Active" />
        ) : user.status === 'suspended' ? (
          <StatusBadge tone="critical" label="Suspended" />
        ) : (
          <StatusBadge tone="neutral" label={user.status} />
        ),
    },
    {
      key: 'created',
      header: 'Created',
      width: 'w-32',
      render: (user) => (
        <span className="text-ops-text-secondary">
          {user.created_at ? formatCreatedAt(user.created_at) : 'N/A'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      render: (user) => {
        const isSelf = Boolean(currentUser && currentUser.id === user.id);
        const isOwner = user.platform_role === 'owner';

        if (isSelf) {
          return (
            <span
              className="inline-flex h-6 cursor-not-allowed select-none items-center rounded border border-ops-border bg-ops-canvas px-2 text-xs text-ops-text-secondary"
              title="You cannot revoke your own administrator privileges"
            >
              Current User (Self)
            </span>
          );
        }
        if (!isCurrentOwner) {
          return (
            <span
              className="inline-flex h-6 cursor-not-allowed select-none items-center rounded border border-ops-border bg-ops-canvas px-2 text-xs text-ops-text-secondary"
              title="Privilege modifications require Platform Owner authorization"
            >
              Requires Owner
            </span>
          );
        }
        if (isOwner) {
          return (
            <span className="text-xs italic text-ops-text-secondary">Platform Owner</span>
          );
        }
        return (
          <div className="flex items-center justify-end gap-1">
            {user.status === 'active' ? (
              <button
                type="button"
                onClick={() => handleOpenConfirmModal(user, 'suspend')}
                className={rowActionButtonClasses('error')}
                title="Suspend account access"
              >
                Suspend
              </button>
            ) : (
              <button
                type="button"
                onClick={() => handleOpenConfirmModal(user, 'reactivate')}
                className={rowActionButtonClasses('neutral')}
                title="Reactivate suspended account"
              >
                Reactivate
              </button>
            )}

            {activeTab === 'admins' ? (
              user.is_platform_admin ? (
                <button
                  type="button"
                  onClick={() => handleOpenConfirmModal(user, 'revoke')}
                  className={rowActionButtonClasses('error')}
                >
                  Revoke Access
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => handleOpenConfirmModal(user, 'grant')}
                  className={rowActionButtonClasses('accent')}
                >
                  Grant Access
                </button>
              )
            ) : (
              <button
                type="button"
                onClick={() => handleOpenConfirmModal(user, 'revoke_operator')}
                className={rowActionButtonClasses('error')}
              >
                Revoke Operator
              </button>
            )}
          </div>
        );
      },
    },
  ];

  const confirmTitles: Record<string, string> = {
    revoke: 'Confirm Privilege Revocation',
    grant: 'Confirm Privilege Grant',
    suspend: 'Confirm Account Suspension',
    reactivate: 'Confirm Account Reactivation',
    revoke_operator: 'Confirm Operator Revocation',
  };

  const confirmConsequences: Record<string, string> = {
    revoke:
      'Are you sure you want to revoke platform administrator privileges from this user? They will lose access to the SaaS control plane, tenant management, and platform audit logs.',
    grant:
      'Are you sure you want to grant platform administrator privileges to this user? They will gain full super-administrator control over all SaaS tenants, outlets, and platform settings.',
    suspend:
      'Suspending this account will immediately revoke all portal and operational access for this user.',
    reactivate:
      'Reactivating this account will restore standard login and permitted platform capabilities.',
    revoke_operator:
      'Revoking platform operator privileges removes their access to the internal operations console.',
  };

  const confirmLabels: Record<string, string> = {
    revoke: 'Confirm Revoke',
    revoke_operator: 'Confirm Revoke',
    grant: 'Confirm Grant',
    suspend: 'Confirm Suspend',
    reactivate: 'Confirm Reactivate',
  };

  return (
    <div>
      {/* Page header */}
      <div className="mb-4 flex flex-col gap-3 border-b border-ops-border pb-4 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold leading-7 tracking-tight text-ops-text-primary">
            Team
          </h1>
          <p className="text-sm leading-5 text-ops-text-secondary">
            People with access to the platform control plane.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isCurrentOwner && (
            <Button variant="secondary" onClick={() => setIsOwnerTransferOpen(true)}>
              <ArrowLeftRight className="h-3.5 w-3.5" aria-hidden="true" />
              Transfer ownership
            </Button>
          )}
          <Button variant="primary" onClick={() => setIsAddOperatorOpen(true)}>
            <Plus className="h-3.5 w-3.5" aria-hidden="true" />
            Add operator
          </Button>
          <Button variant="ghost" onClick={loadDirectory} disabled={loading}>
            <RefreshCw
              className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`}
              aria-hidden="true"
            />
            Refresh
          </Button>
        </div>
      </div>

      {/* Segmented sub-tab navigation */}
      <div className="mb-4 flex gap-6 border-b border-ops-border text-xs font-semibold">
        <button
          type="button"
          onClick={() => setActiveTab('admins')}
          className={`relative -mb-px flex items-center gap-2 pb-3 transition-colors ${
            activeTab === 'admins'
              ? 'text-ops-accent'
              : 'text-ops-text-secondary hover:text-ops-text-primary'
          }`}
        >
          <span>Platform Administrators</span>
          <span className="rounded bg-ops-canvas px-1.5 py-0.5 text-[10px] font-medium text-ops-text-secondary">
            {admins.length}
          </span>
          {activeTab === 'admins' && (
            <span className="absolute inset-x-0 -bottom-px h-0.5 bg-ops-accent" aria-hidden="true" />
          )}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('operators')}
          className={`relative -mb-px flex items-center gap-2 pb-3 transition-colors ${
            activeTab === 'operators'
              ? 'text-ops-accent'
              : 'text-ops-text-secondary hover:text-ops-text-primary'
          }`}
        >
          <span>Platform Operators</span>
          <span className="rounded bg-ops-canvas px-1.5 py-0.5 text-[10px] font-medium text-ops-text-secondary">
            {operators.length}
          </span>
          {activeTab === 'operators' && (
            <span className="absolute inset-x-0 -bottom-px h-0.5 bg-ops-accent" aria-hidden="true" />
          )}
        </button>
      </div>

      {/* Global alerts */}
      {ownerNotInitialized && (
        <div
          role="status"
          className="mb-4 flex items-start justify-between gap-3 rounded-md border border-ops-border bg-ops-status-pending-bg p-4 text-xs text-ops-status-pending-text"
        >
          <div>
            <div className="font-semibold">Platform Governance Offline (Zero-Owner State)</div>
            <p className="mt-0.5 leading-relaxed">
              Platform Owner has not been initialized. Ordinary role-governance endpoints fail
              closed with HTTP 503.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setOwnerNotInitialized(false)}
            aria-label="Dismiss"
            className="rounded p-1 text-ops-status-pending-text hover:bg-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {permissionDenied && (
        <div
          role="alert"
          className="mb-4 flex items-start justify-between gap-3 rounded-md border border-ops-border bg-ops-status-critical-bg p-4 text-xs text-ops-status-critical-text"
        >
          <div>
            <div className="font-semibold">Permission Denied</div>
            <p className="mt-0.5 leading-relaxed">{error}</p>
          </div>
          <button
            type="button"
            onClick={() => setPermissionDenied(false)}
            aria-label="Dismiss"
            className="rounded p-1 text-ops-status-critical-text hover:bg-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {actionSuccess && (
        <div
          role="status"
          className="mb-4 flex items-center justify-between gap-3 rounded-md border border-ops-border bg-ops-status-active-bg p-4 text-xs text-ops-status-active-text"
        >
          <span>{actionSuccess}</span>
          <button
            type="button"
            onClick={() => setActionSuccess(null)}
            aria-label="Dismiss"
            className="rounded p-1 text-ops-status-active-text hover:bg-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {error && !ownerNotInitialized && !permissionDenied && (
        <div
          role="alert"
          className="mb-4 flex items-center justify-between gap-3 rounded-md border border-ops-border bg-ops-status-critical-bg p-4 text-xs text-ops-status-critical-text"
        >
          <div>
            <div className="font-semibold">Error Loading Administrator Directory</div>
            <div>{error}</div>
          </div>
          <Button variant="secondary" onClick={loadDirectory}>
            Retry
          </Button>
        </div>
      )}

      {/* Directory table */}
      <div className="overflow-hidden rounded-md border border-ops-border bg-white">
        {loading ? (
          <div className="py-12 text-center text-sm text-ops-text-secondary">
            {activeTab === 'admins'
              ? 'Loading platform administrator directory...'
              : 'Loading platform operator directory...'}
          </div>
        ) : activeList.length === 0 ? (
          <div className="py-12 text-center text-sm text-ops-text-secondary">
            No platform {activeTab === 'admins' ? 'administrators' : 'operators'} found.
          </div>
        ) : (
          <DataTable
            columns={columns}
            rows={activeList}
            rowKey={(user) => user.id}
            minWidth="900px"
            footer={
              <span>
                Showing {activeList.length} of {activeList.length}{' '}
                {activeTab === 'admins' ? 'team members' : 'platform operators'}
              </span>
            }
          />
        )}
      </div>

      {/* Confirmation dialog */}
      {selectedUser && actionType && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-[rgba(31,41,51,0.40)]"
            aria-hidden="true"
            onClick={handleCloseModal}
          />
          <div
            role="dialog"
            aria-modal="true"
            className="relative w-full max-w-md overflow-hidden rounded-md border border-ops-border bg-white shadow-ops-l2"
          >
            <div className="flex items-center justify-between border-b border-ops-border p-5">
              <h3 className="text-base font-semibold text-ops-text-primary">
                {actionType && confirmTitles[actionType]}
              </h3>
              <button
                type="button"
                onClick={handleCloseModal}
                disabled={isSubmitting}
                aria-label="Close"
                className="rounded p-1 text-ops-text-secondary transition-colors hover:bg-ops-canvas hover:text-ops-text-primary disabled:opacity-50"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-4 p-5">
              {actionError && (
                <div
                  role="alert"
                  className="rounded-md border border-ops-border bg-ops-status-critical-bg p-3 text-xs text-ops-status-critical-text"
                >
                  {actionError}
                </div>
              )}

              <div className="rounded-md border border-ops-border bg-ops-canvas p-4">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-ops-text-secondary">
                  Target Account
                </div>
                <div className="mt-1 text-sm font-medium text-ops-text-primary">
                  {selectedUser.display_name}
                </div>
                <div className="font-mono text-xs text-ops-text-secondary">
                  {selectedUser.email}
                </div>
              </div>

              <p className="text-[13px] leading-5 text-ops-text-secondary">
                {actionType && confirmConsequences[actionType]}
              </p>
            </div>

            <div className="flex justify-end gap-2 border-t border-ops-border p-4">
              <Button variant="secondary" onClick={handleCloseModal} disabled={isSubmitting}>
                Cancel
              </Button>
              <Button
                type="button"
                variant={
                  actionType === 'suspend' || actionType === 'revoke' || actionType === 'revoke_operator'
                    ? 'destructive'
                    : 'primary'
                }
                onClick={handleConfirmAction}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                    <span>Processing...</span>
                  </>
                ) : (
                  <span>{actionType && confirmLabels[actionType]}</span>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Add Operator drawer */}
      <AddOperatorModal
        isOpen={isAddOperatorOpen}
        onClose={() => setIsAddOperatorOpen(false)}
        onSuccess={() => {
          setActionSuccess('Operator successfully provisioned.');
          loadDirectory();
        }}
        token={token}
      />

      {/* Platform Owner Transfer modal */}
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
