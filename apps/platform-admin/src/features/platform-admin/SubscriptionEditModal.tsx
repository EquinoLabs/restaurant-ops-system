import React, { useState, useEffect } from 'react';
import { PlatformBusiness, PlatformSubscriptionUpdatePayload, PlatformPlan } from '@roms/shared-types';
import { updatePlatformSubscription, fetchPlatformPlans } from '@roms/api-client';
import { Button, Drawer, FormField, opsInputClass, opsSelectClass } from '../../components/ops-ui';

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

  const diffRow = (label: string, oldValue: string, newValue: string) => (
    <div
      key={label}
      className="flex items-center justify-between gap-3 border-b border-ops-divider py-2 last:border-b-0"
    >
      <span className="text-ops-text-secondary">{label}</span>
      <span className="flex items-center gap-2 text-[13px]">
        <span className="text-ops-text-secondary">{oldValue}</span>
        <span className="text-ops-text-disabled" aria-hidden="true">
          →
        </span>
        <span className="font-medium text-ops-text-primary">{newValue}</span>
      </span>
    </div>
  );

  const valueRow = (label: string, value: React.ReactNode) => (
    <div
      key={label}
      className="flex items-center justify-between gap-3 border-b border-ops-divider py-2 last:border-b-0"
    >
      <span className="text-ops-text-secondary">{label}</span>
      <span className="font-medium text-ops-text-primary">{value}</span>
    </div>
  );

  return (
    <Drawer
      open={isOpen}
      onClose={onClose}
      title={isConfirming ? 'Confirm Subscription Update' : 'Manage Subscription & Status'}
      subtitle={business.name}
      footer={
        isConfirming ? (
          <>
            <Button
              variant="secondary"
              onClick={() => setIsConfirming(false)}
              disabled={isSubmitting}
            >
              Back to Edit
            </Button>
            <Button
              variant="primary"
              onClick={() =>
                executeSubscriptionUpdate(
                  maxOutlets.trim() ? parseInt(maxOutlets.trim(), 10) : null
                )
              }
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Applying…' : 'Confirm & Apply Changes'}
            </Button>
          </>
        ) : (
          <>
            <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button
              variant="primary"
              type="submit"
              form="subscription-edit-form"
              disabled={isSubmitting}
            >
              Review changes
            </Button>
          </>
        )
      }
    >
      {error && (
        <div
          role="alert"
          className="rounded-md border border-ops-status-critical-bg bg-ops-status-critical-bg/40 p-3 text-[13px] text-ops-error"
        >
          {error}
        </div>
      )}

      {isConfirming ? (
        <div className="space-y-2 rounded-md border border-ops-border bg-ops-canvas p-4 text-[13px]">
          <p className="pb-1 font-medium text-ops-text-primary">
            Please review the proposed subscription changes before applying:
          </p>

          {diffRow('Operation / Action:', '', actionLabels[actionType] || actionType)}

          {!actionType
            ? diffRow(
                'Subscription Status:',
                business.subscription_status || '—',
                subscriptionStatus
              )
            : null}

          {diffRow('Operational Status:', business.status, status)}
          {diffRow('Plan Tier:', business.plan_name || 'None', planName.trim() || 'None')}

          {['activate', 'renew', 'change_plan_new_term'].includes(actionType) && (
            <>
              {valueRow(
                'Contractual Start:',
                currentPeriodStart || 'Today (Immediate)'
              )}
              {valueRow('Contractual End (1 Year):', currentPeriodEnd)}
            </>
          )}

          {actionType === 'mark_past_due_with_extension' &&
            valueRow('Extended Period End:', currentPeriodEnd)}

          {(!actionType || actionType === 'extend_trial') && trialEndsAt.trim() && (
            <div
              key="trial"
              className="flex items-center justify-between gap-3 border-b border-ops-divider py-2 last:border-b-0"
            >
              <span className="text-ops-text-secondary">Trial Expiration:</span>
              <span className="flex items-center gap-2 text-[13px]">
                <span className="text-ops-text-secondary">
                  {business.trial_ends_at
                    ? new Date(business.trial_ends_at).toLocaleDateString()
                    : 'None'}
                </span>
                <span className="text-ops-text-disabled" aria-hidden="true">
                  →
                </span>
                <span className="font-medium text-ops-text-primary">
                  {new Date(trialEndsAt.trim()).toLocaleDateString()}
                </span>
              </span>
            </div>
          )}

          {diffRow(
            'Max Outlets:',
            business.max_outlets !== null && business.max_outlets !== undefined
              ? String(business.max_outlets)
              : '∞',
            maxOutlets.trim() ? maxOutlets.trim() : '∞'
          )}

          {reason.trim() && (
            <div className="py-2">
              <span className="mb-1 block text-ops-text-secondary">Administrative Reason:</span>
              <span className="block rounded-md border border-ops-divider bg-white p-2 font-mono text-[12px] text-ops-text-primary">
                {reason.trim()}
              </span>
            </div>
          )}
        </div>
      ) : (
        <form
          id="subscription-edit-form"
          onSubmit={handleNextOrSubmit}
          className="space-y-4"
        >
          <FormField
            id="sub-action-mode"
            label="Lifecycle Action Mode"
            hint="Choose a contractual action to create a new immutable subscription record or manage status."
          >
            <select
              id="sub-action-mode"
              value={actionType}
              onChange={(e) => setActionType(e.target.value)}
              className={opsSelectClass}
            >
              <option value="">Standard account & limits edit (default)</option>
              <option value="activate">Activate paid subscription (1-year term)</option>
              <option value="renew">Renew annual subscription</option>
              <option value="change_plan">Change plan tier (keep period boundaries)</option>
              <option value="change_plan_new_term">Change plan tier (establish new 1-year term)</option>
              <option value="extend_trial">Extend evaluation trial</option>
              <option value="schedule_cancellation">Schedule cancellation at period end</option>
              <option value="revoke_scheduled_cancellation">Revoke scheduled cancellation</option>
              <option value="cancel_immediately">Cancel immediately</option>
              <option value="mark_past_due">Mark subscription past due</option>
              <option value="mark_past_due_with_extension">
                Mark past due with grace period extension
              </option>
            </select>
          </FormField>

          {!actionType && (
            <FormField id="sub-status" label="Subscription Status" required>
              <select
                id="sub-status"
                value={subscriptionStatus}
                onChange={(e) => setSubscriptionStatus(e.target.value)}
                className={opsSelectClass}
              >
                <option value="trial">Trial (evaluation period)</option>
                <option value="active">Active (paid subscription)</option>
                <option value="past_due">Past due (payment overdue)</option>
                <option value="cancelled">Cancelled (terminated subscription)</option>
              </select>
            </FormField>
          )}

          <FormField id="sub-account-status" label="Account operational status" required>
            <select
              id="sub-account-status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className={opsSelectClass}
            >
              <option value="active">Active (operational access allowed)</option>
              <option value="suspended">Suspended (access restricted)</option>
            </select>
          </FormField>

          {(!actionType ||
            ['activate', 'renew', 'change_plan', 'change_plan_new_term'].includes(actionType)) && (
            <FormField id="sub-plan" label="Plan Tier Name">
              <select
                id="sub-plan"
                value={planName}
                onChange={(e) => setPlanName(e.target.value)}
                className={opsSelectClass}
              >
                <option value="">No plan tier set</option>
                {availablePlans.map((plan) => (
                  <option key={plan.code} value={plan.code}>
                    {plan.name} ({plan.code})
                  </option>
                ))}
              </select>
            </FormField>
          )}

          {/* Annual Contract Dates Controls */}
          {['activate', 'renew', 'change_plan_new_term'].includes(actionType) && (
            <div className="space-y-3 rounded-md border border-ops-border bg-ops-canvas p-3.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-ops-text-secondary">
                  Annual contract period (1 calendar year)
                </span>
                <Button
                  variant="secondary"
                  onClick={handleCalculatePeriodEnd}
                  title="Auto-calculate exact 1-year period end (leap-year aware)"
                >
                  Calculate 1-year end
                </Button>
              </div>

              <FormField id="sub-period-start" label="Contractual period start date" required>
                <input
                  id="sub-period-start"
                  type="date"
                  value={currentPeriodStart}
                  onChange={(e) => setCurrentPeriodStart(e.target.value)}
                  className={opsInputClass}
                />
              </FormField>

              <FormField
                id="sub-period-end"
                label="Contractual period end date (strictly 1 year)"
                required
                hint="Must match calendar 1-year date (e.g., leap days Feb 29 → Feb 28)."
              >
                <input
                  id="sub-period-end"
                  type="date"
                  value={currentPeriodEnd}
                  onChange={(e) => setCurrentPeriodEnd(e.target.value)}
                  className={opsInputClass}
                />
              </FormField>
            </div>
          )}

          {actionType === 'mark_past_due_with_extension' && (
            <FormField id="sub-grace-end" label="Extended grace period end date" required>
              <input
                id="sub-grace-end"
                type="date"
                value={currentPeriodEnd}
                onChange={(e) => setCurrentPeriodEnd(e.target.value)}
                className={opsInputClass}
              />
            </FormField>
          )}

          {(!actionType || actionType === 'extend_trial') && (
            <FormField
              id="sub-trial-end"
              label="Trial expiration date"
              required={actionType === 'extend_trial'}
              hint={actionType === 'extend_trial' ? undefined : 'Optional.'}
            >
              <input
                id="sub-trial-end"
                type="date"
                value={trialEndsAt}
                onChange={(e) => setTrialEndsAt(e.target.value)}
                className={opsInputClass}
              />
            </FormField>
          )}

          <FormField
            id="sub-max-outlets"
            label="Max allowed outlets"
            hint="Leave empty for unlimited."
          >
            <input
              id="sub-max-outlets"
              type="number"
              min="1"
              value={maxOutlets}
              onChange={(e) => setMaxOutlets(e.target.value)}
              placeholder="e.g. 3 (blank = unlimited)"
              className={opsInputClass}
            />
          </FormField>

          {actionType && (
            <FormField
              id="sub-reason"
              label="Administrative reason"
              required={['cancel_immediately', 'mark_past_due_with_extension'].includes(actionType)}
              hint={
                ['cancel_immediately', 'mark_past_due_with_extension'].includes(actionType)
                  ? undefined
                  : 'Optional audit note for this change.'
              }
            >
              <textarea
                id="sub-reason"
                rows={2}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={
                  ['cancel_immediately', 'mark_past_due_with_extension'].includes(actionType)
                    ? 'Mandatory reason for this lifecycle transition…'
                    : 'Optional audit note for this change…'
                }
                className="w-full resize-none rounded-md border border-ops-border bg-white p-2 text-[13px] text-ops-text-primary placeholder:text-ops-text-disabled focus:border-ops-accent focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
              />
            </FormField>
          )}
        </form>
      )}
    </Drawer>
  );
};
