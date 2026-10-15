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
    assignPlatformOwner: vi.fn(),
    fetchPlatformOutlet: vi.fn(),
    updatePlatformOutletProfile: vi.fn(),
    fetchBusinessEntitlements: vi.fn(),
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
    expect(screen.getByText('Businesses')).toBeDefined();
    expect(screen.getByText(/Outlets \(/)).toBeDefined();
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

  it('navigates to outlet detail when Manage Outlet is clicked', async () => {
    (apiClient.fetchPlatformBusiness as any).mockResolvedValue(sampleBusiness);

    renderBusinessDetail();

    const manageBtn = await screen.findByText('Manage Outlet');
    fireEvent.click(manageBtn);

    expect(screen.getByText('Outlet Detail Route')).toBeDefined();
  });

  it('saves business name via updatePlatformBusinessProfile', async () => {
    (apiClient.fetchPlatformBusiness as any).mockResolvedValue(sampleBusiness);
    (apiClient.updatePlatformBusinessProfile as any).mockResolvedValue({ ...sampleBusiness, name: 'Valley Retreat Renamed' });

    renderBusinessDetail();

    fireEvent.click(await screen.findByText('Edit Name'));
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

    fireEvent.click(await screen.findByText('Add Outlet'));
    fireEvent.change(screen.getByPlaceholderText('e.g. Hillside Dhaba'), { target: { value: 'New Branch' } });
    fireEvent.change(screen.getByPlaceholderText('e.g. hillside-dhaba'), { target: { value: 'new-branch' } });
    fireEvent.click(screen.getByText('Create Outlet'));

    await waitFor(() => {
      expect(apiClient.createPlatformOutlet).toHaveBeenCalledWith('biz-1', expect.objectContaining({ name: 'New Branch', public_slug: 'new-branch' }), 'tok-123');
      expect(screen.getByText('Outlet Detail Route')).toBeDefined();
    });
  });

  it('assigns an owner via assignPlatformOwner', async () => {
    (apiClient.fetchPlatformBusiness as any).mockResolvedValue(sampleBusiness);
    (apiClient.assignPlatformOwner as any).mockResolvedValue({});

    renderBusinessDetail();

    fireEvent.click(await screen.findByText('Assign Owner'));
    fireEvent.change(screen.getByPlaceholderText('e.g. Ramesh Kumar'), { target: { value: 'Ramesh Kumar' } });
    fireEvent.change(screen.getByPlaceholderText('owner@restaurant.com'), { target: { value: 'owner@test.com' } });
    fireEvent.change(screen.getByPlaceholderText('••••••••••••'), { target: { value: 'supersecret1' } });
    fireEvent.click(screen.getByText('Assign Owner Account'));

    await waitFor(() => {
      expect(apiClient.assignPlatformOwner).toHaveBeenCalledWith('biz-1', expect.objectContaining({ outlet_id: 'o-1', email: 'owner@test.com' }), 'tok-123');
    });
  });

  it('shows empty state when business has no outlets', async () => {
    (apiClient.fetchPlatformBusiness as any).mockResolvedValue({ ...sampleBusiness, outlets: [] });

    renderBusinessDetail();

    await waitFor(() => {
      expect(screen.getByText('No outlets created yet')).toBeDefined();
      expect(screen.getByText('Outlets (0)')).toBeDefined();
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
      expect(screen.getByText('/m/main-dining')).toBeDefined();
      expect(screen.getByText('Profile & Config')).toBeDefined();
      expect(screen.getByText('Subscription & Entitlements')).toBeDefined();
    });
    const menuLink = screen.getByText('Open Public Menu ↗');
    expect(menuLink.closest('a')?.getAttribute('href')).toBe('/m/main-dining');
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
    fireEvent.click(screen.getByText('Save Profile'));

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
    fireEvent.click(screen.getByText('Save Profile'));

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
      expect(screen.getByText(/outlet-level subscription write API/)).toBeDefined();
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
});
