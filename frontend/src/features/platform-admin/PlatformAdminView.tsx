import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../authentication/AuthContext';
import {
  PlatformBusiness,
  PlatformOutlet,
  PlatformBusinessCreatePayload,
  PlatformOutletCreatePayload,
  PlatformAssignOwnerPayload,
} from '../../types/platform';
import {
  fetchPlatformBusinesses,
  createPlatformBusiness,
  createPlatformOutlet,
  assignPlatformOwner,
} from '../../api/client';

export const PlatformAdminView: React.FC = () => {
  const { token, user, logout } = useAuth();
  const navigate = useNavigate();

  const [businesses, setBusinesses] = useState<PlatformBusiness[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Modals state
  const [isBizModalOpen, setIsBizModalOpen] = useState<boolean>(false);
  const [isOutletModalOpen, setIsOutletModalOpen] = useState<boolean>(false);
  const [selectedBizForOutlet, setSelectedBizForOutlet] = useState<PlatformBusiness | null>(null);

  const [isOwnerModalOpen, setIsOwnerModalOpen] = useState<boolean>(false);
  const [selectedOutletForOwner, setSelectedOutletForOwner] = useState<{ bizId: string; outlet: PlatformOutlet } | null>(null);

  // Form states
  const [bizForm, setBizForm] = useState<PlatformBusinessCreatePayload>({
    name: '',
    primary_outlet_name: '',
    public_slug: '',
    currency: 'INR',
    timezone: 'Asia/Kolkata',
    address: '',
  });

  const [outletForm, setOutletForm] = useState<PlatformOutletCreatePayload>({
    name: '',
    public_slug: '',
    currency: 'INR',
    timezone: 'Asia/Kolkata',
    address: '',
  });

  const [ownerForm, setOwnerForm] = useState<PlatformAssignOwnerPayload>({
    outlet_id: '',
    email: '',
    password: '',
    display_name: '',
  });

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const loadBusinesses = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      setError(null);
      const data = await fetchPlatformBusinesses(token);
      setBusinesses(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load platform business directory.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadBusinesses();
  }, [loadBusinesses]);

  const handleCreateBusinessSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setError(null);
    setSuccessMessage(null);

    if (!bizForm.name.trim() || !bizForm.primary_outlet_name.trim() || !bizForm.public_slug.trim()) {
      setError('Business name, primary outlet name, and public slug are required.');
      return;
    }

    try {
      setIsSubmitting(true);
      const created = await createPlatformBusiness(bizForm, token);
      setSuccessMessage(`Business '${created.name}' and primary outlet created successfully!`);
      setIsBizModalOpen(false);
      setBizForm({
        name: '',
        primary_outlet_name: '',
        public_slug: '',
        currency: 'INR',
        timezone: 'Asia/Kolkata',
        address: '',
      });
      await loadBusinesses();
    } catch (err: any) {
      setError(err.message || 'Failed to create business.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateOutletSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !selectedBizForOutlet) return;
    setError(null);
    setSuccessMessage(null);

    if (!outletForm.name.trim() || !outletForm.public_slug.trim()) {
      setError('Outlet name and public slug are required.');
      return;
    }

    try {
      setIsSubmitting(true);
      const created = await createPlatformOutlet(selectedBizForOutlet.id, outletForm, token);
      setSuccessMessage(`Outlet '${created.name}' added to ${selectedBizForOutlet.name}!`);
      setIsOutletModalOpen(false);
      setSelectedBizForOutlet(null);
      setOutletForm({
        name: '',
        public_slug: '',
        currency: 'INR',
        timezone: 'Asia/Kolkata',
        address: '',
      });
      await loadBusinesses();
    } catch (err: any) {
      setError(err.message || 'Failed to create outlet.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAssignOwnerSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !selectedOutletForOwner) return;
    setError(null);
    setSuccessMessage(null);

    if (!ownerForm.email?.trim() || !ownerForm.password?.trim() || !ownerForm.display_name?.trim()) {
      setError('Email, password, and display name are required to provision owner account.');
      return;
    }

    try {
      setIsSubmitting(true);
      await assignPlatformOwner(
        selectedOutletForOwner.bizId,
        {
          ...ownerForm,
          outlet_id: selectedOutletForOwner.outlet.id,
        },
        token
      );
      setSuccessMessage(`Owner user '${ownerForm.email}' assigned to outlet '${selectedOutletForOwner.outlet.name}'!`);
      setIsOwnerModalOpen(false);
      setSelectedOutletForOwner(null);
      setOwnerForm({ outlet_id: '', email: '', password: '', display_name: '' });
      await loadBusinesses();
    } catch (err: any) {
      setError(err.message || 'Failed to assign owner.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const totalOutlets = businesses.reduce((acc, b) => acc + (b.outlets?.length || 0), 0);

  if (loading && businesses.length === 0) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-300">
        <div className="flex flex-col items-center space-y-4">
          <div className="w-12 h-12 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin"></div>
          <p className="text-sm font-semibold">Loading Platform Control Plane...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans pb-16">
      {/* Platform Header */}
      <header className="sticky top-0 z-40 bg-slate-900/90 backdrop-blur-md border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 font-black text-sm">
              ROMS
            </div>
            <div>
              <span className="font-extrabold text-white text-base tracking-tight">SaaS Control Plane</span>
              <span className="ml-2 text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 px-2 py-0.5 rounded-md uppercase">
                Platform Admin
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <Link
              to="/admin/menu"
              className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-colors"
            >
              Go to Business Admin
            </Link>

            <div className="h-4 w-px bg-slate-800"></div>

            <div className="text-right hidden sm:block">
              <div className="text-xs font-bold text-white">{user?.display_name}</div>
              <div className="text-[10px] text-slate-400">{user?.email}</div>
            </div>

            <button
              onClick={() => {
                logout();
                navigate('/login');
              }}
              className="p-2 rounded-xl text-slate-400 hover:text-red-400 hover:bg-slate-800 transition-colors"
              title="Sign Out"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
        {error && (
          <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-medium">
            {error}
          </div>
        )}

        {successMessage && (
          <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-medium">
            {successMessage}
          </div>
        )}

        {/* Overview Stats Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl">
            <p className="text-xs font-semibold uppercase text-slate-400">Total Customer Businesses</p>
            <p className="text-3xl font-black text-white mt-1">{businesses.length}</p>
          </div>
          <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl">
            <p className="text-xs font-semibold uppercase text-slate-400">Total Active Outlets</p>
            <p className="text-3xl font-black text-indigo-400 mt-1">{totalOutlets}</p>
          </div>
          <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-400">System Platform Health</p>
              <p className="text-sm font-bold text-emerald-400 mt-1">● Operational</p>
            </div>
            <button
              onClick={() => setIsBizModalOpen(true)}
              className="px-4 py-2.5 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold transition-all shadow-lg shadow-indigo-500/20 flex items-center space-x-1.5"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
              </svg>
              <span>Provision Business</span>
            </button>
          </div>
        </div>

        {/* Directory Section Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div>
            <h2 className="text-lg font-bold text-white">Cross-Tenant Business Directory</h2>
            <p className="text-xs text-slate-400">Manage SaaS client accounts, outlets, and owner account assignments</p>
          </div>
        </div>

        {/* Business Directory Cards */}
        <div className="mt-6 space-y-6">
          {businesses.map((biz) => (
            <div key={biz.id} className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-800">
                <div className="flex items-center space-x-3">
                  <h3 className="text-base font-bold text-white">{biz.name}</h3>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 uppercase">
                    {biz.status}
                  </span>
                  <span className="text-xs font-mono text-slate-500">ID: {biz.id.slice(0, 8)}...</span>
                </div>

                <button
                  onClick={() => {
                    setSelectedBizForOutlet(biz);
                    setIsOutletModalOpen(true);
                  }}
                  className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-indigo-400 border border-slate-700 text-xs font-semibold transition-colors flex items-center space-x-1 self-start sm:self-auto"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                  </svg>
                  <span>Add Outlet</span>
                </button>
              </div>

              {/* Outlets Grid */}
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                {biz.outlets?.map((outlet) => (
                  <div key={outlet.id} className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-bold text-white">{outlet.name}</h4>
                        <span className="text-[10px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                          /m/{outlet.public_slug}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-400">
                        {outlet.address || 'No physical address specified'} • {outlet.currency} ({outlet.timezone})
                      </p>
                    </div>

                    <div className="mt-4 pt-3 border-t border-slate-700/60 flex items-center justify-between">
                      <a
                        href={`/m/${outlet.public_slug}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-semibold text-emerald-400 hover:underline flex items-center space-x-1"
                      >
                        <span>Preview Live Menu</span>
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                      </a>

                      <button
                        onClick={() => {
                          setSelectedOutletForOwner({ bizId: biz.id, outlet });
                          setIsOwnerModalOpen(true);
                        }}
                        className="px-2.5 py-1 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-xs font-semibold transition-colors"
                      >
                        Assign Owner
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </main>

      {/* Provision Business Modal */}
      {isBizModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl text-slate-100">
            <div className="flex justify-between items-center pb-4 border-b border-slate-800">
              <h3 className="text-lg font-bold text-white">Provision New SaaS Business</h3>
              <button onClick={() => setIsBizModalOpen(false)} className="text-slate-400 hover:text-white p-1">
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateBusinessSubmit} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-300">Business / Company Name *</label>
                <input
                  type="text"
                  required
                  value={bizForm.name}
                  onChange={(e) => setBizForm({ ...bizForm, name: e.target.value })}
                  placeholder="e.g. Himalayan Hospitality Pvt Ltd"
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-slate-300">Primary Outlet Name *</label>
                <input
                  type="text"
                  required
                  value={bizForm.primary_outlet_name}
                  onChange={(e) => setBizForm({ ...bizForm, primary_outlet_name: e.target.value })}
                  placeholder="e.g. Riverside Camp Restaurant"
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-slate-300">Public Slug (QR Menu Identifier) *</label>
                <input
                  type="text"
                  required
                  value={bizForm.public_slug}
                  onChange={(e) => setBizForm({ ...bizForm, public_slug: e.target.value.toLowerCase().replace(/\s+/g, '-') })}
                  placeholder="e.g. riverside-camp"
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-amber-400 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-slate-300">Address (Optional)</label>
                <input
                  type="text"
                  value={bizForm.address || ''}
                  onChange={(e) => setBizForm({ ...bizForm, address: e.target.value })}
                  placeholder="Kasol Highway, HP"
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="pt-4 border-t border-slate-800 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsBizModalOpen(false)}
                  className="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold disabled:opacity-50"
                >
                  {isSubmitting ? 'Provisioning...' : 'Provision Business'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Outlet Modal */}
      {isOutletModalOpen && selectedBizForOutlet && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl text-slate-100">
            <div className="flex justify-between items-center pb-4 border-b border-slate-800">
              <h3 className="text-lg font-bold text-white">Add Outlet to {selectedBizForOutlet.name}</h3>
              <button onClick={() => setIsOutletModalOpen(false)} className="text-slate-400 hover:text-white p-1">
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateOutletSubmit} className="mt-4 space-y-4">
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

              <div className="pt-4 border-t border-slate-800 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsOutletModalOpen(false)}
                  className="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold disabled:opacity-50"
                >
                  {isSubmitting ? 'Creating...' : 'Create Outlet'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Assign Owner User Modal */}
      {isOwnerModalOpen && selectedOutletForOwner && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl text-slate-100">
            <div className="flex justify-between items-center pb-4 border-b border-slate-800">
              <h3 className="text-lg font-bold text-white">
                Assign Owner for {selectedOutletForOwner.outlet.name}
              </h3>
              <button onClick={() => setIsOwnerModalOpen(false)} className="text-slate-400 hover:text-white p-1">
                ✕
              </button>
            </div>

            <form onSubmit={handleAssignOwnerSubmit} className="mt-4 space-y-4">
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

              <div className="pt-4 border-t border-slate-800 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsOwnerModalOpen(false)}
                  className="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold disabled:opacity-50"
                >
                  {isSubmitting ? 'Assigning...' : 'Assign Owner Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
