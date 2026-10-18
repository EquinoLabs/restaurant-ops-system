import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, fetchPlatformBusinesses } from '@roms/api-client';
import { PlatformBusiness } from '@roms/shared-types';
import { SubscriptionsOverview } from './SubscriptionsOverview';

export const SubscriptionsOverviewPage: React.FC = () => {
  const { token } = useAuth();
  const [businesses, setBusinesses] = useState<PlatformBusiness[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadBusinesses = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      setError(null);
      const data = await fetchPlatformBusinesses(token);
      setBusinesses(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load subscriptions overview.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  const navigate = useNavigate();

  useEffect(() => {
    loadBusinesses();
  }, [loadBusinesses]);

  return (
    <SubscriptionsOverview
      businesses={businesses}
      loading={loading}
      error={error}
      onRetry={loadBusinesses}
      token={token}
      onNavigateOutlet={(outletId) => navigate(`/platform/outlets/${outletId}`)}
    />
  );
};

export default SubscriptionsOverviewPage;
