import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../authentication/AuthContext';
import { PlatformBusiness, BusinessSubscriptionItem } from '../../types/platform';
import { fetchBusinessSubscriptions } from '../../api/client';

export interface SubscriptionHistoryTabProps {
  business: PlatformBusiness;
  onEditSubscription?: (biz: PlatformBusiness) => void;
}

export const SubscriptionHistoryTab: React.FC<SubscriptionHistoryTabProps> = ({
  business,
  onEditSubscription,
}) => {
  const { token } = useAuth();
  const [subscriptions, setSubscriptions] = useState<BusinessSubscriptionItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadSubscriptions = useCallback(async () => {
    if (!token || !business.id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchBusinessSubscriptions(business.id, token);
      setSubscriptions(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load subscription history');
    } finally {
      setLoading(false);
    }
  }, [business.id, token]);

  useEffect(() => {
    loadSubscriptions();
  }, [loadSubscriptions]);

  const currentSub = subscriptions.find((s) => s.is_current);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 uppercase">
            Active
          </span>
        );
      case 'past_due':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30 uppercase">
            Past Due
          </span>
        );
      case 'cancelled':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30 uppercase">
            Cancelled
          </span>
        );
      case 'trial':
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/20 text-sky-400 border border-sky-500/30 uppercase">
            Trial
          </span>
        );
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '—';
    try {
      return new Date(dateStr).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-slate-800">
        <div>
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">
            Subscription Lifecycle & History
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Complete record of authoritative subscription terms and lifecycle state transitions
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={loadSubscriptions}
            disabled={loading}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs transition-colors disabled:opacity-50"
            title="Refresh subscription history"
          >
            <svg
              className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          </button>
          {onEditSubscription && (
            <button
              onClick={() => onEditSubscription(business)}
              className="px-3.5 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold transition-all shadow-lg shadow-indigo-500/20 flex items-center space-x-1.5"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                />
              </svg>
              <span>Manage Lifecycle</span>
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-medium flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={loadSubscriptions}
            className="underline hover:text-red-300 font-bold ml-3"
          >
            Retry
          </button>
        </div>
      )}

      {loading && subscriptions.length === 0 ? (
        <div className="p-10 text-center bg-slate-950/60 border border-slate-800 rounded-2xl text-slate-400">
          <div className="w-6 h-6 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p className="text-xs">Loading subscription records...</p>
        </div>
      ) : (
        <>
          {/* Current Subscription Spotlight Card */}
          {currentSub ? (
            <div className="bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950/30 border border-indigo-500/30 rounded-2xl p-5 shadow-lg space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                    Current Authoritative Subscription
                  </span>
                  <div className="flex items-center space-x-2 mt-2">
                    <h4 className="text-base font-black text-white">
                      {currentSub.plan?.name || currentSub.plan?.code || business.plan_name || 'Standard Plan'}
                    </h4>
                    <span className="text-xs font-mono text-slate-400">
                      ({currentSub.plan?.code || 'canonical'})
                    </span>
                    {getStatusBadge(currentSub.status)}
                  </div>
                </div>
                {currentSub.cancel_at_period_end && (
                  <span className="px-2.5 py-1 rounded-lg text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    ⚠️ Cancels at Period End
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs pt-3 border-t border-slate-800/80">
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-semibold">
                    Current Period Start
                  </span>
                  <span className="font-bold text-white mt-0.5 block">
                    {formatDate(currentSub.current_period_start)}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-semibold">
                    Current Period End
                  </span>
                  <span className="font-bold text-indigo-300 mt-0.5 block">
                    {formatDate(currentSub.current_period_end)}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-semibold">
                    Trial Expiry
                  </span>
                  <span className="font-bold text-slate-300 mt-0.5 block">
                    {formatDate(currentSub.trial_ends_at)}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-semibold">
                    Provisioned On
                  </span>
                  <span className="font-mono text-slate-300 text-[11px] mt-0.5 block">
                    {formatDate(currentSub.created_at)}
                  </span>
                </div>
              </div>

              {currentSub.cancelled_at && (
                <div className="pt-2 border-t border-slate-800/80 text-xs text-rose-400">
                  <span className="font-semibold">Cancelled at: </span>
                  {formatDate(currentSub.cancelled_at)}
                </div>
              )}
            </div>
          ) : (
            <div className="p-6 bg-slate-950/60 border border-slate-800 rounded-2xl text-slate-400 text-xs text-center">
              No active subscription row found in the authoritative ledger. The business may be using legacy profile values.
            </div>
          )}

          {/* Subscription History Ledger */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
              Subscription Ledger ({subscriptions.length} records)
            </h4>

            {subscriptions.length === 0 ? (
              <div className="p-8 text-center bg-slate-950/40 border border-slate-800 rounded-2xl text-slate-500 text-xs">
                No subscription history entries recorded yet.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-900 border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-400">
                    <tr>
                      <th className="px-4 py-3">Plan</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">Current</th>
                      <th className="px-4 py-3">Period Start</th>
                      <th className="px-4 py-3">Period End</th>
                      <th className="px-4 py-3">Cancel at End</th>
                      <th className="px-4 py-3">Created</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {subscriptions.map((sub) => (
                      <tr
                        key={sub.id}
                        className={`hover:bg-slate-900/50 transition-colors ${
                          sub.is_current ? 'bg-indigo-950/20' : ''
                        }`}
                      >
                        <td className="px-4 py-3 font-semibold text-white">
                          <div>{sub.plan?.name || sub.plan?.code || '—'}</div>
                          <div className="text-[10px] font-mono text-slate-500">
                            {sub.plan?.code || sub.plan_id.slice(0, 8)}
                          </div>
                        </td>
                        <td className="px-4 py-3">{getStatusBadge(sub.status)}</td>
                        <td className="px-4 py-3">
                          {sub.is_current ? (
                            <span className="px-2 py-0.5 rounded text-[9px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 uppercase">
                              Current
                            </span>
                          ) : (
                            <span className="text-slate-500 text-[11px]">Past</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-slate-300">
                          {formatDate(sub.current_period_start)}
                        </td>
                        <td className="px-4 py-3 font-medium text-slate-200">
                          {formatDate(sub.current_period_end || sub.trial_ends_at)}
                        </td>
                        <td className="px-4 py-3">
                          {sub.cancel_at_period_end ? (
                            <span className="text-amber-400 font-semibold">Yes</span>
                          ) : (
                            <span className="text-slate-500">No</span>
                          )}
                        </td>
                        <td className="px-4 py-3 font-mono text-[11px] text-slate-400">
                          {formatDate(sub.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};
