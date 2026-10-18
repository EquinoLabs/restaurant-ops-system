import React, { useState, useMemo } from 'react';
import { Plus, Search } from 'lucide-react';
import { PlatformBusiness, PlatformOutlet } from '@roms/shared-types';
import {
  Button,
  DataTable,
  PageHeader,
  StateBlock,
  StatusBadge,
  type DataTableColumn,
  type StatusTone,
} from '../../components/ops-ui';
import { opsInputClass, opsSelectClass } from '../../components/ops-ui/FormField';

export interface BusinessDirectoryProps {
  businesses: PlatformBusiness[];
  loading: boolean;
  error: string | null;
  successMessage?: string | null;
  onRetry?: () => void;
  onOpenProvisionModal?: () => void;
  onViewBusiness?: (businessId: string) => void;
  onOpenSubscriptionModal?: (biz: PlatformBusiness) => void;
  onOpenOutletModal?: (biz: PlatformBusiness) => void;
  onOpenOwnerModal?: (bizId: string, outlet: PlatformOutlet) => void;
  onBusinessUpdated?: (updatedBiz: PlatformBusiness) => void;
}

export function filterBusinesses(
  businesses: PlatformBusiness[],
  searchQuery: string,
  statusFilter: string,
  subscriptionFilter: string
): PlatformBusiness[] {
  const q = searchQuery.trim().toLowerCase();

  return businesses.filter((biz) => {
    const matchesSearch =
      !q ||
      biz.name.toLowerCase().includes(q) ||
      (biz.plan_name && biz.plan_name.toLowerCase().includes(q)) ||
      biz.outlets?.some(
        (o) =>
          o.name.toLowerCase().includes(q) ||
          o.public_slug.toLowerCase().includes(q)
      );

    const matchesStatus = statusFilter === 'all' || biz.status === statusFilter;
    const matchesSubscription =
      subscriptionFilter === 'all' || biz.subscription_status === subscriptionFilter;

    return matchesSearch && matchesStatus && matchesSubscription;
  });
}

export function formatCreatedAt(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function handleBusinessRowClick(businessId: string): void {
  window.location.href = `/platform/businesses/${businessId}`;
}

export function subscriptionTone(status?: string): StatusTone {
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

export function subscriptionLabel(status?: string): string {
  switch (status) {
    case 'active':
      return 'Active';
    case 'past_due':
      return 'Past due';
    case 'cancelled':
      return 'Cancelled';
    case 'trial':
      return 'Trial';
    default:
      return 'Trial';
  }
}

export function accountTone(status: string): StatusTone {
  return status === 'suspended' ? 'critical' : 'active';
}

export function accountLabel(status: string): string {
  return status === 'suspended' ? 'Suspended' : 'Active';
}

export const BusinessDirectory: React.FC<BusinessDirectoryProps> = ({
  businesses,
  loading,
  error,
  successMessage,
  onRetry,
  onOpenProvisionModal,
  onViewBusiness,
}) => {
  const handleRowClick = (biz: PlatformBusiness) => {
    onViewBusiness?.(biz.id);
  };

  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [subscriptionFilter, setSubscriptionFilter] = useState<string>('all');

  const filteredBusinesses = useMemo(
    () => filterBusinesses(businesses, searchQuery, statusFilter, subscriptionFilter),
    [businesses, searchQuery, statusFilter, subscriptionFilter]
  );

  const hasActiveFilters =
    searchQuery.trim() !== '' || statusFilter !== 'all' || subscriptionFilter !== 'all';

  const handleClearFilters = () => {
    setSearchQuery('');
    setStatusFilter('all');
    setSubscriptionFilter('all');
  };

  const columns: DataTableColumn<PlatformBusiness>[] = [
    {
      key: 'business',
      header: 'Business',
      width: '34%',
      getTitle: (biz) => biz.name,
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
      key: 'status',
      header: 'Status',
      width: '26%',
      render: (biz) => (
        <div className="flex flex-wrap items-center gap-1.5">
          <StatusBadge tone={accountTone(biz.status)} label={accountLabel(biz.status)} />
          <StatusBadge
            tone={subscriptionTone(biz.subscription_status)}
            label={subscriptionLabel(biz.subscription_status)}
          />
        </div>
      ),
    },
    {
      key: 'outlets',
      header: 'Outlets',
      width: '20%',
      tabular: true,
      render: (biz) => {
        const outlets = biz.outlets || [];
        const activeOutlets = outlets.filter((o) => o.status === 'active').length;
        return (
          <span className="tabular-nums text-ops-text-primary">
            {activeOutlets} active / {outlets.length} total
          </span>
        );
      },
    },
    {
      key: 'created',
      header: 'Created',
      width: '20%',
      tabular: true,
      render: (biz) => (
        <span className="tabular-nums text-ops-text-secondary">{formatCreatedAt(biz.created_at)}</span>
      ),
    },
  ];

  if (loading && businesses.length === 0) {
    return (
      <div>
        <PageHeader
          title="Businesses"
          description="Manage customer businesses and their outlets."
        />
        <StateBlock variant="loading" title="Loading businesses" />
      </div>
    );
  }

  if (error && businesses.length === 0) {
    return (
      <div>
        <PageHeader
          title="Businesses"
          description="Manage customer businesses and their outlets."
        />
        <StateBlock
          variant="error"
          title="Could not load businesses"
          description={error}
          actionLabel="Retry"
          onAction={onRetry}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Businesses"
        description="One row per registered business with search, status filters, and links to detail pages."
        action={
          onOpenProvisionModal ? (
            <Button variant="primary" onClick={onOpenProvisionModal}>
              <Plus className="h-3.5 w-3.5" aria-hidden="true" />
              Add business
            </Button>
          ) : undefined
        }
      />

      {successMessage && (
        <div
          role="status"
          className="rounded-md border border-ops-status-active-bg bg-ops-status-active-bg/60 px-4 py-3 text-[13px] text-ops-status-active-text"
        >
          {successMessage}
        </div>
      )}

      <div className="rounded-md border border-ops-border bg-white p-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <div className="relative md:col-span-2">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-2.5 text-ops-text-secondary">
              <Search className="h-4 w-4" aria-hidden="true" />
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by business name, plan, outlet, or slug..."
              aria-label="Search businesses"
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
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className={opsSelectClass}
            aria-label="Filter by Operational Status"
          >
            <option value="all">All account statuses</option>
            <option value="active">Active only</option>
            <option value="suspended">Suspended only</option>
          </select>

          <select
            value={subscriptionFilter}
            onChange={(e) => setSubscriptionFilter(e.target.value)}
            className={opsSelectClass}
            aria-label="Filter by Subscription Status"
          >
            <option value="all">All subscriptions</option>
            <option value="trial">Trial</option>
            <option value="active">Active (paid)</option>
            <option value="past_due">Past due</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        <div className="mt-4 flex flex-col gap-2 border-t border-ops-divider pt-3 text-xs text-ops-text-secondary sm:flex-row sm:items-center sm:justify-between">
          <div>
            Showing{' '}
            <span className="font-semibold text-ops-text-primary">
              {filteredBusinesses.length}
            </span>{' '}
            of{' '}
            <span className="font-semibold text-ops-text-primary">{businesses.length}</span>{' '}
            businesses
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
          title="No businesses yet"
          description="Add your first business to start managing outlets."
          actionLabel={onOpenProvisionModal ? 'Add business' : undefined}
          onAction={onOpenProvisionModal}
        />
      ) : filteredBusinesses.length === 0 ? (
        <StateBlock
          variant="no-results"
          title="No businesses match the current search and filter criteria."
          description="Try adjusting your keywords or clearing the status filters."
          actionLabel="Clear All Filters"
          onAction={handleClearFilters}
        />
      ) : (
        <DataTable
          columns={columns}
          rows={filteredBusinesses}
          rowKey={(biz) => biz.id}
          minWidth="720px"
          onRowClick={handleRowClick}
          footer={
            <span>
              {filteredBusinesses.length} of {businesses.length} businesses
            </span>
          }
        />
      )}
    </div>
  );
};
