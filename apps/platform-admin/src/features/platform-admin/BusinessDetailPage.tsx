import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '@roms/api-client';
import { fetchPlatformBusiness, updatePlatformBusinessProfile, createPlatformOutlet, assignPlatformOwner } from '@roms/api-client';
import {
  PlatformBusiness,
  PlatformOutletCreatePayload,
  PlatformAssignOwnerPayload,
} from '@roms/shared-types';

export const BusinessDetailPage: React.FC = () => {
  const { businessId } = useParams<{ businessId: string }>();
  const { token, user } = useAuth();
  const navigate = useNavigate();

  const [business, setBusiness] = useState<PlatformBusiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

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
    return (
      <div className="py-20 text-center text-slate-400">
        <div className="w-10 h-10 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin mx-auto mb-4"></div>
        <p className="text-sm font-medium">Loading business details...</p>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="p-12 text-center text-slate-400 bg-slate-900/60 border border-slate-800 rounded-2xl space-y-3">
        <p className="text-base font-bold text-white">Business not found</p>
        <p className="text-xs">The requested business does not exist or was removed.</p>
        <Link
          to="/platform/businesses"
          className="inline-block mt-2 px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold transition-all"
        >
          Back to Business Directory
        </Link>
      </div>
    );
  }

  if (error || !business) {
    return (
      <div className="p-6 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400">
        <div className="flex items-center space-x-3 mb-3">
          <svg className="w-6 h-6 text-red-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <h3 className="text-base font-bold">Failed to load business details</h3>
        </div>
        <p className="text-xs text-red-300 mb-4">{error}</p>
        <button
          onClick={loadBusiness}
          className="px-4 py-2 rounded-xl bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-200 text-xs font-bold transition-colors"
        >
          Retry Loading
        </button>
      </div>
    );
  }

  const outlets = business.outlets || [];

  return (
    <div className="space-y-6">
      <nav className="flex items-center space-x-2 text-xs text-slate-500" aria-label="Breadcrumb">
        <Link to="/platform/businesses" className="hover:text-indigo-300">Businesses</Link>
        <span>/</span>
        <span className="text-white font-semibold">{business.name}</span>
      </nav>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-extrabold text-white tracking-tight">{business.name}</h1>
          <div className="flex items-center space-x-3 mt-1 text-xs text-slate-400">
            <span className="font-mono">{business.id}</span>
            <span>Created {new Date(business.created_at).toLocaleDateString()}</span>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${
                business.status === 'suspended'
                  ? 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                  : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
              }`}
            >
              {business.status}
            </span>
            {business.subscription_status && (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase border bg-sky-500/20 text-sky-400 border-sky-500/30">
                {business.subscription_status}
              </span>
            )}
          </div>
        </div>
      </div>

      {ownerSuccess && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-medium flex items-center justify-between">
          <span>{ownerSuccess}</span>
          <button onClick={() => setOwnerSuccess(null)} className="text-slate-400 hover:text-white ml-3">✕</button>
        </div>
      )}

      <section className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6">
        <h2 className="text-sm font-bold text-white mb-4">Profile</h2>
        {isEditingName ? (
          <form onSubmit={handleSaveName} className="flex flex-col sm:flex-row gap-3 items-start sm:items-end">
            <div className="flex-1 w-full">
              <label className="block text-xs font-semibold uppercase text-slate-300">Business Name</label>
              <input
                type="text"
                value={nameDraft}
                onChange={(e) => setNameDraft(e.target.value)}
                className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              {nameError && <p className="mt-1 text-xs text-red-400">{nameError}</p>}
            </div>
            <div className="flex space-x-2">
              <button
                type="button"
                onClick={() => { setIsEditingName(false); setNameError(null); }}
                className="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={nameSaving}
                className="px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold disabled:opacity-50"
              >
                {nameSaving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </form>
        ) : (
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-slate-500 uppercase font-semibold">Name</div>
              <div className="text-base font-bold text-white mt-0.5">{business.name}</div>
            </div>
            {!isOperator && (
              <button
                onClick={() => { setNameDraft(business.name); setIsEditingName(true); }}
                className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-slate-700 text-xs font-semibold"
              >
                Edit Name
              </button>
            )}
          </div>
        )}
      </section>

      <section className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <h2 className="text-sm font-bold text-white">Outlets ({outlets.length})</h2>
          <button
            onClick={() => { setOutletError(null); setIsAddOutletOpen(true); }}
            className="px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold transition-all flex items-center space-x-1.5"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            <span>Add Outlet</span>
          </button>
        </div>

        {outlets.length === 0 ? (
          <div className="p-12 text-center text-slate-400 space-y-2">
            <p className="text-sm font-semibold text-slate-300">No outlets created yet</p>
            <p className="text-xs text-slate-500">Create the first outlet for this business to start serving customers.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-[10px] uppercase text-slate-500">
                  <th className="px-6 py-3 font-bold">Outlet</th>
                  <th className="px-6 py-3 font-bold">Slug</th>
                  <th className="px-6 py-3 font-bold">Address</th>
                  <th className="px-6 py-3 font-bold">Status</th>
                  <th className="px-6 py-3 font-bold text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {outlets.map((outlet) => (
                  <tr key={outlet.id} className="border-b border-slate-800/60 last:border-b-0 hover:bg-slate-800/30 transition-colors">
                    <td className="px-6 py-3 font-bold text-white">{outlet.name}</td>
                    <td className="px-6 py-3 font-mono text-amber-400">/m/{outlet.public_slug}</td>
                    <td className="px-6 py-3 text-slate-400 max-w-[240px] truncate">{outlet.address || '—'}</td>
                    <td className="px-6 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${
                          outlet.status === 'suspended'
                            ? 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                            : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                        }`}
                      >
                        {outlet.status}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-right space-x-2 whitespace-nowrap">
                      <button
                        onClick={() => navigate(`/platform/outlets/${outlet.id}`)}
                        className="px-3 py-1.5 rounded-xl bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-semibold"
                      >
                        Manage Outlet
                      </button>
                      <button
                        onClick={() => {
                          setOwnerError(null);
                          setOwnerTarget({ businessId: business.id, outletId: outlet.id, outletName: outlet.name });
                        }}
                        className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-semibold"
                      >
                        Assign Owner
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {isAddOutletOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl text-slate-100">
            <div className="flex justify-between items-center pb-4 border-b border-slate-800">
              <h3 className="text-lg font-bold text-white">Add Outlet to {business.name}</h3>
              <button onClick={() => setIsAddOutletOpen(false)} className="text-slate-400 hover:text-white p-1">✕</button>
            </div>
            <form onSubmit={handleCreateOutlet} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-300">Outlet Name *</label>
                <input
                  type="text"
                  required
                  value={outletForm.name}
                  onChange={(e) => setOutletForm({ ...outletForm, name: e.target.value })}
                  placeholder="e.g. Hillside Dhaba"
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-300">Public Slug *</label>
                <input
                  type="text"
                  required
                  value={outletForm.public_slug}
                  onChange={(e) => setOutletForm({ ...outletForm, public_slug: e.target.value.toLowerCase().replace(/\s+/g, '-') })}
                  placeholder="e.g. hillside-dhaba"
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-amber-400 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              {outletError && <p className="text-xs text-red-400">{outletError}</p>}
              <div className="pt-4 border-t border-slate-800 flex justify-end space-x-3">
                <button type="button" onClick={() => setIsAddOutletOpen(false)} className="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 text-xs font-semibold">Cancel</button>
                <button type="submit" disabled={outletSaving} className="px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold disabled:opacity-50">
                  {outletSaving ? 'Creating...' : 'Create Outlet'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {ownerTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl text-slate-100">
            <div className="flex justify-between items-center pb-4 border-b border-slate-800">
              <h3 className="text-lg font-bold text-white">Assign Owner for {ownerTarget.outletName}</h3>
              <button onClick={() => setOwnerTarget(null)} className="text-slate-400 hover:text-white p-1">✕</button>
            </div>
            <form onSubmit={handleAssignOwner} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-300">Owner Display Name *</label>
                <input
                  type="text"
                  required
                  value={ownerForm.display_name || ''}
                  onChange={(e) => setOwnerForm({ ...ownerForm, display_name: e.target.value })}
                  placeholder="e.g. Ramesh Kumar"
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-300">Owner Login Email *</label>
                <input
                  type="email"
                  required
                  value={ownerForm.email || ''}
                  onChange={(e) => setOwnerForm({ ...ownerForm, email: e.target.value })}
                  placeholder="owner@restaurant.com"
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-300">Initial Password *</label>
                <input
                  type="password"
                  required
                  value={ownerForm.password || ''}
                  onChange={(e) => setOwnerForm({ ...ownerForm, password: e.target.value })}
                  placeholder="••••••••••••"
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              {ownerError && <p className="text-xs text-red-400">{ownerError}</p>}
              <div className="pt-4 border-t border-slate-800 flex justify-end space-x-3">
                <button type="button" onClick={() => setOwnerTarget(null)} className="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 text-xs font-semibold">Cancel</button>
                <button type="submit" disabled={ownerSaving} className="px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold disabled:opacity-50">
                  {ownerSaving ? 'Assigning...' : 'Assign Owner Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default BusinessDetailPage;
