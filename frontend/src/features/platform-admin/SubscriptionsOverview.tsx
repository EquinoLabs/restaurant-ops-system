import React, { useState, useMemo } from 'react';
import { PlatformBusiness } from '../../types/platform';
import { SubscriptionEditModal } from './SubscriptionEditModal';

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

  // Edit Modal State
  const [selectedBizForEdit, setSelectedBizForEdit] = useState<PlatformBusiness | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [successBannerMessage, setSuccessBannerMessage] = useState<string | null>(null);

  const nowMs = referenceDate.getTime();
  const sevenDaysMs = 7 * 24 * 60 * 60 * 1000;

  // Counts for quick filter tabs
  const upcomingCount = useMemo(() => {
    return businesses.filter((b) => {
      if (b.subscription_status !== 'trial' || !b.trial_ends_at) return false;
      const trialEndMs = new Date(b.trial_ends_at).getTime();
      return !isNaN(trialEndMs) && trialEndMs >= nowMs && trialEndMs <= nowMs + sevenDaysMs;
    }).length;
  }, [businesses, nowMs, sevenDaysMs]);

  const pastDueCount = useMemo(() => {
    return businesses.filter((b) => b.subscription_status === 'past_due').length;
  }, [businesses]);

  const activeCount = useMemo(() => {
    return businesses.filter((b) => b.subscription_status === 'active').length;
  }, [businesses]);

  const cancelledCount = useMemo(() => {
    return businesses.filter((b) => b.subscription_status === 'cancelled').length;
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

  const renderSubscriptionBadge = (subStatus: string) => {
    switch (subStatus) {
      case 'active':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 uppercase">Active Sub</span>;
      case 'past_due':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30 uppercase">Past Due</span>;
      case 'cancelled':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-400 border border-red-500/30 uppercase">Cancelled</span>;
      case 'trial':
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/20 text-sky-400 border border-sky-500/30 uppercase">Trial</span>;
    }
  };

  const renderAccountBadge = (status: string) => {
    if (status === 'suspended') {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30 uppercase">Suspended</span>;
    }
    return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 uppercase">Active</span>;
  };

  if (loading && businesses.length === 0) {
    return (
      <div className="py-20 text-center text-slate-400">
        <div className="w-10 h-10 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin mx-auto mb-4"></div>
        <p className="text-sm font-medium">Loading platform subscriptions...</p>
      </div>
    );
  }

  if (error && businesses.length === 0) {
    return (
      <div className="p-6 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400">
        <div className="flex items-center space-x-3 mb-3">
          <svg className="w-6 h-6 text-red-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <h3 className="text-base font-bold">Failed to load subscription data</h3>
        </div>
        <p className="text-xs text-red-300 mb-4">{error}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="px-4 py-2 rounded-xl bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-200 text-xs font-bold transition-colors"
          >
            Retry Loading
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-slate-800">
        <h1 className="text-xl font-extrabold text-white tracking-tight">Subscription & Billing Tiers</h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Manage tenant plan tiers, outlet capacities, evaluation trials, and past-due billing statuses
        </p>
      </div>

      {successBannerMessage && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-medium flex items-center justify-between">
          <span>{successBannerMessage}</span>
          <button onClick={() => setSuccessBannerMessage(null)} className="text-emerald-400 hover:text-emerald-200 ml-4 font-bold">
            ✕
          </button>
        </div>
      )}

      {/* Quick Filter Category Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <button
          onClick={() => {
            setSubscriptionFilter('all');
            setTrialFilter('expiring_soon');
          }}
          className={`p-3.5 rounded-2xl border text-left transition-all ${
            trialFilter === 'expiring_soon'
              ? 'bg-amber-500/15 border-amber-500/40 text-amber-300'
              : 'bg-slate-900/80 border-slate-800 text-slate-300 hover:border-slate-700'
          }`}
        >
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Trials Expiring &lt;7d</span>
          <span className="text-2xl font-black text-amber-400 mt-1 block">{upcomingCount}</span>
        </button>

        <button
          onClick={() => {
            setTrialFilter('all');
            setSubscriptionFilter('past_due');
          }}
          className={`p-3.5 rounded-2xl border text-left transition-all ${
            subscriptionFilter === 'past_due'
              ? 'bg-rose-500/15 border-rose-500/40 text-rose-300'
              : 'bg-slate-900/80 border-slate-800 text-slate-300 hover:border-slate-700'
          }`}
        >
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Past-Due Accounts</span>
          <span className="text-2xl font-black text-rose-400 mt-1 block">{pastDueCount}</span>
        </button>

        <button
          onClick={() => {
            setTrialFilter('all');
            setSubscriptionFilter('active');
          }}
          className={`p-3.5 rounded-2xl border text-left transition-all ${
            subscriptionFilter === 'active'
              ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
              : 'bg-slate-900/80 border-slate-800 text-slate-300 hover:border-slate-700'
          }`}
        >
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Paid Active Subscriptions</span>
          <span className="text-2xl font-black text-emerald-400 mt-1 block">{activeCount}</span>
        </button>

        <button
          onClick={() => {
            setTrialFilter('all');
            setSubscriptionFilter('cancelled');
          }}
          className={`p-3.5 rounded-2xl border text-left transition-all ${
            subscriptionFilter === 'cancelled'
              ? 'bg-red-500/15 border-red-500/40 text-red-300'
              : 'bg-slate-900/80 border-slate-800 text-slate-300 hover:border-slate-700'
          }`}
        >
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">Cancelled Subscriptions</span>
          <span className="text-2xl font-black text-red-400 mt-1 block">{cancelledCount}</span>
        </button>
      </div>

      {/* Toolbar & Filters */}
      <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-2xl space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {/* Search Input */}
          <div className="md:col-span-1 relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search business or plan..."
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white text-xs placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            />
          </div>

          {/* Subscription Status Filter */}
          <div>
            <select
              value={subscriptionFilter}
              onChange={(e) => setSubscriptionFilter(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              aria-label="Filter Subscription Status"
            >
              <option value="all">All Subscription Statuses</option>
              <option value="trial">Trial</option>
              <option value="active">Active (Paid)</option>
              <option value="past_due">Past Due</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          {/* Trial Filter Dropdown */}
          <div>
            <select
              value={trialFilter}
              onChange={(e) => setTrialFilter(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              aria-label="Filter Trial Dates"
            >
              <option value="all">All Trial Periods</option>
              <option value="expiring_soon">Expiring in &lt; 7 Days</option>
              <option value="expired">Expired Trials</option>
            </select>
          </div>

          {/* Operational Status Filter */}
          <div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              aria-label="Filter Operational Account Status"
            >
              <option value="all">All Account Statuses</option>
              <option value="active">Operational Active</option>
              <option value="suspended">Operational Suspended</option>
            </select>
          </div>
        </div>

        {/* Counter and Reset */}
        <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800/80">
          <span>
            Showing <strong className="text-white">{filteredBusinesses.length}</strong> of{' '}
            <strong className="text-white">{businesses.length}</strong> business subscriptions
          </span>
          {hasActiveFilters && (
            <button
              onClick={handleClearFilters}
              className="text-indigo-400 hover:text-indigo-300 font-bold underline"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Subscription Table */}
      {businesses.length === 0 ? (
        <div className="p-12 text-center text-slate-400 bg-slate-900/60 border border-slate-800 rounded-2xl space-y-2">
          <p className="text-sm font-semibold text-slate-300">No subscriptions found.</p>
        </div>
      ) : filteredBusinesses.length === 0 ? (
        <div className="p-12 text-center text-slate-400 bg-slate-900/60 border border-slate-800 rounded-2xl space-y-3">
          <p className="text-sm font-semibold text-slate-300">No subscriptions match criteria.</p>
          <button
            onClick={handleClearFilters}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-slate-700 text-xs font-bold"
          >
            Reset Filters
          </button>
        </div>
      ) : (
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-400 bg-slate-900/80">
                  <th className="py-3.5 px-6">Business Name</th>
                  <th className="py-3.5 px-4">Plan Tier</th>
                  <th className="py-3.5 px-4">Subscription Status</th>
                  <th className="py-3.5 px-4">Operational Status</th>
                  <th className="py-3.5 px-4">Trial Expiration</th>
                  <th className="py-3.5 px-4 text-center">Outlet Limit</th>
                  <th className="py-3.5 px-6 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-xs">
                {filteredBusinesses.map((biz) => {
                  const currentOutlets = biz.outlets?.length || 0;
                  const maxOutlets = biz.max_outlets;

                  let trialBadge = null;
                  if (biz.trial_ends_at) {
                    const trialEndMs = new Date(biz.trial_ends_at).getTime();
                    if (!isNaN(trialEndMs)) {
                      if (trialEndMs < nowMs) {
                        trialBadge = <span className="text-red-400 font-semibold text-[11px]">Expired</span>;
                      } else if (trialEndMs <= nowMs + sevenDaysMs) {
                        trialBadge = (
                          <span className="text-amber-400 font-semibold text-[11px]">
                            Expiring {new Date(biz.trial_ends_at).toLocaleDateString()}
                          </span>
                        );
                      } else {
                        trialBadge = (
                          <span className="text-slate-400 font-mono text-[11px]">
                            {new Date(biz.trial_ends_at).toLocaleDateString()}
                          </span>
                        );
                      }
                    }
                  } else {
                    trialBadge = <span className="text-slate-500 text-[11px]">N/A</span>;
                  }

                  return (
                    <tr key={biz.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-4 px-6 font-bold text-white">
                        <div>{biz.name}</div>
                        <div className="text-[10px] text-slate-500 font-mono font-normal">
                          ID: {biz.id}
                        </div>
                      </td>
                      <td className="py-4 px-4 text-slate-300 capitalize font-medium">
                        {biz.plan_name ? `${biz.plan_name}` : 'Unassigned'}
                      </td>
                      <td className="py-4 px-4">{renderSubscriptionBadge(biz.subscription_status)}</td>
                      <td className="py-4 px-4">{renderAccountBadge(biz.status)}</td>
                      <td className="py-4 px-4">{trialBadge}</td>
                      <td className="py-4 px-4 text-center font-bold text-slate-300">
                        {currentOutlets} / {maxOutlets !== null && maxOutlets !== undefined ? maxOutlets : '∞'}
                      </td>
                      <td className="py-4 px-6 text-right">
                        <button
                          onClick={() => handleOpenEditModal(biz)}
                          className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-slate-700 text-xs font-semibold transition-colors flex items-center space-x-1 ml-auto"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                          <span>Manage Subscription</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Edit Subscription Modal */}
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
