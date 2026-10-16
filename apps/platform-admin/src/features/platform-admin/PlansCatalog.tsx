import React, { useState, useEffect } from 'react';
import { useAuth, fetchPlatformPlans } from '@roms/api-client';
import { PlatformPlan } from '@roms/shared-types';
import { Info, Lock, RefreshCw, Search, Check } from 'lucide-react';
import { Button, Drawer, DataTable, type DataTableColumn } from '../../components/ops-ui';

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

  const columns: DataTableColumn<PlatformPlan>[] = [
    {
      key: 'name',
      header: 'Plan',
      width: 'w-44',
      render: (plan) => (
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 shrink-0 rounded-full ${
              plan.is_active ? 'bg-ops-accent' : 'bg-ops-text-secondary'
            }`}
            aria-hidden="true"
          />
          <span className="font-medium text-ops-text-primary">{plan.name}</span>
        </div>
      ),
    },
    {
      key: 'code',
      header: 'Code',
      width: 'w-32',
      render: (plan) => (
        <span className="rounded bg-ops-canvas px-1.5 py-0.5 font-mono text-[11px] text-ops-text-secondary">
          {plan.code}
        </span>
      ),
    },
    {
      key: 'description',
      header: 'Description',
      render: (plan) => (
        <span className="block truncate text-ops-text-secondary">
          {plan.description || 'No detailed description specified.'}
        </span>
      ),
    },
    {
      key: 'features',
      header: 'Included features',
      width: 'w-36',
      render: (plan) => (
        <span className="text-ops-text-secondary">
          {getPlanFeatureHighlights(plan.code).length} features
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      width: 'w-28',
      render: (plan) =>
        plan.is_active ? (
          <span className="inline-flex h-5 items-center rounded bg-ops-canvas px-1.5 text-[11px] font-medium leading-none text-ops-accent">
            Active
          </span>
        ) : (
          <span className="inline-flex h-5 items-center rounded bg-ops-status-neutral-bg px-1.5 text-[11px] font-medium leading-none text-ops-status-neutral-text">
            Inactive
          </span>
        ),
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      width: 'w-24',
      render: (plan) => (
        <Button
          variant="ghost"
          className="text-ops-accent hover:bg-ops-canvas hover:text-ops-accent-hover"
          aria-label="Inspect Plan Details"
          onClick={() => setSelectedPlan(plan)}
        >
          View
        </Button>
      ),
    },
  ];

  return (
    <div>
      {/* Page header */}
      <div className="mb-6 flex flex-col gap-3 border-b border-ops-border pb-4 md:flex-row md:items-start md:justify-between">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-semibold leading-7 tracking-tight text-ops-text-primary">
              Plans
            </h1>
            <span className="rounded bg-ops-status-neutral-bg px-2 py-0.5 text-[11px] font-medium text-ops-text-secondary">
              Catalog
            </span>
          </div>
          <p className="text-sm leading-5 text-ops-text-secondary">Plans available to customers.</p>
          <div className="mt-1 flex w-fit items-center gap-2 rounded-md border border-ops-border bg-ops-canvas px-3 py-1.5 text-xs text-ops-text-secondary">
            <Info className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>Plans are read-only for now.</span>
          </div>
        </div>
        <Button variant="secondary" onClick={loadPlans} disabled={loading}>
          <RefreshCw
            className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`}
            aria-hidden="true"
          />
          Refresh Catalog
        </Button>
      </div>

      {/* Catalog card */}
      <div className="overflow-hidden rounded-md border border-ops-border bg-white">
        {/* Toolbar */}
        <div className="flex flex-col gap-3 border-b border-ops-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2 text-xs">
            <span className="font-semibold uppercase tracking-wider text-ops-text-primary">
              Plan Catalog
            </span>
            <span className="text-ops-text-secondary">· {plans.length} tiers configured</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search
                className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ops-text-secondary"
                aria-hidden="true"
              />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search plans by name, code, or description..."
                className="h-8 w-64 rounded-md border border-ops-border bg-white pl-8 pr-3 text-[13px] text-ops-text-primary placeholder:text-ops-text-disabled focus:border-ops-accent focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
              />
            </div>
            {searchQuery && (
              <Button variant="ghost" onClick={() => setSearchQuery('')}>
                Clear Search
              </Button>
            )}
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="py-12 text-center text-sm text-ops-text-secondary">
            Loading canonical plans catalog...
          </div>
        ) : error ? (
          <div className="m-4 rounded-md border border-ops-border bg-ops-status-critical-bg p-4">
            <p className="text-sm font-semibold text-ops-status-critical-text">{error}</p>
            <div className="mt-3">
              <Button variant="secondary" onClick={loadPlans}>
                Retry Loading
              </Button>
            </div>
          </div>
        ) : filteredPlans.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-sm font-semibold text-ops-text-primary">No Plans Found</p>
            <p className="mt-1 text-xs text-ops-text-secondary">
              No plans matched your filter criteria "{searchQuery}".
            </p>
          </div>
        ) : (
          <DataTable
            columns={columns}
            rows={filteredPlans}
            rowKey={(plan) => plan.id}
            minWidth="760px"
            footer={
              <span>
                Showing {filteredPlans.length} of {plans.length} operational tiers
              </span>
            }
          />
        )}
      </div>

      {/* Plan details drawer */}
      <Drawer
        open={selectedPlan !== null}
        onClose={() => setSelectedPlan(null)}
        title={selectedPlan ? selectedPlan.name : ''}
        closeAriaLabel="Close plan details"
        footer={
          <div className="flex w-full justify-end">
            <Button variant="secondary" onClick={() => setSelectedPlan(null)}>
              Close
            </Button>
          </div>
        }
      >
        {selectedPlan && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded bg-ops-canvas px-1.5 py-0.5 font-mono text-[11px] text-ops-text-secondary">
                {selectedPlan.code}
              </span>
              {selectedPlan.is_active ? (
                <span className="inline-flex h-5 items-center rounded bg-ops-canvas px-1.5 text-[11px] font-medium leading-none text-ops-accent">
                  Active
                </span>
              ) : (
                <span className="inline-flex h-5 items-center rounded bg-ops-status-neutral-bg px-1.5 text-[11px] font-medium leading-none text-ops-status-neutral-text">
                  Inactive
                </span>
              )}
            </div>

            <p className="text-sm leading-5 text-ops-text-secondary">
              {selectedPlan.description || 'No description provided.'}
            </p>

            <div className="flex items-start gap-2 rounded-md border border-ops-border bg-ops-canvas p-3">
              <Lock className="mt-0.5 h-4 w-4 shrink-0 text-ops-text-secondary" aria-hidden="true" />
              <p className="text-xs leading-5 text-ops-text-secondary">
                Plans are read-only for now. Contact platform engineering to modify tier
                definitions. Plan definitions are canonical and managed via platform-level
                configuration migrations. Tenant-level subscriptions can be modified in the
                Subscriptions section.
              </p>
            </div>

            <div>
              <div className="flex items-center justify-between pb-1">
                <h3 className="text-sm font-semibold tracking-tight text-ops-text-primary">
                  Included features
                </h3>
                <span className="text-[11px] font-medium uppercase text-ops-text-secondary">
                  {getPlanFeatureHighlights(selectedPlan.code).length} Included
                </span>
              </div>
              <ul className="flex flex-col gap-2">
                {getPlanFeatureHighlights(selectedPlan.code).map((item, idx) => (
                  <li key={idx} className="flex items-center gap-2 text-[13px]">
                    <Check className="h-4 w-4 shrink-0 text-ops-accent" aria-hidden="true" />
                    <span className="text-ops-text-primary">{item.highlight}</span>
                  </li>
                ))}
              </ul>
            </div>

            <p className="font-mono text-[11px] text-ops-text-secondary">
              Plan ID {selectedPlan.id}
            </p>
          </div>
        )}
      </Drawer>
    </div>
  );
};
