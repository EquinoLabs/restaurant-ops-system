import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@roms/api-client';
import {
  fetchPlatformBusinesses,
  createPlatformBusiness,
} from '@roms/api-client';
import { PlatformBusiness, PlatformBusinessCreatePayload } from '@roms/shared-types';
import { BusinessDirectory } from './BusinessDirectory';
import { Button, FormField, opsInputClass } from '../../components/ops-ui';

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
    owner_email: '',
    owner_password: '',
    owner_display_name: '',
    public_slug: '',
    currency: 'INR',
    timezone: 'Asia/Kolkata',
    address: '',
  });
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
    if (!bizForm.name.trim() || !bizForm.owner_email.trim() || !bizForm.owner_password.trim() || !bizForm.owner_display_name.trim() || !slug) {
      setProvisionError('Business name, owner details, and public slug are required.');
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
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(bizForm.owner_email.trim())) {
      setProvisionError('Owner email is not a valid email address.');
      return;
    }
    if (bizForm.owner_display_name.trim().length < 1) {
      setProvisionError('Owner display name is required.');
      return;
    }
    if (bizForm.owner_password.length < 8) {
      setProvisionError('Owner password must be at least 8 characters.');
      return;
    }

    try {
      setIsSubmitting(true);
      setSuccessMessage(null);
      const created = await createPlatformBusiness(
        {
          ...bizForm,
          name: bizForm.name.trim(),
          public_slug: slug,
        },
        token
      );

      setIsProvisionOpen(false);
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

      navigate(`/platform/businesses/${created.id}`);
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
        onOpenProvisionModal={() => {
          setProvisionError(null);
          setIsProvisionOpen(true);
        }}
        onViewBusiness={(businessId) => navigate(`/platform/businesses/${businessId}`)}
      />

      {isProvisionOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-[rgba(31,41,51,0.40)]" aria-hidden="true" />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="provision-business-title"
            className="relative flex max-h-[90vh] w-full max-w-lg flex-col rounded-md border border-ops-border bg-white shadow-ops-l2"
          >
            <div className="flex items-center justify-between border-b border-ops-border p-5">
              <h2
                id="provision-business-title"
                className="text-base font-semibold text-ops-text-primary"
              >
                Add business
              </h2>
              <button
                type="button"
                onClick={() => setIsProvisionOpen(false)}
                className="rounded p-1 text-ops-text-secondary hover:bg-ops-canvas hover:text-ops-text-primary focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
                aria-label="Close"
                disabled={isSubmitting}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateBusinessSubmit} className="flex-1 space-y-4 overflow-y-auto p-5">
              <FormField id="biz-name" label="Business name" required>
                <input
                  id="biz-name"
                  type="text"
                  required
                  value={bizForm.name}
                  onChange={(e) => setBizForm({ ...bizForm, name: e.target.value })}
                  placeholder="e.g. Himalayan Hospitality Pvt Ltd"
                  className={opsInputClass}
                />
              </FormField>

              <FormField
                id="biz-slug"
                label="Public slug"
                required
                hint="Lowercase letters, numbers, and hyphens only."
              >
                <input
                  id="biz-slug"
                  type="text"
                  required
                  value={bizForm.public_slug}
                  onChange={(e) =>
                    setBizForm({
                      ...bizForm,
                      public_slug: e.target.value.toLowerCase().replace(/\s+/g, '-'),
                    })
                  }
                  placeholder="e.g. riverside-camp"
                  className={opsInputClass}
                />
              </FormField>

              <div className="grid grid-cols-2 gap-3">
                <FormField id="biz-currency" label="Currency">
                  <input
                    id="biz-currency"
                    type="text"
                    value={bizForm.currency || ''}
                    onChange={(e) =>
                      setBizForm({ ...bizForm, currency: e.target.value.toUpperCase() })
                    }
                    maxLength={3}
                    placeholder="INR"
                    className={`${opsInputClass} uppercase`}
                  />
                </FormField>
                <FormField id="biz-timezone" label="Timezone">
                  <input
                    id="biz-timezone"
                    type="text"
                    value={bizForm.timezone || ''}
                    onChange={(e) => setBizForm({ ...bizForm, timezone: e.target.value })}
                    placeholder="Asia/Kolkata"
                    className={opsInputClass}
                  />
                </FormField>
              </div>

              <FormField id="biz-address" label="Address" hint="Optional">
                <input
                  id="biz-address"
                  type="text"
                  value={bizForm.address || ''}
                  onChange={(e) => setBizForm({ ...bizForm, address: e.target.value })}
                  placeholder="Kasol Highway, HP"
                  className={opsInputClass}
                />
              </FormField>

              <div className="border-t border-ops-divider pt-4">
                <div className="mb-3 text-xs font-semibold text-ops-text-secondary">
                  Owner assignment (required)
                </div>
                <div className="space-y-3">
                  <FormField id="owner-email" label="Owner email" required>
                    <input
                      id="owner-email"
                      type="email"
                      required
                      value={bizForm.owner_email}
                      onChange={(e) => setBizForm({ ...bizForm, owner_email: e.target.value })}
                      placeholder="owner@restaurant.com"
                      className={opsInputClass}
                    />
                  </FormField>
                  <FormField id="owner-name" label="Owner display name" required>
                    <input
                      id="owner-name"
                      type="text"
                      required
                      value={bizForm.owner_display_name}
                      onChange={(e) => setBizForm({ ...bizForm, owner_display_name: e.target.value })}
                      placeholder="Owner display name"
                      className={opsInputClass}
                    />
                  </FormField>
                  <FormField
                    id="owner-password"
                    label="Initial password"
                    required
                    hint="Minimum 8 characters."
                  >
                    <input
                      id="owner-password"
                      type="password"
                      required
                      value={bizForm.owner_password}
                      onChange={(e) => setBizForm({ ...bizForm, owner_password: e.target.value })}
                      placeholder="Initial password"
                      className={opsInputClass}
                    />
                  </FormField>
                </div>
              </div>

              {provisionError && (
                <p role="alert" className="text-xs text-ops-error">
                  {provisionError}
                </p>
              )}

              <div className="flex justify-end gap-2 border-t border-ops-border pt-4">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setIsProvisionOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" variant="primary" disabled={isSubmitting}>
                  {isSubmitting ? 'Adding…' : 'Add business'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
};

export default BusinessDirectoryPage;
