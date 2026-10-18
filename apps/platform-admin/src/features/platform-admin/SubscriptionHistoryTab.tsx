import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '@roms/api-client';
import { PlatformBusiness, BusinessSubscriptionItem, PlatformOutlet } from '@roms/shared-types';
import { fetchBusinessSubscriptions } from '@roms/api-client';
import { StatusBadge, StatusTone } from '../../components/ops-ui/StatusBadge';
import { Button } from '../../components/ops-ui/Button';

export interface SubscriptionHistoryTabProps {
  business: PlatformBusiness;
  onEditSubscription?: (biz: PlatformBusiness) => void;
}

function resolveSubTone(status: string, isCurrent: boolean): StatusTone {
  if (!isCurrent) return 'neutral';
  switch (status) {
    case 'active':
      return 'active';
    case 'trial':
    case 'past_due':
      return 'pending';
    case 'expired':
      return 'critical';
    case 'cancelled':
    default:
      return 'neutral';
  }
}

function resolveSubLabel(status: string, isCurrent: boolean): string {
  if (!isCurrent) {
    return status ? `${status.charAt(0).toUpperCase() + status.slice(1)} (Past)` : 'Past';
  }
  switch (status) {
    case 'active':
      return 'Active';
    case 'trial':
      return 'Trial';
    case 'past_due':
      return 'Past Due';
    case 'expired':
      return 'Expired';
    case 'cancelled':
      return 'Cancelled';
    default:
      return status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Unknown';
  }
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    if (Number.isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return dateStr;
  }
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

  const outlets = useMemo<PlatformOutlet[]>(() => business.outlets || [], [business.outlets]);

  // Index subscriptions by outlet_id
  const { currentSubsByOutlet, historySubsByOutlet } = useMemo(() => {
    const currentMap = new Map<string, BusinessSubscriptionItem>();
    const historyMap = new Map<string, BusinessSubscriptionItem[]>();

    for (const sub of subscriptions) {
      if (!sub.outlet_id) continue;
      const list = historyMap.get(sub.outlet_id) || [];
      list.push(sub);
      historyMap.set(sub.outlet_id, list);

      if (sub.is_current && !currentMap.has(sub.outlet_id)) {
        currentMap.set(sub.outlet_id, sub);
      }
    }

    return { currentSubsByOutlet: currentMap, historySubsByOutlet: historyMap };
  }, [subscriptions]);

  const outletMap = useMemo(() => {
    const map = new Map<string, PlatformOutlet>();
    for (const out of outlets) {
      map.set(out.id, out);
    }
    return map;
  }, [outlets]);

  return (
    <div className="space-y-6">
      {/* Header & Refresh */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-ops-divider pb-4">
        <div>
          <h3 className="text-sm font-semibold text-ops-text-primary">
            Subscription Lifecycle & History
          </h3>
          <p className="mt-0.5 text-xs text-ops-text-secondary">
            Authoritative outlet-scoped subscription records and transition history per Stage 3 architecture.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={loadSubscriptions}
            disabled={loading}
          >
            {loading ? 'Refreshing…' : 'Refresh'}
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center justify-between rounded-md border border-ops-status-critical-bg bg-ops-status-critical-bg/30 p-3.5 text-xs text-ops-status-critical-text">
          <span>{error}</span>
          <button
            type="button"
            onClick={loadSubscriptions}
            className="font-semibold underline hover:opacity-80"
          >
            Retry
          </button>
        </div>
      )}

      {loading && subscriptions.length === 0 ? (
        <div className="flex items-center justify-center rounded-md border border-ops-border bg-white p-8 text-xs text-ops-text-secondary">
          Loading subscription records…
        </div>
      ) : (
        <>
          {/* Outlet Subscriptions Overview Grid */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-ops-text-secondary">
                Outlet Subscriptions ({outlets.length} Outlets)
              </h4>
            </div>

            {outlets.length === 0 ? (
              <div className="rounded-md border border-ops-border bg-white p-6 text-center text-xs text-ops-text-secondary">
                No outlets registered for this business. Subscriptions are scoped to outlets.
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {outlets.map((outlet) => {
                  const currentSub = currentSubsByOutlet.get(outlet.id);
                  const outletHistory = historySubsByOutlet.get(outlet.id) || [];
                  const latestSub = outletHistory.length > 0 ? outletHistory[0] : null;

                  return (
                    <div
                      key={outlet.id}
                      className="rounded-md border border-ops-border bg-white p-4 text-xs shadow-none space-y-3"
                    >
                      <div className="flex items-start justify-between gap-2 border-b border-ops-divider pb-2.5">
                        <div>
                          <div className="font-semibold text-ops-text-primary text-[13px]">
                            {outlet.name}
                          </div>
                          <div className="font-mono text-[11px] text-ops-text-secondary">
                            {outlet.id.slice(0, 8)}…
                          </div>
                        </div>
                        <StatusBadge
                          tone={outlet.status === 'active' ? 'active' : 'critical'}
                          label={outlet.status === 'active' ? 'Active' : 'Suspended'}
                        />
                      </div>

                      <div className="space-y-1.5">
                        <div className="flex justify-between items-center">
                          <span className="text-ops-text-secondary">Current Plan:</span>
                          <span className="font-medium text-ops-text-primary">
                            {currentSub
                              ? currentSub.plan?.name || currentSub.plan?.code || '—'
                              : latestSub
                              ? latestSub.plan?.name || latestSub.plan?.code || '—'
                              : '—'}
                          </span>
                        </div>

                        <div className="flex justify-between items-center">
                          <span className="text-ops-text-secondary">Subscription Status:</span>
                          {currentSub ? (
                            <StatusBadge
                              tone={resolveSubTone(currentSub.status, true)}
                              label={resolveSubLabel(currentSub.status, true)}
                            />
                          ) : latestSub ? (
                            <StatusBadge
                              tone="neutral"
                              label="No current subscription"
                            />
                          ) : (
                            <StatusBadge
                              tone="neutral"
                              label="No subscription"
                            />
                          )}
                        </div>

                        <div className="flex justify-between items-center">
                          <span className="text-ops-text-secondary">Period End / Expiry:</span>
                          <span className="font-mono text-[11px] text-ops-text-primary tabular-nums">
                            {currentSub
                              ? formatDate(currentSub.current_period_end || currentSub.trial_ends_at)
                              : latestSub
                              ? formatDate(latestSub.current_period_end || latestSub.trial_ends_at)
                              : '—'}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Detailed Subscription Ledger Table */}
          <div className="space-y-3 pt-4">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-ops-text-secondary">
              Subscription History Ledger ({subscriptions.length} records)
            </h4>

            {subscriptions.length === 0 ? (
              <div className="rounded-md border border-ops-border bg-white p-6 text-center text-xs text-ops-text-secondary">
                No subscription history entries recorded yet for this business's outlets.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-md border border-ops-border bg-white">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-ops-divider bg-ops-canvas text-[11px] font-semibold uppercase tracking-wider text-ops-text-secondary">
                    <tr>
                      <th className="px-4 py-2.5">Outlet</th>
                      <th className="px-4 py-2.5">Plan</th>
                      <th className="px-4 py-2.5">Stored Status</th>
                      <th className="px-4 py-2.5">Current Term</th>
                      <th className="px-4 py-2.5">Period Start</th>
                      <th className="px-4 py-2.5">Period End</th>
                      <th className="px-4 py-2.5">Auto-Renew</th>
                      <th className="px-4 py-2.5">Provisioned</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ops-divider text-[13px]">
                    {subscriptions.map((sub) => {
                      const outlet = sub.outlet_id ? outletMap.get(sub.outlet_id) : null;
                      const outletDisplayName = outlet ? outlet.name : sub.outlet_id ? `Outlet ${sub.outlet_id.slice(0, 8)}…` : '—';

                      return (
                        <tr
                          key={sub.id}
                          className={`transition-colors hover:bg-ops-canvas/50 ${
                            sub.is_current ? 'bg-ops-accent-subtle/30' : ''
                          }`}
                        >
                          <td className="px-4 py-3 font-medium text-ops-text-primary">
                            <div>{outletDisplayName}</div>
                            {sub.outlet_id && (
                              <div className="font-mono text-[11px] text-ops-text-disabled">
                                {sub.outlet_id.slice(0, 8)}…
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-3 text-ops-text-primary">
                            <div className="font-medium">{sub.plan?.name || sub.plan?.code || '—'}</div>
                            <div className="font-mono text-[11px] text-ops-text-secondary">
                              {sub.plan?.code || sub.plan_id.slice(0, 8)}
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <StatusBadge
                              tone={resolveSubTone(sub.status, sub.is_current)}
                              label={sub.status ? sub.status.charAt(0).toUpperCase() + sub.status.slice(1) : 'Unknown'}
                            />
                          </td>
                          <td className="px-4 py-3">
                            {sub.is_current ? (
                              <span className="inline-flex rounded bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                                Current
                              </span>
                            ) : (
                              <span className="inline-flex rounded bg-gray-100 px-2 py-0.5 text-[11px] text-gray-500">
                                Past
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 font-mono text-[12px] text-ops-text-secondary tabular-nums">
                            {formatDate(sub.current_period_start)}
                          </td>
                          <td className="px-4 py-3 font-mono text-[12px] text-ops-text-secondary tabular-nums">
                            {formatDate(sub.current_period_end || sub.trial_ends_at)}
                          </td>
                          <td className="px-4 py-3 text-[12px] text-ops-text-secondary">
                            {sub.cancel_at_period_end ? (
                              <span className="text-amber-600 font-medium">Cancels</span>
                            ) : (
                              'Renews'
                            )}
                          </td>
                          <td className="px-4 py-3 font-mono text-[12px] text-ops-text-disabled tabular-nums">
                            {formatDate(sub.created_at)}
                          </td>
                        </tr>
                      );
                    })}
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
