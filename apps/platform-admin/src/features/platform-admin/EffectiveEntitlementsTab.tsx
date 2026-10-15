import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '@roms/api-client';
import {
  PlatformBusiness,
  PlatformBusinessEntitlementsResponse,
  PlatformBusinessOverridesResponse,
} from '@roms/shared-types';
import { fetchBusinessEntitlements, fetchBusinessOverrides, revokeBusinessOverride } from '@roms/api-client';
import { CreateOverrideModal } from './CreateOverrideModal';

export interface EffectiveEntitlementsTabProps {
  business: PlatformBusiness;
}

export const EffectiveEntitlementsTab: React.FC<EffectiveEntitlementsTabProps> = ({ business }) => {
  const { token } = useAuth();

  const [selectedOutletId, setSelectedOutletId] = useState<string>('');
  const [entitlements, setEntitlements] = useState<PlatformBusinessEntitlementsResponse | null>(null);
  const [overridesData, setOverridesData] = useState<PlatformBusinessOverridesResponse | null>(null);

  const [loadingEntitlements, setLoadingEntitlements] = useState<boolean>(true);
  const [loadingOverrides, setLoadingOverrides] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [authFilter, setAuthFilter] = useState<string>('all');

  const [isCreateModalOpen, setIsCreateModalOpen] = useState<boolean>(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  // Reset selected outlet whenever business changes
  useEffect(() => {
    setSelectedOutletId('');
  }, [business.id]);

  // Track current active fetch to prevent stale responses from overwriting data
  const fetchCounterRef = useRef<number>(0);

  const loadData = useCallback(async () => {
    if (!token || !business.id) return;

    const currentRequestId = ++fetchCounterRef.current;
    const targetBusinessId = business.id;
    const targetOutletId = selectedOutletId;

    setLoadingEntitlements(true);
    setLoadingOverrides(true);
    setError(null);

    try {
      const entRes = await fetchBusinessEntitlements(
        token,
        targetBusinessId,
        targetOutletId || undefined
      );
      if (currentRequestId === fetchCounterRef.current) {
        setEntitlements(entRes);
      }
    } catch (err: any) {
      if (currentRequestId === fetchCounterRef.current) {
        setError(err?.message || 'Failed to load business entitlements');
      }
    } finally {
      if (currentRequestId === fetchCounterRef.current) {
        setLoadingEntitlements(false);
      }
    }

    try {
      const ovRes = await fetchBusinessOverrides(token, targetBusinessId, true, true);
      if (currentRequestId === fetchCounterRef.current) {
        setOverridesData(ovRes);
      }
    } catch (err: any) {
      if (currentRequestId === fetchCounterRef.current) {
        console.error('Failed to load overrides history:', err);
      }
    } finally {
      if (currentRequestId === fetchCounterRef.current) {
        setLoadingOverrides(false);
      }
    }
  }, [token, business.id, selectedOutletId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRevoke = async (overrideId: string) => {
    const reasonPrompt = prompt('Please enter a mandatory audit reason for revoking this override:');
    if (reasonPrompt === null) return;
    const cleanReason = reasonPrompt.trim();
    if (!cleanReason) {
      alert('Revocation reason cannot be empty.');
      return;
    }

    setRevokingId(overrideId);
    try {
      await revokeBusinessOverride(token!, business.id, overrideId, cleanReason);
      await loadData();
    } catch (err: any) {
      alert(err?.message || 'Failed to revoke override.');
    } finally {
      setRevokingId(null);
    }
  };

  const categories = React.useMemo(() => {
    if (!entitlements?.features) return [];
    const set = new Set<string>();
    entitlements.features.forEach((f) => set.add(f.category));
    return Array.from(set).sort();
  }, [entitlements]);

  const availableFeatures = React.useMemo(() => {
    if (!entitlements?.features) return [];
    return entitlements.features.map((f) => ({
      feature_code: f.feature_code,
      feature_name: f.feature_name,
      category: f.category,
    }));
  }, [entitlements]);

  const filteredFeatures = React.useMemo(() => {
    if (!entitlements?.features) return [];
    const q = searchQuery.trim().toLowerCase();

    return entitlements.features.filter((f) => {
      const matchesQuery =
        !q ||
        f.feature_code.toLowerCase().includes(q) ||
        f.feature_name.toLowerCase().includes(q) ||
        f.reason.toLowerCase().includes(q);

      const matchesCat = categoryFilter === 'all' || f.category === categoryFilter;

      const matchesAuth =
        authFilter === 'all' ||
        (authFilter === 'authorized' && f.authorized) ||
        (authFilter === 'denied' && !f.authorized);

      return matchesQuery && matchesCat && matchesAuth;
    });
  }, [entitlements, searchQuery, categoryFilter, authFilter]);

  const renderStatusBadge = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'active') {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 uppercase">
          Active
        </span>
      );
    }
    if (s === 'past_due' || s === 'trial') {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30 uppercase">
          {status}
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30 uppercase">
        {status}
      </span>
    );
  };

  const renderSourceBadge = (source: string) => {
    switch (source) {
      case 'override':
      case 'grant_override':
      case 'restriction_override':
        return (
          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30 uppercase">
            Override
          </span>
        );
      case 'plan':
        return (
          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 uppercase">
            Plan
          </span>
        );
      case 'read_only_fallback':
        return (
          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30 uppercase">
            Read-Only Fallback
          </span>
        );
      case 'business_suspended':
        return (
          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30 uppercase">
            Suspended
          </span>
        );
      default:
        return (
          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-slate-800 text-slate-400 border border-slate-700 uppercase">
            {source}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 text-slate-100">
      {/* Scope Selector & Create Action Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-950/80 border border-slate-800 p-4 rounded-2xl">
        <div>
          <h4 className="text-xs font-bold text-white uppercase tracking-wider">Evaluation Scope & Overrides</h4>
          <p className="text-[11px] text-slate-400">
            Select scope for inspection or issue administrative grants/restrictions.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <select
            value={selectedOutletId}
            onChange={(e) => setSelectedOutletId(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-xl px-3 py-2 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">Business-Wide Scope (All Outlets)</option>
            {business.outlets?.map((o) => (
              <option key={o.id} value={o.id}>
                Outlet: {o.name} ({o.public_slug})
              </option>
            ))}
          </select>
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="px-3.5 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white border border-indigo-500 text-xs font-bold transition-colors shadow-lg shadow-indigo-500/20 flex items-center space-x-1.5"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            <span>Create Override</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl text-rose-400 text-xs font-medium">
          {error}
        </div>
      )}

      {/* Subscription Summary Card */}
      {entitlements?.subscription && (
        <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-bold text-white uppercase tracking-wider">Subscription Lifecycle</span>
              {renderStatusBadge(entitlements.subscription.resolved_status)}
            </div>
            <span className="text-[11px] font-mono text-indigo-400 font-semibold">
              Plan: {entitlements.subscription.plan_name} ({entitlements.subscription.plan_code})
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px] pt-2 border-t border-slate-800/80">
            <div>
              <span className="text-slate-500 block">Stored Status</span>
              <span className="font-semibold text-slate-300 capitalize">{entitlements.subscription.status}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Resolved Lifecycle</span>
              <span className="font-semibold text-slate-300 capitalize">{entitlements.subscription.resolved_status}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Current Period End</span>
              <span className="font-semibold text-slate-300 font-mono">
                {entitlements.subscription.current_period_end
                  ? new Date(entitlements.subscription.current_period_end).toLocaleDateString()
                  : 'N/A'}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block">Trial Ends At</span>
              <span className="font-semibold text-slate-300 font-mono">
                {entitlements.subscription.trial_ends_at
                  ? new Date(entitlements.subscription.trial_ends_at).toLocaleDateString()
                  : 'N/A'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Feature Entitlements Section */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <h4 className="text-xs font-bold text-white uppercase tracking-wider">
            Effective Feature Entitlements ({filteredFeatures.length})
          </h4>

          <div className="flex flex-wrap items-center gap-2">
            <input
              type="text"
              placeholder="Search features..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-xl px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500 w-36"
            />
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-xl px-2 py-1.5 focus:outline-none"
            >
              <option value="all">All Categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <select
              value={authFilter}
              onChange={(e) => setAuthFilter(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-xl px-2 py-1.5 focus:outline-none"
            >
              <option value="all">All Access</option>
              <option value="authorized">Authorized Only</option>
              <option value="denied">Denied Only</option>
            </select>
          </div>
        </div>

        {loadingEntitlements ? (
          <div className="py-12 text-center text-slate-400 text-xs font-medium">
            Evaluating centralized entitlement rules...
          </div>
        ) : (
          <div className="overflow-x-auto border border-slate-800 rounded-2xl bg-slate-950/80">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-900/60 text-slate-400 font-bold text-[10px] uppercase">
                  <th className="py-2.5 px-3">Feature</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Limit</th>
                  <th className="py-2.5 px-3">Scope</th>
                  <th className="py-2.5 px-3">Source</th>
                  <th className="py-2.5 px-3">Reason / Evaluation Note</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-medium">
                {filteredFeatures.map((feat) => (
                  <tr key={feat.feature_code} className="hover:bg-slate-900/40">
                    <td className="py-2.5 px-3">
                      <div className="font-bold text-white">{feat.feature_name}</div>
                      <div className="font-mono text-[10px] text-slate-400">{feat.feature_code}</div>
                    </td>
                    <td className="py-2.5 px-3">
                      {feat.authorized ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                          Authorized
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30">
                          Denied
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 font-mono">
                      {feat.limit_type === 'numeric'
                        ? feat.limit_value
                        : feat.limit_type === 'unlimited'
                        ? '∞ (Unlimited)'
                        : '—'}
                    </td>
                    <td className="py-2.5 px-3 capitalize text-slate-300 font-semibold">{feat.scope}</td>
                    <td className="py-2.5 px-3">{renderSourceBadge(feat.source)}</td>
                    <td className="py-2.5 px-3 text-[11px] text-slate-400">{feat.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Overrides & Revocation History Section */}
      <div className="space-y-4 pt-4 border-t border-slate-800">
        <h4 className="text-xs font-bold text-white uppercase tracking-wider">
          Overrides & Audit Revocation History
        </h4>

        {loadingOverrides ? (
          <div className="py-8 text-center text-slate-400 text-xs">Loading override records...</div>
        ) : (
          <div className="space-y-4">
            {/* Active & Historical Overrides Table */}
            <div>
              <h5 className="text-[11px] font-bold text-slate-400 uppercase mb-2">Override Entries</h5>
              {!overridesData?.overrides?.length ? (
                <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-xl text-xs text-slate-500 text-center">
                  No active or expired override rules on file.
                </div>
              ) : (
                <div className="overflow-x-auto border border-slate-800 rounded-2xl bg-slate-950/80">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 bg-slate-900/60 text-slate-400 font-bold text-[10px] uppercase">
                        <th className="py-2 px-3">Type</th>
                        <th className="py-2 px-3">Feature</th>
                        <th className="py-2 px-3">Scope</th>
                        <th className="py-2 px-3">Limit</th>
                        <th className="py-2 px-3">Status</th>
                        <th className="py-2 px-3">Reason</th>
                        <th className="py-2 px-3">Created By</th>
                        <th className="py-2 px-3">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {overridesData.overrides.map((ov) => (
                        <tr key={ov.id} className="hover:bg-slate-900/40">
                          <td className="py-2 px-3 font-bold uppercase text-[10px]">
                            {ov.override_type === 'grant' ? (
                              <span className="text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                                Grant
                              </span>
                            ) : (
                              <span className="text-rose-400 bg-rose-500/10 px-1.5 py-0.5 rounded border border-rose-500/20">
                                Restrict
                              </span>
                            )}
                          </td>
                          <td className="py-2 px-3 font-mono">{ov.feature_code}</td>
                          <td className="py-2 px-3">
                            {ov.outlet_name ? `Outlet: ${ov.outlet_name}` : 'Business-Wide'}
                          </td>
                          <td className="py-2 px-3 font-mono">
                            {ov.limit_value !== null ? ov.limit_value : '—'}
                          </td>
                          <td className="py-2 px-3">
                            {ov.is_active ? (
                              <span className="text-emerald-400 text-[10px] font-bold">Active</span>
                            ) : (
                              <span className="text-slate-500 text-[10px]">Expired</span>
                            )}
                          </td>
                          <td className="py-2 px-3 text-[11px] text-slate-400">{ov.reason || 'N/A'}</td>
                          <td className="py-2 px-3 text-[11px] text-slate-400 font-mono">
                            {ov.created_by_email || ov.created_by_user_id || 'System'}
                          </td>
                          <td className="py-2 px-3">
                            {ov.is_active ? (
                              <button
                                disabled={revokingId === ov.id}
                                onClick={() => handleRevoke(ov.id)}
                                className="px-2 py-0.5 rounded bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-300 text-[10px] font-bold transition-colors disabled:opacity-50"
                              >
                                {revokingId === ov.id ? 'Revoking...' : 'Revoke'}
                              </button>
                            ) : (
                              <span className="text-slate-600 text-[10px]">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Revocation Audit Log Table */}
            <div>
              <h5 className="text-[11px] font-bold text-slate-400 uppercase mb-2">Revocation Audit History</h5>
              {!overridesData?.revocation_history?.length ? (
                <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-xl text-xs text-slate-500 text-center">
                  No override revocations recorded in platform audit logs.
                </div>
              ) : (
                <div className="overflow-x-auto border border-slate-800 rounded-2xl bg-slate-950/80">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 bg-slate-900/60 text-slate-400 font-bold text-[10px] uppercase">
                        <th className="py-2 px-3">Date</th>
                        <th className="py-2 px-3">Revoked Override ID</th>
                        <th className="py-2 px-3">Feature Code</th>
                        <th className="py-2 px-3">Revoked By</th>
                        <th className="py-2 px-3">Reason</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {overridesData.revocation_history.map((rev) => (
                        <tr key={rev.audit_log_id} className="hover:bg-slate-900/40 text-slate-300">
                          <td className="py-2 px-3 font-mono text-[11px]">
                            {new Date(rev.revoked_at).toLocaleString()}
                          </td>
                          <td className="py-2 px-3 font-mono text-[10px] text-slate-400">
                            {rev.revoked_override_id || 'N/A'}
                          </td>
                          <td className="py-2 px-3 font-mono">{rev.feature_code || 'N/A'}</td>
                          <td className="py-2 px-3 font-mono text-[11px]">{rev.actor_email || 'N/A'}</td>
                          <td className="py-2 px-3 text-[11px] text-slate-400">{rev.reason || 'N/A'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Create Override Modal */}
      <CreateOverrideModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        business={business}
        availableFeatures={availableFeatures}
        onSuccess={loadData}
      />
    </div>
  );
};
