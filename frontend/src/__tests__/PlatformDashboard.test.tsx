import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { PlatformShell } from '../features/platform-admin/PlatformShell';
import { DashboardOverview, calculateDashboardMetrics } from '../features/platform-admin/DashboardOverview';
import { PlatformBusiness } from '../types/platform';
import { AuthProvider } from '../features/authentication/AuthContext';
import * as authContext from '../features/authentication/AuthContext';

describe('calculateDashboardMetrics', () => {
  const referenceDate = new Date('2026-10-10T12:00:00Z');

  it('calculates metrics correctly for mixed business dataset', () => {
    const sampleBusinesses: PlatformBusiness[] = [
      {
        id: 'biz-1',
        name: 'Active Enterprise',
        status: 'active',
        subscription_status: 'active',
        plan_name: 'enterprise',
        max_outlets: 5,
        trial_ends_at: null,
        outlets: [
          {
            id: 'o-1',
            business_id: 'biz-1',
            name: 'Outlet A',
            public_slug: 'outlet-a',
            currency: 'INR',
            timezone: 'Asia/Kolkata',
            address: null,
            status: 'active',
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
          {
            id: 'o-2',
            business_id: 'biz-1',
            name: 'Outlet B',
            public_slug: 'outlet-b',
            currency: 'INR',
            timezone: 'Asia/Kolkata',
            address: null,
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
        name: 'Trial Business - Expiring Soon',
        status: 'active',
        subscription_status: 'trial',
        plan_name: 'starter',
        max_outlets: 2,
        trial_ends_at: '2026-10-14T12:00:00Z', // 4 days from reference date (within 7d)
        outlets: [
          {
            id: 'o-3',
            business_id: 'biz-2',
            name: 'Outlet C',
            public_slug: 'outlet-c',
            currency: 'INR',
            timezone: 'Asia/Kolkata',
            address: null,
            status: 'active',
            created_at: '2026-10-01T00:00:00Z',
            updated_at: '2026-10-01T00:00:00Z',
          },
        ],
        created_at: '2026-10-01T00:00:00Z',
        updated_at: '2026-10-01T00:00:00Z',
      },
      {
        id: 'biz-3',
        name: 'Trial Business - Expiring Far Future',
        status: 'active',
        subscription_status: 'trial',
        plan_name: 'starter',
        max_outlets: 2,
        trial_ends_at: '2026-11-01T12:00:00Z', // > 7 days
        outlets: [],
        created_at: '2026-10-05T00:00:00Z',
        updated_at: '2026-10-05T00:00:00Z',
      },
      {
        id: 'biz-4',
        name: 'Past Due Suspended Business',
        status: 'suspended',
        subscription_status: 'past_due',
        plan_name: 'pro',
        max_outlets: 3,
        trial_ends_at: null,
        outlets: [
          {
            id: 'o-4',
            business_id: 'biz-4',
            name: 'Outlet D',
            public_slug: 'outlet-d',
            currency: 'INR',
            timezone: 'Asia/Kolkata',
            address: null,
            status: 'active',
            created_at: '2026-02-01T00:00:00Z',
            updated_at: '2026-02-01T00:00:00Z',
          },
        ],
        created_at: '2026-02-01T00:00:00Z',
        updated_at: '2026-02-01T00:00:00Z',
      },
    ];

    const metrics = calculateDashboardMetrics(sampleBusinesses, referenceDate);

    expect(metrics.totalBusinesses).toBe(4);
    expect(metrics.totalOutlets).toBe(4);
    expect(metrics.businessesInTrial).toBe(2);
    expect(metrics.upcomingExpirations).toBe(1); // biz-2 only
    expect(metrics.pastDueSubscriptions).toBe(1); // biz-4
    expect(metrics.activeAccountCount).toBe(3);
    expect(metrics.suspendedAccountCount).toBe(1);
  });

  it('handles trial expiration filter edge cases correctly', () => {
    const edgeCaseBusinesses: PlatformBusiness[] = [
      {
        id: 'b-trial-valid',
        name: 'Valid Trial Expiring Soon',
        status: 'active',
        subscription_status: 'trial',
        plan_name: 'starter',
        max_outlets: 2,
        trial_ends_at: '2026-10-14T12:00:00Z', // 4d from ref date -> COUNTED
        outlets: [],
        created_at: '2026-10-01T00:00:00Z',
        updated_at: '2026-10-01T00:00:00Z',
      },
      {
        id: 'b-active-legacy-date',
        name: 'Converted Active Business with Legacy Trial Date',
        status: 'active',
        subscription_status: 'active', // NOT trial -> NOT COUNTED
        plan_name: 'pro',
        max_outlets: 5,
        trial_ends_at: '2026-10-14T12:00:00Z',
        outlets: [],
        created_at: '2026-10-01T00:00:00Z',
        updated_at: '2026-10-01T00:00:00Z',
      },
      {
        id: 'b-cancelled-legacy-date',
        name: 'Cancelled Business with Legacy Trial Date',
        status: 'suspended',
        subscription_status: 'cancelled', // NOT trial -> NOT COUNTED
        plan_name: 'starter',
        max_outlets: 1,
        trial_ends_at: '2026-10-14T12:00:00Z',
        outlets: [],
        created_at: '2026-10-01T00:00:00Z',
        updated_at: '2026-10-01T00:00:00Z',
      },
      {
        id: 'b-trial-expired',
        name: 'Trial Already Expired',
        status: 'active',
        subscription_status: 'trial',
        plan_name: 'starter',
        max_outlets: 2,
        trial_ends_at: '2026-10-05T12:00:00Z', // In past -> NOT COUNTED
        outlets: [],
        created_at: '2026-09-01T00:00:00Z',
        updated_at: '2026-09-01T00:00:00Z',
      },
      {
        id: 'b-trial-invalid-date',
        name: 'Trial with Invalid Date String',
        status: 'active',
        subscription_status: 'trial',
        plan_name: 'starter',
        max_outlets: 2,
        trial_ends_at: 'invalid-date-string', // Invalid -> NOT COUNTED
        outlets: [],
        created_at: '2026-10-01T00:00:00Z',
        updated_at: '2026-10-01T00:00:00Z',
      },
    ];

    const metrics = calculateDashboardMetrics(edgeCaseBusinesses, referenceDate);
    expect(metrics.upcomingExpirations).toBe(1);
  });

  it('returns zeroes for empty business dataset', () => {
    const metrics = calculateDashboardMetrics([], referenceDate);
    expect(metrics.totalBusinesses).toBe(0);
    expect(metrics.totalOutlets).toBe(0);
    expect(metrics.businessesInTrial).toBe(0);
    expect(metrics.upcomingExpirations).toBe(0);
    expect(metrics.pastDueSubscriptions).toBe(0);
    expect(metrics.activeAccountCount).toBe(0);
    expect(metrics.suspendedAccountCount).toBe(0);
  });
});

describe('PlatformShell Component', () => {
  it('renders header, navigation links, and handles tab switching', () => {
    const handleTabChange = vi.fn();

    render(
      <MemoryRouter>
        <AuthProvider>
          <PlatformShell activeTab="dashboard" onTabChange={handleTabChange}>
            <div>Inner Content</div>
          </PlatformShell>
        </AuthProvider>
      </MemoryRouter>
    );

    expect(screen.getByText('SaaS Control Plane')).toBeDefined();
    expect(screen.getByText('Inner Content')).toBeDefined();

    // Click Businesses navigation tab
    const bizButtons = screen.getAllByText('Businesses & Outlets');
    expect(bizButtons.length).toBeGreaterThan(0);
    fireEvent.click(bizButtons[0]);

    expect(handleTabChange).toHaveBeenCalledWith('businesses');
  });

  it('toggles mobile menu drawer', () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <PlatformShell activeTab="dashboard" onTabChange={vi.fn()}>
            <div>Inner Content</div>
          </PlatformShell>
        </AuthProvider>
      </MemoryRouter>
    );

    const toggleButton = screen.getByLabelText('Toggle Navigation Menu');
    expect(toggleButton).toBeDefined();
    fireEvent.click(toggleButton);

    expect(screen.getByText('Navigation Menu')).toBeDefined();
  });

  it('completely hides Platform Admins navigation tab from desktop sidebar and mobile menu when user is Operator', () => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      token: 'test-token',
      user: {
        id: 'op-1',
        email: 'operator@platform.com',
        display_name: 'Test Operator Account',
        status: 'active',
        is_platform_admin: false,
        platform_role: 'operator',
        memberships: [],
      },
      loading: false,
      selectedOutlet: null,
      setSelectedOutletId: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter>
        <PlatformShell activeTab="dashboard" onTabChange={vi.fn()}>
          <div>Inner Content</div>
        </PlatformShell>
      </MemoryRouter>
    );

    // Platform Admins navigation entry should be completely hidden
    expect(screen.queryByText('Platform Admins')).toBeNull();

    // Other tabs should remain visible
    expect(screen.getAllByText('Businesses & Outlets').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Subscriptions').length).toBeGreaterThan(0);

    // Header badge displays Platform Operator
    expect(screen.getByText('Platform Operator')).toBeDefined();
  });

  it('displays Platform Admins navigation tab and accurate role badge for Owner and Legacy Admin', () => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      token: 'test-token',
      user: {
        id: 'owner-1',
        email: 'owner@platform.com',
        display_name: 'Test Owner Account',
        status: 'active',
        is_platform_admin: true,
        platform_role: 'owner',
        memberships: [],
      },
      loading: false,
      selectedOutlet: null,
      setSelectedOutletId: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter>
        <PlatformShell activeTab="dashboard" onTabChange={vi.fn()}>
          <div>Inner Content</div>
        </PlatformShell>
      </MemoryRouter>
    );

    // Platform Admins tab is visible for Owner
    expect(screen.getAllByText('Platform Admins').length).toBeGreaterThan(0);
    expect(screen.getByText('Platform Owner')).toBeDefined();
  });
});

describe('DashboardOverview Component', () => {
  const sampleBusinesses: PlatformBusiness[] = [
    {
      id: 'biz-1',
      name: 'Himalayan Bistro',
      status: 'active',
      subscription_status: 'trial',
      plan_name: 'starter',
      max_outlets: 2,
      trial_ends_at: '2026-10-15T00:00:00Z',
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
          created_at: '2026-10-01T00:00:00Z',
          updated_at: '2026-10-01T00:00:00Z',
        },
      ],
      created_at: '2026-10-01T00:00:00Z',
      updated_at: '2026-10-01T00:00:00Z',
    },
  ];

  const referenceDate = new Date('2026-10-10T12:00:00Z');

  it('renders 5 metric cards and tenant overview table with Registered restaurant branches label', () => {
    render(
      <DashboardOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        referenceDate={referenceDate}
      />
    );

    expect(screen.getByText('Platform Overview')).toBeDefined();
    expect(screen.getByText('Himalayan Bistro')).toBeDefined();
    expect(screen.getByText(/Kasol Branch/)).toBeDefined();
    expect(screen.getByText('Registered restaurant branches')).toBeDefined();
  });

  it('renders loading spinner when loading and no data', () => {
    render(
      <DashboardOverview
        businesses={[]}
        loading={true}
        error={null}
      />
    );

    expect(screen.getByText('Loading platform metrics...')).toBeDefined();
  });

  it('renders empty state when business list is empty', () => {
    const handleProvisionClick = vi.fn();
    render(
      <DashboardOverview
        businesses={[]}
        loading={false}
        error={null}
        onOpenProvisionModal={handleProvisionClick}
      />
    );

    expect(screen.getByText('No tenant businesses registered yet.')).toBeDefined();
    const btn = screen.getByRole('button', { name: /Provision Business/i });
    fireEvent.click(btn);
    expect(handleProvisionClick).toHaveBeenCalled();
  });

  it('renders error banner and handles retry button click', () => {
    const handleRetry = vi.fn();
    render(
      <DashboardOverview
        businesses={[]}
        loading={false}
        error="Network response timeout"
        onRetry={handleRetry}
      />
    );

    expect(screen.getByText('Failed to load platform data')).toBeDefined();
    expect(screen.getByText('Network response timeout')).toBeDefined();

    const retryBtn = screen.getByRole('button', { name: /Retry Loading/i });
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalled();
  });
});
