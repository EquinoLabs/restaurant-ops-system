import React, { useState, useEffect } from 'react';
import { PlatformBusiness, PlatformSubscriptionUpdatePayload } from '../../types/platform';
import { updatePlatformSubscription } from '../../api/client';

export interface SubscriptionEditModalProps {
  business: PlatformBusiness | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (updated: PlatformBusiness) => void;
  token: string | null;
}

export const SubscriptionEditModal: React.FC<SubscriptionEditModalProps> = ({
  business,
  isOpen,
  onClose,
  onSuccess,
  token,
}) => {
  const [subscriptionStatus, setSubscriptionStatus] = useState<string>('trial');
  const [status, setStatus] = useState<string>('active');
  const [planName, setPlanName] = useState<string>('');
  const [maxOutlets, setMaxOutlets] = useState<string>('');
  const [trialEndsAt, setTrialEndsAt] = useState<string>('');

  const [isConfirming, setIsConfirming] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Pre-populate fields when business changes or modal opens
  useEffect(() => {
    if (business && isOpen) {
      setSubscriptionStatus(business.subscription_status || 'trial');
      setStatus(business.status || 'active');
      setPlanName(business.plan_name || '');
      setMaxOutlets(
        business.max_outlets !== null && business.max_outlets !== undefined
          ? String(business.max_outlets)
          : ''
      );
      if (business.trial_ends_at) {
        try {
          const isoDate = new Date(business.trial_ends_at).toISOString().split('T')[0];
          setTrialEndsAt(isoDate);
        } catch {
          setTrialEndsAt('');
        }
      } else {
        setTrialEndsAt('');
      }
      setIsConfirming(false);
      setError(null);
    }
  }, [business, isOpen]);

  if (!isOpen || !business) return null;

  const handleNextOrSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    const parsedMaxOutlets = maxOutlets.trim() ? parseInt(maxOutlets.trim(), 10) : null;
    if (parsedMaxOutlets !== null && (isNaN(parsedMaxOutlets) || parsedMaxOutlets < 1)) {
      setError('Max outlets limit must be a positive integer (>= 1) or left blank for unlimited.');
      return;
    }

    if (trialEndsAt.trim() && isNaN(new Date(trialEndsAt.trim()).getTime())) {
      setError('Invalid trial expiration date format.');
      return;
    }

    if (!isConfirming) {
      setIsConfirming(true);
      return;
    }

    // Perform actual API submission
    executeSubscriptionUpdate(parsedMaxOutlets);
  };

  const executeSubscriptionUpdate = async (parsedMaxOutlets: number | null) => {
    if (!token || !business) return;

    const formattedTrialDate = trialEndsAt.trim()
      ? new Date(trialEndsAt.trim()).toISOString()
      : null;

    const payload: PlatformSubscriptionUpdatePayload = {
      subscription_status: subscriptionStatus,
      status: status,
      plan_name: planName.trim() || null,
      max_outlets: parsedMaxOutlets,
      trial_ends_at: formattedTrialDate,
    };

    try {
      setIsSubmitting(true);
      setError(null);
      const updated = await updatePlatformSubscription(business.id, payload, token);
      setIsConfirming(false);
      onSuccess(updated);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to update subscription settings.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl text-slate-100 overflow-hidden">
        {/* Modal Header */}
        <div className="flex justify-between items-center pb-4 border-b border-slate-800">
          <div>
            <h3 className="text-lg font-black text-white tracking-tight">
              {isConfirming ? 'Confirm Subscription Update' : 'Manage Subscription & Status'}
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">{business.name}</p>
          </div>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 disabled:opacity-50"
            aria-label="Close Subscription Modal"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="mt-4 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-medium flex items-start space-x-2">
            <svg className="w-4 h-4 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{error}</span>
          </div>
        )}

        {isConfirming ? (
          /* Confirmation Step Diff View */
          <div className="mt-4 space-y-4">
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3 text-xs">
              <p className="text-slate-300 font-semibold mb-2">
                Please review the proposed subscription changes before applying:
              </p>

              <div className="flex items-center justify-between py-1.5 border-b border-slate-800/80">
                <span className="text-slate-400">Subscription Status:</span>
                <div className="flex items-center space-x-2">
                  <span className="text-slate-500 uppercase">{business.subscription_status}</span>
                  <span className="text-slate-600">➔</span>
                  <span className="font-bold text-indigo-400 uppercase">{subscriptionStatus}</span>
                </div>
              </div>

              <div className="flex items-center justify-between py-1.5 border-b border-slate-800/80">
                <span className="text-slate-400">Operational Status:</span>
                <div className="flex items-center space-x-2">
                  <span className="text-slate-500 uppercase">{business.status}</span>
                  <span className="text-slate-600">➔</span>
                  <span className="font-bold text-emerald-400 uppercase">{status}</span>
                </div>
              </div>

              <div className="flex items-center justify-between py-1.5 border-b border-slate-800/80">
                <span className="text-slate-400">Plan Tier:</span>
                <div className="flex items-center space-x-2">
                  <span className="text-slate-500">{business.plan_name || 'None'}</span>
                  <span className="text-slate-600">➔</span>
                  <span className="font-bold text-white">{planName.trim() || 'None'}</span>
                </div>
              </div>

              <div className="flex items-center justify-between py-1.5 border-b border-slate-800/80">
                <span className="text-slate-400">Max Outlets:</span>
                <div className="flex items-center space-x-2">
                  <span className="text-slate-500">{business.max_outlets ?? '∞'}</span>
                  <span className="text-slate-600">➔</span>
                  <span className="font-bold text-white">{maxOutlets.trim() ? maxOutlets.trim() : '∞'}</span>
                </div>
              </div>

              <div className="flex items-center justify-between py-1.5">
                <span className="text-slate-400">Trial Expiration:</span>
                <div className="flex items-center space-x-2">
                  <span className="text-slate-500">
                    {business.trial_ends_at ? new Date(business.trial_ends_at).toLocaleDateString() : 'None'}
                  </span>
                  <span className="text-slate-600">➔</span>
                  <span className="font-bold text-amber-400">
                    {trialEndsAt.trim() ? new Date(trialEndsAt.trim()).toLocaleDateString() : 'None'}
                  </span>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-800 flex items-center justify-end space-x-3">
              <button
                type="button"
                disabled={isSubmitting}
                onClick={() => setIsConfirming(false)}
                className="px-4 py-2.5 rounded-xl border border-slate-700 text-slate-300 text-xs font-semibold hover:bg-slate-800 transition-colors disabled:opacity-50"
              >
                Back to Edit
              </button>
              <button
                type="button"
                disabled={isSubmitting}
                onClick={() => executeSubscriptionUpdate(maxOutlets.trim() ? parseInt(maxOutlets.trim(), 10) : null)}
                className="px-4 py-2.5 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold transition-all shadow-lg shadow-indigo-500/20 disabled:opacity-50 flex items-center space-x-2"
              >
                {isSubmitting ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    <span>Applying Changes...</span>
                  </>
                ) : (
                  <span>Confirm & Apply Changes</span>
                )}
              </button>
            </div>
          </div>
        ) : (
          /* Form Controls View */
          <form onSubmit={handleNextOrSubmit} className="mt-4 space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-300">
                Subscription Status *
              </label>
              <select
                value={subscriptionStatus}
                onChange={(e) => setSubscriptionStatus(e.target.value)}
                className="mt-1.5 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="trial">Trial (Evaluation Period)</option>
                <option value="active">Active (Paid Subscription)</option>
                <option value="past_due">Past Due (Payment Overdue)</option>
                <option value="cancelled">Cancelled (Terminated Subscription)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-300">
                Account Operational Status *
              </label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="mt-1.5 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="active">Active (Operational Access Allowed)</option>
                <option value="suspended">Suspended (Access Restricted)</option>
              </select>
              <p className="text-[10px] text-slate-500 mt-1">
                Note: Operational status controls whether staff & APIs can execute orders.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-300">
                Plan Tier Name
              </label>
              <select
                value={planName}
                onChange={(e) => setPlanName(e.target.value)}
                className="mt-1.5 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">No Plan Tier Set</option>
                <option value="starter">Starter Plan</option>
                <option value="growth">Growth Plan</option>
                <option value="pro">Pro Plan</option>
                <option value="enterprise">Enterprise Plan</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-300">
                Max Allowed Outlets (Leave empty for unlimited)
              </label>
              <input
                type="number"
                min="1"
                value={maxOutlets}
                onChange={(e) => setMaxOutlets(e.target.value)}
                placeholder="e.g. 3 (blank = unlimited)"
                className="mt-1.5 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-300">
                Trial Expiration Date (Optional)
              </label>
              <input
                type="date"
                value={trialEndsAt}
                onChange={(e) => setTrialEndsAt(e.target.value)}
                className="mt-1.5 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="pt-4 border-t border-slate-800 flex items-center justify-end space-x-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 text-xs font-semibold hover:bg-slate-800 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold transition-all shadow-lg shadow-indigo-500/20"
              >
                Review Changes
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
