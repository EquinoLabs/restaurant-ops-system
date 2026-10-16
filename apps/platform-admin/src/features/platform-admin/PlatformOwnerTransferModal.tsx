import React, { useState } from 'react';
import { PlatformAdminUser, UserMe } from '@roms/shared-types';
import { transferPlatformOwner, useAuth } from '@roms/api-client';
import { AlertTriangle, Eye, EyeOff, Info, Loader2, X } from 'lucide-react';
import { Button } from '../../components/ops-ui';

interface PlatformOwnerTransferModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  token: string | null;
  candidates: PlatformAdminUser[];
}

export const PlatformOwnerTransferModal: React.FC<PlatformOwnerTransferModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  token,
  candidates,
}) => {
  const [targetUserId, setTargetUserId] = useState<string>('');
  const [currentPassword, setCurrentPassword] = useState<string>('');
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  let currentUser: UserMe | null = null;
  try {
    const auth = useAuth();
    currentUser = auth.user;
  } catch {
    currentUser = null;
  }

  if (!isOpen) return null;

  const eligibleCandidates = candidates.filter(
    (c) => c.platform_role !== 'owner' && c.status === 'active'
  );

  const successor = eligibleCandidates.find((c) => c.id === targetUserId);
  const successorName = successor ? successor.display_name : 'The selected team member';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    if (!targetUserId) {
      setError('Please select an active platform user to receive the Platform Owner role.');
      return;
    }
    if (!currentPassword) {
      setError('Please enter your current Platform Owner password to confirm this transfer.');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await transferPlatformOwner(
        {
          target_user_id: targetUserId,
          current_password: currentPassword,
        },
        token
      );
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Platform owner transfer failed. Please verify credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-[rgba(31,41,51,0.40)]"
        aria-hidden="true"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="transfer-owner-title"
        className="relative w-full max-w-lg overflow-hidden rounded-md border border-ops-border bg-white shadow-ops-l2"
      >
        <div className="flex items-start justify-between border-b border-ops-border p-5">
          <div>
            <h2
              id="transfer-owner-title"
              className="text-base font-semibold leading-6 text-ops-text-primary"
            >
              Transfer Platform Ownership
            </h2>
            <p className="mt-0.5 text-xs leading-4 text-ops-text-secondary">
              Sole Root Authority Transfer Workflow
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close"
            className="ml-3 rounded p-1 text-ops-text-secondary transition-colors hover:bg-ops-canvas hover:text-ops-text-primary disabled:opacity-50"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          {/* Irreversibility warning */}
          <div className="rounded-md border border-ops-border bg-ops-status-critical-bg p-4 text-xs leading-5 text-ops-status-critical-text">
            <div className="mb-1 flex items-center gap-2 font-semibold">
              <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span>Irreversible Governance Action</span>
            </div>
            <p>
              This operation atomically reassigns the sole <strong>Platform Owner</strong> role
              to the selected user. Upon confirmation, your personal account will be demoted to{' '}
              <strong>Platform Admin</strong>. This action is immutably recorded in the platform
              audit trail.
            </p>
          </div>

          {/* What will change */}
          <div className="rounded-md border border-ops-border bg-ops-canvas p-4">
            <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-ops-text-primary">
              <Info className="h-4 w-4 shrink-0 text-ops-text-secondary" aria-hidden="true" />
              <span>What will change</span>
            </div>
            <ul className="flex list-disc flex-col gap-1.5 pl-5 text-xs leading-5 text-ops-text-secondary marker:text-ops-text-secondary">
              <li>
                {successorName} will become the Platform Owner with full platform authority.
              </li>
              <li>You will be re-assigned to the Admin role.</li>
              <li>
                You will immediately lose Owner-only permissions, including subsequent ownership
                transfers.
              </li>
            </ul>
          </div>

          {currentUser && (
            <div className="rounded-md border border-ops-border bg-white p-3">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-ops-text-secondary">
                Current owner
              </div>
              <div className="mt-1.5 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-ops-text-primary">
                    {currentUser.display_name}
                  </div>
                  <div className="truncate font-mono text-xs text-ops-text-secondary">
                    {currentUser.email}
                  </div>
                </div>
                <span className="shrink-0 rounded bg-ops-status-neutral-bg px-1.5 py-0.5 text-[11px] font-medium text-ops-text-secondary">
                  Owner
                </span>
              </div>
            </div>
          )}

          {error && (
            <div
              role="alert"
              className="rounded-md border border-ops-border bg-ops-status-critical-bg p-3 text-xs text-ops-status-critical-text"
            >
              {error}
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="transfer-successor-select"
              className="text-xs font-semibold text-ops-text-secondary"
            >
              Select Successor Candidate
            </label>
            {eligibleCandidates.length === 0 ? (
              <div className="rounded-md border border-ops-border bg-ops-canvas p-3 text-xs text-ops-status-pending-text">
                No active eligible candidates found in the directory. You must first create or
                invite an active Platform Admin or Operator.
              </div>
            ) : (
              <select
                id="transfer-successor-select"
                required
                value={targetUserId}
                onChange={(e) => setTargetUserId(e.target.value)}
                className="h-8 w-full rounded-md border border-ops-border bg-white px-2.5 text-[13px] text-ops-text-primary focus:border-ops-accent focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
              >
                <option value="">-- Choose active successor candidate --</option>
                {eligibleCandidates.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.display_name} ({c.email}) — Role: {c.platform_role || 'Admin'}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="transfer-password"
              className="text-xs font-semibold text-ops-text-secondary"
            >
              Re-enter Current Platform Owner Password
            </label>
            <div className="relative">
              <input
                id="transfer-password"
                type={showPassword ? 'text' : 'password'}
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Your current account password"
                className="h-8 w-full rounded-md border border-ops-border bg-white px-2.5 pr-9 text-[13px] text-ops-text-primary placeholder:text-ops-text-disabled focus:border-ops-accent focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label="Toggle password visibility"
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-ops-text-secondary hover:text-ops-text-primary"
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Eye className="h-4 w-4" aria-hidden="true" />
                )}
              </button>
            </div>
            <p className="text-[11px] leading-4 text-ops-text-secondary">
              Backend cryptographic re-authentication is mandatory before root privileges can be
              ceded.
            </p>
          </div>

          <div className="flex items-center justify-end gap-2 border-t border-ops-border pt-4">
            <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="destructive"
              disabled={isSubmitting || eligibleCandidates.length === 0}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  <span>Transferring Authority...</span>
                </>
              ) : (
                <span>Confirm &amp; Relinquish Ownership</span>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
