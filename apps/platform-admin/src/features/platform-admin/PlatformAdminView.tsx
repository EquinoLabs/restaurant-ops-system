import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@roms/api-client';
import { PlatformShell, PlatformTab } from './PlatformShell';
import { DashboardOverview } from './DashboardOverview';
import { BusinessDirectory } from './BusinessDirectory';
import { SubscriptionsOverview } from './SubscriptionsOverview';
import { PlatformAdminManagement } from './PlatformAdminManagement';
import { PlatformAuditLogs } from './PlatformAuditLogs';
import { PlansCatalog } from './PlansCatalog';
import {
  PlatformBusiness,
  PlatformOutlet,
  PlatformBusinessCreatePayload,
  PlatformSubscriptionUpdatePayload,
  PlatformOutletCreatePayload,
  PlatformAssignOwnerPayload,
  PlatformAuditLogItem,
} from '@roms/shared-types';
import {
  fetchPlatformBusinesses,
  createPlatformBusiness,
  updatePlatformSubscription,
  createPlatformOutlet,
  assignPlatformOwner,
  fetchPlatformAuditLogs,
} from '@roms/api-client';

export const PlatformAdminView: React.FC = () => {
  const { token } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  // Active tab state derived from URL or default to 'dashboard'
  const getTabFromPath = (path: string): PlatformTab => {
    if (path.includes('/platform/businesses')) return 'businesses';
    if (path.includes('/platform/plans')) return 'plans';
    if (path.includes('/platform/subscriptions')) return 'subscriptions';
    if (path.includes('/platform/admins') || path.includes('/platform/team')) return 'admins';
    if (path.includes('/platform/audit-logs')) return 'audit-logs';
    return 'dashboard';
  };

  const [activeTab, setActiveTabState] = useState<PlatformTab>(() => getTabFromPath(location.pathname));

  useEffect(() => {
    const currentTab = getTabFromPath(location.pathname);
    if (currentTab !== activeTab) {
      setActiveTabState(currentTab);
    }
  }, [location.pathname]);

  const handleTabChange = (tab: PlatformTab) => {
    setActiveTabState(tab);
    if (tab === 'dashboard') {
      navigate('/platform/dashboard');
    } else {
      navigate(`/platform/${tab}`);
    }
  };

  const [businesses, setBusinesses] = useState<PlatformBusiness[]>([]);
  const [recentAuditLogs, setRecentAuditLogs] = useState<PlatformAuditLogItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const loadRecentAuditLogs = useCallback(async () => {
    if (!token) return;
    try {
      const data = await fetchPlatformAuditLogs(token, { limit: 5 });
      setRecentAuditLogs(data.items);
    } catch {
      // Non-blocking
    }
  }, [token]);

  useEffect(() => {
    loadRecentAuditLogs();
  }, [loadRecentAuditLogs]);

  // Modals state
  const [isBizModalOpen, setIsBizModalOpen] = useState<boolean>(false);
  const [isOutletModalOpen, setIsOutletModalOpen] = useState<boolean>(false);
  const [selectedBizForOutlet, setSelectedBizForOutlet] = useState<PlatformBusiness | null>(null);

  const [isSubModalOpen, setIsSubModalOpen] = useState<boolean>(false);
  const [selectedBizForSub, setSelectedBizForSub] = useState<PlatformBusiness | null>(null);

  const [isOwnerModalOpen, setIsOwnerModalOpen] = useState<boolean>(false);
  const [selectedBizForOwner, setSelectedBizForOwner] = useState<PlatformBusiness | null>(null);

  // Form states
  const [bizForm, setBizForm] = useState<PlatformBusinessCreatePayload>({
    name: '',
    owner_email: '',
    owner_password: '',
    owner_display_name: '',
    public_slug: '',
    currency: 'INR',
    timezone: 'Asia/Kolkata',
    address: '',
  });

  const [subForm, setSubForm] = useState<{
    subscription_status: string;
    status: string;
    plan_name: string;
    max_outlets: string;
  }>({
    subscription_status: 'trial',
    status: 'active',
    plan_name: '',
    max_outlets: '',
  });

  const [outletForm, setOutletForm] = useState<PlatformOutletCreatePayload>({
    name: '',
    public_slug: '',
    currency: 'INR',
    timezone: 'Asia/Kolkata',
    address: '',
    plan_code: 'trial',
  });

  const [ownerForm, setOwnerForm] = useState<PlatformAssignOwnerPayload>({
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

    if (!bizForm.name.trim() || !bizForm.owner_email.trim() || !bizForm.owner_password.trim() || !bizForm.owner_display_name.trim() || !bizForm.public_slug.trim()) {
      setError('Business name, owner details, and public slug are required.');
      return;
    }

    try {
      setIsSubmitting(true);
      const created = await createPlatformBusiness(bizForm, token);
      setSuccessMessage(`Business '${created.name}' created successfully!`);
      setIsBizModalOpen(false);
      setBizForm({
        name: '',
        owner_email: '',
        owner_password: '',
        owner_display_name: '',
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

  const handleOpenSubscriptionModal = (biz: PlatformBusiness) => {
    setSelectedBizForSub(biz);
    setSubForm({
      subscription_status: biz.subscription_status || 'trial',
      status: biz.status || 'active',
      plan_name: biz.plan_name || '',
      max_outlets: biz.max_outlets !== null && biz.max_outlets !== undefined ? String(biz.max_outlets) : '',
    });
    setIsSubModalOpen(true);
  };

  const handleUpdateSubscriptionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !selectedBizForSub) return;
    setError(null);
    setSuccessMessage(null);

    const parsedMaxOutlets = subForm.max_outlets.trim() ? parseInt(subForm.max_outlets, 10) : null;
    if (parsedMaxOutlets !== null && (isNaN(parsedMaxOutlets) || parsedMaxOutlets < 1)) {
      setError('Max outlets limit must be a positive integer (>= 1) or left blank for unlimited.');
      return;
    }

    const payload: PlatformSubscriptionUpdatePayload = {
      subscription_status: subForm.subscription_status,
      status: subForm.status,
      plan_name: subForm.plan_name.trim() || null,
      max_outlets: parsedMaxOutlets,
    };

    try {
      setIsSubmitting(true);
      const updated = await updatePlatformSubscription(selectedBizForSub.id, payload, token);
      setSuccessMessage(`Subscription and status for business '${updated.name}' updated successfully!`);
      setIsSubModalOpen(false);
      setSelectedBizForSub(null);
      await loadBusinesses();
    } catch (err: any) {
      setError(err.message || 'Failed to update subscription.');
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
        plan_code: 'trial',
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
    if (!token || !selectedBizForOwner) return;
    setError(null);
    setSuccessMessage(null);

    if (!ownerForm.email?.trim() || !ownerForm.password?.trim() || !ownerForm.display_name?.trim()) {
      setError('Email, password, and display name are required to provision owner account.');
      return;
    }

    try {
      setIsSubmitting(true);
      await assignPlatformOwner(
        selectedBizForOwner.id,
        ownerForm,
        token
      );
      setSuccessMessage(`Owner user '${ownerForm.email}' assigned to business '${selectedBizForOwner.name}'!`);
      setIsOwnerModalOpen(false);
      setSelectedBizForOwner(null);
      setOwnerForm({ email: '', password: '', display_name: '' });
      await loadBusinesses();
    } catch (err: any) {
      setError(err.message || 'Failed to assign owner.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PlatformShell activeTab={activeTab} onTabChange={handleTabChange}>
      {/* Tab Content Rendering */}
      {activeTab === 'dashboard' && (
        <DashboardOverview
          businesses={businesses}
          recentAuditLogs={recentAuditLogs}
          loading={loading}
          error={error}
          onRetry={() => {
            loadBusinesses();
            loadRecentAuditLogs();
          }}
          onNavigateTab={handleTabChange}
          onOpenProvisionModal={() => setIsBizModalOpen(true)}
        />
      )}

      {activeTab === 'businesses' && (
        <BusinessDirectory
          businesses={businesses}
          loading={loading}
          error={error}
          successMessage={successMessage}
          onRetry={loadBusinesses}
          onOpenProvisionModal={() => setIsBizModalOpen(true)}
          onOpenSubscriptionModal={handleOpenSubscriptionModal}
          onOpenOutletModal={(biz) => {
            setSelectedBizForOutlet(biz);
            setIsOutletModalOpen(true);
          }}
          onOpenOwnerModal={(bizId) => {
            const biz = businesses.find(b => b.id === bizId);
            if (biz) setSelectedBizForOwner(biz);
            setIsOwnerModalOpen(true);
          }}
          onBusinessUpdated={loadBusinesses}
        />
      )}

      {activeTab === 'plans' && (
        <PlansCatalog />
      )}

      {activeTab === 'subscriptions' && (
        <SubscriptionsOverview
          businesses={businesses}
          loading={loading}
          error={error}
          onRetry={loadBusinesses}
          token={token}
        />
      )}

      {activeTab === 'admins' && (
        <PlatformAdminManagement token={token} />
      )}

      {activeTab === 'audit-logs' && (
        <PlatformAuditLogs token={token} businesses={businesses} />
      )}

      {/* Edit Subscription & Status Modal */}
      {isSubModalOpen && selectedBizForSub && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl text-slate-100">
            <div className="flex justify-between items-center pb-4 border-b border-slate-800">
              <div>
                <h3 className="text-lg font-bold text-white">Subscription & Account Controls</h3>
                <p className="text-xs text-slate-400">{selectedBizForSub.name}</p>
              </div>
              <button onClick={() => setIsSubModalOpen(false)} className="text-slate-400 hover:text-white p-1">
                ✕
              </button>
            </div>

            <form onSubmit={handleUpdateSubscriptionSubmit} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-300">Subscription Status *</label>
                <select
                  value={subForm.subscription_status}
                  onChange={(e) => setSubForm({ ...subForm, subscription_status: e.target.value })}
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="trial">Trial (Free Evaluation)</option>
                  <option value="active">Active (Paid & Active)</option>
                  <option value="past_due">Past Due (Payment Failure)</option>
                  <option value="cancelled">Cancelled (Terminated)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-slate-300">Account Operational Status *</label>
                <select
                  value={subForm.status}
                  onChange={(e) => setSubForm({ ...subForm, status: e.target.value })}
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="active">Active (Full Access Allowed)</option>
                  <option value="suspended">Suspended (Access Disabled)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-slate-300">Plan Tier Name</label>
                <input
                  type="text"
                  value={subForm.plan_name}
                  onChange={(e) => setSubForm({ ...subForm, plan_name: e.target.value })}
                  placeholder="e.g. starter, growth, enterprise"
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-slate-300">Max Outlets Limit (Leave empty for unlimited)</label>
                <input
                  type="number"
                  min="1"
                  value={subForm.max_outlets}
                  onChange={(e) => setSubForm({ ...subForm, max_outlets: e.target.value })}
                  placeholder="e.g. 2"
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="pt-4 border-t border-slate-800 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsSubModalOpen(false)}
                  className="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold disabled:opacity-50"
                >
                  {isSubmitting ? 'Saving...' : 'Save Subscription Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

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
                <label className="block text-xs font-semibold uppercase text-slate-300">Public Slug (QR Menu Identifier) *</label>
                <input
                  type="text"
                  required
                  value={bizForm.public_slug}
                  onChange={(e) => setBizForm({ ...bizForm, public_slug: e.target.value.toLowerCase().replace(/\s+/g, '-') })}
                  placeholder="e.g. riverside-camp"
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold uppercase text-slate-300">Currency</label>
                  <input
                    type="text"
                    value={bizForm.currency || ''}
                    onChange={(e) => setBizForm({ ...bizForm, currency: e.target.value.toUpperCase() })}
                    placeholder="INR"
                    maxLength={3}
                    className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 uppercase"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase text-slate-300">Timezone</label>
                  <input
                    type="text"
                    value={bizForm.timezone || ''}
                    onChange={(e) => setBizForm({ ...bizForm, timezone: e.target.value })}
                    placeholder="Asia/Kolkata"
                    className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
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

              <div className="pt-4 border-t border-slate-800">
                <label className="block text-xs font-semibold uppercase text-slate-400 mb-3">Owner Assignment (Required)</label>
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs text-slate-400">Owner Email *</label>
                    <input
                      type="email"
                      required
                      value={bizForm.owner_email}
                      onChange={(e) => setBizForm({ ...bizForm, owner_email: e.target.value })}
                      placeholder="owner@restaurant.com"
                      className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400">Owner Display Name *</label>
                    <input
                      type="text"
                      required
                      value={bizForm.owner_display_name}
                      onChange={(e) => setBizForm({ ...bizForm, owner_display_name: e.target.value })}
                      placeholder="e.g. Ramesh Kumar"
                      className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400">Initial Password *</label>
                    <input
                      type="password"
                      required
                      value={bizForm.owner_password}
                      onChange={(e) => setBizForm({ ...bizForm, owner_password: e.target.value })}
                      placeholder="Minimum 8 characters"
                      className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                </div>
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

              <div>
                <label className="block text-xs font-semibold uppercase text-slate-300">Plan</label>
                <select
                  value={outletForm.plan_code ?? 'trial'}
                  onChange={(e) => setOutletForm({ ...outletForm, plan_code: e.target.value })}
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="trial">Trial — 30-day trial on Starter POS</option>
                  <option value="starter_pos">Starter POS — active subscription</option>
                  <option value="growth_pos">Growth POS — active subscription</option>
                  <option value="pro_kds">Pro KDS — active subscription</option>
                  <option value="enterprise">Enterprise — active subscription</option>
                  <option value="free_qr">Free QR Menu — non-expiring</option>
                </select>
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

      {/* Assign Owner Modal */}
      {isOwnerModalOpen && selectedBizForOwner && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl text-slate-100">
            <div className="flex justify-between items-center pb-4 border-b border-slate-800">
              <h3 className="text-lg font-bold text-white">
                Assign Owner for {selectedBizForOwner.name}
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
    </PlatformShell>
  );
};
