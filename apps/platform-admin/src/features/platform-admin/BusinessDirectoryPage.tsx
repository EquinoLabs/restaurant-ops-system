import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@roms/api-client';
import { fetchPlatformBusinesses, createPlatformBusiness, assignPlatformOwner } from '@roms/api-client';
import { PlatformBusiness, PlatformBusinessCreatePayload } from '@roms/shared-types';
import { BusinessDirectory } from './BusinessDirectory';

export const BusinessDirectoryPage: React.FC = () => {
  const { token } = useAuth();
  const navigate = useNavigate();

  const [businesses, setBusinesses] = useState<PlatformBusiness[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [isProvisionOpen, setIsProvisionOpen] = useState(false);
  const [bizForm, setBizForm] = useState<PlatformBusinessCreatePayload>({
    name: '',
    primary_outlet_name: '',
    public_slug: '',
    currency: 'INR',
    timezone: 'Asia/Kolkata',
    address: '',
  });
  const [ownerEmail, setOwnerEmail] = useState('');
  const [ownerName, setOwnerName] = useState('');
  const [ownerPassword, setOwnerPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [provisionError, setProvisionError] = useState<string | null>(null);

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
    setProvisionError(null);

    const slug = bizForm.public_slug.trim();
    if (!bizForm.name.trim() || !bizForm.primary_outlet_name.trim() || !slug) {
      setProvisionError('Business name, primary outlet name, and public slug are required.');
      return;
    }
    if (!/^[a-z0-9-]+$/.test(slug)) {
      setProvisionError('Public slug may only contain lowercase letters, numbers, and hyphens.');
      return;
    }
    if (bizForm.name.trim().length < 2 || bizForm.name.trim().length > 200) {
      setProvisionError('Business name must be between 2 and 200 characters.');
      return;
    }
    if (bizForm.primary_outlet_name.trim().length < 2 || bizForm.primary_outlet_name.trim().length > 200) {
      setProvisionError('Primary outlet name must be between 2 and 200 characters.');
      return;
    }
    if (ownerEmail.trim()) {
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(ownerEmail.trim())) {
        setProvisionError('Owner email is not a valid email address.');
        return;
      }
      if (!ownerName.trim() || !ownerPassword.trim()) {
        setProvisionError('Owner display name and password are required when provisioning an owner.');
        return;
      }
      if (ownerPassword.length < 8) {
        setProvisionError('Owner password must be at least 8 characters.');
        return;
      }
    }

    try {
      setIsSubmitting(true);
      setSuccessMessage(null);
      const created = await createPlatformBusiness(
        { ...bizForm, name: bizForm.name.trim(), public_slug: slug, primary_outlet_name: bizForm.primary_outlet_name.trim() },
        token
      );

      let ownerWarning: string | null = null;
      if (ownerEmail.trim()) {
        const primaryOutlet = created.outlets?.[0];
        if (primaryOutlet) {
          try {
            await assignPlatformOwner(created.id, {
              outlet_id: primaryOutlet.id,
              email: ownerEmail.trim(),
              password: ownerPassword,
              display_name: ownerName.trim(),
            }, token);
          } catch (ownerErr: any) {
            ownerWarning = `Business created, but owner assignment failed: ${ownerErr.message || 'unknown error'}. You can assign an owner from the business detail page.`;
          }
        } else {
          ownerWarning = 'Business created, but no primary outlet was returned for owner assignment.';
        }
      }

      setIsProvisionOpen(false);
      setBizForm({ name: '', primary_outlet_name: '', public_slug: '', currency: 'INR', timezone: 'Asia/Kolkata', address: '' });
      setOwnerEmail('');
      setOwnerName('');
      setOwnerPassword('');

      if (ownerWarning) {
        setSuccessMessage(ownerWarning);
        await loadBusinesses();
      } else {
        navigate(`/platform/businesses/${created.id}`);
      }
    } catch (err: any) {
      setProvisionError(err.message || 'Failed to create business.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <BusinessDirectory
        businesses={businesses}
        loading={loading}
        error={error}
        successMessage={successMessage}
        onRetry={loadBusinesses}
        onOpenProvisionModal={() => { setProvisionError(null); setIsProvisionOpen(true); }}
        onViewBusiness={(businessId) => navigate(`/platform/businesses/${businessId}`)}
      />

      {isProvisionOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl text-slate-100 max-h-[90vh] overflow-y-auto">
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

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold uppercase text-slate-300">Currency</label>
                  <input
                    type="text"
                    value={bizForm.currency || ''}
                    onChange={(e) => setBizForm({ ...bizForm, currency: e.target.value.toUpperCase() })}
                    maxLength={3}
                    placeholder="INR"
                    className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm uppercase focus:outline-none focus:ring-2 focus:ring-indigo-500"
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

              <div className="pt-3 border-t border-slate-800">
                <div className="text-xs font-semibold uppercase text-slate-400 mb-2">Owner Assignment (Optional)</div>
                <div className="space-y-3">
                  <input
                    type="email"
                    value={ownerEmail}
                    onChange={(e) => setOwnerEmail(e.target.value)}
                    placeholder="owner@restaurant.com"
                    className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  {ownerEmail.trim() && (
                    <>
                      <input
                        type="text"
                        value={ownerName}
                        onChange={(e) => setOwnerName(e.target.value)}
                        placeholder="Owner display name"
                        className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                      <input
                        type="password"
                        value={ownerPassword}
                        onChange={(e) => setOwnerPassword(e.target.value)}
                        placeholder="Initial password (min 8 characters)"
                        className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </>
                  )}
                </div>
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

export default BusinessDirectoryPage;
