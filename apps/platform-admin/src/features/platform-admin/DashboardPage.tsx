import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, fetchPlatformBusinesses, fetchPlatformAuditLogs } from '@roms/api-client';
import { PlatformBusiness, PlatformAuditLogItem, PlatformBusinessCreatePayload } from '@roms/shared-types';
import { DashboardOverview } from './DashboardOverview';
import { createPlatformBusiness } from '@roms/api-client';

export const DashboardPage: React.FC = () => {
  const { token } = useAuth();
  const navigate = useNavigate();

  const [businesses, setBusinesses] = useState<PlatformBusiness[]>([]);
  const [recentAuditLogs, setRecentAuditLogs] = useState<PlatformAuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isProvisionOpen, setIsProvisionOpen] = useState(false);
  const [bizForm, setBizForm] = useState<PlatformBusinessCreatePayload>({
    name: '',
    primary_outlet_name: '',
    public_slug: '',
    currency: 'INR',
    timezone: 'Asia/Kolkata',
    address: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [provisionError, setProvisionError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      setError(null);
      const [bizData, auditData] = await Promise.all([
        fetchPlatformBusinesses(token),
        fetchPlatformAuditLogs(token, { limit: 5 }).catch(() => ({ items: [], total: 0, limit: 5, offset: 0 })),
      ]);
      setBusinesses(bizData);
      setRecentAuditLogs(auditData.items);
    } catch (err: any) {
      setError(err.message || 'Failed to load platform dashboard.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreateBusinessSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setProvisionError(null);
    if (!bizForm.name.trim() || !bizForm.primary_outlet_name.trim() || !bizForm.public_slug.trim()) {
      setProvisionError('Business name, primary outlet name, and public slug are required.');
      return;
    }
    try {
      setIsSubmitting(true);
      const created = await createPlatformBusiness(bizForm, token);
      setIsProvisionOpen(false);
      setBizForm({ name: '', primary_outlet_name: '', public_slug: '', currency: 'INR', timezone: 'Asia/Kolkata', address: '' });
      navigate(`/platform/businesses/${created.id}`);
    } catch (err: any) {
      setProvisionError(err.message || 'Failed to create business.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <DashboardOverview
        businesses={businesses}
        recentAuditLogs={recentAuditLogs}
        loading={loading}
        error={error}
        onRetry={loadData}
        onNavigateTab={(tab) => {
          if (tab === 'dashboard') navigate('/platform/dashboard');
          else navigate(`/platform/${tab}`);
        }}
        onOpenProvisionModal={() => { setProvisionError(null); setIsProvisionOpen(true); }}
      />

      {isProvisionOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl text-slate-100">
            <div className="flex justify-between items-center pb-4 border-b border-slate-800">
              <h3 className="text-lg font-bold text-white">Provision New SaaS Business</h3>
              <button onClick={() => setIsProvisionOpen(false)} className="text-slate-400 hover:text-white p-1">✕</button>
            </div>
            <form onSubmit={handleCreateBusinessSubmit} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-300">Business / Company Name *</label>
                <input
                  type="text"
                  required
                  value={bizForm.name}
                  onChange={(e) => setBizForm({ ...bizForm, name: e.target.value })}
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
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-300">Public Slug *</label>
                <input
                  type="text"
                  required
                  value={bizForm.public_slug}
                  onChange={(e) => setBizForm({ ...bizForm, public_slug: e.target.value.toLowerCase().replace(/\s+/g, '-') })}
                  className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-amber-400 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              {provisionError && <p className="text-xs text-red-400">{provisionError}</p>}
              <div className="pt-4 border-t border-slate-800 flex justify-end space-x-3">
                <button type="button" onClick={() => setIsProvisionOpen(false)} className="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 text-xs font-semibold">Cancel</button>
                <button type="submit" disabled={isSubmitting} className="px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold disabled:opacity-50">
                  {isSubmitting ? 'Provisioning...' : 'Provision Business'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
};

export default DashboardPage;
