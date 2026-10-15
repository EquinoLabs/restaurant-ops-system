import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { BusinessDirectory, filterBusinesses } from '../features/platform-admin/BusinessDirectory';
import { OutletDetailDrawer } from '../features/platform-admin/OutletDetailDrawer';
import { PlatformBusiness } from '@roms/shared-types';
import * as apiClient from '@roms/api-client';
import * as authContext from '@roms/api-client';

describe('filterBusinesses Helper Function', () => {
  const sampleBusinesses: PlatformBusiness[] = [
    {
      id: 'biz-1',
      name: 'Himalayan Hospitality',
      status: 'active',
      subscription_status: 'trial',
      plan_name: 'starter',
      max_outlets: 2,
      trial_ends_at: null,
      outlets: [
        {
          id: 'o-1',
          business_id: 'biz-1',
          name: 'Kasol Branch',
          public_slug: 'kasol-branch',
          currency: 'INR',
          timezone: 'Asia/Kolkata',
          address: 'Main Street',
          status: 'active',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    {
      id: 'biz-2',
      name: 'Shimla Sweets',
      status: 'suspended',
      subscription_status: 'past_due',
      plan_name: 'pro',
      max_outlets: 5,
      trial_ends_at: null,
      outlets: [
        {
          id: 'o-2',
          business_id: 'biz-2',
          name: 'Mall Road Outlet',
          public_slug: 'mall-road',
          currency: 'INR',
          timezone: 'Asia/Kolkata',
          address: 'Mall Road',
          status: 'active',
          created_at: '2026-02-01T00:00:00Z',
          updated_at: '2026-02-01T00:00:00Z',
        },
      ],
      created_at: '2026-02-01T00:00:00Z',
      updated_at: '2026-02-01T00:00:00Z',
    },
    {
      id: 'biz-3',
      name: 'Manali Heights',
      status: 'active',
      subscription_status: 'active',
      plan_name: 'enterprise',
      max_outlets: null,
      trial_ends_at: null,
      outlets: [],
      created_at: '2026-03-01T00:00:00Z',
      updated_at: '2026-03-01T00:00:00Z',
    },
  ];

  it('filters by search query matching business name', () => {
    const results = filterBusinesses(sampleBusinesses, 'Himalayan', 'all', 'all');
    expect(results.length).toBe(1);
    expect(results[0].id).toBe('biz-1');
  });

  it('filters by search query matching outlet slug', () => {
    const results = filterBusinesses(sampleBusinesses, 'mall-road', 'all', 'all');
    expect(results.length).toBe(1);
    expect(results[0].id).toBe('biz-2');
  });

  it('filters by operational status (active vs suspended)', () => {
    const activeOnly = filterBusinesses(sampleBusinesses, '', 'active', 'all');
    expect(activeOnly.length).toBe(2);

    const suspendedOnly = filterBusinesses(sampleBusinesses, '', 'suspended', 'all');
    expect(suspendedOnly.length).toBe(1);
    expect(suspendedOnly[0].id).toBe('biz-2');
  });

  it('filters by subscription status', () => {
    const trialOnly = filterBusinesses(sampleBusinesses, '', 'all', 'trial');
    expect(trialOnly.length).toBe(1);
    expect(trialOnly[0].id).toBe('biz-1');

    const pastDueOnly = filterBusinesses(sampleBusinesses, '', 'all', 'past_due');
    expect(pastDueOnly.length).toBe(1);
    expect(pastDueOnly[0].id).toBe('biz-2');
  });

  it('handles combined search query, status filter, and subscription filter', () => {
    const combined = filterBusinesses(sampleBusinesses, 'Manali', 'active', 'active');
    expect(combined.length).toBe(1);
    expect(combined[0].id).toBe('biz-3');

    const noMatch = filterBusinesses(sampleBusinesses, 'Himalayan', 'suspended', 'trial');
    expect(noMatch.length).toBe(0);
  });
});

describe('BusinessDirectory Component', () => {
  const sampleBusinesses: PlatformBusiness[] = [
    {
      id: 'biz-1',
      name: 'Valley Retreat',
      status: 'active',
      subscription_status: 'active',
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
    },
  ];

  it('renders search input, filter dropdowns, and business list', () => {
    render(
      <BusinessDirectory
        businesses={sampleBusinesses}
        loading={false}
        error={null}
      />
    );

    expect(screen.getByText('Businesses & Outlets Directory')).toBeDefined();
    expect(screen.getByPlaceholderText(/Search by business name/)).toBeDefined();
    expect(screen.getByText('Valley Retreat')).toBeDefined();
  });

  it('filters business list on user typing search query', () => {
    render(
      <BusinessDirectory
        businesses={sampleBusinesses}
        loading={false}
        error={null}
      />
    );

    const searchInput = screen.getByPlaceholderText(/Search by business name/);
    fireEvent.change(searchInput, { target: { value: 'NonExistentSearch' } });

    expect(screen.getByText('No businesses match the current search and filter criteria.')).toBeDefined();

    const clearBtn = screen.getByRole('button', { name: /Clear All Filters/i });
    fireEvent.click(clearBtn);

    expect(screen.getByText('Valley Retreat')).toBeDefined();
  });
});

describe('OutletDetailDrawer Component', () => {
  const sampleBusiness: PlatformBusiness = {
    id: 'biz-1',
    name: 'Pine Tree Cafe',
    status: 'active',
    subscription_status: 'trial',
    plan_name: 'starter',
    max_outlets: 3,
    trial_ends_at: '2026-10-20T00:00:00Z',
    outlets: [
      {
        id: 'o-1',
        business_id: 'biz-1',
        name: 'Hilltop Branch',
        public_slug: 'hilltop-branch',
        currency: 'INR',
        timezone: 'Asia/Kolkata',
        address: 'Hilltop Rd',
        status: 'active',
        created_at: '2026-10-01T00:00:00Z',
        updated_at: '2026-10-01T00:00:00Z',
      },
    ],
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
  };

  it('renders drawer content when open', () => {
    const handleClose = vi.fn();

    render(
      <OutletDetailDrawer
        business={sampleBusiness}
        isOpen={true}
        onClose={handleClose}
      />
    );

    expect(screen.getByText('Pine Tree Cafe')).toBeDefined();
    expect(screen.getByText('Hilltop Branch')).toBeDefined();
    expect(screen.getByText('/m/hilltop-branch')).toBeDefined();

    const closeBtn = screen.getByLabelText('Close Outlet Detail Drawer');
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalled();
  });

  it('renders empty outlet state when business has zero outlets', () => {
    const emptyBiz: PlatformBusiness = {
      ...sampleBusiness,
      outlets: [],
    };

    render(
      <OutletDetailDrawer
        business={emptyBiz}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText('No outlets registered under this business yet.')).toBeDefined();
  });

  it('allows Owner or Admin to edit business name successfully', async () => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      user: {
        id: 'u-admin',
        email: 'admin@platform.com',
        display_name: 'Platform Admin',
        status: 'active',
        is_platform_admin: true,
        platform_role: 'admin',
        outlets: [],
      },
      token: 'admin-token',
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
      loading: false,
    });

    vi.spyOn(apiClient, 'updatePlatformBusinessProfile').mockResolvedValue({
      ...sampleBusiness,
      name: 'Renamed Cafe',
    });

    const handleUpdated = vi.fn();

    render(
      <OutletDetailDrawer
        business={sampleBusiness}
        isOpen={true}
        onClose={vi.fn()}
        onBusinessUpdated={handleUpdated}
      />
    );

    const editBtn = screen.getByLabelText('Edit Business Name');
    fireEvent.click(editBtn);

    const input = screen.getByLabelText('Business Name Input');
    fireEvent.change(input, { target: { value: 'Renamed Cafe' } });

    const saveBtn = screen.getByRole('button', { name: /Save/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(apiClient.updatePlatformBusinessProfile).toHaveBeenCalledWith(
        'biz-1',
        { name: 'Renamed Cafe' },
        'admin-token'
      );
      expect(screen.getByText('Business name updated successfully.')).toBeDefined();
      expect(screen.getByText('Renamed Cafe')).toBeDefined();
      expect(handleUpdated).toHaveBeenCalled();
    });
  });

  it('restricts business name editing for Operators', () => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      user: {
        id: 'u-op',
        email: 'operator@platform.com',
        display_name: 'Platform Operator',
        status: 'active',
        is_platform_admin: false,
        platform_role: 'operator',
        outlets: [],
      },
      token: 'op-token',
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
      loading: false,
    });

    render(
      <OutletDetailDrawer
        business={sampleBusiness}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    expect(screen.queryByLabelText('Edit Business Name')).toBeNull();
    expect(screen.getByText('Name locked')).toBeDefined();
  });

  it('allows Operator to edit outlet profile successfully', async () => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      user: {
        id: 'u-op',
        email: 'operator@platform.com',
        display_name: 'Platform Operator',
        status: 'active',
        is_platform_admin: false,
        platform_role: 'operator',
        outlets: [],
      },
      token: 'op-token',
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
      loading: false,
    });

    vi.spyOn(apiClient, 'updatePlatformOutletProfile').mockResolvedValue({
      ...sampleBusiness.outlets[0],
      name: 'Hilltop Grand Branch',
      address: 'New Valley Road',
      timezone: 'Asia/Kolkata',
      currency: 'INR',
      primary_color: '#4F46E5',
      accent_color: '#10B981',
    });

    const handleUpdated = vi.fn();

    render(
      <OutletDetailDrawer
        business={sampleBusiness}
        isOpen={true}
        onClose={vi.fn()}
        onBusinessUpdated={handleUpdated}
      />
    );

    const editOutletBtn = screen.getByLabelText('Edit Profile for Hilltop Branch');
    fireEvent.click(editOutletBtn);

    // Modal open
    expect(screen.getByText('Edit Outlet Profile')).toBeDefined();
    expect(screen.getByLabelText('Public Slug Readonly')).toBeDefined();

    const nameInput = screen.getByLabelText('Outlet Name Input');
    fireEvent.change(nameInput, { target: { value: 'Hilltop Grand Branch' } });

    const addrInput = screen.getByLabelText('Physical Address Input');
    fireEvent.change(addrInput, { target: { value: 'New Valley Road' } });

    const saveChangesBtn = screen.getByRole('button', { name: /Save Changes/i });
    fireEvent.click(saveChangesBtn);

    await waitFor(() => {
      expect(apiClient.updatePlatformOutletProfile).toHaveBeenCalledWith(
        'o-1',
        expect.objectContaining({
          name: 'Hilltop Grand Branch',
          address: 'New Valley Road',
        }),
        'op-token'
      );
      expect(screen.getByText("Outlet 'Hilltop Grand Branch' profile updated successfully.")).toBeDefined();
      expect(screen.getByText('Hilltop Grand Branch')).toBeDefined();
      expect(handleUpdated).toHaveBeenCalled();
    });
  });

  it('validates outlet profile inputs before submitting', async () => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      user: {
        id: 'u-op',
        email: 'operator@platform.com',
        display_name: 'Platform Operator',
        status: 'active',
        is_platform_admin: false,
        platform_role: 'operator',
        outlets: [],
      },
      token: 'op-token',
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
      loading: false,
    });

    render(
      <OutletDetailDrawer
        business={sampleBusiness}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    const editOutletBtn = screen.getByLabelText('Edit Profile for Hilltop Branch');
    fireEvent.click(editOutletBtn);

    // 1. Invalid currency code
    const currInput = screen.getByLabelText('Currency Code Input');
    fireEvent.change(currInput, { target: { value: 'INVALID' } });

    const saveChangesBtn = screen.getByRole('button', { name: /Save Changes/i });
    fireEvent.click(saveChangesBtn);

    expect(screen.getByText('Currency code must be a 3-letter ISO code (e.g. INR, USD).')).toBeDefined();

    // 2. Fix currency, test invalid color format
    fireEvent.change(currInput, { target: { value: 'USD' } });
    const colorInput = screen.getByLabelText('Primary Color Input');
    fireEvent.change(colorInput, { target: { value: 'not-hex' } });

    fireEvent.click(saveChangesBtn);
    expect(screen.getByText('Primary color must be in #RRGGBB format (e.g. #4F46E5).')).toBeDefined();
  });

  it('displays error message when outlet update fails', async () => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      user: {
        id: 'u-op',
        email: 'operator@platform.com',
        display_name: 'Platform Operator',
        status: 'active',
        is_platform_admin: false,
        platform_role: 'operator',
        outlets: [],
      },
      token: 'op-token',
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
      loading: false,
    });

    vi.spyOn(apiClient, 'updatePlatformOutletProfile').mockRejectedValue(
      new Error('Server failed to update outlet')
    );

    render(
      <OutletDetailDrawer
        business={sampleBusiness}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    const editOutletBtn = screen.getByLabelText('Edit Profile for Hilltop Branch');
    fireEvent.click(editOutletBtn);

    const saveChangesBtn = screen.getByRole('button', { name: /Save Changes/i });
    fireEvent.click(saveChangesBtn);

    await waitFor(() => {
      expect(screen.getByText('Server failed to update outlet')).toBeDefined();
    });
  });

  it('hides Plan Tier, Outlet Capacity, and Trial Status cards for Operators', () => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      user: {
        id: 'u-op',
        email: 'operator@platform.com',
        display_name: 'Platform Operator',
        status: 'active',
        is_platform_admin: false,
        platform_role: 'operator',
        outlets: [],
      },
      token: 'op-token',
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
      loading: false,
    });

    render(
      <OutletDetailDrawer
        business={sampleBusiness}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    // Operator must NOT see commercial cards
    expect(screen.queryByText('Plan Tier')).toBeNull();
    expect(screen.queryByText('Outlet Capacity')).toBeNull();
    expect(screen.queryByText('Trial Status')).toBeNull();

    // Operational overview and outlet data remain fully visible
    expect(screen.getByText('Created Date')).toBeDefined();
    expect(screen.getByText('Hilltop Branch')).toBeDefined();
    expect(screen.getByText('Associated Outlets (1)')).toBeDefined();
  });

  it('displays commercial summary cards for Owner or Admin users', () => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      user: {
        id: 'u-admin',
        email: 'admin@platform.com',
        display_name: 'Platform Admin',
        status: 'active',
        is_platform_admin: true,
        platform_role: 'admin',
        outlets: [],
      },
      token: 'admin-token',
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
      loading: false,
    });

    render(
      <OutletDetailDrawer
        business={sampleBusiness}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText('Plan Tier')).toBeDefined();
    expect(screen.getByText('Outlet Capacity')).toBeDefined();
    expect(screen.getByText('Trial Status')).toBeDefined();
    expect(screen.getByText('Created Date')).toBeDefined();
  });

  it('fails closed and hides commercial summary cards when user role is missing or invalid', () => {
    // 1. Missing user
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      user: null,
      token: null,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: false,
      loading: false,
    });

    const { rerender } = render(
      <OutletDetailDrawer
        business={sampleBusiness}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    expect(screen.queryByText('Plan Tier')).toBeNull();
    expect(screen.queryByText('Outlet Capacity')).toBeNull();
    expect(screen.queryByText('Trial Status')).toBeNull();

    // 2. Invalid role
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      user: {
        id: 'u-invalid',
        email: 'invalid@platform.com',
        display_name: 'Invalid User',
        status: 'active',
        is_platform_admin: false,
        platform_role: 'unknown_role',
        outlets: [],
      },
      token: 'token',
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
      loading: false,
    });

    rerender(
      <OutletDetailDrawer
        business={sampleBusiness}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    expect(screen.queryByText('Plan Tier')).toBeNull();
    expect(screen.queryByText('Outlet Capacity')).toBeNull();
    expect(screen.queryByText('Trial Status')).toBeNull();
  });
});
