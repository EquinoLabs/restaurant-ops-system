import React, { useState } from 'react';
import { PlatformAdminUser } from '@roms/shared-types';
import { transferPlatformOwner } from '@roms/api-client';

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
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const eligibleCandidates = candidates.filter(
    (c) => c.platform_role !== 'owner' && c.status === 'active'
  );

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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-red-500/30 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-5">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 flex items-center justify-center font-bold">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Transfer Platform Ownership</h3>
              <p className="text-xs text-slate-400">Sole Root Authority Transfer Workflow</p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="text-slate-400 hover:text-white transition p-1 rounded-lg"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Warning Banner */}
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs space-y-2">
          <div className="font-bold flex items-center space-x-2 text-red-200">
            <svg className="w-4 h-4 text-red-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>Irreversible Governance Action</span>
          </div>
          <p>
            This operation atomically reassigns the sole <strong>Platform Owner</strong> role to the selected user.
            Upon confirmation, your personal account will be demoted to <strong>Platform Admin</strong>.
            This action is immutably recorded in the platform audit trail.
          </p>
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Select Successor Candidate
            </label>
            {eligibleCandidates.length === 0 ? (
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl text-xs text-amber-400">
                No active eligible candidates found in the directory. You must first create or invite an active Platform Admin or Operator.
              </div>
            ) : (
              <select
                required
                value={targetUserId}
                onChange={(e) => setTargetUserId(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white text-xs focus:outline-none focus:border-red-500"
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

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Re-enter Current Platform Owner Password
            </label>
            <input
              type="password"
              required
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Your current account password"
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-red-500"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Backend cryptographic re-authentication is mandatory before root privileges can be ceded.
            </p>
          </div>

          <div className="flex items-center justify-end space-x-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || eligibleCandidates.length === 0}
              className="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-bold transition flex items-center space-x-2 shadow-lg shadow-red-600/30 disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Transferring Authority...</span>
                </>
              ) : (
                <span>Confirm & Relinquish Ownership</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
