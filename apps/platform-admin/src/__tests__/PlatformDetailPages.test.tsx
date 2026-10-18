import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { BusinessDetailPage } from '../features/platform-admin/BusinessDetailPage';
import { OutletDetailPage } from '../features/platform-admin/OutletDetailPage';
import { PlatformBusiness, PlatformOutletDetail } from '@roms/shared-types';
import * as apiClient from '@roms/api-client';

const mockUseAuth = vi.fn();

vi.mock('@roms/api-client', async () => {
  const actual = await vi.importActual('@roms/api-client');
  return {
    ...actual,
    useAuth: () => mockUseAuth(),
    fetchPlatformBusiness: vi.fn(),
    updatePlatformBusinessProfile: vi.fn(),
    createPlatformOutlet: vi.fn(),
    fetchPlatformOutlet: vi.fn(),
    updatePlatformOutletProfile: vi.fn(),
    fetchBusinessEntitlements: vi.fn(),
    fetchPlatformAuditLogs: vi.fn(),
    fetchBusinessSubscriptions: vi.fn().mockResolvedValue([]),
  };
});

const sampleBusiness: PlatformBusiness = {
  id: 'biz-1',
  name: 'Valley Retreat',
  status: 'active',
  subscription_status: 'trial',
  plan_name: 'starter',
  max_outlets: 2,
  trial_ends_at: null,
  outlets: [
    {
      id: 'o-1',
      business_id: 'biz-1',
      name: 'Main Dining',
      public_slug: 'main-dining',
      currency: 'INR',
      timezone: 'Asia/Kolkata',
      address: 'Valley Rd',
      status: 'active',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const sampleOutlet: PlatformOutletDetail = {
  ...sampleBusiness.outlets[0],
  business_name: 'Valley Retreat',
};

function renderBusinessDetail() {
  return render(
    <MemoryRouter initialEntries={['/platform/businesses/biz-1']}>
      <Routes>
        <Route path="/platform/businesses/:businessId" element={<BusinessDetailPage />} />
        <Route path="/platform/outlets/:outletId" element={<div>Outlet Detail Route</div>} />
      </Routes>
    </MemoryRouter>
  );
}

function renderOutletDetail() {
  return render(
    <MemoryRouter initialEntries={['/platform/outlets/o-1']}>
      <Routes>
        <Route path="/platform/outlets/:outletId" element={<OutletDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('BusinessDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({ token: 'tok-123', user: { is_platform_admin: true, platform_role: 'admin' } });
  });

  it('renders business name, id, outlet table, and breadcrumb', async () => {
    (apiClient.fetchPlatformBusiness as any).mockResolvedValue(sampleBusiness);

    renderBusinessDetail();

    await waitFor(() => {
      expect(screen.getAllByText('Valley Retreat').length).toBeGreaterThan(0);
      expect(screen.getByText('biz-1')).toBeDefined();
      expect(screen.getByText('Main Dining')).toBeDefined();
      expect(screen.getByText('/m/main-dining')).toBeDefined();
    });
    expect(screen.getByRole('link', { name: 'Back to Businesses' })).toBeDefined();
    expect(screen.getByText('Assigned Outlets')).toBeDefined();
  });

  it('shows not-found panel when fetch returns 404', async () => {
    const err = new Error('missing') as Error & { status: number };
    err.status = 404;
    (apiClient.fetchPlatformBusiness as any).mockRejectedValue(err);

    renderBusinessDetail();

    await waitFor(() => {
      expect(screen.getByText('Business not found')).toBeDefined();
      expect(screen.getByText('Back to Business Directory')).toBeDefined();
    });
  });

  it('shows error panel with retry on non-404 failure', async () => {
    (apiClient.fetchPlatformBusiness as any).mockRejectedValue(new Error('boom'));

    renderBusinessDetail();

    await waitFor(() => {
      expect(screen.getByText('Failed to load business details')).toBeDefined();
      expect(screen.getByText('boom')).toBeDefined();
    });
  });

  it('navigates to outlet detail when outlet row is clicked', async () => {
    (apiClient.fetchPlatformBusiness as any).mockResolvedValue(sampleBusiness);

    renderBusinessDetail();

    const outletName = await screen.findByText('Main Dining');
    fireEvent.click(outletName);

    expect(screen.getByText('Outlet Detail Route')).toBeDefined();
  });

  it('saves business name via updatePlatformBusinessProfile', async () => {
    (apiClient.fetchPlatformBusiness as any).mockResolvedValue(sampleBusiness);
    (apiClient.updatePlatformBusinessProfile as any).mockResolvedValue({ ...sampleBusiness, name: 'Valley Retreat Renamed' });

    renderBusinessDetail();

    fireEvent.click(await screen.findByText('Edit details'));
    const input = screen.getByDisplayValue('Valley Retreat');
    fireEvent.change(input, { target: { value: 'Valley Retreat Renamed' } });
    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(apiClient.updatePlatformBusinessProfile).toHaveBeenCalledWith('biz-1', { name: 'Valley Retreat Renamed' }, 'tok-123');
      expect(screen.getAllByText('Valley Retreat Renamed').length).toBeGreaterThan(0);
    });
  });

  it('creates a new outlet and navigates to its detail page', async () => {
    (apiClient.fetchPlatformBusiness as any).mockResolvedValue(sampleBusiness);
    (apiClient.createPlatformOutlet as any).mockResolvedValue({
      ...sampleBusiness.outlets[0],
      id: 'o-new',
      name: 'New Branch',
      public_slug: 'new-branch',
    });

    renderBusinessDetail();

    fireEvent.click(await screen.findByText('Add outlet'));
    fireEvent.change(screen.getByPlaceholderText('e.g. Hillside Dhaba'), { target: { value: 'New Branch' } });
    fireEvent.change(screen.getByPlaceholderText('e.g. hillside-dhaba'), { target: { value: 'new-branch' } });
    fireEvent.click(screen.getByText('Create Outlet'));

    await waitFor(() => {
      expect(apiClient.createPlatformOutlet).toHaveBeenCalledWith('biz-1', expect.objectContaining({ name: 'New Branch', public_slug: 'new-branch' }), 'tok-123');
      expect(screen.getByText('Outlet Detail Route')).toBeDefined();
    });
  });

  it('shows empty state when business has no outlets', async () => {
    (apiClient.fetchPlatformBusiness as any).mockResolvedValue({ ...sampleBusiness, outlets: [] });

    renderBusinessDetail();

    await waitFor(() => {
      expect(screen.getByText('No outlets created yet')).toBeDefined();
      expect(screen.getByText('Assigned Outlets')).toBeDefined();
    });
  });

  it('loads business-scoped audit events on the Activity tab', async () => {
    (apiClient.fetchPlatformBusiness as any).mockResolvedValue(sampleBusiness);
    (apiClient.fetchPlatformAuditLogs as any).mockResolvedValue({
      items: [
        {
          id: 'log-1',
          business_id: 'biz-1',
          business_name: 'Valley Retreat',
          outlet_id: null,
          outlet_name: null,
          actor_user_id: 'u-1',
          actor_display_name: 'Aarav Mehta',
          actor_email: 'aarav@roms.internal',
          action: 'business_updated',
          entity_type: 'business',
          entity_id: 'biz-1',
          metadata_json: null,
          created_at: '2026-10-10T10:30:00Z',
        },
      ],
      total: 1,
      limit: 25,
      offset: 0,
    });

    renderBusinessDetail();

    fireEvent.click(await screen.findByRole('tab', { name: 'Activity' }));

    await waitFor(() => {
      expect(apiClient.fetchPlatformAuditLogs).toHaveBeenCalledWith('tok-123', {
        business_id: 'biz-1',
        limit: 25,
        offset: 0,
      });
      expect(screen.getByText('business_updated')).toBeDefined();
      expect(screen.getByText(/Aarav Mehta/)).toBeDefined();
    });
  });

  it('shows the subscription summary with outlet-scoped messaging', async () => {
    (apiClient.fetchPlatformBusiness as any).mockResolvedValue(sampleBusiness);

    renderBusinessDetail();

    fireEvent.click(await screen.findByRole('tab', { name: 'Subscription' }));

    expect(screen.getByText('Managed per outlet')).toBeDefined();
    expect(screen.getByText('Active outlets')).toBeDefined();
    expect(screen.getAllByText('Open Subscriptions').length).toBeGreaterThan(0);
    expect(await screen.findByText(/Subscription Lifecycle & History/i)).toBeDefined();
    expect(screen.getByText(/Outlet Subscriptions/i)).toBeDefined();
  });

  it('restricts editing for operator role', async () => {
    mockUseAuth.mockReturnValue({ token: 'tok-123', user: { is_platform_admin: false, platform_role: 'operator' } });
    (apiClient.fetchPlatformBusiness as any).mockResolvedValue(sampleBusiness);

    renderBusinessDetail();

    await waitFor(() => {
      expect(screen.getByText('Valley Retreat')).toBeDefined();
      expect(screen.queryByRole('button', { name: 'Edit details' })).toBeNull();
    });
  });
});

describe('OutletDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({ token: 'tok-123', user: { is_platform_admin: true, platform_role: 'admin' } });
  });

  it('renders outlet name, slug badge, status, and public menu link', async () => {
    (apiClient.fetchPlatformOutlet as any).mockResolvedValue(sampleOutlet);

    renderOutletDetail();

    await waitFor(() => {
      expect(screen.getAllByText('Main Dining').length).toBeGreaterThan(0);
      expect(screen.getAllByText('/m/main-dining').length).toBeGreaterThan(0);
      expect(screen.getByText('Profile & Config')).toBeDefined();
      expect(screen.getByText('Subscription & Entitlements')).toBeDefined();
    });
    const menuLinks = screen.getAllByRole('link', { name: '/m/main-dining' });
    expect(menuLinks.length).toBeGreaterThan(0);
    menuLinks.forEach((link) => expect(link.getAttribute('href')).toBe('/m/main-dining'));
  });

  it('shows not-found panel when fetch returns 404', async () => {
    const err = new Error('missing') as Error & { status: number };
    err.status = 404;
    (apiClient.fetchPlatformOutlet as any).mockRejectedValue(err);

    renderOutletDetail();

    await waitFor(() => {
      expect(screen.getByText('Outlet not found')).toBeDefined();
    });
  });

  it('saves profile via updatePlatformOutletProfile with validated payload', async () => {
    (apiClient.fetchPlatformOutlet as any).mockResolvedValue(sampleOutlet);
    (apiClient.updatePlatformOutletProfile as any).mockResolvedValue(sampleOutlet);

    renderOutletDetail();

    const nameInput = await screen.findByDisplayValue('Main Dining');
    fireEvent.change(nameInput, { target: { value: 'Main Dining Hall' } });
    fireEvent.click(screen.getByText('Save changes'));

    await waitFor(() => {
      expect(apiClient.updatePlatformOutletProfile).toHaveBeenCalledWith(
        'o-1',
        expect.objectContaining({ name: 'Main Dining Hall', timezone: 'Asia/Kolkata', currency: 'INR' }),
        'tok-123'
      );
      expect(screen.getByText('Profile updated successfully.')).toBeDefined();
    });
  });

  it('rejects invalid timezone client-side', async () => {
    (apiClient.fetchPlatformOutlet as any).mockResolvedValue(sampleOutlet);

    renderOutletDetail();

    const tzInput = await screen.findByDisplayValue('Asia/Kolkata');
    fireEvent.change(tzInput, { target: { value: 'Not/AZone' } });
    fireEvent.click(screen.getByText('Save changes'));

    await waitFor(() => {
      expect(screen.getByText(/valid IANA identifier/)).toBeDefined();
    });
    expect(apiClient.updatePlatformOutletProfile).not.toHaveBeenCalled();
  });

  it('loads and renders entitlements on subscription tab', async () => {
    (apiClient.fetchPlatformOutlet as any).mockResolvedValue(sampleOutlet);
    (apiClient.fetchBusinessEntitlements as any).mockResolvedValue({
      business_id: 'biz-1',
      business_name: 'Valley Retreat',
      business_status: 'active',
      outlet_id: 'o-1',
      outlet_name: 'Main Dining',
      subscription: {
        id: 'sub-1',
        status: 'trial',
        resolved_status: 'trial',
        plan_code: 'starter_pos',
        plan_name: 'Starter POS',
        plan_is_active: true,
        trial_ends_at: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString(),
        current_period_start: null,
        current_period_end: null,
        cancel_at_period_end: false,
        cancelled_at: null,
      },
      features: [
        {
          feature_code: 'pos_ordering',
          feature_name: 'POS Ordering',
          category: 'pos',
          authorized: true,
          limit_value: null,
          limit_type: 'unlimited',
          reason: 'plan_default',
          source: 'plan',
          scope: 'outlet',
        },
        {
          feature_code: 'qr_menu',
          feature_name: 'QR Menu',
          category: 'digital',
          authorized: false,
          limit_value: 0,
          limit_type: 'numeric',
          reason: 'not_in_plan',
          source: 'plan',
          scope: 'outlet',
        },
      ],
    });

    renderOutletDetail();

    fireEvent.click(await screen.findByText('Subscription & Entitlements'));

    await waitFor(() => {
      expect(apiClient.fetchBusinessEntitlements).toHaveBeenCalledWith('tok-123', 'biz-1', 'o-1');
      expect(screen.getByText('Starter POS')).toBeDefined();
      expect(screen.getByText('POS Ordering')).toBeDefined();
      expect(screen.getByText('Granted')).toBeDefined();
      expect(screen.getByText('Denied')).toBeDefined();
      expect(screen.getByText(/Subscriptions are canonical and managed independently per outlet/)).toBeDefined();
      expect(screen.getByRole('button', { name: 'Manage Subscription' })).toBeDefined();
    });
  });

  it('shows error panel with retry on entitlements failure', async () => {
    (apiClient.fetchPlatformOutlet as any).mockResolvedValue(sampleOutlet);
    (apiClient.fetchBusinessEntitlements as any).mockRejectedValue(new Error('entitlements down'));

    renderOutletDetail();

    fireEvent.click(await screen.findByText('Subscription & Entitlements'));

    await waitFor(() => {
      expect(screen.getByText('Failed to load entitlements')).toBeDefined();
      expect(screen.getByText('entitlements down')).toBeDefined();
    });
  });

  it('shows the unsaved-changes bar and discards edits without saving', async () => {
    (apiClient.fetchPlatformOutlet as any).mockResolvedValue(sampleOutlet);

    renderOutletDetail();

    const nameInput = await screen.findByDisplayValue('Main Dining');
    expect(screen.queryByText('You have unsaved changes')).toBeNull();

    fireEvent.change(nameInput, { target: { value: 'Changed Name' } });
    expect(screen.getByText('You have unsaved changes')).toBeDefined();

    fireEvent.click(screen.getByText('Discard'));

    expect(screen.getByDisplayValue('Main Dining')).toBeDefined();
    expect(screen.queryByText('You have unsaved changes')).toBeNull();
    expect(apiClient.updatePlatformOutletProfile).not.toHaveBeenCalled();
  });

  it('restricts editing for operator role', async () => {
    mockUseAuth.mockReturnValue({ token: 'tok-123', user: { is_platform_admin: false, platform_role: 'operator' } });
    (apiClient.fetchPlatformOutlet as any).mockResolvedValue(sampleOutlet);

    renderOutletDetail();

    await waitFor(() => {
      expect(screen.getAllByText('Main Dining').length).toBeGreaterThan(0);
    });

    const nameInput = screen.getByDisplayValue('Main Dining') as HTMLInputElement;
    expect(nameInput.disabled).toBe(true);
  });
});
