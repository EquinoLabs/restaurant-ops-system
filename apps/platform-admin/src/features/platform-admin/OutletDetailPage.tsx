import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '@roms/api-client';
import { fetchPlatformOutlet, updatePlatformOutletProfile, fetchBusinessEntitlements } from '@roms/api-client';
import {
  PlatformOutletDetail,
  PlatformOutletProfileUpdatePayload,
  PlatformBusinessEntitlementsResponse,
} from '@roms/shared-types';
import { ArrowLeft, Copy, Info, Loader2 } from 'lucide-react';
import {
  Button,
  DataTable,
  StateBlock,
  StatusBadge,
  Tabs,
  FormField,
  opsInputClass,
  type DataTableColumn,
} from '../../components/ops-ui';
import { accountLabel, accountTone, formatCreatedAt, subscriptionLabel, subscriptionTone } from './BusinessDirectory';

type OutletTab = 'profile' | 'subscription';

const VALID_CURRENCIES = ['INR', 'USD', 'EUR', 'GBP', 'AED', 'SGD', 'AUD', 'CAD', 'JPY'];

function isValidTimezone(tz: string): boolean {
  try {
    new Intl.DateTimeFormat('en-US', { timeZone: tz });
    return true;
  } catch {
    return false;
  }
}

function isValidHex(value: string | null | undefined): value is string {
  return typeof value === 'string' && /^#[0-9a-fA-F]{6}$/.test(value);
}

export const OutletDetailPage: React.FC = () => {
  const { outletId } = useParams<{ outletId: string }>();
  const { token, user } = useAuth();

  const [outlet, setOutlet] = useState<PlatformOutletDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const [activeTab, setActiveTab] = useState<OutletTab>('profile');

  const [form, setForm] = useState<PlatformOutletProfileUpdatePayload>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [copied, setCopied] = useState(false);

  const [entitlements, setEntitlements] = useState<PlatformBusinessEntitlementsResponse | null>(null);
  const [entitlementsLoading, setEntitlementsLoading] = useState(false);
  const [entitlementsError, setEntitlementsError] = useState<string | null>(null);

  const isOperator = user?.platform_role === 'operator';

  const loadOutlet = useCallback(async () => {
    if (!token || !outletId) return;
    try {
      setLoading(true);
      setError(null);
      setNotFound(false);
      const data = await fetchPlatformOutlet(outletId, token);
      setOutlet(data);
      setForm({
        name: data.name,
        address: data.address ?? '',
        timezone: data.timezone,
        currency: data.currency,
        primary_color: data.primary_color ?? '',
        accent_color: data.accent_color ?? '',
      });
      setDirty(false);
      setSaveSuccess(false);
      setSaveError(null);
    } catch (err: any) {
      if (err.status === 404) {
        setNotFound(true);
        setError(null);
      } else {
        setError(err.message || 'Failed to load outlet details.');
      }
    } finally {
      setLoading(false);
    }
  }, [token, outletId]);

  useEffect(() => {
    loadOutlet();
  }, [loadOutlet]);

  const loadEntitlements = useCallback(async () => {
    if (!token || !outlet?.business_id || !outlet?.id) return;
    try {
      setEntitlementsLoading(true);
      setEntitlementsError(null);
      const data = await fetchBusinessEntitlements(token, outlet.business_id, outlet.id);
      setEntitlements(data);
    } catch (err: any) {
      setEntitlementsError(err.message || 'Failed to load entitlements.');
    } finally {
      setEntitlementsLoading(false);
    }
  }, [token, outlet?.business_id, outlet?.id]);

  useEffect(() => {
    if (activeTab === 'subscription') {
      loadEntitlements();
    }
  }, [activeTab, loadEntitlements]);

  const trialDaysRemaining = useMemo(() => {
    if (!entitlements?.subscription.trial_ends_at) return null;
    const end = new Date(entitlements.subscription.trial_ends_at).getTime();
    if (isNaN(end)) return null;
    return Math.max(0, Math.ceil((end - Date.now()) / (24 * 60 * 60 * 1000)));
  }, [entitlements?.subscription.trial_ends_at]);

  const updateField = <K extends keyof PlatformOutletProfileUpdatePayload>(
    key: K,
    value: PlatformOutletProfileUpdatePayload[K]
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setDirty(true);
    setSaveSuccess(false);
  };

  const submitProfile = async () => {
    if (!token || !outletId) return;

    const name = form.name?.trim();
    if (!name || name.length < 2 || name.length > 200) {
      setSaveError('Outlet name must be between 2 and 200 characters.');
      return;
    }
    const timezone = form.timezone?.trim();
    if (!timezone || !isValidTimezone(timezone)) {
      setSaveError('Timezone must be a valid IANA identifier (e.g. Asia/Kolkata).');
      return;
    }
    const currency = form.currency?.trim().toUpperCase();
    if (!currency || currency.length !== 3 || !/^[A-Z]{3}$/.test(currency)) {
      setSaveError('Currency must be a 3-letter ISO code (e.g. INR, USD).');
      return;
    }
    for (const color of [form.primary_color, form.accent_color]) {
      if (color && !/^#[0-9a-fA-F]{6}$/.test(color)) {
        setSaveError('Colors must be hex values in #RRGGBB format.');
        return;
      }
    }

    try {
      setSaving(true);
      setSaveError(null);
      setSaveSuccess(false);
      const payload: PlatformOutletProfileUpdatePayload = {
        name,
        timezone,
        currency,
        address: form.address ?? '',
        primary_color: form.primary_color || null,
        accent_color: form.accent_color || null,
      };
      const updated = await updatePlatformOutletProfile(outletId, payload, token);
      setOutlet(updated);
      setSaveSuccess(true);
      setDirty(false);
    } catch (err: any) {
      setSaveError(err.message || 'Failed to update outlet profile.');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveProfile = (e: React.FormEvent) => {
    e.preventDefault();
    void submitProfile();
  };

  const discardChanges = () => {
    if (!outlet) return;
    setForm({
      name: outlet.name,
      address: outlet.address ?? '',
      timezone: outlet.timezone,
      currency: outlet.currency,
      primary_color: outlet.primary_color ?? '',
      accent_color: outlet.accent_color ?? '',
    });
    setDirty(false);
    setSaveError(null);
    setSaveSuccess(false);
  };

  const handleCopyLink = async () => {
    if (!outlet || !navigator.clipboard) return;
    try {
      await navigator.clipboard.writeText(`/m/${outlet.public_slug}`);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access denied; leave the label unchanged.
    }
  };

  if (loading) {
    return <StateBlock variant="loading" title="Loading outlet details..." />;
  }

  if (notFound) {
    return (
      <StateBlock
        variant="not-found"
        title="Outlet not found"
        description="The requested outlet does not exist or was removed."
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

  if (error || !outlet) {
    return (
      <StateBlock
        variant="error"
        title="Failed to load outlet details"
        description={error || undefined}
        actionLabel="Retry Loading"
        onAction={loadOutlet}
      />
    );
  }

  const tabs: { id: OutletTab; label: string }[] = [
    { id: 'profile', label: 'Profile & Config' },
    { id: 'subscription', label: 'Subscription & Entitlements' },
  ];

  const featureColumns: DataTableColumn<PlatformBusinessEntitlementsResponse['features'][number]>[] = [
    {
      key: 'feature',
      header: 'Feature',
      width: '34%',
      render: (f) => (
        <div className="flex min-w-0 flex-col">
          <span className="truncate font-medium text-ops-text-primary">{f.feature_name}</span>
          <span className="mt-0.5 truncate font-mono text-[11px] text-ops-text-secondary">
            {f.feature_code}
          </span>
        </div>
      ),
    },
    {
      key: 'authorized',
      header: 'Authorized',
      width: '16%',
      render: (f) => (
        <StatusBadge
          tone={f.authorized ? 'active' : 'critical'}
          label={f.authorized ? 'Granted' : 'Denied'}
        />
      ),
    },
    {
      key: 'limit',
      header: 'Limit',
      width: '16%',
      render: (f) => (
        <span className="tabular-nums text-ops-text-primary">
          {f.limit_type === 'unlimited' ? 'Unlimited' : f.limit_type === 'numeric' ? String(f.limit_value) : '—'}
        </span>
      ),
    },
    {
      key: 'source',
      header: 'Source',
      width: '17%',
      render: (f) => <span className="capitalize text-ops-text-secondary">{f.source}</span>,
    },
    {
      key: 'scope',
      header: 'Scope',
      width: '17%',
      render: (f) => <span className="capitalize text-ops-text-secondary">{f.scope}</span>,
    },
  ];

  return (
    <div className="space-y-4">
      <Link
        to={outlet.business_id ? `/platform/businesses/${outlet.business_id}` : '/platform/businesses'}
        className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ops-accent hover:underline"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        {outlet.business_id
          ? `Back to ${outlet.business_name || outlet.business_id}`
          : 'Back to Businesses'}
      </Link>

      <div className="rounded-md border border-ops-border bg-white p-5">
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-xl font-semibold leading-7 tracking-tight text-ops-text-primary">
              {outlet.name}
            </h1>
            <StatusBadge tone={accountTone(outlet.status)} label={accountLabel(outlet.status)} />
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-ops-text-secondary">
            {outlet.business_id && (
              <>
                <span>
                  Parent business:{' '}
                  <Link
                    to={`/platform/businesses/${outlet.business_id}`}
                    className="font-medium text-ops-accent hover:underline"
                  >
                    {outlet.business_name || outlet.business_id}
                  </Link>
                </span>
                <span className="text-ops-text-disabled" aria-hidden="true">
                  •
                </span>
              </>
            )}
            <span className="flex items-center gap-1.5">
              <span>Public link:</span>
              <a
                href={`/m/${outlet.public_slug}`}
                target="_blank"
                rel="noreferrer"
                className="font-medium text-ops-text-primary hover:text-ops-accent"
              >
                {`/m/${outlet.public_slug}`}
              </a>
              <button
                type="button"
                onClick={handleCopyLink}
                aria-label="Copy public link"
                className="inline-flex h-5 items-center gap-1 rounded bg-ops-canvas px-1.5 text-[11px] font-medium text-ops-text-secondary transition-colors hover:bg-ops-border hover:text-ops-text-primary focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
              >
                <Copy className="h-3 w-3" aria-hidden="true" />
                {copied ? 'Copied' : 'Copy'}
              </button>
            </span>
          </div>
        </div>

        <div className="mt-4">
          <Tabs
            tabs={tabs}
            activeId={activeTab}
            onChange={(id) => setActiveTab(id as OutletTab)}
          />
        </div>
      </div>

      {activeTab === 'profile' && (
        <div className="grid gap-4 lg:grid-cols-12">
          <form
            id="outlet-profile-form"
            onSubmit={handleSaveProfile}
            className="space-y-5 rounded-md border border-ops-border bg-white p-5 lg:col-span-8"
          >
            <div className="border-b border-ops-divider pb-3">
              <h2 className="text-sm font-semibold text-ops-text-primary">Outlet profile</h2>
              <p className="mt-0.5 text-xs text-ops-text-secondary">
                Operational identity, localization standards, and digital branding assets for this
                specific unit.
              </p>
            </div>

            <FormField id="outlet-profile-name" label="Outlet Name" required>
              <input
                type="text"
                value={form.name || ''}
                onChange={(e) => updateField('name', e.target.value)}
                disabled={isOperator}
                className={opsInputClass}
              />
            </FormField>

            <FormField id="outlet-profile-slug" label="Public Slug" hint="Slug is immutable after creation.">
              <input
                type="text"
                value={outlet.public_slug}
                disabled
                className={`${opsInputClass} font-mono`}
              />
            </FormField>

            <FormField id="outlet-profile-address" label="Physical Address">
              <textarea
                rows={2}
                value={form.address || ''}
                onChange={(e) => updateField('address', e.target.value)}
                disabled={isOperator}
                placeholder="Street, city, region"
                className="min-h-[64px] w-full resize-none rounded-md border border-ops-border bg-white px-2.5 py-1.5 text-[13px] leading-5 text-ops-text-primary placeholder:text-ops-text-disabled focus:border-ops-accent focus:outline-none focus:ring-2 focus:ring-ops-accent-focus disabled:opacity-50"
              />
            </FormField>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormField id="outlet-profile-timezone" label="Operating Timezone" required>
                <input
                  type="text"
                  value={form.timezone || ''}
                  onChange={(e) => updateField('timezone', e.target.value)}
                  disabled={isOperator}
                  placeholder="Asia/Kolkata"
                  list="platform-iana-timezones"
                  className={opsInputClass}
                />
              </FormField>
              <FormField id="outlet-profile-currency" label="Base Currency" required>
                <input
                  type="text"
                  value={form.currency || ''}
                  onChange={(e) => updateField('currency', e.target.value.toUpperCase())}
                  disabled={isOperator}
                  maxLength={3}
                  placeholder="INR"
                  list="platform-iso-currencies"
                  className={`${opsInputClass} uppercase`}
                />
              </FormField>
            </div>

            <datalist id="platform-iana-timezones">
              <option value="Asia/Kolkata" />
              <option value="Asia/Dubai" />
              <option value="Europe/London" />
              <option value="America/New_York" />
              <option value="America/Los_Angeles" />
              <option value="Australia/Sydney" />
              <option value="Asia/Singapore" />
              <option value="Asia/Tokyo" />
            </datalist>
            <datalist id="platform-iso-currencies">
              {VALID_CURRENCIES.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>

            <div className="border-t border-ops-divider pt-4">
              <span className="mb-3 block text-xs font-semibold uppercase tracking-wide text-ops-text-secondary">
                Branding Configuration
              </span>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <label
                    htmlFor="outlet-profile-primary-color"
                    className="text-xs font-semibold text-ops-text-secondary"
                  >
                    Primary Color
                  </label>
                  <div className="flex h-8 items-center gap-2 rounded-md border border-ops-border bg-white pl-2 pr-1">
                    <span
                      aria-hidden="true"
                      className="h-4 w-4 shrink-0 rounded-full border border-ops-border"
                      style={{ backgroundColor: isValidHex(form.primary_color) ? form.primary_color : '#CBD2D9' }}
                    />
                    <input
                      id="outlet-profile-primary-color"
                      type="text"
                      value={form.primary_color || ''}
                      onChange={(e) => updateField('primary_color', e.target.value)}
                      disabled={isOperator}
                      placeholder="#2554C7"
                      maxLength={7}
                      className="h-6 w-full bg-transparent font-mono text-[13px] uppercase text-ops-text-primary placeholder:text-ops-text-disabled focus:outline-none disabled:opacity-50"
                    />
                  </div>
                  <p className="text-[11px] leading-4 text-ops-text-secondary">
                    Header chrome and checkout buttons
                  </p>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label
                    htmlFor="outlet-profile-accent-color"
                    className="text-xs font-semibold text-ops-text-secondary"
                  >
                    Accent Color
                  </label>
                  <div className="flex h-8 items-center gap-2 rounded-md border border-ops-border bg-white pl-2 pr-1">
                    <span
                      aria-hidden="true"
                      className="h-4 w-4 shrink-0 rounded-full border border-ops-border"
                      style={{ backgroundColor: isValidHex(form.accent_color) ? form.accent_color : '#CBD2D9' }}
                    />
                    <input
                      id="outlet-profile-accent-color"
                      type="text"
                      value={form.accent_color || ''}
                      onChange={(e) => updateField('accent_color', e.target.value)}
                      disabled={isOperator}
                      placeholder="#1B7F4B"
                      maxLength={7}
                      className="h-6 w-full bg-transparent font-mono text-[13px] uppercase text-ops-text-primary placeholder:text-ops-text-disabled focus:outline-none disabled:opacity-50"
                    />
                  </div>
                  <p className="text-[11px] leading-4 text-ops-text-secondary">
                    Badges, specials, and highlight accents
                  </p>
                </div>
              </div>
            </div>

            {saveError && (
              <p role="alert" className="text-xs text-ops-error">
                {saveError}
              </p>
            )}
            {saveSuccess && (
              <p role="status" className="text-xs font-medium text-ops-status-active-text">
                Profile updated successfully.
              </p>
            )}
          </form>

          <aside className="lg:col-span-4">
            <section className="rounded-md border border-ops-border bg-white p-4">
              <div className="mb-3 flex items-center justify-between border-b border-ops-divider pb-3">
                <h3 className="text-sm font-semibold text-ops-text-primary">Outlet summary</h3>
                <Info className="h-4 w-4 text-ops-text-secondary" aria-hidden="true" />
              </div>
              <dl className="flex flex-col text-[13px]">
                <div className="flex items-center justify-between gap-2 border-b border-ops-divider py-2.5">
                  <dt className="text-xs text-ops-text-secondary">Status</dt>
                  <dd>
                    <StatusBadge tone={accountTone(outlet.status)} label={accountLabel(outlet.status)} />
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-2 border-b border-ops-divider py-2.5">
                  <dt className="text-xs text-ops-text-secondary">Parent business</dt>
                  <dd className="min-w-0 truncate text-right">
                    {outlet.business_id ? (
                      <Link
                        to={`/platform/businesses/${outlet.business_id}`}
                        className="font-medium text-ops-accent hover:underline"
                      >
                        {outlet.business_name || outlet.business_id}
                      </Link>
                    ) : (
                      '—'
                    )}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-2 border-b border-ops-divider py-2.5">
                  <dt className="text-xs text-ops-text-secondary">Public URL</dt>
                  <dd className="min-w-0 truncate text-right">
                    <a
                      href={`/m/${outlet.public_slug}`}
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium text-ops-text-primary hover:text-ops-accent"
                    >
                      {`/m/${outlet.public_slug}`}
                    </a>
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-2 py-2.5">
                  <dt className="text-xs text-ops-text-secondary">Created date</dt>
                  <dd className="text-ops-text-primary">{formatCreatedAt(outlet.created_at)}</dd>
                </div>
              </dl>
            </section>
          </aside>
        </div>
      )}

      {activeTab === 'subscription' && (
        <div className="space-y-4">
          <div className="rounded-md border border-ops-status-pending-bg bg-ops-status-pending-bg/50 px-4 py-3 text-[13px] leading-5 text-ops-status-pending-text">
            Subscription and entitlements are inspected per outlet (canonical scope). Plan changes,
            trial extensions, and lifecycle actions require an outlet-level subscription write API
            which is not yet available; the legacy business-level subscription endpoint is
            intentionally not exposed here.
          </div>

          {entitlementsLoading && (
            <div
              role="status"
              className="flex items-center justify-center gap-2 rounded-md border border-ops-border bg-white p-8 text-[13px] text-ops-text-secondary"
            >
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              Loading subscription entitlements...
            </div>
          )}

          {entitlementsError && !entitlementsLoading && (
            <div
              role="alert"
              className="rounded-md border border-ops-status-critical-bg bg-ops-status-critical-bg/40 p-4"
            >
              <p className="text-[13px] font-semibold text-ops-error">Failed to load entitlements</p>
              <p className="mt-1 text-xs text-ops-error">{entitlementsError}</p>
              <Button variant="secondary" className="mt-3" onClick={loadEntitlements}>
                Retry
              </Button>
            </div>
          )}

          {!entitlementsLoading && !entitlementsError && entitlements && (
            <>
              <section className="rounded-md border border-ops-border bg-white p-5">
                <div className="mb-4 border-b border-ops-divider pb-3">
                  <h2 className="text-sm font-semibold text-ops-text-primary">Current Subscription</h2>
                  <p className="mt-0.5 text-xs text-ops-text-secondary">
                    Resolved plan state for this outlet's parent business.
                  </p>
                </div>
                <div className="grid grid-cols-1 gap-4 text-[13px] sm:grid-cols-3">
                  <div>
                    <div className="text-xs font-semibold text-ops-text-secondary">Plan</div>
                    <div className="mt-1 font-medium text-ops-text-primary">
                      {entitlements.subscription.plan_name}
                    </div>
                    <div className="mt-0.5 font-mono text-xs text-ops-text-secondary">
                      {entitlements.subscription.plan_code}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-ops-text-secondary">Status</div>
                    <div className="mt-1">
                      <StatusBadge
                        tone={subscriptionTone(entitlements.subscription.resolved_status)}
                        label={subscriptionLabel(entitlements.subscription.resolved_status)}
                      />
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-ops-text-secondary">Trial Ends</div>
                    <div className="mt-1 font-medium text-ops-text-primary">
                      {entitlements.subscription.trial_ends_at
                        ? new Date(entitlements.subscription.trial_ends_at).toLocaleDateString()
                        : '—'}
                    </div>
                    {trialDaysRemaining !== null && (
                      <div className="mt-0.5 text-xs text-ops-text-secondary">
                        {trialDaysRemaining} day(s) remaining
                      </div>
                    )}
                  </div>
                </div>
              </section>

              <DataTable
                columns={featureColumns}
                rows={entitlements.features}
                rowKey={(f) => f.feature_code}
                minWidth="760px"
                footer={
                  <span>
                    Showing {entitlements.features.length} feature entitlements
                  </span>
                }
              />
            </>
          )}
        </div>
      )}

      {!isOperator && dirty && (
        <div className="fixed bottom-4 left-4 right-4 z-40 lg:left-64">
          <div className="mx-auto flex max-w-[1160px] items-center justify-between gap-4 rounded-md border border-ops-border bg-white px-4 py-2.5 shadow-ops-l2">
            <div className="flex items-center gap-2 text-[13px] font-medium text-ops-text-primary">
              <span className="h-2 w-2 animate-pulse rounded-full bg-ops-accent" aria-hidden="true" />
              You have unsaved changes
            </div>
            <div className="flex items-center gap-2">
              <Button variant="secondary" onClick={discardChanges} disabled={saving}>
                Discard
              </Button>
              <Button variant="primary" onClick={() => void submitProfile()} disabled={saving}>
                {saving ? 'Saving…' : 'Save changes'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default OutletDetailPage;
