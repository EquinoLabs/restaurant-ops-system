import React, { useState, useMemo } from 'react';
import { PlatformBusiness, PlatformOutlet } from '../../types/platform';
import { OutletDetailDrawer } from './OutletDetailDrawer';

export interface BusinessDirectoryProps {
  businesses: PlatformBusiness[];
  loading: boolean;
  error: string | null;
  successMessage?: string | null;
  onRetry?: () => void;
  onOpenProvisionModal?: () => void;
  onOpenSubscriptionModal?: (biz: PlatformBusiness) => void;
  onOpenOutletModal?: (biz: PlatformBusiness) => void;
  onOpenOwnerModal?: (bizId: string, outlet: PlatformOutlet) => void;
}

export function filterBusinesses(
  businesses: PlatformBusiness[],
  searchQuery: string,
  statusFilter: string,
  subscriptionFilter: string
): PlatformBusiness[] {
  const q = searchQuery.trim().toLowerCase();

  return businesses.filter((biz) => {
    // Search match against business name, plan tier, or any outlet name / public slug
    const matchesSearch =
      !q ||
      biz.name.toLowerCase().includes(q) ||
      (biz.plan_name && biz.plan_name.toLowerCase().includes(q)) ||
      biz.outlets?.some(
        (o) =>
          o.name.toLowerCase().includes(q) ||
          o.public_slug.toLowerCase().includes(q)
      );

    // Operational status match (Active vs Suspended)
    const matchesStatus = statusFilter === 'all' || biz.status === statusFilter;

    // Subscription status match (Trial, Active, Past Due, Cancelled)
    const matchesSubscription =
      subscriptionFilter === 'all' || biz.subscription_status === subscriptionFilter;

    return matchesSearch && matchesStatus && matchesSubscription;
  });
}

export const BusinessDirectory: React.FC<BusinessDirectoryProps> = ({
  businesses,
  loading,
  error,
  successMessage,
  onRetry,
  onOpenProvisionModal,
  onOpenSubscriptionModal,
  onOpenOutletModal,
  onOpenOwnerModal,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [subscriptionFilter, setSubscriptionFilter] = useState<string>('all');

  // Drawer state
  const [selectedBizForDrawer, setSelectedBizForDrawer] = useState<PlatformBusiness | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const filteredBusinesses = useMemo(
    () => filterBusinesses(businesses, searchQuery, statusFilter, subscriptionFilter),
    [businesses, searchQuery, statusFilter, subscriptionFilter]
  );

  const hasActiveFilters = searchQuery.trim() !== '' || statusFilter !== 'all' || subscriptionFilter !== 'all';

  const handleClearFilters = () => {
    setSearchQuery('');
    setStatusFilter('all');
    setSubscriptionFilter('all');
  };

  const handleOpenDrawer = (biz: PlatformBusiness) => {
    setSelectedBizForDrawer(biz);
    setIsDrawerOpen(true);
  };

  const handleCloseDrawer = () => {
    setIsDrawerOpen(false);
    setSelectedBizForDrawer(null);
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
        <p className="text-sm font-medium">Loading platform business directory...</p>
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
          <h3 className="text-base font-bold">Failed to load business directory</h3>
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
      {/* Directory Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-extrabold text-white tracking-tight">Businesses & Outlets Directory</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Cross-tenant directory with client-side search, multi-filter criteria, and outlet detail inspection
          </p>
        </div>
        {onOpenProvisionModal && (
          <button
            onClick={onOpenProvisionModal}
            className="px-4 py-2.5 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold transition-all shadow-lg shadow-indigo-500/20 flex items-center space-x-1.5 shrink-0 self-start sm:self-auto"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            <span>Provision Business</span>
          </button>
        )}
      </div>

      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-medium">
          {successMessage}
        </div>
      )}

      {/* Search & Filter Toolbar */}
      <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-2xl space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {/* Search Input */}
          <div className="md:col-span-2 relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by business name, plan, outlet, or slug..."
              className="w-full pl-9 pr-8 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white text-xs placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-white text-xs"
                aria-label="Clear Search Input"
              >
                ✕
              </button>
            )}
          </div>

          {/* Operational Status Filter */}
          <div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              aria-label="Filter by Operational Status"
            >
              <option value="all">All Account Statuses</option>
              <option value="active">Active Only</option>
              <option value="suspended">Suspended Only</option>
            </select>
          </div>

          {/* Subscription Status Filter */}
          <div>
            <select
              value={subscriptionFilter}
              onChange={(e) => setSubscriptionFilter(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-white text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              aria-label="Filter by Subscription Status"
            >
              <option value="all">All Subscriptions</option>
              <option value="trial">Trial</option>
              <option value="active">Active (Paid)</option>
              <option value="past_due">Past Due</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
        </div>

        {/* Counter and Active Filters Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs text-slate-400 gap-2 pt-2 border-t border-slate-800/80">
          <div>
            <span>
              Showing <strong className="text-white font-bold">{filteredBusinesses.length}</strong> of{' '}
              <strong className="text-white font-bold">{businesses.length}</strong> registered businesses
            </span>
            <span className="ml-2 text-[10px] text-slate-500 italic">(Client-side Filter)</span>
          </div>

          {hasActiveFilters && (
            <button
              onClick={handleClearFilters}
              className="text-xs font-bold text-indigo-400 hover:text-indigo-300 underline self-start sm:self-auto"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Directory Cards */}
      {businesses.length === 0 ? (
        <div className="p-12 text-center text-slate-400 bg-slate-900/60 border border-slate-800 rounded-2xl space-y-3">
          <svg className="w-12 h-12 text-slate-600 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5m3 0h1m-4-8l2-2m0 0l2 2m-2-2v4" />
          </svg>
          <p className="text-sm font-semibold text-slate-300">No tenant businesses registered yet.</p>
          <p className="text-xs text-slate-500">Provision your first client business to start managing outlets.</p>
          {onOpenProvisionModal && (
            <button
              onClick={onOpenProvisionModal}
              className="mt-2 px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold transition-all shadow-lg shadow-indigo-500/20"
            >
              Provision Business
            </button>
          )}
        </div>
      ) : filteredBusinesses.length === 0 ? (
        <div className="p-12 text-center text-slate-400 bg-slate-900/60 border border-slate-800 rounded-2xl space-y-3">
          <svg className="w-12 h-12 text-slate-600 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <p className="text-sm font-semibold text-slate-300">No businesses match the current search and filter criteria.</p>
          <p className="text-xs text-slate-500">Try adjusting your keywords or clearing the status filters.</p>
          <button
            onClick={handleClearFilters}
            className="mt-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-slate-700 text-xs font-bold transition-colors"
          >
            Clear All Filters
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {filteredBusinesses.map((biz) => {
            const currentOutletCount = biz.outlets?.length || 0;
            const maxOutlets = biz.max_outlets;
            const isLimitReached = maxOutlets !== null && maxOutlets !== undefined && currentOutletCount >= maxOutlets;

            return (
              <div key={biz.id} className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-sm">
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-slate-800">
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="text-base font-bold text-white">{biz.name}</h3>
                    {renderAccountBadge(biz.status)}
                    {renderSubscriptionBadge(biz.subscription_status)}
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700 capitalize">
                      {biz.plan_name ? `${biz.plan_name} Plan` : 'No Plan Set'}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase ${
                      isLimitReached
                        ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                        : 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30'
                    }`}>
                      {currentOutletCount} / {maxOutlets !== null && maxOutlets !== undefined ? `${maxOutlets} Outlets` : '∞ Outlets'}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 self-start lg:self-auto">
                    <button
                      onClick={() => handleOpenDrawer(biz)}
                      className="px-3 py-1.5 rounded-xl bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-semibold transition-colors flex items-center space-x-1"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                      <span>Inspect Outlets ({currentOutletCount})</span>
                    </button>

                    {onOpenSubscriptionModal && (
                      <button
                        onClick={() => onOpenSubscriptionModal(biz)}
                        className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-semibold transition-colors flex items-center space-x-1"
                      >
                        <svg className="w-3.5 h-3.5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                        <span>Edit Plan</span>
                      </button>
                    )}

                    {onOpenOutletModal && (
                      <button
                        disabled={isLimitReached}
                        onClick={() => onOpenOutletModal(biz)}
                        title={isLimitReached ? `Cannot add outlet. Limit of ${maxOutlets} reached.` : 'Add Outlet'}
                        className={`px-3 py-1.5 rounded-xl border text-xs font-semibold transition-colors flex items-center space-x-1 ${
                          isLimitReached
                            ? 'bg-slate-800/40 text-slate-500 border-slate-800 cursor-not-allowed'
                            : 'bg-slate-800 hover:bg-slate-700 text-indigo-400 border-slate-700'
                        }`}
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                        </svg>
                        <span>Add Outlet</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Outlets Summary Grid */}
                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                  {biz.outlets?.map((outlet) => (
                    <div key={outlet.id} className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 flex flex-col justify-between">
                      <div>
                        <div className="flex items-center justify-between">
                          <h4 className="text-sm font-bold text-white">{outlet.name}</h4>
                          <span className="text-[10px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                            /m/{outlet.public_slug}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-slate-400">
                          {outlet.address || 'No physical address specified'} • {outlet.currency} ({outlet.timezone})
                        </p>
                      </div>

                      <div className="mt-4 pt-3 border-t border-slate-700/60 flex items-center justify-between">
                        <a
                          href={`/m/${outlet.public_slug}`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs font-semibold text-emerald-400 hover:underline flex items-center space-x-1"
                        >
                          <span>Preview Live Menu</span>
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </a>

                        {onOpenOwnerModal && (
                          <button
                            onClick={() => onOpenOwnerModal(biz.id, outlet)}
                            className="px-2.5 py-1 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-xs font-semibold transition-colors"
                          >
                            Assign Owner
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Outlet Detail Drawer */}
      <OutletDetailDrawer
        business={selectedBizForDrawer}
        isOpen={isDrawerOpen}
        onClose={handleCloseDrawer}
        onAddOutlet={onOpenOutletModal}
        onEditSubscription={onOpenSubscriptionModal}
        onAssignOwner={onOpenOwnerModal}
      />
    </div>
  );
};
