import React, { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { Search } from 'lucide-react';
import { PlatformBusiness } from '@roms/shared-types';
import { fetchBusinessSubscriptions } from '@roms/api-client';
import type { BusinessSubscriptionItem } from '@roms/shared-types';
import {
  Button,
  DataTable,
  Drawer,
  PageHeader,
  StatBlock,
  StateBlock,
  StatusBadge,
  type DataTableColumn,
  type StatusTone,
} from '../../components/ops-ui';
import { opsInputClass, opsSelectClass } from '../../components/ops-ui/FormField';

export interface SubscriptionsOverviewProps {
  businesses: PlatformBusiness[];
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
  token: string | null;
  referenceDate?: Date;
  onNavigateOutlet?: (outletId: string) => void;
}

export interface OutletSubRow {
  businessId: string;
  businessName: string;
  businessStatus: string;
  outletId: string;
  outletName: string;
  planCode: string;
  planName: string;
  status: string;
  resolvedStatus: string;
  trialEndsAt: string | null;
  currentPeriodEnd: string | null;
  cancelAtPeriodEnd: boolean;
}

export function filterSubscriptions(
  rows: OutletSubRow[],
  searchQuery: string,
  subscriptionFilter: string,
  statusFilter: string,
  trialFilter: string = 'all',
  referenceDate: Date = new Date()
): OutletSubRow[] {
  const q = searchQuery.trim().toLowerCase();
  const nowMs = referenceDate.getTime();
  const sevenDaysMs = 7 * 24 * 60 * 60 * 1000;

  return rows.filter((row) => {
    const matchesSearch =
      !q ||
      row.businessName.toLowerCase().includes(q) ||
      row.outletName.toLowerCase().includes(q) ||
      row.planCode.toLowerCase().includes(q) ||
      row.planName.toLowerCase().includes(q);

    const matchesSubscription =
      subscriptionFilter === 'all' || row.resolvedStatus === subscriptionFilter;

    const matchesStatus = statusFilter === 'all' || row.businessStatus === statusFilter;

    let matchesTrial = true;
    if (trialFilter === 'expiring_soon') {
      if (row.resolvedStatus !== 'trial' || !row.trialEndsAt) {
        matchesTrial = false;
      } else {
        const trialEndMs = new Date(row.trialEndsAt).getTime();
        matchesTrial = !isNaN(trialEndMs) && trialEndMs >= nowMs && trialEndMs <= nowMs + sevenDaysMs;
      }
    } else if (trialFilter === 'expired') {
      if (row.resolvedStatus !== 'expired') {
        matchesTrial = false;
      } else {
        matchesTrial = true;
      }
    }

    return matchesSearch && matchesSubscription && matchesStatus && matchesTrial;
  });
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function resolveStatusTone(resolvedStatus: string): StatusTone {
  switch (resolvedStatus) {
    case 'active':
      return 'active';
    case 'past_due':
      return 'pending';
    case 'cancelled':
      return 'neutral';
    case 'trial':
      return 'pending';
    case 'expired':
      return 'critical';
    case 'no_current_subscription':
    case 'no_subscription':
    case 'unknown':
    default:
      return 'neutral';
  }
}

function resolveStatusLabel(resolvedStatus: string): string {
  switch (resolvedStatus) {
    case 'active':
      return 'Active';
    case 'past_due':
      return 'Past due';
    case 'cancelled':
      return 'Cancelled';
    case 'trial':
      return 'Trial';
    case 'expired':
      return 'Expired';
    case 'no_current_subscription':
      return 'No current subscription';
    case 'no_subscription':
      return 'No subscription';
    case 'unknown':
      return 'Unknown';
    default:
      return resolvedStatus.replace(/_/g, ' ');
  }
}

function accountTone(status: string): StatusTone {
  return status === 'suspended' ? 'critical' : 'active';
}

function accountLabel(status: string): string {
  return status === 'suspended' ? 'Suspended' : 'Active';
}

function formatPlanLabel(code: string): string {
  switch (code) {
    case 'starter_pos': return 'Starter POS';
    case 'growth_pos': return 'Growth POS';
    case 'pro_kds': return 'Pro KDS';
    case 'enterprise': return 'Enterprise';
    case 'free_qr': return 'Free QR Menu';
    default: return code;
  }
}

function formatActionLabel(action: string): string {
  switch (action) {
    case 'change_plan': return 'Change Plan';
    case 'activate': return 'Activate Annual Term';
    case 'extend_trial': return 'Extend Trial';
    case 'cancel_immediately': return 'Cancel Immediately';
    case 'schedule_cancellation': return 'Schedule Cancellation';
    default: return action;
  }
}

export const SubscriptionsOverview: React.FC<SubscriptionsOverviewProps> = ({
  businesses,
  loading,
  error,
  onRetry,
  token,
  referenceDate = new Date(),
  onNavigateOutlet,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [subscriptionFilter, setSubscriptionFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [trialFilter, setTrialFilter] = useState<string>('all');
  const [selectedSubRow, setSelectedSubRow] = useState<OutletSubRow | null>(null);
  const [workflowStep, setWorkflowStep] = useState<'inspect' | 'edit' | 'review'>('inspect');
  const [targetPlanCode, setTargetPlanCode] = useState<string>('growth_pos');
  const [actionType, setActionType] = useState<string>('change_plan');
  const [reasonDraft, setReasonDraft] = useState<string>('');
  const [subscriptionsCache, setSubscriptionsCache] = useState<Map<string, BusinessSubscriptionItem[]>>(new Map());
  const [subscriptionsError, setSubscriptionsError] = useState<string | null>(null);
  const [subscriptionsLoading, setSubscriptionsLoading] = useState(false);
  const loadInitiatedRef = useRef(false);
  const prevTokenRef = useRef<string | null>(null);
  const prevBusinessesRef = useRef<any[]>([]);

  const nowMs = referenceDate.getTime();
  const oneDayMs = 24 * 60 * 60 * 1000;

  // Flatten businesses into outlet-level rows using fetched subscription data
  const outletRows = useMemo<OutletSubRow[]>(() => {
    const rows: OutletSubRow[] = [];
    for (const biz of businesses) {
      const outlets = biz.outlets || [];
      const subList = subscriptionsCache.get(biz.id) || [];
      if (outlets.length === 0) {
        // Business with no outlets — show placeholder row indicating no outlets
        rows.push({
          businessId: biz.id,
          businessName: biz.name,
          businessStatus: biz.status,
          outletId: '',
          outletName: '(no outlets)',
          planCode: '—',
          planName: '—',
          status: 'no_subscription',
          resolvedStatus: 'no_subscription',
          trialEndsAt: null,
          currentPeriodEnd: null,
          cancelAtPeriodEnd: false,
        });
        continue;
      }

      // Map current and historical subscriptions by outlet_id for this business
      const currentSubByOutlet = new Map<string, BusinessSubscriptionItem>();
      const historySubsByOutlet = new Map<string, BusinessSubscriptionItem[]>();

      for (const sub of subList) {
        if (!sub.outlet_id) continue;
        const existing = historySubsByOutlet.get(sub.outlet_id) || [];
        existing.push(sub);
        historySubsByOutlet.set(sub.outlet_id, existing);

        if (sub.is_current) {
          currentSubByOutlet.set(sub.outlet_id, sub);
        }
      }

      for (const outlet of outlets) {
        const currentSub = currentSubByOutlet.get(outlet.id);
        const outletHistory = historySubsByOutlet.get(outlet.id) || [];

        if (currentSub) {
          const planName = currentSub.plan?.name || (currentSub.plan?.code ? currentSub.plan.code.charAt(0).toUpperCase() + currentSub.plan.code.slice(1) : 'Unknown');
          const planCode = currentSub.plan?.code || 'unknown';

          let resolvedStatus = currentSub.status;
          if (currentSub.status === 'trial' && currentSub.trial_ends_at) {
            if (new Date(currentSub.trial_ends_at).getTime() < referenceDate.getTime()) {
              resolvedStatus = 'expired';
            }
          } else if (currentSub.status === 'active' && currentSub.current_period_end) {
            if (new Date(currentSub.current_period_end).getTime() < referenceDate.getTime()) {
              resolvedStatus = 'expired';
            }
          }

          rows.push({
            businessId: biz.id,
            businessName: biz.name,
            businessStatus: biz.status,
            outletId: outlet.id,
            outletName: outlet.name,
            planCode,
            planName,
            status: currentSub.status,
            resolvedStatus,
            trialEndsAt: currentSub.trial_ends_at || null,
            currentPeriodEnd: currentSub.current_period_end || null,
            cancelAtPeriodEnd: currentSub.cancel_at_period_end || false,
          });
        } else if (outletHistory.length > 0) {
          // Historical records exist, but no current subscription (is_current=false)
          const latestSub = outletHistory[0];
          const planName = latestSub.plan?.name || (latestSub.plan?.code ? latestSub.plan.code.charAt(0).toUpperCase() + latestSub.plan.code.slice(1) : '—');
          const planCode = latestSub.plan?.code || '—';

          let resolvedStatus = 'no_current_subscription';
          if (latestSub.status === 'cancelled') {
            resolvedStatus = 'cancelled';
          } else if (latestSub.status === 'trial' && latestSub.trial_ends_at && new Date(latestSub.trial_ends_at).getTime() < referenceDate.getTime()) {
            resolvedStatus = 'expired';
          } else if (latestSub.current_period_end && new Date(latestSub.current_period_end).getTime() < referenceDate.getTime()) {
            resolvedStatus = 'expired';
          }

          rows.push({
            businessId: biz.id,
            businessName: biz.name,
            businessStatus: biz.status,
            outletId: outlet.id,
            outletName: outlet.name,
            planCode,
            planName,
            status: latestSub.status,
            resolvedStatus,
            trialEndsAt: latestSub.trial_ends_at || null,
            currentPeriodEnd: latestSub.current_period_end || null,
            cancelAtPeriodEnd: latestSub.cancel_at_period_end || false,
          });
        } else {
          // Zero subscription records for this outlet
          rows.push({
            businessId: biz.id,
            businessName: biz.name,
            businessStatus: biz.status,
            outletId: outlet.id,
            outletName: outlet.name,
            planCode: '—',
            planName: '—',
            status: 'no_subscription',
            resolvedStatus: 'no_subscription',
            trialEndsAt: null,
            currentPeriodEnd: null,
            cancelAtPeriodEnd: false,
          });
        }
      }
    }
    return rows;
  }, [businesses, subscriptionsCache]);

  const filteredRows = useMemo(
    () => filterSubscriptions(outletRows, searchQuery, subscriptionFilter, statusFilter, trialFilter, referenceDate),
    [outletRows, searchQuery, subscriptionFilter, statusFilter, trialFilter, referenceDate]
  );

  // Load subscriptions for all businesses
  const loadAllSubscriptions = useCallback(async () => {
    if (!token || businesses.length === 0) return;
    if (loadInitiatedRef.current && prevTokenRef.current === token && prevBusinessesRef.current === businesses) return;
    loadInitiatedRef.current = true;
    prevTokenRef.current = token;
    prevBusinessesRef.current = businesses;
    setSubscriptionsLoading(true);
    setSubscriptionsError(null);
    const newCache = new Map(subscriptionsCache);
    try {
      for (const biz of businesses) {
        const cacheKey = biz.id;
        if (newCache.has(cacheKey)) continue;
        try {
          const data = await fetchBusinessSubscriptions(biz.id, token);
          newCache.set(cacheKey, data);
        } catch {
          // Silently skip businesses that fail — don't block the whole page
        }
      }
      setSubscriptionsCache(newCache);
    } catch (err: any) {
      setSubscriptionsError(err.message || 'Failed to load outlet subscriptions.');
    } finally {
      setSubscriptionsLoading(false);
    }
  }, [token, businesses]);

  useEffect(() => {
    loadAllSubscriptions();
  }, [loadAllSubscriptions]);

  const hasActiveFilters =
    searchQuery.trim() !== '' ||
    subscriptionFilter !== 'all' ||
    statusFilter !== 'all' ||
    trialFilter !== 'all';

  const handleClearFilters = () => {
    setSearchQuery('');
    setSubscriptionFilter('all');
    setStatusFilter('all');
    setTrialFilter('all');
  };

  // Metrics
  const activeCount = useMemo(
    () => filteredRows.filter((r) => r.resolvedStatus === 'active').length,
    [filteredRows]
  );
  const trialCount = useMemo(
    () => filteredRows.filter((r) => r.resolvedStatus === 'trial').length,
    [filteredRows]
  );
  const expiredCount = useMemo(
    () => filteredRows.filter((r) => r.resolvedStatus === 'expired').length,
    [filteredRows]
  );

  const columns: DataTableColumn<OutletSubRow>[] = [
    {
      key: 'outlet',
      header: 'Outlet',
      width: '28%',
      getTitle: (row) => `${row.outletName} (${row.businessName})`,
      render: (row) => (
        <div className="flex min-w-0 flex-col">
          <span className="truncate font-medium text-ops-text-primary">{row.outletName}</span>
          <span className="mt-0.5 truncate text-[11px] text-ops-text-secondary">
            {row.businessName}
          </span>
          <span className="mt-0 truncate text-[10px] text-ops-text-secondary">
            {row.businessId}
          </span>
        </div>
      ),
    },
    {
      key: 'plan',
      header: 'Plan',
      width: '14%',
      render: (row) => (
        <span className="text-ops-text-primary">{row.planName}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      width: '16%',
      render: (row) => (
        <div className="flex flex-wrap items-center gap-1.5">
          <StatusBadge
            tone={resolveStatusTone(row.resolvedStatus)}
            label={resolveStatusLabel(row.resolvedStatus)}
          />
          {row.businessStatus !== 'active' && row.businessStatus !== undefined && (
            <StatusBadge
              tone={accountTone(row.businessStatus)}
              label={accountLabel(row.businessStatus)}
            />
          )}
        </div>
      ),
    },
    {
      key: 'trial-end',
      header: 'Trial end / Period end',
      width: '20%',
      tabular: true,
      render: (row) => {
        if (row.trialEndsAt) {
          const trialEndMs = new Date(row.trialEndsAt).getTime();
          if (isNaN(trialEndMs)) return <span className="text-ops-text-disabled">—</span>;
          const date = formatDate(row.trialEndsAt);
          if (row.resolvedStatus === 'expired' || trialEndMs < nowMs) {
            return <span className="text-ops-error tabular-nums">Expired {date}</span>;
          }
          const days = Math.max(1, Math.ceil((trialEndMs - nowMs) / oneDayMs));
          if (days <= 7) {
            return (
              <span className="font-medium text-ops-status-pending-text tabular-nums">
                Ends in {days} day{days === 1 ? '' : 's'} ({date})
              </span>
            );
          }
          return (
            <span className="text-ops-text-primary tabular-nums">
              Ends in {days} day{days === 1 ? '' : 's'} ({date})
            </span>
          );
        }
        if (row.currentPeriodEnd) {
          return <span className="text-ops-text-primary tabular-nums">{formatDate(row.currentPeriodEnd)}</span>;
        }
        if (row.resolvedStatus === 'expired') {
          return <span className="text-ops-error">No period end set</span>;
        }
        return <span className="text-ops-text-disabled">—</span>;
      },
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      width: '12%',
      render: (row) =>
        row.outletId ? (
          <button
            type="button"
            onClick={() => {
              setSelectedSubRow(row);
              setWorkflowStep('inspect');
              setTargetPlanCode(row.planCode !== '—' && row.planCode !== 'unknown' ? row.planCode : 'growth_pos');
              setActionType('change_plan');
              setReasonDraft('');
            }}
            className="h-8 rounded-md px-2 text-[13px] font-medium text-ops-accent transition-colors hover:bg-ops-canvas focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
          >
            View
          </button>
        ) : (
          <span className="text-ops-text-disabled text-[13px]">—</span>
        ),
    },
  ];

  const pageHeader = (
    <PageHeader
      title="Subscriptions"
      description="Outlet-level subscription overview. Each row represents one outlet's current subscription plan and status."
    />
  );

  if (loading && businesses.length === 0) {
    return (
      <div>
        {pageHeader}
        <StateBlock
          variant="loading"
          title="Loading platform subscriptions..."
          description="Fetching the latest subscription data."
        />
      </div>
    );
  }

  if (error && businesses.length === 0) {
    return (
      <div>
        {pageHeader}
        <StateBlock
          variant="error"
          title="Failed to load subscription data"
          description={error}
          actionLabel="Retry Loading"
          onAction={onRetry}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {pageHeader}

      {subscriptionsLoading && (
        <div
          role="status"
          className="rounded-md border border-ops-border bg-ops-canvas px-4 py-2 text-xs text-ops-text-secondary"
        >
          Fetching outlet subscriptions…
        </div>
      )}

      {subscriptionsError && !subscriptionsLoading && (
        <div
          role="alert"
          className="rounded-md border border-ops-status-critical-bg bg-ops-status-critical-bg/40 px-4 py-3 text-[13px] text-ops-error"
        >
          {subscriptionsError}
          <button
            type="button"
            onClick={loadAllSubscriptions}
            className="ml-3 text-ops-accent underline"
          >
            Retry
          </button>
        </div>
      )}

      <section
        aria-label="Subscription metrics"
        className="grid grid-cols-1 gap-4 sm:grid-cols-4"
      >
        <StatBlock caption="Active" value={activeCount} />
        <StatBlock caption="Trial" value={trialCount} />
        <StatBlock caption="Expired" value={expiredCount} />
        <StatBlock
          caption="Total outlets"
          value={outletRows.length}
          badge={
            outletRows.length > 0 ? (
              <span className="text-xs text-ops-text-secondary">
                {businesses.reduce((s, b) => s + (b.outlets?.length || 0), 0)} total
              </span>
            ) : undefined
          }
        />
      </section>

      <div className="rounded-md border border-ops-border bg-white p-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <div className="relative md:col-span-1">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-2.5 text-ops-text-secondary">
              <Search className="h-4 w-4" aria-hidden="true" />
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search business or outlet…"
              aria-label="Search subscriptions"
              className={`${opsInputClass} pl-8 pr-8`}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute inset-y-0 right-0 flex items-center pr-2.5 text-[11px] text-ops-text-secondary hover:text-ops-text-primary"
                aria-label="Clear Search Input"
              >
                ✕
              </button>
            )}
          </div>

          <select
            value={subscriptionFilter}
            onChange={(e) => setSubscriptionFilter(e.target.value)}
            className={opsSelectClass}
            aria-label="Filter Subscription Status"
          >
            <option value="all">All subscription statuses</option>
            <option value="trial">Trial</option>
            <option value="active">Active (paid)</option>
            <option value="past_due">Past due</option>
            <option value="cancelled">Cancelled</option>
            <option value="expired">Expired</option>
          </select>

          <select
            value={trialFilter}
            onChange={(e) => setTrialFilter(e.target.value)}
            className={opsSelectClass}
            aria-label="Filter Trial Dates"
          >
            <option value="all">All trials</option>
            <option value="expiring_soon">Expiring in &lt; 7 days</option>
            <option value="expired">Expired trials</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className={opsSelectClass}
            aria-label="Filter Operational Account Status"
          >
            <option value="all">All account statuses</option>
            <option value="active">Operational active</option>
            <option value="suspended">Operational suspended</option>
          </select>
        </div>

        <div className="mt-4 flex flex-col gap-2 border-t border-ops-divider pt-3 text-xs text-ops-text-secondary sm:flex-row sm:items-center sm:justify-between">
          <div>
            Showing{' '}
            <span className="font-semibold text-ops-text-primary">
              {filteredRows.length}
            </span>{' '}
            of <span className="font-semibold text-ops-text-primary">{outletRows.length}</span>{' '}
            outlet subscriptions
            <span className="ml-2 text-[11px] text-ops-text-secondary">(client-side filter)</span>
          </div>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={handleClearFilters}
              className="self-start text-xs font-medium text-ops-accent hover:underline sm:self-auto"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {businesses.length === 0 ? (
        <StateBlock
          variant="empty"
          title="No subscriptions found."
          description="Subscriptions appear here once outlets are provisioned."
        />
      ) : filteredRows.length === 0 ? (
        <StateBlock
          variant="no-results"
          title="No subscriptions match the current criteria."
          description="Try adjusting your search keywords or clearing the filters."
          actionLabel="Clear All Filters"
          onAction={handleClearFilters}
        />
      ) : (
        <DataTable
          columns={columns}
          rows={filteredRows}
          rowKey={(row) => row.outletId || `${row.businessId}::no-outlet`}
          minWidth="840px"
          footer={
            <span>
              Showing {filteredRows.length} of {outletRows.length} total outlet subscriptions
            </span>
          }
        />
      )}

      {subscriptionsLoading && businesses.length > 0 && (
        <p className="text-xs text-ops-text-secondary">
          Fetching per-outlet subscription data…
        </p>
      )}

      <div className="rounded-md border border-ops-border bg-ops-canvas p-3 text-xs text-ops-text-secondary">
        <span className="font-semibold">Note:</span> Subscriptions are per-outlet under Stage 3. The business-level fields shown below are legacy and not authoritative for outlet subscriptions.
        {!subscriptionsLoading && !subscriptionsError && (
          <button
            type="button"
            onClick={loadAllSubscriptions}
            className="ml-2 text-ops-accent underline"
          >
            Refresh subscriptions
          </button>
        )}
      </div>

      <Drawer
        open={Boolean(selectedSubRow)}
        onClose={() => setSelectedSubRow(null)}
        title={
          workflowStep === 'edit'
            ? 'Edit Subscription'
            : workflowStep === 'review'
            ? 'Review Subscription Changes'
            : 'Subscription Details'
        }
        subtitle={
          selectedSubRow
            ? `${selectedSubRow.outletName} • ${selectedSubRow.businessName}`
            : undefined
        }
        width="w-[520px]"
        footer={
          <div className="flex w-full items-center justify-between">
            {workflowStep === 'inspect' && (
              <>
                <Button variant="secondary" onClick={() => setSelectedSubRow(null)}>
                  Close
                </Button>
                <Button
                  variant="primary"
                  onClick={() => setWorkflowStep('edit')}
                >
                  Edit Subscription
                </Button>
              </>
            )}

            {workflowStep === 'edit' && (
              <>
                <Button variant="secondary" onClick={() => setWorkflowStep('inspect')}>
                  Back to Details
                </Button>
                <Button variant="primary" onClick={() => setWorkflowStep('review')}>
                  Review Changes
                </Button>
              </>
            )}

            {workflowStep === 'review' && (
              <>
                <Button variant="secondary" onClick={() => setWorkflowStep('edit')}>
                  Back
                </Button>
                <Button
                  variant="primary"
                  disabled
                  title="Outlet-level subscription write API is pending backend deployment"
                >
                  Update Subscription
                </Button>
              </>
            )}
          </div>
        }
      >
        {selectedSubRow && workflowStep === 'inspect' && (
          <div className="space-y-6 py-2">
            <div className="space-y-4">
              <div className="border-b border-ops-divider pb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-ops-text-secondary">
                  Outlet Context
                </h3>
              </div>
              <dl className="grid grid-cols-2 gap-4 text-xs">
                <div className="min-h-[36px]">
                  <dt className="text-ops-text-secondary">Outlet</dt>
                  <dd className="mt-1 font-medium text-ops-text-primary">{selectedSubRow.outletName}</dd>
                </div>
                <div className="min-h-[36px]">
                  <dt className="text-ops-text-secondary">Outlet ID</dt>
                  <dd className="mt-1 font-mono text-[11px] text-ops-text-secondary">{selectedSubRow.outletId || '—'}</dd>
                </div>
                <div className="min-h-[36px]">
                  <dt className="text-ops-text-secondary">Business</dt>
                  <dd className="mt-1 font-medium text-ops-text-primary">{selectedSubRow.businessName}</dd>
                </div>
                <div className="min-h-[36px]">
                  <dt className="text-ops-text-secondary">Account Status</dt>
                  <dd className="mt-1">
                    <StatusBadge
                      tone={accountTone(selectedSubRow.businessStatus)}
                      label={accountLabel(selectedSubRow.businessStatus)}
                    />
                  </dd>
                </div>
              </dl>
            </div>

            <div className="space-y-4">
              <div className="border-b border-ops-divider pb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-ops-text-secondary">
                  Subscription Status & Plan
                </h3>
              </div>
              <dl className="grid grid-cols-2 gap-4 text-xs">
                <div className="min-h-[36px]">
                  <dt className="text-ops-text-secondary">Plan Name</dt>
                  <dd className="mt-1 font-semibold text-ops-text-primary">{selectedSubRow.planName}</dd>
                </div>
                <div className="min-h-[36px]">
                  <dt className="text-ops-text-secondary">Plan Code</dt>
                  <dd className="mt-1">
                    <span className="rounded bg-ops-canvas px-1.5 py-0.5 font-mono text-[11px] text-ops-text-secondary">
                      {selectedSubRow.planCode}
                    </span>
                  </dd>
                </div>
                <div className="min-h-[36px]">
                  <dt className="text-ops-text-secondary">Subscription Status</dt>
                  <dd className="mt-1">
                    <StatusBadge
                      tone={resolveStatusTone(selectedSubRow.resolvedStatus)}
                      label={resolveStatusLabel(selectedSubRow.resolvedStatus)}
                    />
                  </dd>
                </div>
                <div className="min-h-[36px]">
                  <dt className="text-ops-text-secondary">Stored Status</dt>
                  <dd className="mt-1 text-ops-text-primary font-mono text-[11px]">
                    {selectedSubRow.status}
                  </dd>
                </div>
                <div className="min-h-[36px]">
                  <dt className="text-ops-text-secondary">Trial Expiration</dt>
                  <dd className="mt-1 font-medium text-ops-text-primary tabular-nums">
                    {selectedSubRow.trialEndsAt ? formatDate(selectedSubRow.trialEndsAt) : '—'}
                  </dd>
                </div>
                <div className="min-h-[36px]">
                  <dt className="text-ops-text-secondary">Current Period End</dt>
                  <dd className="mt-1 font-medium text-ops-text-primary tabular-nums">
                    {selectedSubRow.currentPeriodEnd ? formatDate(selectedSubRow.currentPeriodEnd) : '—'}
                  </dd>
                </div>
                <div className="min-h-[36px]">
                  <dt className="text-ops-text-secondary">Auto-Renew</dt>
                  <dd className="mt-1 font-medium text-ops-text-primary">
                    {selectedSubRow.cancelAtPeriodEnd ? 'Cancelling at period end' : 'Active renewal'}
                  </dd>
                </div>
              </dl>
            </div>

            <div className="rounded-md border border-ops-border bg-ops-canvas p-3.5 text-xs text-ops-text-secondary">
              <p className="font-semibold text-ops-text-primary">Outlet Subscription Governance</p>
              <p className="mt-1 leading-5">
                Subscriptions are managed directly from this panel for each individual outlet. To configure this outlet's plan or lifecycle status, click <strong>Edit Subscription</strong> below.
              </p>
            </div>
          </div>
        )}

        {selectedSubRow && workflowStep === 'edit' && (
          <div className="space-y-6 py-2">
            <div className="border-b border-ops-divider pb-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-ops-text-secondary">
                Configure Outlet Subscription
              </h3>
              <p className="mt-1 text-xs text-ops-text-secondary">
                Select a target plan and action for <strong>{selectedSubRow.outletName}</strong>.
              </p>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <label htmlFor="target-plan-select" className="block font-medium text-ops-text-primary mb-1.5">
                  Target Subscription Plan
                </label>
                <select
                  id="target-plan-select"
                  value={targetPlanCode}
                  onChange={(e) => setTargetPlanCode(e.target.value)}
                  className={opsSelectClass}
                >
                  <option value="starter_pos">Starter POS — Base operations & digital ordering</option>
                  <option value="growth_pos">Growth POS — Multi-device dining & standard reporting</option>
                  <option value="pro_kds">Pro KDS — Real-time kitchen display & advanced routing</option>
                  <option value="enterprise">Enterprise — Dedicated capacity & custom integrations</option>
                  <option value="free_qr">Free QR Menu — Digital view-only menu</option>
                </select>
              </div>

              <div>
                <label htmlFor="action-type-select" className="block font-medium text-ops-text-primary mb-1.5">
                  Action Type
                </label>
                <select
                  id="action-type-select"
                  value={actionType}
                  onChange={(e) => setActionType(e.target.value)}
                  className={opsSelectClass}
                >
                  <option value="change_plan">Change Plan — Switch to target plan</option>
                  <option value="activate">Activate — Start annual term</option>
                  <option value="extend_trial">Extend Trial — Add 30-day trial extension</option>
                  <option value="cancel_immediately">Cancel Immediately — Terminate access</option>
                  <option value="schedule_cancellation">Schedule Cancellation — Cancel at period end</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {selectedSubRow && workflowStep === 'review' && (
          <div className="space-y-6 py-2">
            <div className="border-b border-ops-divider pb-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-ops-text-secondary">
                Review Proposed Changes
              </h3>
              <p className="mt-1 text-xs text-ops-text-secondary">
                Verify the planned subscription transition for <strong>{selectedSubRow.outletName}</strong>.
              </p>
            </div>

            <div className="rounded-md border border-ops-border bg-ops-canvas p-4 text-xs space-y-3">
              <div className="flex justify-between items-center border-b border-ops-divider pb-2">
                <span className="text-ops-text-secondary">Outlet</span>
                <span className="font-semibold text-ops-text-primary">{selectedSubRow.outletName}</span>
              </div>
              <div className="flex justify-between items-center border-b border-ops-divider pb-2">
                <span className="text-ops-text-secondary">Current Plan</span>
                <span className="text-ops-text-primary">{selectedSubRow.planName} ({selectedSubRow.planCode})</span>
              </div>
              <div className="flex justify-between items-center border-b border-ops-divider pb-2">
                <span className="text-ops-text-secondary">Target Plan</span>
                <span className="font-semibold text-ops-accent">{formatPlanLabel(targetPlanCode)} ({targetPlanCode})</span>
              </div>
              <div className="flex justify-between items-center border-b border-ops-divider pb-2">
                <span className="text-ops-text-secondary">Action</span>
                <span className="font-medium text-ops-text-primary">{formatActionLabel(actionType)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-ops-text-secondary">Effective Term</span>
                <span className="text-ops-text-primary">1-Year Standard Term (Decision 002)</span>
              </div>
            </div>

            <div className="space-y-1.5 text-xs">
              <label htmlFor="reason-input" className="block font-medium text-ops-text-primary">
                Administrative Reason (Optional)
              </label>
              <textarea
                id="reason-input"
                rows={2}
                value={reasonDraft}
                onChange={(e) => setReasonDraft(e.target.value)}
                placeholder="e.g. Contract signed per offline agreement"
                className="w-full rounded-md border border-ops-border bg-white px-3 py-2 text-xs text-ops-text-primary focus:border-ops-accent focus:outline-none"
              />
            </div>

            <div className="rounded-md border border-ops-status-pending-bg bg-ops-status-pending-bg/50 p-3.5 text-xs text-ops-status-pending-text">
              <p className="font-semibold">Outlet-Level Subscription Updates Pending Backend Support</p>
              <p className="mt-1 leading-5">
                Outlet-scoped subscription mutations require <code>PATCH /api/v1/platform/outlets/{'{id}'}/subscription</code>, which is pending backend deployment. The update action is disabled to prevent unauthorized business-wide subscription propagation.
              </p>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
};
