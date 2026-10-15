import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '@roms/api-client';
import { fetchPlatformOutlet, updatePlatformOutletProfile, fetchBusinessEntitlements } from '@roms/api-client';
import {
  PlatformOutletDetail,
  PlatformOutletProfileUpdatePayload,
  PlatformBusinessEntitlementsResponse,
} from '@roms/shared-types';

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

export const OutletDetailPage: React.FC = () => {
  const { outletId } = useParams<{ outletId: string }>();
  const { token, user } = useAuth();

  const [outlet, setOutlet] = useState<PlatformOutletDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const [activeTab, setActiveTab] = useState<OutletTab>('profile');

  const [form, setForm] = useState<PlatformOutletProfileUpdatePayload>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

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

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
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
    } catch (err: any) {
      setSaveError(err.message || 'Failed to update outlet profile.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="py-20 text-center text-slate-400">
        <div className="w-10 h-10 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin mx-auto mb-4"></div>
        <p className="text-sm font-medium">Loading outlet details...</p>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="p-12 text-center text-slate-400 bg-slate-900/60 border border-slate-800 rounded-2xl space-y-3">
        <p className="text-base font-bold text-white">Outlet not found</p>
        <p className="text-xs">The requested outlet does not exist or was removed.</p>
        <Link
          to="/platform/businesses"
          className="inline-block mt-2 px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold transition-all"
        >
          Back to Business Directory
        </Link>
      </div>
    );
  }

  if (error || !outlet) {
    return (
      <div className="p-6 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400">
        <div className="flex items-center space-x-3 mb-3">
          <svg className="w-6 h-6 text-red-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <h3 className="text-base font-bold">Failed to load outlet details</h3>
        </div>
        <p className="text-xs text-red-300 mb-4">{error}</p>
        <button
          onClick={loadOutlet}
          className="px-4 py-2 rounded-xl bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-200 text-xs font-bold transition-colors"
        >
          Retry Loading
        </button>
      </div>
    );
  }

  const tabs: { id: OutletTab; label: string }[] = [
    { id: 'profile', label: 'Profile & Config' },
    { id: 'subscription', label: 'Subscription & Entitlements' },
  ];

  return (
    <div className="space-y-6">
      <nav className="flex items-center space-x-2 text-xs text-slate-500" aria-label="Breadcrumb">
        <Link to="/platform/businesses" className="hover:text-indigo-300">Businesses</Link>
        <span>/</span>
        {outlet.business_id && (
          <>
            <Link to={`/platform/businesses/${outlet.business_id}`} className="hover:text-indigo-300">
              {outlet.business_name || outlet.business_id}
            </Link>
            <span>/</span>
          </>
        )}
        <span className="text-white font-semibold">{outlet.name}</span>
      </nav>

      <div className="pb-4 border-b border-slate-800">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-extrabold text-white tracking-tight">{outlet.name}</h1>
              <span className="font-mono text-[10px] text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                /m/{outlet.public_slug}
              </span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${
                  outlet.status === 'suspended'
                    ? 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                    : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                }`}
              >
                {outlet.status}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1 font-mono">{outlet.id}</p>
          </div>
          <a
            href={`/m/${outlet.public_slug}`}
            target="_blank"
            rel="noreferrer"
            className="px-4 py-2 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs font-semibold transition-colors self-start sm:self-auto"
          >
            Open Public Menu ↗
          </a>
        </div>
      </div>

      <div className="border-b border-slate-800 flex space-x-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-xs font-bold border-b-2 -mb-px transition-colors ${
              activeTab === tab.id
                ? 'border-indigo-500 text-indigo-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'profile' && (
        <form onSubmit={handleSaveProfile} className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4 max-w-2xl">
          <h2 className="text-sm font-bold text-white">Outlet Profile & Configuration</h2>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-300">Outlet Name *</label>
            <input
              type="text"
              value={form.name || ''}
              onChange={(e) => { setForm({ ...form, name: e.target.value }); setSaveSuccess(false); }}
              disabled={isOperator}
              className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-300">Public Slug</label>
            <input
              type="text"
              value={outlet.public_slug}
              disabled
              className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800/50 border border-slate-800 text-amber-400 font-mono text-sm cursor-not-allowed"
            />
            <p className="mt-1 text-[10px] text-slate-500">Slug is immutable after creation.</p>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-300">Address</label>
            <input
              type="text"
              value={form.address || ''}
              onChange={(e) => { setForm({ ...form, address: e.target.value }); setSaveSuccess(false); }}
              disabled={isOperator}
              placeholder="Street, city, region"
              className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-300">Timezone *</label>
              <input
                type="text"
                value={form.timezone || ''}
                onChange={(e) => { setForm({ ...form, timezone: e.target.value }); setSaveSuccess(false); }}
                disabled={isOperator}
                placeholder="Asia/Kolkata"
                list="platform-iana-timezones"
                className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
              />
              <datalist id="platform-iana-timezones">
                {VALID_CURRENCIES.length > 0 && (
                  <>
                    <option value="Asia/Kolkata" />
                    <option value="Asia/Dubai" />
                    <option value="Europe/London" />
                    <option value="America/New_York" />
                    <option value="America/Los_Angeles" />
                    <option value="Australia/Sydney" />
                    <option value="Asia/Singapore" />
                    <option value="Asia/Tokyo" />
                  </>
                )}
              </datalist>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-300">Currency *</label>
              <input
                type="text"
                value={form.currency || ''}
                onChange={(e) => { setForm({ ...form, currency: e.target.value.toUpperCase() }); setSaveSuccess(false); }}
                disabled={isOperator}
                maxLength={3}
                placeholder="INR"
                list="platform-iso-currencies"
                className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm uppercase focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
              />
              <datalist id="platform-iso-currencies">
                {VALID_CURRENCIES.map((c) => <option key={c} value={c} />)}
              </datalist>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-300">Primary Color</label>
              <div className="mt-1 flex items-center space-x-2">
                <input
                  type="color"
                  value={form.primary_color && /^#[0-9a-fA-F]{6}$/.test(form.primary_color) ? form.primary_color : '#6366f1'}
                  onChange={(e) => { setForm({ ...form, primary_color: e.target.value }); setSaveSuccess(false); }}
                  disabled={isOperator}
                  className="w-10 h-10 rounded-lg border border-slate-700 bg-slate-800 cursor-pointer disabled:cursor-not-allowed"
                />
                <input
                  type="text"
                  value={form.primary_color || ''}
                  onChange={(e) => { setForm({ ...form, primary_color: e.target.value }); setSaveSuccess(false); }}
                  disabled={isOperator}
                  placeholder="#6366f1"
                  className="flex-1 px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-300">Accent Color</label>
              <div className="mt-1 flex items-center space-x-2">
                <input
                  type="color"
                  value={form.accent_color && /^#[0-9a-fA-F]{6}$/.test(form.accent_color) ? form.accent_color : '#10b981'}
                  onChange={(e) => { setForm({ ...form, accent_color: e.target.value }); setSaveSuccess(false); }}
                  disabled={isOperator}
                  className="w-10 h-10 rounded-lg border border-slate-700 bg-slate-800 cursor-pointer disabled:cursor-not-allowed"
                />
                <input
                  type="text"
                  value={form.accent_color || ''}
                  onChange={(e) => { setForm({ ...form, accent_color: e.target.value }); setSaveSuccess(false); }}
                  disabled={isOperator}
                  placeholder="#10b981"
                  className="flex-1 px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
                />
              </div>
            </div>
          </div>

          {saveError && <p className="text-xs text-red-400">{saveError}</p>}
          {saveSuccess && <p className="text-xs text-emerald-400 font-semibold">Profile updated successfully.</p>}

          {!isOperator && (
            <div className="pt-4 border-t border-slate-800 flex justify-end">
              <button
                type="submit"
                disabled={saving}
                className="px-5 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save Profile'}
              </button>
            </div>
          )}
        </form>
      )}

      {activeTab === 'subscription' && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs">
            Subscription and entitlements are inspected per outlet (canonical scope). Plan changes, trial extensions, and lifecycle actions
            require an outlet-level subscription write API which is not yet available; the legacy business-level subscription endpoint is
            intentionally not exposed here.
          </div>

          {entitlementsLoading && (
            <div className="py-12 text-center text-slate-400">
              <div className="w-8 h-8 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin mx-auto mb-3"></div>
              <p className="text-xs font-medium">Loading subscription entitlements...</p>
            </div>
          )}

          {entitlementsError && (
            <div className="p-6 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400">
              <p className="text-xs font-bold mb-2">Failed to load entitlements</p>
              <p className="text-xs text-red-300 mb-3">{entitlementsError}</p>
              <button
                onClick={loadEntitlements}
                className="px-4 py-2 rounded-xl bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-200 text-xs font-bold"
              >
                Retry
              </button>
            </div>
          )}

          {!entitlementsLoading && !entitlementsError && entitlements && (
            <>
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6">
                <h2 className="text-sm font-bold text-white mb-4">Current Subscription</h2>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                  <div>
                    <div className="text-slate-500 uppercase font-semibold">Plan</div>
                    <div className="text-white font-bold mt-0.5">{entitlements.subscription.plan_name}</div>
                    <div className="text-slate-400 font-mono">{entitlements.subscription.plan_code}</div>
                  </div>
                  <div>
                    <div className="text-slate-500 uppercase font-semibold">Status</div>
                    <div className="mt-0.5">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${
                        entitlements.subscription.resolved_status === 'active'
                          ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                          : entitlements.subscription.resolved_status === 'cancelled'
                          ? 'bg-red-500/20 text-red-400 border-red-500/30'
                          : entitlements.subscription.resolved_status === 'past_due'
                          ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                          : 'bg-sky-500/20 text-sky-400 border-sky-500/30'
                      }`}>
                        {entitlements.subscription.resolved_status}
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="text-slate-500 uppercase font-semibold">Trial Ends</div>
                    <div className="text-white font-semibold mt-0.5">
                      {entitlements.subscription.trial_ends_at
                        ? new Date(entitlements.subscription.trial_ends_at).toLocaleDateString()
                        : '—'}
                    </div>
                    {trialDaysRemaining !== null && (
                      <div className="text-slate-400">{trialDaysRemaining} day(s) remaining</div>
                    )}
                  </div>
                </div>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-800">
                  <h2 className="text-sm font-bold text-white">Feature Entitlements</h2>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-[10px] uppercase text-slate-500">
                        <th className="px-6 py-3 font-bold">Feature</th>
                        <th className="px-6 py-3 font-bold">Authorized</th>
                        <th className="px-6 py-3 font-bold">Limit</th>
                        <th className="px-6 py-3 font-bold">Source</th>
                        <th className="px-6 py-3 font-bold">Scope</th>
                      </tr>
                    </thead>
                    <tbody>
                      {entitlements.features.map((f) => (
                        <tr key={f.feature_code} className="border-b border-slate-800/60 last:border-b-0">
                          <td className="px-6 py-3">
                            <div className="text-white font-semibold">{f.feature_name}</div>
                            <div className="text-slate-500 font-mono text-[10px]">{f.feature_code}</div>
                          </td>
                          <td className="px-6 py-3">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${
                              f.authorized
                                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                                : 'bg-red-500/20 text-red-400 border-red-500/30'
                            }`}>
                              {f.authorized ? 'Granted' : 'Denied'}
                            </span>
                          </td>
                          <td className="px-6 py-3 text-slate-300">
                            {f.limit_type === 'unlimited' ? 'Unlimited' : f.limit_type === 'numeric' ? String(f.limit_value) : '—'}
                          </td>
                          <td className="px-6 py-3 text-slate-400 capitalize">{f.source}</td>
                          <td className="px-6 py-3 text-slate-400 capitalize">{f.scope}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default OutletDetailPage;
