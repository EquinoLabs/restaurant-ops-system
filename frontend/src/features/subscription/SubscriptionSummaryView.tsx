import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../authentication/AuthContext';
import { fetchOwnerSubscriptionSummary } from '../../api/client';
import { OwnerSubscriptionSummary } from '../../types/subscription';

export const SubscriptionSummaryView: React.FC = () => {
  const { token, user, selectedOutlet, setSelectedOutletId, logout } = useAuth();
  const navigate = useNavigate();

  const [summary, setSummary] = useState<OwnerSubscriptionSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const isOwner = selectedOutlet?.role === 'owner' || user?.memberships.some((m) => m.role === 'owner');

  const loadSubscription = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      setError(null);
      const data = await fetchOwnerSubscriptionSummary(token);
      setSummary(data);
    } catch (err: any) {
      if (err.status === 403) {
        setError('You are not authorized as an owner of this business to view subscription details.');
      } else {
        setError(err.message || 'Failed to load subscription information.');
      }
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (isOwner) {
      loadSubscription();
    } else {
      setLoading(false);
    }
  }, [isOwner, loadSubscription]);

  const handleSignOut = () => {
    logout();
    navigate('/login');
  };

  const formatDate = (isoString: string | null) => {
    if (!isoString) return 'N/A';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return isoString;
    }
  };

  const getStatusBadge = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'active') {
      return (
        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          Active
        </span>
      );
    }
    if (s === 'trial') {
      return (
        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
          Trial
        </span>
      );
    }
    if (s === 'expired') {
      return (
        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
          Expired
        </span>
      );
    }
    if (s === 'past_due') {
      return (
        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
          Past Due
        </span>
      );
    }
    return (
      <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-400 border border-slate-500/20">
        {status}
      </span>
    );
  };

  if (!isOwner) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-6 flex flex-col items-center justify-center">
        <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/30 flex items-center justify-center mx-auto text-rose-400">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-white">Owner Access Required</h2>
          <p className="text-sm text-slate-400">
            Subscription and billing information is restricted to business owners. Your current account role does not have permission to view this page.
          </p>
          <div className="pt-2">
            <Link
              to="/admin/menu"
              className="inline-flex items-center justify-center px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 text-sm font-semibold transition-colors"
            >
              Return to Menu Management
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans pb-16">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-40 bg-slate-900/90 backdrop-blur-md border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Link to="/admin/menu" className="flex items-center space-x-2 text-amber-400 font-extrabold text-lg tracking-tight">
              <div className="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/30 flex items-center justify-center">
                <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
              </div>
              <span className="hidden sm:inline">ROMS Admin</span>
            </Link>

            {user && user.memberships.length > 0 && (
              <div className="relative">
                <select
                  value={selectedOutlet?.outlet_id || ''}
                  onChange={(e) => setSelectedOutletId(e.target.value)}
                  className="bg-slate-800 border border-slate-700 text-white text-xs font-semibold rounded-xl px-3 py-2 pr-8 focus:outline-none focus:ring-2 focus:ring-amber-500/50 cursor-pointer"
                >
                  {user.memberships.map((m) => (
                    <option key={m.outlet_id} value={m.outlet_id}>
                      {m.outlet_name} ({m.role.toUpperCase()})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <div className="flex items-center space-x-3">
            <Link
              to="/admin/menu"
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-colors"
            >
              <span>Menu Admin</span>
            </Link>

            <Link
              to="/staff/orders"
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-colors"
            >
              <span>POS Orders</span>
            </Link>

            <button
              onClick={handleSignOut}
              className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-colors"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
        <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800 pb-5">
          <div>
            <h1 className="text-2xl font-black text-white tracking-tight flex items-center space-x-3">
              <span>Business Subscription & Capacity</span>
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Read-only overview of your business plan, active entitlement allowances, and outlet usage.
            </p>
          </div>
          <button
            onClick={loadSubscription}
            disabled={loading}
            className="self-start sm:self-auto inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-colors disabled:opacity-50"
          >
            <svg className={`w-4 h-4 text-slate-400 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>Refresh</span>
          </button>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="py-20 flex flex-col items-center justify-center space-y-4 text-slate-400">
            <div className="w-10 h-10 border-4 border-amber-500/20 border-t-amber-500 rounded-full animate-spin"></div>
            <p className="text-sm font-medium">Loading subscription details...</p>
          </div>
        )}

        {/* Error State */}
        {!loading && error && (
          <div className="bg-rose-500/10 border border-rose-500/30 rounded-2xl p-6 text-rose-300 space-y-3">
            <div className="flex items-center space-x-2 font-bold text-rose-200">
              <svg className="w-5 h-5 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>Unable to load subscription</span>
            </div>
            <p className="text-sm">{error}</p>
            <button
              onClick={loadSubscription}
              className="mt-2 inline-flex items-center px-3.5 py-1.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-xs font-semibold text-rose-200 transition-colors"
            >
              Try Again
            </button>
          </div>
        )}

        {/* Success / Data State */}
        {!loading && !error && summary && (
          <div className="space-y-6">
            {/* Action Required Support Banner (CTA) */}
            {summary.support_cta.requires_action && (
              <div
                data-testid="support-cta-banner"
                className="bg-amber-500/10 border border-amber-500/40 rounded-2xl p-6 text-amber-200 space-y-3 shadow-lg shadow-amber-950/20"
              >
                <div className="flex items-center space-x-2.5 text-base font-bold text-amber-300">
                  <svg className="w-5 h-5 text-amber-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <span>Attention: Subscription Action Required</span>
                </div>
                <p className="text-sm text-amber-100 leading-relaxed">
                  {summary.support_cta.message ||
                    'Your subscription requires attention. Please contact support to maintain uninterrupted service.'}
                </p>
                <div className="pt-1 flex flex-wrap items-center gap-3">
                  <a
                    href={`mailto:${summary.support_cta.support_email}?subject=Subscription%20Support%20Request%20-%20${encodeURIComponent(summary.business_name)}`}
                    className="inline-flex items-center space-x-2 px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-xs transition-colors"
                  >
                    <svg className="w-4 h-4 text-slate-950" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                    <span>Contact {summary.support_cta.support_email}</span>
                  </a>
                  <span className="text-xs text-amber-300/80">
                    Self-service online upgrades are managed via platform administrators.
                  </span>
                </div>
              </div>
            )}

            {/* Top Grid: Plan & Outlets */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Plan Card */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Current Plan</span>
                    <h2 className="text-xl font-bold text-white mt-1">{summary.plan.name}</h2>
                    {summary.plan.description && (
                      <p className="text-xs text-slate-400 mt-0.5">{summary.plan.description}</p>
                    )}
                  </div>
                  <div>{getStatusBadge(summary.subscription.status)}</div>
                </div>

                <div className="border-t border-slate-800/80 pt-4 space-y-2 text-xs">
                  <div className="flex justify-between py-1">
                    <span className="text-slate-400">Business Name:</span>
                    <span className="font-semibold text-slate-200">{summary.business_name}</span>
                  </div>
                  {summary.subscription.trial_ends_at && (
                    <div className="flex justify-between py-1">
                      <span className="text-slate-400">Trial Expiration:</span>
                      <span className="font-semibold text-amber-400">{formatDate(summary.subscription.trial_ends_at)}</span>
                    </div>
                  )}
                  {summary.subscription.current_period_end && (
                    <div className="flex justify-between py-1">
                      <span className="text-slate-400">Current Term Renews:</span>
                      <span className="font-semibold text-slate-200">{formatDate(summary.subscription.current_period_end)}</span>
                    </div>
                  )}
                  {summary.subscription.cancel_at_period_end && (
                    <div className="flex justify-between py-1 text-rose-400">
                      <span>Renewal Status:</span>
                      <span className="font-semibold">Cancellation scheduled at period end</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Outlet Capacity Card */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Outlet Allowance</span>
                    <h2 className="text-xl font-bold text-white mt-1">
                      {summary.outlets.current_count}{' '}
                      <span className="text-sm font-normal text-slate-400">
                        of {summary.outlets.max_allowed !== null ? `${summary.outlets.max_allowed} Allowed` : 'Unlimited'}
                      </span>
                    </h2>
                  </div>
                  <div>
                    {summary.outlets.is_limit_reached ? (
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                        Limit Reached
                      </span>
                    ) : (
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        Capacity Available
                      </span>
                    )}
                  </div>
                </div>

                {/* Capacity Progress Bar */}
                {summary.outlets.max_allowed !== null && (
                  <div className="space-y-1.5 pt-1">
                    <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
                      <div
                        className={`h-2.5 rounded-full transition-all duration-500 ${
                          summary.outlets.is_limit_reached ? 'bg-rose-500' : 'bg-emerald-500'
                        }`}
                        style={{
                          width: `${Math.min(
                            100,
                            (summary.outlets.current_count / summary.outlets.max_allowed) * 100
                          )}%`,
                        }}
                      />
                    </div>
                    <p className="text-[11px] text-slate-400 text-right">
                      {summary.outlets.max_allowed - summary.outlets.current_count > 0
                        ? `${summary.outlets.max_allowed - summary.outlets.current_count} outlet allowance remaining`
                        : '0 outlet allowance remaining'}
                    </p>
                  </div>
                )}

                <div className="border-t border-slate-800/80 pt-4 text-xs text-slate-400">
                  <p>
                    Outlets represent physical or virtual dining locations managed under this restaurant business.
                    To add more outlets, please reach out to{' '}
                    <span className="text-amber-400 font-semibold">{summary.support_cta.support_email}</span>.
                  </p>
                </div>
              </div>
            </div>

            {/* Included Features Section */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
              <div>
                <h3 className="text-base font-bold text-white">Platform Entitlements & Features</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Authorized capabilities currently provisioned for your business tier.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-2">
                {summary.features.map((feat) => (
                  <div
                    key={feat.code}
                    className={`p-3.5 rounded-xl border transition-colors ${
                      feat.authorized
                        ? 'bg-slate-800/60 border-slate-700/60 text-slate-200'
                        : 'bg-slate-950/40 border-slate-800/40 text-slate-500 opacity-60'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-white">{feat.name}</span>
                      {feat.authorized ? (
                        <span className="inline-flex items-center text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-500/20">
                          Enabled
                        </span>
                      ) : (
                        <span className="inline-flex items-center text-[10px] font-semibold text-slate-400 bg-slate-800 px-2 py-0.5 rounded-md">
                          Disabled
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex items-center justify-between text-[11px] text-slate-400">
                      <span className="capitalize">{feat.category}</span>
                      {feat.limit_value !== null && (
                        <span className="text-slate-300 font-mono">Limit: {feat.limit_value}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
