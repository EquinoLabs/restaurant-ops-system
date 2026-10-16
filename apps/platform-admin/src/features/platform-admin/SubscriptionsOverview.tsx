import React, { useState, useMemo } from 'react';
import { Search } from 'lucide-react';
import { PlatformBusiness } from '@roms/shared-types';
import { SubscriptionEditModal } from './SubscriptionEditModal';
import {
  DataTable,
  PageHeader,
  StatBlock,
  StateBlock,
  StatusBadge,
  type DataTableColumn,
  type StatusTone,
} from '../../components/ops-ui';
import { opsInputClass } from '../../components/ops-ui/FormField';

export interface SubscriptionsOverviewProps {
  businesses: PlatformBusiness[];
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
  onUpdateSubscription?: (updated: PlatformBusiness) => void;
  token: string | null;
  referenceDate?: Date;
}

export function filterSubscriptions(
  businesses: PlatformBusiness[],
  searchQuery: string,
  subscriptionFilter: string,
  statusFilter: string,
  trialFilter: string = 'all',
  referenceDate: Date = new Date()
): PlatformBusiness[] {
  const q = searchQuery.trim().toLowerCase();
  const nowMs = referenceDate.getTime();
  const sevenDaysMs = 7 * 24 * 60 * 60 * 1000;

  return businesses.filter((biz) => {
    // Search match against business name, plan tier, or outlet info
    const matchesSearch =
      !q ||
      biz.name.toLowerCase().includes(q) ||
      (biz.plan_name && biz.plan_name.toLowerCase().includes(q)) ||
      biz.outlets?.some(
        (o) => o.name.toLowerCase().includes(q) || o.public_slug.toLowerCase().includes(q)
      );

    // Subscription status match
    const matchesSubscription =
      subscriptionFilter === 'all' || biz.subscription_status === subscriptionFilter;

    // Operational status match
    const matchesStatus = statusFilter === 'all' || biz.status === statusFilter;

    // Trial expiration filter
    let matchesTrial = true;
    if (trialFilter === 'expiring_soon') {
      if (biz.subscription_status !== 'trial' || !biz.trial_ends_at) {
        matchesTrial = false;
      } else {
        const trialEndMs = new Date(biz.trial_ends_at).getTime();
        matchesTrial = !isNaN(trialEndMs) && trialEndMs >= nowMs && trialEndMs <= nowMs + sevenDaysMs;
      }
    } else if (trialFilter === 'expired') {
      if (!biz.trial_ends_at) {
        matchesTrial = false;
      } else {
        const trialEndMs = new Date(biz.trial_ends_at).getTime();
        matchesTrial = !isNaN(trialEndMs) && trialEndMs < nowMs;
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

function subscriptionTone(status?: string): StatusTone {
  switch (status) {
    case 'active':
      return 'active';
    case 'past_due':
      return 'pending';
    case 'cancelled':
      return 'neutral';
    case 'trial':
    default:
      return 'pending';
  }
}

function subscriptionLabel(status?: string): string {
  switch (status) {
    case 'active':
      return 'Active';
    case 'past_due':
      return 'Past due';
    case 'cancelled':
      return 'Cancelled';
    case 'trial':
    default:
      return 'Trial';
  }
}

export const SubscriptionsOverview: React.FC<SubscriptionsOverviewProps> = ({
  businesses,
  loading,
  error,
  onRetry,
  onUpdateSubscription,
  token,
  referenceDate = new Date(),
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [subscriptionFilter, setSubscriptionFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [trialFilter, setTrialFilter] = useState<string>('all');

  // Edit drawer state
  const [selectedBizForEdit, setSelectedBizForEdit] = useState<PlatformBusiness | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [successBannerMessage, setSuccessBannerMessage] = useState<string | null>(null);

  const nowMs = referenceDate.getTime();
  const oneDayMs = 24 * 60 * 60 * 1000;

  const activeCount = useMemo(() => {
    return businesses.filter((b) => b.subscription_status === 'active').length;
  }, [businesses]);

  const pastDueCount = useMemo(() => {
    return businesses.filter((b) => b.subscription_status === 'past_due').length;
  }, [businesses]);

  const outletStats = useMemo(() => {
    const totalOutlets = businesses.reduce((sum, b) => sum + (b.outlets?.length || 0), 0);
    const activeOutlets = businesses.reduce(
      (sum, b) => sum + (b.outlets?.filter((o) => o.status === 'active').length || 0),
      0
    );
    return { totalOutlets, activeOutlets };
  }, [businesses]);

  const filteredBusinesses = useMemo(
    () => filterSubscriptions(businesses, searchQuery, subscriptionFilter, statusFilter, trialFilter, referenceDate),
    [businesses, searchQuery, subscriptionFilter, statusFilter, trialFilter, referenceDate]
  );

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

  const handleOpenEditModal = (biz: PlatformBusiness) => {
    setSelectedBizForEdit(biz);
    setIsEditModalOpen(true);
  };

  const handleModalSuccess = (updated: PlatformBusiness) => {
    setSuccessBannerMessage(`Subscription for business '${updated.name}' successfully updated!`);
    if (onUpdateSubscription) {
      onUpdateSubscription(updated);
    }
  };

  const renderTrialCell = (biz: PlatformBusiness) => {
    if (biz.subscription_status !== 'trial' || !biz.trial_ends_at) {
      return <span className="text-ops-text-disabled">—</span>;
    }
    const trialEndMs = new Date(biz.trial_ends_at).getTime();
    if (isNaN(trialEndMs)) {
      return <span className="text-ops-text-disabled">—</span>;
    }
    const date = formatDate(biz.trial_ends_at);
    if (trialEndMs < nowMs) {
      return <span className="text-ops-error">Expired {date}</span>;
    }
    const days = Math.max(1, Math.ceil((trialEndMs - nowMs) / oneDayMs));
    if (days <= 7) {
      return (
        <span className="font-medium text-ops-status-pending-text">
          Ends in {days} day{days === 1 ? '' : 's'} ({date})
        </span>
      );
    }
    return (
      <span className="text-ops-text-primary">
        Ends in {days} day{days === 1 ? '' : 's'} ({date})
      </span>
    );
  };

  const columns: DataTableColumn<PlatformBusiness>[] = [
    {
      key: 'business',
      header: 'Business',
      width: '28%',
      render: (biz) => (
        <div className="flex min-w-0 flex-col">
          <span className="truncate font-medium text-ops-text-primary">{biz.name}</span>
          <span className="mt-0.5 truncate font-mono text-[11px] text-ops-text-secondary">
            {biz.id}
          </span>
        </div>
      ),
    },
    {
      key: 'plan',
      header: 'Plan',
      width: '13%',
      render: (biz) => (
        <span className="text-ops-text-primary">{biz.plan_name || 'Unassigned'}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      width: '19%',
      render: (biz) => (
        <div className="flex flex-wrap items-center gap-1.5">
          {biz.status === 'suspended' ? (
            <>
              <StatusBadge
                tone={subscriptionTone(biz.subscription_status)}
                label={subscriptionLabel(biz.subscription_status)}
              />
              <StatusBadge tone="critical" label="Suspended" />
            </>
          ) : (
            <StatusBadge
              tone={subscriptionTone(biz.subscription_status)}
              label={subscriptionLabel(biz.subscription_status)}
            />
          )}
        </div>
      ),
    },
    {
      key: 'trial-end',
      header: 'Trial end / Renews',
      width: '18%',
      render: (biz) => renderTrialCell(biz),
    },
    {
      key: 'outlets',
      header: 'Outlets used',
      width: '11%',
      render: (biz) => (
        <span className="tabular-nums text-ops-text-primary">
          {biz.outlets?.length || 0} / {biz.max_outlets !== null && biz.max_outlets !== undefined ? biz.max_outlets : '∞'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      width: '11%',
      render: (biz) => (
        <button
          type="button"
          onClick={() => handleOpenEditModal(biz)}
          className="h-8 rounded-md px-2 text-[13px] font-medium text-ops-accent transition-colors hover:bg-ops-canvas focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
        >
          Edit
        </button>
      ),
    },
  ];

  const pageHeader = (
    <PageHeader
      title="Subscriptions"
      description="Manage commercial plans, billing cycles, trial windows, and outlet quotas."
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

  const outletPct =
    outletStats.totalOutlets > 0
      ? Math.round((outletStats.activeOutlets / outletStats.totalOutlets) * 100)
      : 0;

  return (
    <div className="space-y-6">
      {pageHeader}

      {successBannerMessage && (
        <div
          role="status"
          className="rounded-md border border-ops-status-active-bg bg-ops-status-active-bg/60 px-4 py-3 text-[13px] text-ops-status-active-text"
        >
          {successBannerMessage}
        </div>
      )}

      <section
        aria-label="Subscription metrics"
        className="grid grid-cols-1 gap-4 sm:grid-cols-3"
      >
        <StatBlock caption="Active subscriptions" value={activeCount} />
        <StatBlock
          caption="Active outlets"
          value={`${outletStats.activeOutlets} / ${outletStats.totalOutlets}`}
          badge={
            outletStats.totalOutlets > 0 ? (
              <span className="text-xs text-ops-text-secondary">{outletPct}% active</span>
            ) : undefined
          }
        />
        <StatBlock
          caption="Past due"
          value={pastDueCount}
          badge={
            pastDueCount > 0 ? (
              <StatusBadge
                tone="critical"
                label={`${pastDueCount} account${pastDueCount === 1 ? '' : 's'}`}
              />
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
              placeholder="Search business or plan..."
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
            className={opsInputClass}
            aria-label="Filter Subscription Status"
          >
            <option value="all">All subscription statuses</option>
            <option value="trial">Trial</option>
            <option value="active">Active (paid)</option>
            <option value="past_due">Past due</option>
            <option value="cancelled">Cancelled</option>
          </select>

          <select
            value={trialFilter}
            onChange={(e) => setTrialFilter(e.target.value)}
            className={opsInputClass}
            aria-label="Filter Trial Dates"
          >
            <option value="all">All trial periods</option>
            <option value="expiring_soon">Expiring in &lt; 7 days</option>
            <option value="expired">Expired trials</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className={opsInputClass}
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
              {filteredBusinesses.length}
            </span>{' '}
            of <span className="font-semibold text-ops-text-primary">{businesses.length}</span>{' '}
            business subscriptions
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
          description="Subscriptions appear here once businesses are provisioned."
        />
      ) : filteredBusinesses.length === 0 ? (
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
          rows={filteredBusinesses}
          rowKey={(biz) => biz.id}
          minWidth="840px"
          footer={
            <span>
              Showing {filteredBusinesses.length} of {businesses.length} total subscriptions
            </span>
          }
        />
      )}

      <SubscriptionEditModal
        business={selectedBizForEdit}
        isOpen={isEditModalOpen}
        onClose={() => {
          setIsEditModalOpen(false);
          setSelectedBizForEdit(null);
        }}
        onSuccess={handleModalSuccess}
        token={token}
      />
    </div>
  );
};
