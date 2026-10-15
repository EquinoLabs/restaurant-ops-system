import React, { useState, useEffect } from 'react';
import { PlatformBusiness, PlatformSubscriptionUpdatePayload, PlatformPlan } from '@roms/shared-types';
import { updatePlatformSubscription, fetchPlatformPlans } from '@roms/api-client';

export interface SubscriptionEditModalProps {
  business: PlatformBusiness | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (updated: PlatformBusiness) => void;
  token: string | null;
}

export function computeAnnualPeriodEnd(startDateStr: string): string {
  if (!startDateStr || !startDateStr.includes('-')) return '';
  const [yearStr, monthStr, dayStr] = startDateStr.split('-');
  const startYear = parseInt(yearStr, 10);
  const startMonth = parseInt(monthStr, 10);
  const startDay = parseInt(dayStr, 10);
  if (isNaN(startYear) || isNaN(startMonth) || isNaN(startDay)) return '';

  const targetYear = startYear + 1;
  const isLeapYear = (y: number) => (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
  const daysInMonth = [
    31,
    isLeapYear(targetYear) ? 29 : 28,
    31, 30, 31, 30, 31, 31, 30, 31, 30, 31,
  ];
  const maxDay = daysInMonth[startMonth - 1];
  const targetDay = Math.min(startDay, maxDay);

  const pad = (n: number) => String(n).padStart(2, '0');
  return `${targetYear}-${pad(startMonth)}-${pad(targetDay)}`;
}

const FALLBACK_PLANS: { code: string; name: string }[] = [
  { code: 'starter', name: 'Starter Plan' },
  { code: 'growth', name: 'Growth Plan' },
  { code: 'pro', name: 'Pro Plan' },
  { code: 'enterprise', name: 'Enterprise Plan' },
];

export const SubscriptionEditModal: React.FC<SubscriptionEditModalProps> = ({
  business,
  isOpen,
  onClose,
  onSuccess,
  token,
}) => {
  // Action selection: "" means basic/metadata update
  const [actionType, setActionType] = useState<string>('');

  // Form fields
  const [subscriptionStatus, setSubscriptionStatus] = useState<string>('trial');
  const [status, setStatus] = useState<string>('active');
  const [planName, setPlanName] = useState<string>('');
  const [maxOutlets, setMaxOutlets] = useState<string>('');
  const [trialEndsAt, setTrialEndsAt] = useState<string>('');

  // Lifecycle specific fields
  const [currentPeriodStart, setCurrentPeriodStart] = useState<string>('');
  const [currentPeriodEnd, setCurrentPeriodEnd] = useState<string>('');
  const [reason, setReason] = useState<string>('');

  // Plans catalog
  const [availablePlans, setAvailablePlans] = useState<{ code: string; name: string }[]>(FALLBACK_PLANS);

  const [isConfirming, setIsConfirming] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch plans catalog
  useEffect(() => {
    if (isOpen && token) {
      fetchPlatformPlans(token)
        .then((plans: PlatformPlan[]) => {
          const active = plans.filter((p) => p.is_active);
          if (active.length > 0) {
            setAvailablePlans(active.map((p) => ({ code: p.code, name: p.name })));
          }
        })
        .catch(() => {
          // Keep fallback plans on network error
        });
    }
  }, [isOpen, token]);

  // Pre-populate fields when business changes or modal opens
  useEffect(() => {
    if (business && isOpen) {
      setActionType('');
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

      // Default start date to today
      const today = new Date().toISOString().split('T')[0];
      setCurrentPeriodStart(today);
      setCurrentPeriodEnd(computeAnnualPeriodEnd(today));
      setReason('');
      setIsConfirming(false);
      setError(null);
    }
  }, [business, isOpen]);

  if (!isOpen || !business) return null;

  const handleCalculatePeriodEnd = () => {
    if (!currentPeriodStart) {
      setError('Please provide a valid period start date first.');
      return;
    }
    const computed = computeAnnualPeriodEnd(currentPeriodStart);
    if (computed) {
      setCurrentPeriodEnd(computed);
      setError(null);
    } else {
      setError('Unable to compute period end from the provided start date.');
    }
  };

  const handleNextOrSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Common Validation
    const parsedMaxOutlets = maxOutlets.trim() ? parseInt(maxOutlets.trim(), 10) : null;
    if (parsedMaxOutlets !== null && (isNaN(parsedMaxOutlets) || parsedMaxOutlets < 1)) {
      setError('Max outlets limit must be a positive integer (>= 1) or left blank for unlimited.');
      return;
    }

    if (trialEndsAt.trim() && isNaN(new Date(trialEndsAt.trim()).getTime())) {
      setError('Invalid trial expiration date format.');
      return;
    }

    // Lifecycle Action Validation
    if (actionType === 'activate' || actionType === 'renew' || actionType === 'change_plan_new_term') {
      if (!planName.trim()) {
        setError('A plan tier must be selected for this lifecycle action.');
        return;
      }
      if (!currentPeriodStart.trim()) {
        setError('Current period start date is required.');
        return;
      }
      if (!currentPeriodEnd.trim()) {
        setError('Current period end date is required.');
        return;
      }
      const expected = computeAnnualPeriodEnd(currentPeriodStart.trim());
      if (expected && currentPeriodEnd.trim() !== expected) {
        setError(`Period end date must be exactly one calendar year after start date (${expected}).`);
        return;
      }
    }

    if (actionType === 'change_plan') {
      if (!planName.trim()) {
        setError('A target plan tier must be selected.');
        return;
      }
    }

    if (actionType === 'extend_trial') {
      if (!trialEndsAt.trim()) {
        setError('A new trial expiration date is required to extend evaluation.');
        return;
      }
    }

    if (actionType === 'cancel_immediately') {
      if (!reason.trim()) {
        setError('A clear administrative reason is strictly required for immediate cancellation.');
        return;
      }
    }

    if (actionType === 'mark_past_due_with_extension') {
      if (!currentPeriodEnd.trim()) {
        setError('Extended current period end date is required for recovery extension.');
        return;
      }
      if (!reason.trim()) {
        setError('A reason is required when granting a past-due grace period extension.');
        return;
      }
    }

    if (!isConfirming) {
      setIsConfirming(true);
      return;
    }

    // Perform actual API submission
    executeSubscriptionUpdate(parsedMaxOutlets);
  };

  const toUtcIso = (dateStr: string) => {
    if (!dateStr.trim()) return null;
    return `${dateStr.trim()}T00:00:00Z`;
  };

  const executeSubscriptionUpdate = async (parsedMaxOutlets: number | null) => {
    if (!token || !business) return;

    let payload: PlatformSubscriptionUpdatePayload;

    if (!actionType) {
      // Basic / direct metadata update (backward compatible)
      const formattedTrialDate = trialEndsAt.trim() ? toUtcIso(trialEndsAt) : null;
      payload = {
        subscription_status: subscriptionStatus,
        status: status,
        plan_name: planName.trim() || null,
        max_outlets: parsedMaxOutlets,
        trial_ends_at: formattedTrialDate,
      };
    } else {
      // Bounded lifecycle action
      payload = {
        action_type: actionType,
        plan_code: planName.trim() || undefined,
        status: status,
        max_outlets: parsedMaxOutlets,
        reason: reason.trim() || undefined,
      };

      if (['activate', 'renew', 'change_plan_new_term'].includes(actionType)) {
        if (currentPeriodStart.trim()) payload.current_period_start = toUtcIso(currentPeriodStart);
        if (currentPeriodEnd.trim()) payload.current_period_end = toUtcIso(currentPeriodEnd);
      } else if (actionType === 'mark_past_due_with_extension') {
        if (currentPeriodEnd.trim()) payload.current_period_end = toUtcIso(currentPeriodEnd);
      } else if (actionType === 'extend_trial') {
        if (trialEndsAt.trim()) payload.trial_ends_at = toUtcIso(trialEndsAt);
      }
    }

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

  const actionLabels: Record<string, string> = {
    '': 'Basic Account & Limits Update',
    activate: 'Activate Paid Subscription (Annual 1-Year)',
    renew: 'Renew Annual Subscription',
    change_plan: 'Change Plan Tier (Keep Current Period)',
    change_plan_new_term: 'Change Plan Tier (New 1-Year Term)',
    extend_trial: 'Extend Evaluation Trial',
    schedule_cancellation: 'Schedule Cancellation at Period End',
    revoke_scheduled_cancellation: 'Revoke Scheduled Cancellation',
    cancel_immediately: 'Cancel Immediately (Immediate Cutoff)',
    mark_past_due: 'Mark Subscription Past Due',
    mark_past_due_with_extension: 'Mark Past Due with Grace Period Extension',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl text-slate-100 overflow-hidden max-h-[90vh] flex flex-col">
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

        <div className="overflow-y-auto flex-1 pr-1">
          {isConfirming ? (
            /* Confirmation Step Diff View */
            <div className="mt-4 space-y-4">
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3 text-xs">
                <p className="text-slate-300 font-semibold mb-2">
                  Please review the proposed subscription changes before applying:
                </p>

                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/80">
                  <span className="text-slate-400">Operation / Action:</span>
                  <span className="font-bold text-indigo-400">{actionLabels[actionType] || actionType}</span>
                </div>

                {!actionType ? (
                  <div className="flex items-center justify-between py-1.5 border-b border-slate-800/80">
                    <span className="text-slate-400">Subscription Status:</span>
                    <div className="flex items-center space-x-2">
                      <span className="text-slate-500 uppercase">{business.subscription_status}</span>
                      <span className="text-slate-600">➔</span>
                      <span className="font-bold text-indigo-400 uppercase">{subscriptionStatus}</span>
                    </div>
                  </div>
                ) : null}

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

                {['activate', 'renew', 'change_plan_new_term'].includes(actionType) && (
                  <>
                    <div className="flex items-center justify-between py-1.5 border-b border-slate-800/80">
                      <span className="text-slate-400">Contractual Start:</span>
                      <span className="font-bold text-white">{currentPeriodStart || 'Today (Immediate)'}</span>
                    </div>
                    <div className="flex items-center justify-between py-1.5 border-b border-slate-800/80">
                      <span className="text-slate-400">Contractual End (1 Year):</span>
                      <span className="font-bold text-indigo-400">{currentPeriodEnd}</span>
                    </div>
                  </>
                )}

                {actionType === 'mark_past_due_with_extension' && (
                  <div className="flex items-center justify-between py-1.5 border-b border-slate-800/80">
                    <span className="text-slate-400">Extended Period End:</span>
                    <span className="font-bold text-amber-400">{currentPeriodEnd}</span>
                  </div>
                )}

                {(!actionType || actionType === 'extend_trial') && trialEndsAt.trim() && (
                  <div className="flex items-center justify-between py-1.5 border-b border-slate-800/80">
                    <span className="text-slate-400">Trial Expiration:</span>
                    <div className="flex items-center space-x-2">
                      <span className="text-slate-500">
                        {business.trial_ends_at ? new Date(business.trial_ends_at).toLocaleDateString() : 'None'}
                      </span>
                      <span className="text-slate-600">➔</span>
                      <span className="font-bold text-amber-400">
                        {new Date(trialEndsAt.trim()).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-between py-1.5 border-b border-slate-800/80">
                  <span className="text-slate-400">Max Outlets:</span>
                  <div className="flex items-center space-x-2">
                    <span className="text-slate-500">{business.max_outlets ?? '∞'}</span>
                    <span className="text-slate-600">➔</span>
                    <span className="font-bold text-white">{maxOutlets.trim() ? maxOutlets.trim() : '∞'}</span>
                  </div>
                </div>

                {reason.trim() && (
                  <div className="py-1.5">
                    <span className="text-slate-400 block mb-1">Administrative Reason:</span>
                    <span className="text-slate-200 italic font-mono bg-slate-900 p-2 rounded block">
                      {reason.trim()}
                    </span>
                  </div>
                )}
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
                  Lifecycle Action Mode
                </label>
                <select
                  value={actionType}
                  onChange={(e) => setActionType(e.target.value)}
                  className="mt-1.5 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">Standard Account & Limits Edit (Default)</option>
                  <option value="activate">Activate Paid Subscription (1-Year Term)</option>
                  <option value="renew">Renew Annual Subscription</option>
                  <option value="change_plan">Change Plan Tier (Keep Period Boundaries)</option>
                  <option value="change_plan_new_term">Change Plan Tier (Establish New 1-Year Term)</option>
                  <option value="extend_trial">Extend Evaluation Trial</option>
                  <option value="schedule_cancellation">Schedule Cancellation at Period End</option>
                  <option value="revoke_scheduled_cancellation">Revoke Scheduled Cancellation</option>
                  <option value="cancel_immediately">Cancel Immediately</option>
                  <option value="mark_past_due">Mark Past Due</option>
                  <option value="mark_past_due_with_extension">Mark Past Due with Grace Period Extension</option>
                </select>
                <p className="text-[10px] text-slate-500 mt-1">
                  Choose a contractual action to create a new immutable subscription record or manage status.
                </p>
              </div>

              {!actionType && (
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
              )}

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
              </div>

              {(!actionType || ['activate', 'renew', 'change_plan', 'change_plan_new_term'].includes(actionType)) && (
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
                    {availablePlans.map((plan) => (
                      <option key={plan.code} value={plan.code}>
                        {plan.name} ({plan.code})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Annual Contract Dates Controls */}
              {['activate', 'renew', 'change_plan_new_term'].includes(actionType) && (
                <div className="p-3.5 bg-slate-950/70 rounded-xl border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-indigo-300 uppercase">
                      Annual Contract Period (1 Calendar Year)
                    </span>
                    <button
                      type="button"
                      onClick={handleCalculatePeriodEnd}
                      className="px-2 py-1 rounded-lg bg-indigo-500/20 hover:bg-indigo-500/30 border border-indigo-500/40 text-indigo-300 text-[10px] font-bold transition-colors"
                      title="Auto-calculate exact 1-year period end (leap-year aware)"
                    >
                      📅 Calculate 1-Year End
                    </button>
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-slate-400">
                      Contractual Period Start Date *
                    </label>
                    <input
                      type="date"
                      value={currentPeriodStart}
                      onChange={(e) => setCurrentPeriodStart(e.target.value)}
                      className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-slate-400">
                      Contractual Period End Date (Strictly 1 Year) *
                    </label>
                    <input
                      type="date"
                      value={currentPeriodEnd}
                      onChange={(e) => setCurrentPeriodEnd(e.target.value)}
                      className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    <p className="text-[10px] text-slate-500 mt-1">
                      Must match calendar 1-year date (e.g., leap days Feb 29 ➔ Feb 28).
                    </p>
                  </div>
                </div>
              )}

              {actionType === 'mark_past_due_with_extension' && (
                <div>
                  <label className="block text-xs font-semibold uppercase text-slate-300">
                    Extended Grace Period End Date *
                  </label>
                  <input
                    type="date"
                    value={currentPeriodEnd}
                    onChange={(e) => setCurrentPeriodEnd(e.target.value)}
                    className="mt-1.5 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              )}

              {(!actionType || actionType === 'extend_trial') && (
                <div>
                  <label className="block text-xs font-semibold uppercase text-slate-300">
                    Trial Expiration Date {actionType === 'extend_trial' ? '*' : '(Optional)'}
                  </label>
                  <input
                    type="date"
                    value={trialEndsAt}
                    onChange={(e) => setTrialEndsAt(e.target.value)}
                    className="mt-1.5 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              )}

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

              {(actionType || '') && (
                <div>
                  <label className="block text-xs font-semibold uppercase text-slate-300">
                    Administrative Reason {['cancel_immediately', 'mark_past_due_with_extension'].includes(actionType) ? '*' : '(Optional)'}
                  </label>
                  <textarea
                    rows={2}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder={
                      ['cancel_immediately', 'mark_past_due_with_extension'].includes(actionType)
                        ? 'Mandatory reason for this lifecycle transition...'
                        : 'Optional audit note for this change...'
                    }
                    className="mt-1.5 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                  />
                </div>
              )}

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
    </div>
  );
};
