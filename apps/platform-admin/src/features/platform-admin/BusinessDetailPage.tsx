import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '@roms/api-client';
import {
  fetchPlatformBusiness,
  updatePlatformBusinessProfile,
  createPlatformOutlet,
  fetchPlatformAuditLogs,
} from '@roms/api-client';
import {
  PlatformBusiness,
  PlatformOutletCreatePayload,
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
  opsSelectClass,
  type DataTableColumn,
} from '../../components/ops-ui';
import {
  accountLabel,
  accountTone,
  formatCreatedAt,
} from './BusinessDirectory';
import { SubscriptionHistoryTab } from './SubscriptionHistoryTab';

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

function SubscriptionSummaryRows({ business }: { business: PlatformBusiness }) {
  const outlets = business.outlets || [];
  const activeOutlets = outlets.filter((o) => o.status === 'active').length;
  return (
    <dl className="flex flex-col text-[13px]">
      <div className="flex min-h-[36px] items-center justify-between gap-3 border-b border-ops-divider py-2">
        <dt className="w-40 shrink-0 text-ops-text-secondary">Active outlets</dt>
        <dd className="font-medium text-ops-text-primary tabular-nums">
          {activeOutlets} / {outlets.length}
        </dd>
      </div>
      <div className="flex min-h-[36px] items-center justify-between gap-3 border-b border-ops-divider py-2">
        <dt className="w-40 shrink-0 text-ops-text-secondary">Subscription scope</dt>
        <dd className="font-medium text-ops-text-primary">Managed per outlet</dd>
      </div>
      <div className="flex min-h-[36px] items-center justify-between gap-3 py-2">
        <dt className="w-40 shrink-0 text-ops-text-secondary">Manage subscriptions</dt>
        <dd>
          <Link
            to="/platform/subscriptions"
            className="font-medium text-ops-accent hover:underline text-[13px]"
          >
            Open Subscriptions
          </Link>
        </dd>
      </div>
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
    plan_code: 'trial',
  });
  const [outletSaving, setOutletSaving] = useState(false);
  const [outletError, setOutletError] = useState<string | null>(null);

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
      setOutletForm({ name: '', public_slug: '', currency: 'INR', timezone: 'Asia/Kolkata', address: '', plan_code: 'trial' });
      navigate(`/platform/outlets/${created.id}`);
    } catch (err: any) {
      setOutletError(err.message || 'Failed to create outlet.');
    } finally {
      setOutletSaving(false);
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
      width: '28%',
      getTitle: (outlet) => outlet.name,
      render: (outlet) => (
        <span className="truncate font-medium text-ops-text-primary">{outlet.name}</span>
      ),
    },
    {
      key: 'publicUrl',
      header: 'Public URL',
      width: '24%',
      render: (outlet) => (
        <a
          href={`/m/${outlet.public_slug}`}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 font-mono text-[12px] text-ops-accent hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          {`/m/${outlet.public_slug}`}
          <ExternalLink className="h-3 w-3" aria-hidden="true" />
        </a>
      ),
    },
    {
      key: 'address',
      header: 'Address',
      width: '24%',
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
                Subscriptions are outlet-scoped under Stage 3.
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
                {` ${outlets.length} outlet${outlets.length === 1 ? '' : 's'} provisioned.`}
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
              onRowClick={(outlet) => navigate(`/platform/outlets/${outlet.id}`)}
              footer={
                <span>
                  Showing {outlets.length} of {outlets.length} provisioned records
                </span>
              }
            />
          )}
        </div>
      )}

      {activeTab === 'subscription' && (
        <div className="space-y-6">
          <div className="grid gap-4 lg:grid-cols-12">
            <section className="rounded-md border border-ops-border bg-white p-5 lg:col-span-7">
              <div className="mb-4 border-b border-ops-divider pb-3">
                <h2 className="text-sm font-semibold text-ops-text-primary">Subscription</h2>
                <p className="mt-0.5 text-xs text-ops-text-secondary">
                  Subscriptions are outlet-scoped under Stage 3 (Owner Decision 002).
                </p>
              </div>
              <SubscriptionSummaryRows business={business} />
            </section>

            <section className="rounded-md border border-ops-border bg-white p-5 lg:col-span-5">
              <div className="mb-4 border-b border-ops-divider pb-3">
                <h2 className="text-sm font-semibold text-ops-text-primary">Manage subscriptions</h2>
              </div>
              <p className="text-[13px] leading-5 text-ops-text-secondary">
                Subscriptions are managed on the central Subscriptions page.
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

          <section className="rounded-md border border-ops-border bg-white p-5">
            <SubscriptionHistoryTab business={business} />
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

              <FormField id="outlet-plan" label="Plan" required>
                <select
                  value={outletForm.plan_code ?? 'trial'}
                  onChange={(e) => setOutletForm({ ...outletForm, plan_code: e.target.value })}
                  className={opsSelectClass}
                >
                  <option value="trial">Trial — 30-day trial on Starter POS</option>
                  <option value="starter_pos">Starter POS — active subscription</option>
                  <option value="growth_pos">Growth POS — active subscription</option>
                  <option value="pro_kds">Pro KDS — active subscription</option>
                  <option value="enterprise">Enterprise — active subscription</option>
                  <option value="free_qr">Free QR Menu — non-expiring</option>
                </select>
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
    </div>
  );
};

export default BusinessDetailPage;
