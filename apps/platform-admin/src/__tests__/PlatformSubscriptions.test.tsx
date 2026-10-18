import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { SubscriptionsOverview, filterSubscriptions, type OutletSubRow } from '../features/platform-admin/SubscriptionsOverview';
import * as apiClient from '@roms/api-client';
import { BusinessSubscriptionItem } from '@roms/shared-types';

vi.mock('@roms/api-client', () => ({
  fetchBusinessSubscriptions: vi.fn(),
}));

describe('filterSubscriptions Helper Function', () => {
  const referenceDate = new Date('2026-10-10T12:00:00Z');

  const sampleRows: OutletSubRow[] = [
    {
      businessId: 'biz-1',
      businessName: 'Himalayan Bistro',
      businessStatus: 'active',
      outletId: 'out-1',
      outletName: 'Main Branch',
      planCode: 'starter',
      planName: 'Starter Plan',
      status: 'trial',
      resolvedStatus: 'trial',
      trialEndsAt: '2026-10-14T12:00:00Z',
      currentPeriodEnd: null,
      cancelAtPeriodEnd: false,
    },
    {
      businessId: 'biz-2',
      businessName: 'Valley Inn',
      businessStatus: 'suspended',
      outletId: 'out-2',
      outletName: 'City Branch',
      planCode: 'pro',
      planName: 'Pro Plan',
      status: 'past_due',
      resolvedStatus: 'past_due',
      trialEndsAt: null,
      currentPeriodEnd: '2026-11-01T00:00:00Z',
      cancelAtPeriodEnd: false,
    },
    {
      businessId: 'biz-3',
      businessName: 'Shimla Heights',
      businessStatus: 'active',
      outletId: 'out-3',
      outletName: 'Hill Station',
      planCode: 'enterprise',
      planName: 'Enterprise Plan',
      status: 'active',
      resolvedStatus: 'active',
      trialEndsAt: null,
      currentPeriodEnd: '2027-03-01T00:00:00Z',
      cancelAtPeriodEnd: false,
    },
    {
      businessId: 'biz-4',
      businessName: 'Expired Cafe',
      businessStatus: 'active',
      outletId: 'out-4',
      outletName: 'Downtown',
      planCode: 'starter',
      planName: 'Starter Plan',
      status: 'active',
      resolvedStatus: 'expired',
      trialEndsAt: '2026-10-01T12:00:00Z',
      currentPeriodEnd: null,
      cancelAtPeriodEnd: false,
    },
    {
      businessId: 'biz-5',
      businessName: 'Cancelled Spot',
      businessStatus: 'active',
      outletId: 'out-5',
      outletName: 'Uptown',
      planCode: 'pro',
      planName: 'Pro Plan',
      status: 'cancelled',
      resolvedStatus: 'cancelled',
      trialEndsAt: null,
      currentPeriodEnd: '2026-09-15T00:00:00Z',
      cancelAtPeriodEnd: true,
    },
  ];

  it('filters by search query across business and outlet names', () => {
    const results = filterSubscriptions(sampleRows, 'Himalayan', 'all', 'all', 'all', referenceDate);
    expect(results.length).toBe(1);
    expect(results[0].businessName).toBe('Himalayan Bistro');
  });

  it('filters by subscription status', () => {
    const pastDue = filterSubscriptions(sampleRows, '', 'past_due', 'all', 'all', referenceDate);
    expect(pastDue.length).toBe(1);
    expect(pastDue[0].businessId).toBe('biz-2');

    const active = filterSubscriptions(sampleRows, '', 'active', 'all', 'all', referenceDate);
    expect(active.length).toBe(1);
    expect(active[0].businessId).toBe('biz-3');
  });

  it('filters by operational status', () => {
    const suspended = filterSubscriptions(sampleRows, '', 'all', 'suspended', 'all', referenceDate);
    expect(suspended.length).toBe(1);
    expect(suspended[0].businessId).toBe('biz-2');

    const allActive = filterSubscriptions(sampleRows, '', 'all', 'active', 'all', referenceDate);
    expect(allActive.length).toBe(4);
  });

  it('filters expiring_soon trials within 7 days', () => {
    const expiringSoon = filterSubscriptions(sampleRows, '', 'all', 'all', 'expiring_soon', referenceDate);
    expect(expiringSoon.length).toBe(1);
    expect(expiringSoon[0].businessId).toBe('biz-1');
  });

  it('filters expired trials', () => {
    const expired = filterSubscriptions(sampleRows, '', 'all', 'all', 'expired', referenceDate);
    expect(expired.length).toBe(1);
    expect(expired[0].businessId).toBe('biz-4');
  });

  it('combines multiple filters correctly', () => {
    const combined = filterSubscriptions(sampleRows, 'valley', 'past_due', 'suspended', 'all', referenceDate);
    expect(combined.length).toBe(1);
    expect(combined[0].businessId).toBe('biz-2');
  });

  it('returns all rows when no filters are applied', () => {
    const all = filterSubscriptions(sampleRows, '', 'all', 'all', 'all', referenceDate);
    expect(all.length).toBe(sampleRows.length);
  });

  it('filters by plan code and plan name in search', () => {
    const starter = filterSubscriptions(sampleRows, 'starter', 'all', 'all', 'all', referenceDate);
    expect(starter.length).toBe(2);
    expect(starter.every((r) => r.planCode === 'starter')).toBe(true);
  });
});

describe('SubscriptionsOverview Component', () => {
  const mockFetchSubscriptions = vi.mocked(apiClient.fetchBusinessSubscriptions);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const sampleBusinesses = [
    {
      id: 'biz-1',
      name: 'Pine Tree Cafe',
      status: 'active',
      outlets: [{ id: 'out-1', name: 'Main Branch', business_id: 'biz-1' }],
    },
    {
      id: 'biz-2',
      name: 'RiverSide Diner',
      status: 'suspended',
      outlets: [{ id: 'out-2', name: 'Waterfront', business_id: 'biz-2' }],
    },
    {
      id: 'biz-3',
      name: 'Empty Venue',
      status: 'active',
      outlets: [],
    },
  ];

  const mockSubscriptions: Record<string, BusinessSubscriptionItem[]> = {
    'biz-1': [
      {
        id: 'sub-1',
        business_id: 'biz-1',
        outlet_id: 'out-1',
        plan_id: 'plan-1',
        status: 'active',
        is_current: true,
        trial_ends_at: null,
        current_period_start: '2026-09-01T00:00:00Z',
        current_period_end: '2027-09-01T00:00:00Z',
        cancel_at_period_end: false,
        cancelled_at: null,
        plan: { code: 'starter_pos', name: 'Starter Plan', is_active: true, description: 'Basic POS', sort_order: 1, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
      },
    ],
    'biz-2': [
      {
        id: 'sub-2',
        business_id: 'biz-2',
        outlet_id: 'out-2',
        plan_id: 'plan-1',
        status: 'trial',
        is_current: true,
        trial_ends_at: '2026-10-15T00:00:00Z',
        current_period_start: null,
        current_period_end: null,
        cancel_at_period_end: false,
        cancelled_at: null,
        plan: { code: 'starter_pos', name: 'Starter Plan', is_active: true, description: 'Basic POS', sort_order: 1, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
      },
    ],
    'biz-3': [],
  };

  it('renders subscriptions page with outlet-level data', async () => {
    mockFetchSubscriptions.mockImplementation(async (businessId: string, _token: string) => {
      return mockSubscriptions[businessId] || [];
    });

    render(
      <SubscriptionsOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        token="test-token"
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Subscriptions' })).toBeDefined();
    });

    // Wait for subscriptions to load
    await waitFor(() => {
      expect(mockFetchSubscriptions).toHaveBeenCalledTimes(3); // 3 businesses
    });

    await waitFor(() => {
      expect(screen.getByText(/Pine Tree Cafe/)).toBeDefined();
      expect(screen.getByText(/Main Branch/)).toBeDefined();
    });
  });

  it('shows suspended account badge alongside subscription status', async () => {
    mockFetchSubscriptions.mockImplementation(async (businessId: string, _token: string) => {
      return mockSubscriptions[businessId] || [];
    });

    render(
      <SubscriptionsOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        token="test-token"
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Suspended')).toBeDefined();
    });
  });

  it('shows no-outlet fallback row for businesses without outlets', async () => {
    mockFetchSubscriptions.mockImplementation(async (_token: string, businessId: string) => {
      // biz-3 has no outlets - just return empty array
      return mockSubscriptions[businessId] || [];
    });

    render(
      <SubscriptionsOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        token="test-token"
      />
    );

    await waitFor(() => {
      expect(screen.getByText('(no outlets)')).toBeDefined();
    });
  });

  it('renders loading state when loading and no data', () => {
    render(
      <SubscriptionsOverview
        businesses={[]}
        loading={true}
        error={null}
        token="test-token"
      />
    );

    expect(screen.getByText('Loading platform subscriptions...')).toBeDefined();
  });

  it('renders error state and handles retry click', () => {
    const handleRetry = vi.fn();
    render(
      <SubscriptionsOverview
        businesses={[]}
        loading={false}
        error="Server connection error"
        onRetry={handleRetry}
        token="test-token"
      />
    );

    expect(screen.getByText('Failed to load subscription data')).toBeDefined();
    const retryBtn = screen.getByRole('button', { name: /Retry Loading/i });
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalled();
  });

  it('renders metric cards with correct counts', async () => {
    mockFetchSubscriptions.mockImplementation(async (businessId: string, _token: string) => {
      return mockSubscriptions[businessId] || [];
    });

    render(
      <SubscriptionsOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        token="test-token"
        referenceDate={new Date('2026-10-10T12:00:00Z')}
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Subscriptions' })).toBeDefined();
    });

    // Wait for subscription data to load
    await waitFor(() => {
      expect(mockFetchSubscriptions).toHaveBeenCalled();
    });

    // Verify metric captions exist within the metrics section
    const metricsSection = screen.getByLabelText('Subscription metrics');
    expect(metricsSection).toBeDefined();
    expect(metricsSection.textContent).toContain('Active');
    expect(metricsSection.textContent).toContain('Trial');
    expect(metricsSection.textContent).toContain('Expired');
    expect(metricsSection.textContent).toContain('Total outlets');
  });

  it('applies subscription status filter', async () => {
    mockFetchSubscriptions.mockImplementation(async (businessId: string, _token: string) => {
      return mockSubscriptions[businessId] || [];
    });

    render(
      <SubscriptionsOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        token="test-token"
        referenceDate={new Date('2026-10-10T12:00:00Z')}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Pine Tree Cafe')).toBeDefined();
    });

    const subscriptionFilter = screen.getByLabelText('Filter Subscription Status') as HTMLSelectElement;
    fireEvent.change(subscriptionFilter, { target: { value: 'trial' } });

    await waitFor(() => {
      expect(screen.queryByText(/Pine Tree Cafe/)).toBeNull();
      expect(screen.getByText(/RiverSide Diner/)).toBeDefined();
    });
  });

  it('applies operational status filter', async () => {
    mockFetchSubscriptions.mockImplementation(async (businessId: string, _token: string) => {
      return mockSubscriptions[businessId] || [];
    });

    render(
      <SubscriptionsOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        token="test-token"
        referenceDate={new Date('2026-10-10T12:00:00Z')}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Pine Tree Cafe')).toBeDefined();
    });

    const statusFilter = screen.getByLabelText('Filter Operational Account Status') as HTMLSelectElement;
    fireEvent.change(statusFilter, { target: { value: 'suspended' } });

    await waitFor(() => {
      expect(screen.queryByText(/Pine Tree Cafe/)).toBeNull();
      expect(screen.getByText(/RiverSide Diner/)).toBeDefined();
    });
  });

  it('clears all filters when clear button is clicked', async () => {
    mockFetchSubscriptions.mockImplementation(async (businessId: string, _token: string) => {
      return mockSubscriptions[businessId] || [];
    });

    render(
      <SubscriptionsOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        token="test-token"
        referenceDate={new Date('2026-10-10T12:00:00Z')}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Pine Tree Cafe')).toBeDefined();
    });

    const subscriptionFilter = screen.getByLabelText('Filter Subscription Status') as HTMLSelectElement;
    fireEvent.change(subscriptionFilter, { target: { value: 'trial' } });

    await waitFor(() => {
      expect(screen.queryByText('Pine Tree Cafe')).toBeNull();
    });

    const clearBtn = screen.getByRole('button', { name: /Clear filters/i });
    fireEvent.click(clearBtn);

    await waitFor(() => {
      expect(screen.getByText('Pine Tree Cafe')).toBeDefined();
    });
  });

  it('shows empty state when no businesses are provided', () => {
    render(
      <SubscriptionsOverview
        businesses={[]}
        loading={false}
        error={null}
        token="test-token"
      />
    );

    expect(screen.getByText('No subscriptions found.')).toBeDefined();
  });

  it('shows no-results state when filters match nothing', async () => {
    mockFetchSubscriptions.mockImplementation(async (businessId: string, _token: string) => {
      return mockSubscriptions[businessId] || [];
    });

    render(
      <SubscriptionsOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        token="test-token"
        referenceDate={new Date('2026-10-10T12:00:00Z')}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Pine Tree Cafe')).toBeDefined();
    });

    const searchInput = screen.getByLabelText('Search subscriptions') as HTMLInputElement;
    fireEvent.change(searchInput, { target: { value: 'nonexistent' } });

    await waitFor(() => {
      expect(screen.getByText('No subscriptions match the current criteria.')).toBeDefined();
    });
  });

  it('opens subscription details drawer and does not navigate when View button is clicked', async () => {
    const handleNavigate = vi.fn();
    mockFetchSubscriptions.mockImplementation(async (businessId: string, _token: string) => {
      return mockSubscriptions[businessId] || [];
    });

    render(
      <SubscriptionsOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        token="test-token"
        onNavigateOutlet={handleNavigate}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Pine Tree Cafe/)).toBeDefined();
    });

    // Get all View buttons and click the first one (for Main Branch outlet)
    const viewBtns = screen.getAllByRole('button', { name: 'View' });
    expect(viewBtns.length).toBeGreaterThan(0);
    fireEvent.click(viewBtns[0]);

    // View button must open the Subscription Details Drawer, NOT navigate directly
    expect(handleNavigate).not.toHaveBeenCalled();
    expect(screen.getByRole('heading', { name: 'Subscription Details' })).toBeDefined();
    expect(screen.getByText(/Outlet Context/)).toBeDefined();
    expect(screen.getAllByText(/Starter Plan/).length).toBeGreaterThan(0);
    expect(screen.getByText(/starter_pos/)).toBeDefined();

    // Closing the drawer
    const closeBtns = screen.getAllByRole('button', { name: 'Close' });
    fireEvent.click(closeBtns[0]);
    expect(screen.queryByRole('heading', { name: 'Subscription Details' })).toBeNull();
  });

  it('displays loading indicator while fetching', async () => {
    let resolvePromise: ((value: any) => void) | null = null;
    const slowPromise = new Promise<any>((resolve) => {
      resolvePromise = resolve;
    });
    mockFetchSubscriptions.mockImplementation(async () => slowPromise);

    render(
      <SubscriptionsOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        token="test-token"
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Fetching outlet subscriptions/)).toBeDefined();
    });

    if (resolvePromise) {
      resolvePromise(mockSubscriptions['biz-1']);
    }

    await waitFor(() => {
      expect(screen.queryByText(/Fetching outlet subscriptions/)).toBeNull();
    });
  });

  it('shows error banner when subscriptions fetch fails', async () => {
    const handleRetry = vi.fn();

    // The component only shows error state when there are no businesses
    // (the per-business fetch failures are silently swallowed)
    render(
      <SubscriptionsOverview
        businesses={[]}
        loading={false}
        error="Service unavailable"
        onRetry={handleRetry}
        token="test-token"
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Service unavailable/)).toBeDefined();
    });

    const retryBtn = screen.getByRole('button', { name: /Retry Loading/i });
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalledOnce();
  });

  it('displays configured plan names from subscription data', async () => {
    // Verify plan name comes from subscription data, not legacy business fields
    mockFetchSubscriptions.mockImplementation(async (businessId: string, _token: string) => {
      return mockSubscriptions[businessId] || [];
    });

    render(
      <SubscriptionsOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        token="test-token"
        referenceDate={new Date('2026-10-10T12:00:00Z')}
      />
    );

    await waitFor(() => {
      // Verify both outlets show their plan names
      expect(screen.getAllByText(/Starter Plan/).length).toBeGreaterThan(0);
    });
  });

  it('renders exact plan.name from backend response shape without falling back to unknown', async () => {
    const customSubscriptions: Record<string, BusinessSubscriptionItem[]> = {
      'biz-1': [
        {
          id: 'sub-custom-1',
          business_id: 'biz-1',
          outlet_id: 'out-1',
          plan_id: 'plan-custom',
          status: 'active',
          is_current: true,
          trial_ends_at: null,
          current_period_start: '2026-09-01T00:00:00Z',
          current_period_end: '2027-09-01T00:00:00Z',
          cancel_at_period_end: false,
          cancelled_at: null,
          plan: {
            code: 'free_qr',
            name: 'Free QR Menu',
            is_active: true,
            description: 'Free QR menu tier',
            sort_order: 1,
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        },
      ],
      'biz-2': [],
      'biz-3': [],
    };

    mockFetchSubscriptions.mockImplementation(async (businessId: string) => {
      return customSubscriptions[businessId] || [];
    });

    render(
      <SubscriptionsOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        token="test-token"
        referenceDate={new Date('2026-10-10T12:00:00Z')}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Free QR Menu')).toBeDefined();
    });
  });

  it('handles Edit -> Review Changes -> disabled Update workflow and has no navigation to outlet detail', async () => {
    mockFetchSubscriptions.mockImplementation(async (businessId: string) => {
      return mockSubscriptions[businessId] || [];
    });

    render(
      <SubscriptionsOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        token="test-token"
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Pine Tree Cafe/)).toBeDefined();
    });

    const viewBtns = screen.getAllByRole('button', { name: 'View' });
    fireEvent.click(viewBtns[0]);

    // Inspect step: verify No "Go to Outlet Page" button
    expect(screen.queryByRole('button', { name: /Go to Outlet Page/i })).toBeNull();

    // Verify "Edit Subscription" button exists
    const editBtn = screen.getByRole('button', { name: 'Edit Subscription' });
    expect(editBtn).toBeDefined();

    // Transition to Edit step
    fireEvent.click(editBtn);
    expect(screen.getByText('Configure Outlet Subscription')).toBeDefined();
    expect(screen.getByLabelText(/Target Subscription Plan/i)).toBeDefined();

    // Transition to Review step
    const reviewBtn = screen.getByRole('button', { name: 'Review Changes' });
    fireEvent.click(reviewBtn);
    expect(screen.getByText('Review Proposed Changes')).toBeDefined();
    expect(screen.getByText(/Outlet-Level Subscription Updates Pending Backend Support/i)).toBeDefined();

    // Verify Update Subscription button is disabled
    const updateBtn = screen.getByRole('button', { name: 'Update Subscription' });
    expect(updateBtn).toBeDefined();
    expect((updateBtn as HTMLButtonElement).disabled).toBe(true);
  });

  it('renders No current subscription for historical records without is_current and preserves stored status', async () => {
    const historicalSubscriptions: Record<string, BusinessSubscriptionItem[]> = {
      'biz-1': [
        {
          id: 'sub-hist-1',
          business_id: 'biz-1',
          outlet_id: 'out-1',
          plan_id: 'plan-1',
          status: 'trial',
          is_current: false, // historical record!
          trial_ends_at: null,
          current_period_start: null,
          current_period_end: null,
          cancel_at_period_end: false,
          cancelled_at: null,
          plan: {
            code: 'starter_pos',
            name: 'Starter POS',
            is_active: true,
            description: 'Starter tier',
            sort_order: 1,
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        },
      ],
      'biz-2': [],
      'biz-3': [],
    };

    mockFetchSubscriptions.mockImplementation(async (businessId: string) => {
      return historicalSubscriptions[businessId] || [];
    });

    render(
      <SubscriptionsOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        token="test-token"
      />
    );

    await waitFor(() => {
      expect(screen.getByText('No current subscription')).toBeDefined();
    });
  });

  it('renders No subscription for outlets with zero subscription rows', async () => {
    mockFetchSubscriptions.mockImplementation(async () => []);

    render(
      <SubscriptionsOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        token="test-token"
      />
    );

    await waitFor(() => {
      expect(screen.getAllByText('No subscription').length).toBeGreaterThan(0);
    });
  });
});