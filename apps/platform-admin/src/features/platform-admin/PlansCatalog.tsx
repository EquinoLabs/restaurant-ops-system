import React, { useState, useEffect } from 'react';
import { useAuth, fetchPlatformPlans } from '@roms/api-client';
import { PlatformPlan } from '@roms/shared-types';

interface PlansCatalogProps {
  token?: string;
}

export const PlansCatalog: React.FC<PlansCatalogProps> = ({ token: propToken }) => {
  let contextToken: string | null = null;
  try {
    const auth = useAuth();
    contextToken = auth.token;
  } catch {
    contextToken = null;
  }
  const token = propToken || contextToken;
  const [plans, setPlans] = useState<PlatformPlan[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedPlan, setSelectedPlan] = useState<PlatformPlan | null>(null);

  const loadPlans = async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPlatformPlans(token);
      setPlans(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load canonical plans catalog.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPlans();
  }, [token]);

  const filteredPlans = plans.filter((p) => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return true;
    return (
      p.name.toLowerCase().includes(q) ||
      p.code.toLowerCase().includes(q) ||
      (p.description && p.description.toLowerCase().includes(q))
    );
  });

  // Feature capability highlights based on canonical plan codes
  const getPlanFeatureHighlights = (code: string): { label: string; highlight: string }[] => {
    switch (code.toLowerCase()) {
      case 'starter_pos':
      case 'starter':
        return [
          { label: 'Outlets Included', highlight: 'Up to 2 Outlets' },
          { label: 'POS Terminal', highlight: 'Single Cashier Register' },
          { label: 'Digital QR Menu', highlight: 'Standard Dine-in QR' },
          { label: 'KDS Workflow', highlight: 'Basic Kitchen Ticket View' },
        ];
      case 'growth_pos':
      case 'growth':
        return [
          { label: 'Outlets Included', highlight: 'Up to 5 Outlets' },
          { label: 'POS Terminal', highlight: 'Multi-Device Staff Billing' },
          { label: 'Digital QR Menu', highlight: 'Guest Table Self-Ordering' },
          { label: 'Kitchen Automation', highlight: 'Multi-Station KDS Routing' },
        ];
      case 'pro_kds':
      case 'pro':
        return [
          { label: 'Outlets Included', highlight: 'Up to 10 Outlets' },
          { label: 'Kitchen Display', highlight: 'Real-time Station Audio & Routing' },
          { label: 'Inventory & Recipes', highlight: 'Automated Stock Depletion' },
          { label: 'Tenant Governance', highlight: 'Role-Based Staff Access' },
        ];
      case 'enterprise':
        return [
          { label: 'Outlets Included', highlight: 'Unlimited Outlets' },
          { label: 'Dedicated Support', highlight: '24/7 SLA & Custom Integration' },
          { label: 'Central Kitchen', highlight: 'Multi-Unit Commissary Routing' },
          { label: 'Custom Overrides', highlight: 'Platform-level Entitlement Overrides' },
        ];
      default:
        return [
          { label: 'Outlets Included', highlight: '1 Outlet' },
          { label: 'Menu Viewing', highlight: 'Public QR Menu Only' },
        ];
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-black text-white tracking-tight">Plan Catalog</h1>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-800 text-indigo-400 border border-slate-700">
              {plans.length} Tiers Available
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Canonical commercial plans and entitlement packages available for restaurant tenants.
          </p>
        </div>

        <button
          onClick={loadPlans}
          disabled={loading}
          className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition"
        >
          <svg
            className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>Refresh Catalog</span>
        </button>
      </div>

      {/* Informational Banner */}
      <div className="p-4 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs flex items-start space-x-3">
        <svg className="w-5 h-5 flex-shrink-0 text-indigo-400 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <div>
          <span className="font-bold text-white">Canonical Plan Tier Specifications: </span>
          Plans define the core commercial capabilities offered to businesses. In accordance with platform governance,
          plan definitions are canonical and managed via platform-level configuration migrations. Tenant-level subscriptions
          can be modified in the Subscriptions section.
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
        <div className="relative flex-1 max-w-md">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search plans by name, code, or description..."
            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
          />
          <svg className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>

        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="text-xs text-slate-400 hover:text-white transition px-2 py-1"
          >
            Clear Search
          </button>
        )}
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="py-20 text-center">
          <div className="inline-block w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="mt-3 text-xs text-slate-400 font-medium">Loading canonical plans catalog...</p>
        </div>
      ) : error ? (
        <div className="p-6 rounded-xl bg-red-500/10 border border-red-500/20 text-center space-y-3">
          <p className="text-sm font-semibold text-red-400">{error}</p>
          <button
            onClick={loadPlans}
            className="px-4 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-300 text-xs font-semibold transition"
          >
            Retry Loading
          </button>
        </div>
      ) : filteredPlans.length === 0 ? (
        <div className="py-16 text-center bg-slate-900/40 rounded-xl border border-slate-800">
          <svg className="w-12 h-12 text-slate-600 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
          <p className="text-sm font-semibold text-slate-300">No Plans Found</p>
          <p className="text-xs text-slate-500 mt-1">No plans matched your filter criteria "{searchQuery}".</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredPlans.map((plan) => {
            const highlights = getPlanFeatureHighlights(plan.code);
            return (
              <div
                key={plan.id}
                className="bg-slate-900/90 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 flex flex-col justify-between transition-all duration-200 shadow-lg"
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700">
                        {plan.code}
                      </span>
                      <h3 className="text-lg font-bold text-white mt-2">{plan.name}</h3>
                    </div>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-md uppercase border ${
                        plan.is_active
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          : 'bg-slate-800 text-slate-400 border-slate-700'
                      }`}
                    >
                      {plan.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>

                  <p className="text-xs text-slate-400 mt-3 line-clamp-2 min-h-[32px]">
                    {plan.description || 'No detailed description specified.'}
                  </p>

                  <div className="mt-5 pt-4 border-t border-slate-800/80 space-y-2">
                    <div className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
                      Included Capabilities
                    </div>
                    {highlights.map((h, idx) => (
                      <div key={idx} className="flex items-center justify-between text-xs py-1">
                        <span className="text-slate-400">{h.label}</span>
                        <span className="font-semibold text-white">{h.highlight}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-6 pt-4 border-t border-slate-800/80 flex items-center justify-between">
                  <span className="text-[10px] font-mono text-slate-500">
                    Sort Order: {plan.sort_order}
                  </span>
                  <button
                    onClick={() => setSelectedPlan(plan)}
                    className="px-3 py-1.5 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 text-xs font-semibold border border-indigo-500/30 transition"
                  >
                    Inspect Plan Details
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Plan Details Modal */}
      {selectedPlan && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <span className="text-[10px] font-mono uppercase bg-slate-800 text-slate-400 px-2 py-0.5 rounded border border-slate-700">
                  {selectedPlan.code}
                </span>
                <h3 className="text-xl font-bold text-white mt-1">{selectedPlan.name}</h3>
              </div>
              <button
                onClick={() => setSelectedPlan(null)}
                aria-label="Close plan details"
                className="text-slate-400 hover:text-white p-1 rounded-lg transition"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Description</label>
                <p className="text-sm text-slate-200 mt-1 bg-slate-950 p-3 rounded-xl border border-slate-800/80">
                  {selectedPlan.description || 'No description provided.'}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800/80">
                  <span className="text-slate-400 block">Plan ID</span>
                  <span className="font-mono text-white text-[11px] mt-0.5 block truncate" title={selectedPlan.id}>
                    {selectedPlan.id}
                  </span>
                </div>
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800/80">
                  <span className="text-slate-400 block">Status</span>
                  <span className="font-semibold text-emerald-400 mt-0.5 block">
                    {selectedPlan.is_active ? 'Active Canonical Tier' : 'Inactive'}
                  </span>
                </div>
              </div>

              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80 space-y-2.5">
                <div className="text-xs font-bold text-white">Tier Capabilities & Limits</div>
                {getPlanFeatureHighlights(selectedPlan.code).map((item, idx) => (
                  <div key={idx} className="flex items-center justify-between text-xs py-1 border-b border-slate-800/50 last:border-0">
                    <span className="text-slate-400">{item.label}</span>
                    <span className="font-semibold text-slate-100">{item.highlight}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedPlan(null)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
