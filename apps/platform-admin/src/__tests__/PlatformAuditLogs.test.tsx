import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PlatformAuditLogs } from '../features/platform-admin/PlatformAuditLogs';
import { PlatformAuditLogsResponse, PlatformBusiness } from '@roms/shared-types';
import * as apiClient from '@roms/api-client';

describe('PlatformAuditLogs Component', () => {
  const sampleBusinesses: PlatformBusiness[] = [
    {
      id: 'biz-1',
      name: 'Himalayan Bistro',
      status: 'active',
      subscription_status: 'trial',
      plan_name: 'starter',
      max_outlets: 2,
      trial_ends_at: null,
      outlets: [],
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ];

  const sampleAuditResponse: PlatformAuditLogsResponse = {
    items: [
      {
        id: 'log-1',
        business_id: 'biz-1',
        business_name: 'Himalayan Bistro',
        outlet_id: 'outlet-1',
        outlet_name: 'Kasol Main',
        actor_user_id: 'user-1',
        actor_display_name: 'Super Admin',
        actor_email: 'admin@platform.com',
        action: 'platform.business.create',
        entity_type: 'business',
        entity_id: 'biz-1',
        metadata_json: { outcome: 'success', plan_name: 'starter' },
        created_at: '2026-10-10T12:00:00Z',
      },
      {
        id: 'log-2',
        business_id: null,
        business_name: null,
        outlet_id: null,
        outlet_name: null,
        actor_user_id: null,
        actor_display_name: null,
        actor_email: null,
        action: 'platform.admin.grant',
        entity_type: 'user',
        entity_id: 'user-2',
        metadata_json: { outcome: 'success' },
        created_at: '2026-10-09T10:00:00Z',
      },
    ],
    total: 2,
    limit: 50,
    offset: 0,
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders platform audit log viewer with list of audit events and actor/business details', async () => {
    vi.spyOn(apiClient, 'fetchPlatformAuditLogs').mockResolvedValue(sampleAuditResponse);

    render(<PlatformAuditLogs token="test-token" businesses={sampleBusinesses} />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Audit logs' })).toBeDefined();
      expect(screen.getAllByText('platform.business.create').length).toBeGreaterThan(0);
    });

    expect(screen.getAllByText('Business Provisioned').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Himalayan Bistro').length).toBeGreaterThan(0);
    expect(screen.getByText('Kasol Main')).toBeDefined();
    expect(screen.getByText('Super Admin')).toBeDefined();
    expect(screen.getByText('admin@platform.com')).toBeDefined();
    expect(screen.getAllByText('platform.admin.grant').length).toBeGreaterThan(0);
    expect(screen.getByText('System / Automated')).toBeDefined();
    expect(screen.getByText('System Level')).toBeDefined();
  });

  it('handles action and business filter changes', async () => {
    const fetchSpy = vi
      .spyOn(apiClient, 'fetchPlatformAuditLogs')
      .mockResolvedValue(sampleAuditResponse);

    render(<PlatformAuditLogs token="test-token" businesses={sampleBusinesses} />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Audit logs' })).toBeDefined();
    });

    const actionSelect = screen.getByLabelText(/Action Type/i);
    fireEvent.change(actionSelect, { target: { value: 'platform.business.create' } });

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith('test-token', {
        limit: 50,
        offset: 0,
        action: 'platform.business.create',
        business_id: undefined,
      });
    });
  });

  it('handles pagination (Previous and Next page navigation)', async () => {
    const paginatedResp: PlatformAuditLogsResponse = {
      ...sampleAuditResponse,
      total: 100,
      limit: 50,
      offset: 0,
    };
    const fetchSpy = vi.spyOn(apiClient, 'fetchPlatformAuditLogs').mockResolvedValue(paginatedResp);

    render(<PlatformAuditLogs token="test-token" businesses={sampleBusinesses} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Next/i })).toBeDefined();
    });

    const nextBtn = screen.getByRole('button', { name: /Next/i });
    expect(nextBtn.hasAttribute('disabled')).toBe(false);

    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith('test-token', {
        limit: 50,
        offset: 50,
        action: undefined,
        business_id: undefined,
      });
    });
  });

  it('opens the audit event detail drawer when clicking View Details', async () => {
    vi.spyOn(apiClient, 'fetchPlatformAuditLogs').mockResolvedValue(sampleAuditResponse);

    render(<PlatformAuditLogs token="test-token" businesses={sampleBusinesses} />);

    await waitFor(() => {
      expect(screen.getAllByText('platform.business.create').length).toBeGreaterThan(0);
    });

    const viewDetailsBtns = screen.getAllByRole('button', { name: /View Details/i });
    fireEvent.click(viewDetailsBtns[0]);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Audit event detail' })).toBeDefined();
      expect(screen.getByText(/Captured Metadata Payload/i)).toBeDefined();
      expect(screen.getByText(/"plan_name": "starter"/i)).toBeDefined();
      expect(screen.getByRole('button', { name: /Close inspector panel/i })).toBeDefined();
    });
  });

  it('handles empty audit log state', async () => {
    vi.spyOn(apiClient, 'fetchPlatformAuditLogs').mockResolvedValue({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    });

    render(<PlatformAuditLogs token="test-token" businesses={sampleBusinesses} />);

    await waitFor(() => {
      expect(
        screen.getByText('No platform audit events match the selected criteria.')
      ).toBeDefined();
    });
  });

  it('handles API error and permits retry', async () => {
    const fetchSpy = vi
      .spyOn(apiClient, 'fetchPlatformAuditLogs')
      .mockRejectedValueOnce(new Error('Server communication error'))
      .mockResolvedValueOnce(sampleAuditResponse);

    render(<PlatformAuditLogs token="test-token" businesses={sampleBusinesses} />);

    await waitFor(() => {
      expect(screen.getByText('Error Loading Audit Logs')).toBeDefined();
      expect(screen.getByText('Server communication error')).toBeDefined();
    });

    const retryBtn = screen.getByRole('button', { name: /Retry/i });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledTimes(2);
      expect(screen.getByRole('heading', { name: 'Audit logs' })).toBeDefined();
    });
  });
});
