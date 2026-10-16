import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '@roms/api-client';
import {
  fetchPlatformBusiness,
  updatePlatformBusinessProfile,
  createPlatformOutlet,
  assignPlatformOwner,
  fetchPlatformAuditLogs,
} from '@roms/api-client';
import {
  PlatformBusiness,
  PlatformOutletCreatePayload,
  PlatformAssignOwnerPayload,
  PlatformAuditLogItem,
} from '@roms/shared-types';
import { ArrowLeft, ExternalLink, Loader2, Pencil, Plus, X } from 'lucide-react';
import {
  Button,
  DataTable,
  InlineStateBanner,
  StateBlock,
  StatusBadge,
  Tabs,
  FormField,
  opsInputClass,
  type DataTableColumn,
} from '../../components/ops-ui';
import {
  accountLabel,
  accountTone,
  formatCreatedAt,
  subscriptionLabel,
  subscriptionTone,
} from './BusinessDirectory';

type BusinessTab = 'overview' | 'outlets' | 'subscription' | 'activity';

function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function planDisplayName(planName?: string | null): string {
  if (!planName) return 'current';
  return planName.charAt(0).toUpperCase() + planName.slice(1);
}

function SubscriptionSummaryRows({ business }: { business: PlatformBusiness }) {
  const outlets = business.outlets || [];
  return (
    <dl className="flex flex-col text-[13px]">
      <div className="flex items-center justify-between gap-3 border-b border-ops-divider py-2.5">
        <dt className="text-ops-text-secondary">Plan</dt>
        <dd className="font-medium text-ops-text-primary">{business.plan_name || '—'}</dd>
      </div>
      <div className="flex items-center justify-between gap-3 border-b border-ops-divider py-2.5">
        <dt className="text-ops-text-secondary">Status</dt>
        <dd>
          <StatusBadge
            tone={subscriptionTone(business.subscription_status)}
            label={subscriptionLabel(business.subscription_status)}
          />
        </dd>
      </div>
      <div className="flex items-center justify-between gap-3 border-b border-ops-divider py-2.5">
        <dt className="text-ops-text-secondary">Outlet limit</dt>
        <dd className="font-mono text-ops-text-primary tabular-nums">
          {outlets.length} / {business.max_outlets ?? '∞'} used
        </dd>
      </div>
      {business.trial_ends_at && (
        <div className="flex items-center justify-between gap-3 py-2.5">
          <dt className="text-ops-text-secondary">Trial ends</dt>
          <dd className="font-mono text-ops-text-primary">
            {formatCreatedAt(business.trial_ends_at)}
          </dd>
        </div>
      )}
    </dl>
  );
}

export const BusinessDetailPage: React.FC = () => {
  const { businessId } = useParams<{ businessId: string }>();
  const { token, user } = useAuth();
  const navigate = useNavigate();

  const [business, setBusiness] = useState<PlatformBusiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const [activeTab, setActiveTab] = useState<BusinessTab>('outlets');

  const [isEditingName, setIsEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const [nameSaving, setNameSaving] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);

  const [isAddOutletOpen, setIsAddOutletOpen] = useState(false);
  const [outletForm, setOutletForm] = useState<PlatformOutletCreatePayload>({
    name: '',
    public_slug: '',
    currency: 'INR',
    timezone: 'Asia/Kolkata',
    address: '',
  });
  const [outletSaving, setOutletSaving] = useState(false);
  const [outletError, setOutletError] = useState<string | null>(null);

  const [ownerTarget, setOwnerTarget] = useState<{ businessId: string; outletId: string; outletName: string } | null>(null);
  const [ownerForm, setOwnerForm] = useState<PlatformAssignOwnerPayload>({
    outlet_id: '',
    email: '',
    password: '',
    display_name: '',
  });
  const [ownerSaving, setOwnerSaving] = useState(false);
  const [ownerError, setOwnerError] = useState<string | null>(null);
  const [ownerSuccess, setOwnerSuccess] = useState<string | null>(null);

  const [activity, setActivity] = useState<PlatformAuditLogItem[]>([]);
  const [activityTotal, setActivityTotal] = useState(0);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityError, setActivityError] = useState<string | null>(null);

  const isOperator = user?.platform_role === 'operator';

  const loadBusiness = useCallback(async () => {
    if (!token || !businessId) return;
    try {
      setLoading(true);
      setError(null);
      setNotFound(false);
      const data = await fetchPlatformBusiness(businessId, token);
      setBusiness(data);
    } catch (err: any) {
      if (err.status === 404) {
        setNotFound(true);
        setError(null);
      } else {
        setError(err.message || 'Failed to load business details.');
      }
    } finally {
      setLoading(false);
    }
  }, [token, businessId]);

  useEffect(() => {
    loadBusiness();
  }, [loadBusiness]);

  const loadActivity = useCallback(async () => {
    if (!token || !businessId) return;
    try {
      setActivityLoading(true);
      setActivityError(null);
      const response = await fetchPlatformAuditLogs(token, {
        business_id: businessId,
        limit: 25,
        offset: 0,
      });
      setActivity(response.items);
      setActivityTotal(response.total);
    } catch (err: any) {
      setActivityError(err.message || 'Failed to load activity.');
    } finally {
      setActivityLoading(false);
    }
  }, [token, businessId]);

  useEffect(() => {
    if (activeTab === 'activity') {
      loadActivity();
    }
  }, [activeTab, loadActivity]);

  const handleSaveName = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !businessId) return;
    const trimmed = nameDraft.trim();
    if (trimmed.length < 2 || trimmed.length > 200) {
      setNameError('Business name must be between 2 and 200 characters.');
      return;
    }
    try {
      setNameSaving(true);
      setNameError(null);
      const updated = await updatePlatformBusinessProfile(businessId, { name: trimmed }, token);
      setBusiness(updated);
      setIsEditingName(false);
    } catch (err: any) {
      setNameError(err.message || 'Failed to update business name.');
    } finally {
      setNameSaving(false);
    }
  };

  const handleCreateOutlet = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !businessId) return;
    if (!outletForm.name.trim() || !outletForm.public_slug.trim()) {
      setOutletError('Outlet name and public slug are required.');
      return;
    }
    if (!/^[a-z0-9-]+$/.test(outletForm.public_slug)) {
      setOutletError('Public slug may only contain lowercase letters, numbers, and hyphens.');
      return;
    }
    try {
      setOutletSaving(true);
      setOutletError(null);
      const created = await createPlatformOutlet(businessId, {
        ...outletForm,
        name: outletForm.name.trim(),
        public_slug: outletForm.public_slug.trim(),
      }, token);
      setIsAddOutletOpen(false);
      setOutletForm({ name: '', public_slug: '', currency: 'INR', timezone: 'Asia/Kolkata', address: '' });
      navigate(`/platform/outlets/${created.id}`);
    } catch (err: any) {
      setOutletError(err.message || 'Failed to create outlet.');
    } finally {
      setOutletSaving(false);
    }
  };

  const handleAssignOwner = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !ownerTarget) return;
    if (!ownerForm.email?.trim() || !ownerForm.password?.trim() || !ownerForm.display_name?.trim()) {
      setOwnerError('Email, password, and display name are required to provision an owner account.');
      return;
    }
    try {
      setOwnerSaving(true);
      setOwnerError(null);
      await assignPlatformOwner(ownerTarget.businessId, {
        ...ownerForm,
        outlet_id: ownerTarget.outletId,
      }, token);
      setOwnerSuccess(`Owner user '${ownerForm.email}' assigned to outlet '${ownerTarget.outletName}'.`);
      setOwnerTarget(null);
      setOwnerForm({ outlet_id: '', email: '', password: '', display_name: '' });
      await loadBusiness();
    } catch (err: any) {
      setOwnerError(err.message || 'Failed to assign owner.');
    } finally {
      setOwnerSaving(false);
    }
  };

  if (loading) {
    return <StateBlock variant="loading" title="Loading business details..." />;
  }

  if (notFound) {
    return (
      <StateBlock
        variant="not-found"
        title="Business not found"
        description="The requested business does not exist or was removed."
        secondaryAction={
          <Link
            to="/platform/businesses"
            className="inline-flex h-8 items-center rounded-md border border-ops-border bg-white px-3 text-[13px] font-medium text-ops-text-primary hover:bg-ops-canvas"
          >
            Back to Business Directory
          </Link>
        }
      />
    );
  }

  if (error || !business) {
    return (
      <StateBlock
        variant="error"
        title="Failed to load business details"
        description={error || undefined}
        actionLabel="Retry Loading"
        onAction={loadBusiness}
      />
    );
  }

  const outlets = business.outlets || [];
  const activeOutlets = outlets.filter((o) => o.status === 'active').length;
  const hasQuota = typeof business.max_outlets === 'number' && business.max_outlets > 0;
  const capacityPct = hasQuota
    ? Math.min(100, Math.round((outlets.length / (business.max_outlets as number)) * 100))
    : null;

  const openAddOutlet = () => {
    setOutletError(null);
    setIsAddOutletOpen(true);
  };

  const openEditName = () => {
    setNameDraft(business.name);
    setNameError(null);
    setIsEditingName(true);
    setActiveTab('overview');
  };

  const outletColumns: DataTableColumn<PlatformBusiness['outlets'][number]>[] = [
    {
      key: 'outlet',
      header: 'Outlet',
      width: '24%',
      render: (outlet) => (
        <span className="truncate font-medium text-ops-text-primary">{outlet.name}</span>
      ),
    },
    {
      key: 'publicUrl',
      header: 'Public URL',
      width: '20%',
      render: (outlet) => (
        <a
          href={`/m/${outlet.public_slug}`}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 font-mono text-[12px] text-ops-accent hover:underline"
        >
          {`/m/${outlet.public_slug}`}
          <ExternalLink className="h-3 w-3" aria-hidden="true" />
        </a>
      ),
    },
    {
      key: 'address',
      header: 'Address',
      width: '22%',
      render: (outlet) => (
        <span className="block truncate text-ops-text-secondary">{outlet.address || '—'}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      width: '12%',
      render: (outlet) => (
        <StatusBadge tone={accountTone(outlet.status)} label={accountLabel(outlet.status)} />
      ),
    },
    {
      key: 'created',
      header: 'Created',
      width: '12%',
      render: (outlet) => (
        <span className="text-ops-text-secondary">{formatCreatedAt(outlet.created_at)}</span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      width: '16%',
      render: (outlet) => (
        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={() => navigate(`/platform/outlets/${outlet.id}`)}
            className="text-[13px] font-medium text-ops-accent hover:underline"
          >
            Manage
          </button>
          <button
            type="button"
            onClick={() => {
              setOwnerError(null);
              setOwnerTarget({
                businessId: business.id,
                outletId: outlet.id,
                outletName: outlet.name,
              });
            }}
            className="text-[13px] font-medium text-ops-text-secondary hover:text-ops-text-primary"
          >
            Assign Owner
          </button>
        </div>
      ),
    },
  ];

  const activityColumns: DataTableColumn<PlatformAuditLogItem>[] = [
    {
      key: 'event',
      header: 'Event',
      width: '46%',
      render: (log) => (
        <div className="flex min-w-0 flex-col">
          <span className="truncate font-medium text-ops-text-primary">{log.action}</span>
          <span className="mt-0.5 truncate font-mono text-[11px] text-ops-text-secondary">
            {log.entity_type} · {log.entity_id}
            {log.outlet_name ? ` · ${log.outlet_name}` : ''}
          </span>
        </div>
      ),
    },
    {
      key: 'actor',
      header: 'Actor',
      width: '30%',
      render: (log) => (
        <div className="flex min-w-0 flex-col">
          <span className="truncate text-ops-text-primary">
            {log.actor_display_name || log.actor_email || '—'}
          </span>
          {log.actor_display_name && log.actor_email && (
            <span className="mt-0.5 truncate text-[11px] text-ops-text-secondary">
              {log.actor_email}
            </span>
          )}
        </div>
      ),
    },
    {
      key: 'created',
      header: 'Time',
      width: '24%',
      render: (log) => (
        <span className="text-ops-text-secondary">{formatDateTime(log.created_at)}</span>
      ),
    },
  ];

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'outlets', label: 'Outlets' },
    { id: 'subscription', label: 'Subscription' },
    { id: 'activity', label: 'Activity' },
  ];

  return (
    <div className="space-y-4">
      <Link
        to="/platform/businesses"
        className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ops-accent hover:underline"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to Businesses
      </Link>

      <div className="rounded-md border border-ops-border bg-white p-5">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
          <div className="flex flex-col gap-1.5">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-xl font-semibold leading-7 tracking-tight text-ops-text-primary">
                {business.name}
              </h1>
              <StatusBadge tone={accountTone(business.status)} label={accountLabel(business.status)} />
              <StatusBadge
                tone={subscriptionTone(business.subscription_status)}
                label={subscriptionLabel(business.subscription_status)}
              />
            </div>
            <p className="text-xs text-ops-text-secondary">
              ID <span className="font-mono text-ops-text-primary">{business.id}</span>
              <span className="mx-1.5">•</span>
              Created {formatCreatedAt(business.created_at)}
            </p>
          </div>
          {!isOperator && (
            <div className="flex shrink-0 items-center gap-2">
              <Button variant="secondary" onClick={openEditName}>
                <Pencil className="h-4 w-4 text-ops-text-secondary" aria-hidden="true" />
                Edit details
              </Button>
            </div>
          )}
        </div>

        <div className="mt-4">
          <Tabs
            tabs={tabs}
            activeId={activeTab}
            onChange={(id) => setActiveTab(id as BusinessTab)}
          />
        </div>
      </div>

      {ownerSuccess && (
        <div
          role="status"
          className="flex items-center justify-between gap-3 rounded-md border border-ops-status-active-bg bg-ops-status-active-bg/60 px-4 py-3 text-[13px] text-ops-status-active-text"
        >
          <span>{ownerSuccess}</span>
          <button
            type="button"
            onClick={() => setOwnerSuccess(null)}
            aria-label="Dismiss"
            className="rounded p-1 text-ops-text-secondary hover:bg-white hover:text-ops-text-primary focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      )}

      {activeTab === 'overview' && (
        <div className="grid gap-4 lg:grid-cols-12">
          <section className="rounded-md border border-ops-border bg-white p-5 lg:col-span-7">
            <div className="mb-4 border-b border-ops-divider pb-3">
              <h2 className="text-sm font-semibold text-ops-text-primary">Profile</h2>
              <p className="mt-0.5 text-xs text-ops-text-secondary">
                Registered identity for this business on the platform.
              </p>
            </div>
            {isEditingName ? (
              <form onSubmit={handleSaveName} className="space-y-3">
                <FormField id="business-name" label="Business Name" required error={nameError}>
                  <input
                    type="text"
                    value={nameDraft}
                    onChange={(e) => setNameDraft(e.target.value)}
                    className={opsInputClass}
                  />
                </FormField>
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => {
                      setIsEditingName(false);
                      setNameError(null);
                    }}
                    disabled={nameSaving}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" variant="primary" disabled={nameSaving}>
                    {nameSaving ? 'Saving...' : 'Save'}
                  </Button>
                </div>
              </form>
            ) : (
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold text-ops-text-secondary">Name</div>
                  <div className="mt-0.5 text-base font-semibold text-ops-text-primary">
                    {business.name}
                  </div>
                </div>
                {!isOperator && (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setNameDraft(business.name);
                      setNameError(null);
                      setIsEditingName(true);
                    }}
                  >
                    Edit Name
                  </Button>
                )}
              </div>
            )}
          </section>

          <section className="rounded-md border border-ops-border bg-white p-5 lg:col-span-5">
            <div className="mb-4 border-b border-ops-divider pb-3">
              <h2 className="text-sm font-semibold text-ops-text-primary">Subscription</h2>
              <p className="mt-0.5 text-xs text-ops-text-secondary">
                Current commercial state for this business.
              </p>
            </div>
            <SubscriptionSummaryRows business={business} />
          </section>
        </div>
      )}

      {activeTab === 'outlets' && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col justify-between gap-3 rounded-md border border-ops-border bg-white p-4 sm:flex-row sm:items-center">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-ops-text-primary">Assigned Outlets</h2>
                <span className="inline-flex h-5 items-center rounded bg-ops-canvas px-1.5 text-[11px] font-medium text-ops-text-secondary tabular-nums">
                  {activeOutlets} / {outlets.length} Active
                </span>
              </div>
              <p className="text-xs text-ops-text-secondary">
                {hasQuota
                  ? `${outlets.length} of ${business.max_outlets} allowable outlets provisioned on ${planDisplayName(business.plan_name)} plan.`
                  : `${outlets.length} outlet${outlets.length === 1 ? '' : 's'} provisioned.`}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="primary" onClick={openAddOutlet}>
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                Add outlet
              </Button>
            </div>
          </div>

          {outlets.length === 0 ? (
            <div className="rounded-md border border-ops-border bg-white">
              <div className="flex flex-col items-center gap-2 p-10 text-center">
                <p className="text-sm font-semibold text-ops-text-primary">No outlets created yet</p>
                <p className="text-xs text-ops-text-secondary">
                  Create the first outlet for this business to start serving customers.
                </p>
              </div>
            </div>
          ) : (
            <DataTable
              columns={outletColumns}
              rows={outlets}
              rowKey={(outlet) => outlet.id}
              minWidth="840px"
              footer={
                <>
                  <span>
                    Showing {outlets.length} of {outlets.length} provisioned records
                  </span>
                  {hasQuota && (
                    <span className="flex items-center gap-2">
                      <span className="font-semibold text-ops-text-primary tabular-nums">
                        Plan Capacity: {capacityPct}% utilized
                      </span>
                      <span className="text-ops-text-secondary">•</span>
                      <Link
                        to="/platform/plans"
                        className="font-medium text-ops-accent hover:underline"
                      >
                        Upgrade to add more
                      </Link>
                    </span>
                  )}
                </>
              }
            />
          )}
        </div>
      )}

      {activeTab === 'subscription' && (
        <div className="grid gap-4 lg:grid-cols-12">
          <section className="rounded-md border border-ops-border bg-white p-5 lg:col-span-7">
            <div className="mb-4 border-b border-ops-divider pb-3">
              <h2 className="text-sm font-semibold text-ops-text-primary">Subscription</h2>
              <p className="mt-0.5 text-xs text-ops-text-secondary">
                Plan, status, outlet quota, and trial window for this business.
              </p>
            </div>
            <SubscriptionSummaryRows business={business} />
          </section>

          <section className="rounded-md border border-ops-border bg-white p-5 lg:col-span-5">
            <div className="mb-4 border-b border-ops-divider pb-3">
              <h2 className="text-sm font-semibold text-ops-text-primary">Manage subscription</h2>
            </div>
            <p className="text-[13px] leading-5 text-ops-text-secondary">
              Plan changes, billing cycles, trial windows, and status transitions are managed
              from the Subscriptions page.
            </p>
            <Button
              variant="secondary"
              className="mt-4"
              onClick={() => navigate('/platform/subscriptions')}
            >
              Open Subscriptions
            </Button>
          </section>
        </div>
      )}

      {activeTab === 'activity' && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between rounded-md border border-ops-border bg-white p-4">
            <div className="flex flex-col gap-0.5">
              <h2 className="text-sm font-semibold text-ops-text-primary">Activity</h2>
              <p className="text-xs text-ops-text-secondary">
                Audit events recorded against this business.
              </p>
            </div>
          </div>

          {activityLoading && (
            <div
              role="status"
              className="flex items-center justify-center gap-2 rounded-md border border-ops-border bg-white p-8 text-[13px] text-ops-text-secondary"
            >
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              Loading activity...
            </div>
          )}

          {!activityLoading && activityError && (
            <InlineStateBanner
              variant="error"
              message={`Failed to load activity — ${activityError}`}
              action={
                <Button variant="secondary" onClick={loadActivity}>
                  Retry
                </Button>
              }
            />
          )}

          {!activityLoading && !activityError && activity.length === 0 && (
            <div className="rounded-md border border-ops-border bg-white">
              <div className="flex flex-col items-center gap-2 p-10 text-center">
                <p className="text-sm font-semibold text-ops-text-primary">
                  No activity recorded yet
                </p>
                <p className="text-xs text-ops-text-secondary">
                  Audit events for this business will appear here.
                </p>
              </div>
            </div>
          )}

          {!activityLoading && !activityError && activity.length > 0 && (
            <DataTable
              columns={activityColumns}
              rows={activity}
              rowKey={(log) => log.id}
              minWidth="640px"
              footer={
                <span>
                  Showing {activity.length} of {activityTotal} events
                </span>
              }
            />
          )}
        </div>
      )}

      {isAddOutletOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-[rgba(31,41,51,0.40)]" aria-hidden="true" />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-outlet-title"
            className="relative flex max-h-[90vh] w-full max-w-[480px] flex-col rounded-md border border-ops-border bg-white shadow-ops-l2"
          >
            <div className="flex items-center justify-between border-b border-ops-border p-5">
              <h2 id="add-outlet-title" className="text-base font-semibold text-ops-text-primary">
                Add Outlet to {business.name}
              </h2>
              <button
                type="button"
                onClick={() => setIsAddOutletOpen(false)}
                className="rounded p-1 text-ops-text-secondary hover:bg-ops-canvas hover:text-ops-text-primary focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
                aria-label="Close"
                disabled={outletSaving}
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>

            <form onSubmit={handleCreateOutlet} className="flex-1 space-y-4 overflow-y-auto p-5">
              <FormField id="outlet-name" label="Outlet Name" required>
                <input
                  type="text"
                  required
                  value={outletForm.name}
                  onChange={(e) => setOutletForm({ ...outletForm, name: e.target.value })}
                  placeholder="e.g. Hillside Dhaba"
                  className={opsInputClass}
                />
              </FormField>

              <FormField
                id="outlet-slug"
                label="Public Slug"
                required
                hint="Lowercase letters, numbers, and hyphens only."
              >
                <input
                  type="text"
                  required
                  value={outletForm.public_slug}
                  onChange={(e) =>
                    setOutletForm({
                      ...outletForm,
                      public_slug: e.target.value.toLowerCase().replace(/\s+/g, '-'),
                    })
                  }
                  placeholder="e.g. hillside-dhaba"
                  className={`${opsInputClass} font-mono`}
                />
              </FormField>

              {outletError && (
                <p role="alert" className="text-xs text-ops-error">
                  {outletError}
                </p>
              )}

              <div className="flex justify-end gap-2 border-t border-ops-border pt-4">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setIsAddOutletOpen(false)}
                  disabled={outletSaving}
                >
                  Cancel
                </Button>
                <Button type="submit" variant="primary" disabled={outletSaving}>
                  {outletSaving ? 'Creating...' : 'Create Outlet'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {ownerTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-[rgba(31,41,51,0.40)]" aria-hidden="true" />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="assign-owner-title"
            className="relative flex max-h-[90vh] w-full max-w-[480px] flex-col rounded-md border border-ops-border bg-white shadow-ops-l2"
          >
            <div className="flex items-center justify-between border-b border-ops-border p-5">
              <h2 id="assign-owner-title" className="text-base font-semibold text-ops-text-primary">
                Assign Owner for {ownerTarget.outletName}
              </h2>
              <button
                type="button"
                onClick={() => setOwnerTarget(null)}
                className="rounded p-1 text-ops-text-secondary hover:bg-ops-canvas hover:text-ops-text-primary focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
                aria-label="Close"
                disabled={ownerSaving}
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>

            <form onSubmit={handleAssignOwner} className="flex-1 space-y-4 overflow-y-auto p-5">
              <FormField id="owner-display-name" label="Owner Display Name" required>
                <input
                  type="text"
                  required
                  value={ownerForm.display_name || ''}
                  onChange={(e) => setOwnerForm({ ...ownerForm, display_name: e.target.value })}
                  placeholder="e.g. Ramesh Kumar"
                  className={opsInputClass}
                />
              </FormField>

              <FormField id="owner-email" label="Owner Login Email" required>
                <input
                  type="email"
                  required
                  value={ownerForm.email || ''}
                  onChange={(e) => setOwnerForm({ ...ownerForm, email: e.target.value })}
                  placeholder="owner@restaurant.com"
                  className={opsInputClass}
                />
              </FormField>

              <FormField
                id="owner-password"
                label="Initial Password"
                required
                hint="Minimum 8 characters for provisioning."
              >
                <input
                  type="password"
                  required
                  value={ownerForm.password || ''}
                  onChange={(e) => setOwnerForm({ ...ownerForm, password: e.target.value })}
                  placeholder="••••••••••••"
                  className={opsInputClass}
                />
              </FormField>

              {ownerError && (
                <p role="alert" className="text-xs text-ops-error">
                  {ownerError}
                </p>
              )}

              <div className="flex justify-end gap-2 border-t border-ops-border pt-4">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setOwnerTarget(null)}
                  disabled={ownerSaving}
                >
                  Cancel
                </Button>
                <Button type="submit" variant="primary" disabled={ownerSaving}>
                  {ownerSaving ? 'Assigning...' : 'Assign Owner Account'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default BusinessDetailPage;
