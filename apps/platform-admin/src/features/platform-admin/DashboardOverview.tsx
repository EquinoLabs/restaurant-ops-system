import { PlatformBusiness, PlatformAuditLogItem } from '@roms/shared-types';
import { PlatformTab } from './PlatformShell';

export interface DashboardOverviewProps {
  businesses: PlatformBusiness[];
  recentAuditLogs?: PlatformAuditLogItem[];
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
  onNavigateTab?: (tab: PlatformTab) => void;
  onOpenProvisionModal?: () => void;
  referenceDate?: Date;
}

export function calculateDashboardMetrics(businesses: PlatformBusiness[], referenceDate: Date = new Date()) {
  const totalBusinesses = businesses.length;
  const totalOutlets = businesses.reduce((sum, b) => sum + (b.outlets?.length || 0), 0);
  const businessesInTrial = businesses.filter((b) => b.subscription_status === 'trial').length;

  const nowMs = referenceDate.getTime();
  const sevenDaysMs = 7 * 24 * 60 * 60 * 1000;

  const upcomingExpirations = businesses.filter((b) => {
    if (b.subscription_status !== 'trial' || !b.trial_ends_at) return false;
    const trialEndMs = new Date(b.trial_ends_at).getTime();
    if (isNaN(trialEndMs)) return false;
    return trialEndMs >= nowMs && trialEndMs <= nowMs + sevenDaysMs;
  }).length;

  const pastDueSubscriptions = businesses.filter((b) => b.subscription_status === 'past_due').length;

  const activeAccountCount = businesses.filter((b) => b.status === 'active').length;
  const suspendedAccountCount = businesses.filter((b) => b.status === 'suspended').length;

  return {
    totalBusinesses,
    totalOutlets,
    businessesInTrial,
    upcomingExpirations,
    pastDueSubscriptions,
    activeAccountCount,
    suspendedAccountCount,
  };
}

export const DashboardOverview: React.FC<DashboardOverviewProps> = ({
  businesses,
  recentAuditLogs = [],
  loading,
  error,
  onRetry,
  onNavigateTab,
  onOpenProvisionModal,
  referenceDate,
}) => {
  if (loading && businesses.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-400">
        <div className="w-10 h-10 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin mb-4"></div>
        <p className="text-sm font-medium">Loading platform metrics...</p>
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
          <h3 className="text-base font-bold">Failed to load platform data</h3>
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

  const metrics = calculateDashboardMetrics(businesses, referenceDate);

  // Sort businesses by created_at descending for recent registrations table
  const sortedBusinesses = [...businesses].sort((a, b) => {
    const dateA = new Date(a.created_at || 0).getTime();
    const dateB = new Date(b.created_at || 0).getTime();
    return dateB - dateA;
  });

  const activeRatio = metrics.totalBusinesses > 0
    ? Math.round((metrics.activeAccountCount / metrics.totalBusinesses) * 100)
    : 100;

  return (
    <div className="space-y-8">
      {/* Banner / Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight">Platform Overview</h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time SaaS control plane metrics, trial monitor, and tenant health
          </p>
        </div>
        {onOpenProvisionModal && (
          <button
            onClick={onOpenProvisionModal}
            className="px-4 py-2.5 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold transition-all shadow-lg shadow-indigo-500/20 flex items-center space-x-2 shrink-0 self-start sm:self-auto"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            <span>Provision New Business</span>
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-center justify-between">
          <span>{error}</span>
          {onRetry && (
            <button onClick={onRetry} className="underline font-bold text-red-300 ml-4">
              Retry
            </button>
          )}
        </div>
      )}

      {/* Quick Operational Shortcuts */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <button
          onClick={() => onNavigateTab && onNavigateTab('businesses')}
          className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-indigo-500/50 flex items-center space-x-3 text-left transition group"
        >
          <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 group-hover:bg-indigo-500/20">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5m3 0h1m-4-8l2-2m0 0l2 2m-2-2v4" />
            </svg>
          </div>
          <div>
            <div className="text-xs font-bold text-white">Businesses</div>
            <div className="text-[10px] text-slate-400">Directory & Outlets</div>
          </div>
        </button>

        <button
          onClick={() => onNavigateTab && onNavigateTab('plans')}
          className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-sky-500/50 flex items-center space-x-3 text-left transition group"
        >
          <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 group-hover:bg-sky-500/20">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <div>
            <div className="text-xs font-bold text-white">Plan Catalog</div>
            <div className="text-[10px] text-slate-400">Tiers & Features</div>
          </div>
        </button>

        <button
          onClick={() => onNavigateTab && onNavigateTab('subscriptions')}
          className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-amber-500/50 flex items-center space-x-3 text-left transition group"
        >
          <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 group-hover:bg-amber-500/20">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <div>
            <div className="text-xs font-bold text-white">Subscriptions</div>
            <div className="text-[10px] text-slate-400">Entitlements & Plans</div>
          </div>
        </button>

        <button
          onClick={() => onNavigateTab && onNavigateTab('audit-logs')}
          className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-emerald-500/50 flex items-center space-x-3 text-left transition group"
        >
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 group-hover:bg-emerald-500/20">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          </div>
          <div>
            <div className="text-xs font-bold text-white">Audit Trail</div>
            <div className="text-[10px] text-slate-400">Governance History</div>
          </div>
        </button>
      </div>

      {/* 5 Core Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Metric 1: Total Businesses */}
        <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Total Businesses</span>
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5m3 0h1m-4-8l2-2m0 0l2 2m-2-2v4" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <p className="text-3xl font-black text-white">{metrics.totalBusinesses}</p>
            <p className="text-[10px] text-slate-400 mt-1">Tenant accounts in system</p>
          </div>
        </div>

        {/* Metric 2: Total Outlets */}
        <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Total Outlets</span>
            <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <p className="text-3xl font-black text-sky-400">{metrics.totalOutlets}</p>
            <p className="text-[10px] text-slate-400 mt-1">Registered restaurant branches</p>
          </div>
        </div>

        {/* Metric 3: Businesses in Trial */}
        <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Businesses in Trial</span>
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-300">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <p className="text-3xl font-black text-indigo-300">{metrics.businessesInTrial}</p>
            <p className="text-[10px] text-slate-400 mt-1">Evaluating platform</p>
          </div>
        </div>

        {/* Metric 4: Upcoming Expirations */}
        <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Trial Expiring &lt;7d</span>
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <p className="text-3xl font-black text-amber-400">{metrics.upcomingExpirations}</p>
            <p className="text-[10px] text-slate-400 mt-1">Requires subscription conversion</p>
          </div>
        </div>

        {/* Metric 5: Past-Due Subscriptions */}
        <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Past-Due Subscriptions</span>
            <div className="w-8 h-8 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <p className="text-3xl font-black text-rose-400">{metrics.pastDueSubscriptions}</p>
            <p className="text-[10px] text-slate-400 mt-1">Payment failure action needed</p>
          </div>
        </div>
      </div>

      {/* Account Status Breakdown Bar */}
      <div className="bg-slate-900/60 border border-slate-800 p-6 rounded-2xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">Account Operational Status</h3>
            <p className="text-xs text-slate-400 mt-0.5">Enforcement health across all registered businesses</p>
          </div>
          <div className="flex items-center space-x-4 text-xs font-semibold">
            <div className="flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
              <span className="text-slate-300">Active: {metrics.activeAccountCount}</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-400"></span>
              <span className="text-slate-300">Suspended: {metrics.suspendedAccountCount}</span>
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-slate-800 h-3 rounded-full overflow-hidden flex">
          <div
            className="bg-emerald-500 h-full transition-all duration-500"
            style={{ width: `${activeRatio}%` }}
            title={`Active: ${metrics.activeAccountCount} (${activeRatio}%)`}
          />
          <div
            className="bg-rose-500 h-full transition-all duration-500"
            style={{ width: `${100 - activeRatio}%` }}
            title={`Suspended: ${metrics.suspendedAccountCount} (${100 - activeRatio}%)`}
          />
        </div>
      </div>

      {/* Split Section: Needs Attention & Recent Platform Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Panel 1: Needs Attention */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">Needs Attention</h3>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  {metrics.suspendedAccountCount + metrics.pastDueSubscriptions + metrics.upcomingExpirations} Items
                </span>
              </div>
              {onNavigateTab && (
                <button
                  onClick={() => onNavigateTab('businesses')}
                  className="text-xs font-semibold text-indigo-400 hover:text-indigo-300"
                >
                  View All
                </button>
              )}
            </div>

            <div className="mt-3 divide-y divide-slate-800/60">
              {metrics.suspendedAccountCount === 0 && metrics.pastDueSubscriptions === 0 && metrics.upcomingExpirations === 0 ? (
                <div className="py-8 text-center text-slate-400 text-xs">
                  <svg className="w-8 h-8 text-emerald-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="font-semibold text-slate-200">All Systems Operational</p>
                  <p className="text-slate-500 text-[11px] mt-0.5">No accounts require urgent administrative review.</p>
                </div>
              ) : (
                businesses
                  .filter((b) => b.status === 'suspended' || b.subscription_status === 'past_due' || (b.subscription_status === 'trial' && b.trial_ends_at))
                  .slice(0, 5)
                  .map((b) => (
                    <div key={b.id} className="py-2.5 flex items-center justify-between text-xs">
                      <div>
                        <div className="font-bold text-white">{b.name}</div>
                        <div className="text-[10px] text-slate-400">
                          {b.status === 'suspended'
                            ? 'Tenant account suspended'
                            : b.subscription_status === 'past_due'
                            ? 'Subscription payment past due'
                            : 'Trial period active'}
                        </div>
                      </div>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase border ${
                          b.status === 'suspended'
                            ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                            : b.subscription_status === 'past_due'
                            ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                            : 'bg-sky-500/10 text-sky-400 border-sky-500/20'
                        }`}
                      >
                        {b.status === 'suspended' ? 'Suspended' : b.subscription_status}
                      </span>
                    </div>
                  ))
              )}
            </div>
          </div>
        </div>

        {/* Panel 2: Recent Activity */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">Recent Activity</h3>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                  Live Audit Trail
                </span>
              </div>
              {onNavigateTab && (
                <button
                  onClick={() => onNavigateTab('audit-logs')}
                  className="text-xs font-semibold text-indigo-400 hover:text-indigo-300"
                >
                  Full Audit Trail
                </button>
              )}
            </div>

            <div className="mt-3 divide-y divide-slate-800/60">
              {recentAuditLogs.length === 0 ? (
                <div className="py-8 text-center text-slate-400 text-xs">
                  <p className="font-semibold text-slate-300">No Recent Audit Records</p>
                  <p className="text-slate-500 text-[11px] mt-0.5">Platform operations and mutations will appear here.</p>
                </div>
              ) : (
                recentAuditLogs.slice(0, 5).map((log) => {
                  const logDate = log.created_at
                    ? new Date(log.created_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })
                    : '';

                  return (
                    <div key={log.id} className="py-2.5 flex items-center justify-between text-xs">
                      <div>
                        <div className="font-semibold text-white capitalize">
                          {log.action.replace(/_/g, ' ')}
                        </div>
                        <div className="text-[10px] text-slate-400">
                          {log.actor_email || 'System Action'} • {log.business_name || log.entity_type}
                        </div>
                      </div>
                      <span className="text-[10px] font-mono text-slate-500">{logDate}</span>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Recent Registrations Table */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="p-6 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-white">Registered Tenant Directory Overview</h3>
            <p className="text-xs text-slate-400 mt-0.5">Summary listing of active and evaluating businesses</p>
          </div>
          {onNavigateTab && (
            <button
              onClick={() => onNavigateTab('businesses')}
              className="text-xs font-bold text-indigo-400 hover:text-indigo-300 flex items-center space-x-1"
            >
              <span>Manage Directory</span>
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          )}
        </div>

        {businesses.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            <svg className="w-12 h-12 text-slate-600 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5m3 0h1m-4-8l2-2m0 0l2 2m-2-2v4" />
            </svg>
            <p className="text-sm font-semibold text-slate-300">No tenant businesses registered yet.</p>
            <p className="text-xs text-slate-500 mt-1">Get started by provisioning the first SaaS client business.</p>
            {onOpenProvisionModal && (
              <button
                onClick={onOpenProvisionModal}
                className="mt-4 px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold transition-all shadow-lg shadow-indigo-500/20"
              >
                Provision Business
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-400 bg-slate-900/40">
                  <th className="py-3 px-6">Business Name</th>
                  <th className="py-3 px-4">Plan Tier</th>
                  <th className="py-3 px-4">Subscription Status</th>
                  <th className="py-3 px-4">Account Status</th>
                  <th className="py-3 px-4 text-center">Outlets</th>
                  <th className="py-3 px-4">Created Date</th>
                  <th className="py-3 px-6 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-xs">
                {sortedBusinesses.map((biz) => {
                  const createdDate = biz.created_at
                    ? new Date(biz.created_at).toLocaleDateString(undefined, {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                      })
                    : 'N/A';

                  return (
                    <tr key={biz.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-4 px-6 font-bold text-white">
                        <div>{biz.name}</div>
                        {biz.outlets?.[0] && (
                          <div className="text-[10px] text-slate-400 font-normal">
                            Primary: {biz.outlets[0].name} (/m/{biz.outlets[0].public_slug})
                          </div>
                        )}
                      </td>
                      <td className="py-4 px-4 text-slate-300 capitalize">
                        {biz.plan_name ? `${biz.plan_name}` : 'Default'}
                      </td>
                      <td className="py-4 px-4">
                        {biz.subscription_status === 'active' && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 uppercase">
                            Active
                          </span>
                        )}
                        {biz.subscription_status === 'trial' && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/20 text-sky-400 border border-sky-500/30 uppercase">
                            Trial
                          </span>
                        )}
                        {biz.subscription_status === 'past_due' && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30 uppercase">
                            Past Due
                          </span>
                        )}
                        {biz.subscription_status === 'cancelled' && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-400 border border-red-500/30 uppercase">
                            Cancelled
                          </span>
                        )}
                      </td>
                      <td className="py-4 px-4">
                        {biz.status === 'suspended' ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30 uppercase">
                            Suspended
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 uppercase">
                            Active
                          </span>
                        )}
                      </td>
                      <td className="py-4 px-4 text-center font-bold text-slate-300">
                        {biz.outlets?.length || 0} / {biz.max_outlets !== null && biz.max_outlets !== undefined ? biz.max_outlets : '∞'}
                      </td>
                      <td className="py-4 px-4 text-slate-400 font-mono text-[11px]">
                        {createdDate}
                      </td>
                      <td className="py-4 px-6 text-right">
                        {onNavigateTab && (
                          <button
                            onClick={() => onNavigateTab('businesses')}
                            className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-slate-700 text-[11px] font-semibold transition-colors"
                          >
                            View Details
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
