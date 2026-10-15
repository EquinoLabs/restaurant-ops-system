import React, { useState, useEffect, useCallback } from 'react';
import { useAuth, fetchPlatformBusinesses } from '@roms/api-client';
import { PlatformBusiness } from '@roms/shared-types';
import { PlatformAuditLogs } from './PlatformAuditLogs';

export const AuditLogsPage: React.FC = () => {
  const { token } = useAuth();
  const [businesses, setBusinesses] = useState<PlatformBusiness[]>([]);

  const loadBusinesses = useCallback(async () => {
    if (!token) return;
    try {
      const data = await fetchPlatformBusinesses(token);
      setBusinesses(data);
    } catch {
      // Business filter is non-blocking for audit log rendering
    }
  }, [token]);

  useEffect(() => {
    loadBusinesses();
  }, [loadBusinesses]);

  return <PlatformAuditLogs token={token} businesses={businesses} />;
};

export default AuditLogsPage;
