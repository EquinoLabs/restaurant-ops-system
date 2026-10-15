import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { SubscriptionSummaryView } from '../features/subscription/SubscriptionSummaryView';
import * as authContext from '@roms/api-client';
import * as apiClient from '@roms/api-client';
import { OwnerSubscriptionSummary } from '@roms/shared-types';

describe('SubscriptionSummaryView Component', () => {
  const mockOwnerUser = {
    id: 'user-1',
    email: 'owner@test.com',
    display_name: 'Test Owner',
    status: 'active',
    is_platform_admin: false,
    platform_role: null,
    memberships: [
      {
        outlet_id: 'outlet-1',
        outlet_name: 'Riverside Camp',
        public_slug: 'riverside-camp',
        business_id: 'biz-1',
        business_name: 'Himachal Hospitality',
        role: 'owner',
      },
    ],
  };

  const mockManagerUser = {
    id: 'user-2',
    email: 'manager@test.com',
    display_name: 'Test Manager',
    status: 'active',
    is_platform_admin: false,
    platform_role: null,
    memberships: [
      {
        outlet_id: 'outlet-1',
        outlet_name: 'Riverside Camp',
        public_slug: 'riverside-camp',
        business_id: 'biz-1',
        business_name: 'Himachal Hospitality',
        role: 'manager',
      },
    ],
  };

  const sampleActiveSummary: OwnerSubscriptionSummary = {
    business_id: 'biz-1',
    business_name: 'Himachal Hospitality',
    business_status: 'active',
    plan: {
      code: 'growth_pos',
      name: 'Growth POS',
      description: 'Multi-outlet POS and KDS operations',
    },
    subscription: {
      status: 'active',
      is_current: true,
      trial_ends_at: null,
      current_period_start: '2026-10-01T00:00:00Z',
      current_period_end: '2027-10-01T00:00:00Z',
      cancel_at_period_end: false,
    },
    outlets: {
      current_count: 2,
      max_allowed: 3,
      is_limit_reached: false,
    },
    features: [
      {
        code: 'menu.digital',
        name: 'Digital Menu',
        category: 'menu',
        authorized: true,
        limit_value: null,
      },
      {
        code: 'outlets.max_count',
        name: 'Max Outlets',
        category: 'billing',
        authorized: true,
        limit_value: 3,
      },
    ],
    support_cta: {
      requires_action: false,
      reason: null,
      support_email: 'support@roms.com',
      message: null,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders subscription summary cleanly for an authorized owner', async () => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      token: 'valid-token',
      user: mockOwnerUser as any,
      loading: false,
      selectedOutlet: mockOwnerUser.memberships[0] as any,
      setSelectedOutletId: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });

    vi.spyOn(apiClient, 'fetchOwnerSubscriptionSummary').mockResolvedValue(sampleActiveSummary);

    render(
      <BrowserRouter>
        <SubscriptionSummaryView />
      </BrowserRouter>
    );

    expect(screen.getByText('Loading subscription details...')).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText('Growth POS')).toBeDefined();
    });

    expect(screen.getByText('Himachal Hospitality')).toBeDefined();
    expect(screen.getByText('Active')).toBeDefined();
    expect(screen.getByText(/of 3 Allowed/i)).toBeDefined();
    expect(screen.getByText('Capacity Available')).toBeDefined();
    expect(screen.getByText('Digital Menu')).toBeDefined();

    // Verify no misleading upgrade or checkout buttons exist
    expect(screen.queryByText(/upgrade now/i)).toBeNull();
    expect(screen.queryByText(/checkout/i)).toBeNull();
  });

  it('renders support CTA banner when trial has expired', async () => {
    const expiredSummary: OwnerSubscriptionSummary = {
      ...sampleActiveSummary,
      subscription: {
        ...sampleActiveSummary.subscription,
        status: 'expired',
        trial_ends_at: '2026-10-01T00:00:00Z',
      },
      support_cta: {
        requires_action: true,
        reason: 'TRIAL_EXPIRED',
        support_email: 'support@roms.com',
        message: 'Your trial has expired. Please contact support@roms.com to upgrade your subscription.',
      },
    };

    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      token: 'valid-token',
      user: mockOwnerUser as any,
      loading: false,
      selectedOutlet: mockOwnerUser.memberships[0] as any,
      setSelectedOutletId: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });

    vi.spyOn(apiClient, 'fetchOwnerSubscriptionSummary').mockResolvedValue(expiredSummary);

    render(
      <BrowserRouter>
        <SubscriptionSummaryView />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('support-cta-banner')).toBeDefined();
    });

    expect(screen.getByText(/Attention: Subscription Action Required/i)).toBeDefined();
    expect(screen.getByText(/Your trial has expired/i)).toBeDefined();
    expect(screen.getByText('Contact support@roms.com')).toBeDefined();
    expect(screen.getByText(/Self-service online upgrades are managed via platform administrators/i)).toBeDefined();
  });

  it('renders support CTA banner when outlet limit is reached', async () => {
    const limitReachedSummary: OwnerSubscriptionSummary = {
      ...sampleActiveSummary,
      outlets: {
        current_count: 3,
        max_allowed: 3,
        is_limit_reached: true,
      },
      support_cta: {
        requires_action: true,
        reason: 'OUTLET_LIMIT_REACHED',
        support_email: 'support@roms.com',
        message: 'You have reached your limit of 3 outlet(s). Contact support@roms.com to add more outlets.',
      },
    };

    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      token: 'valid-token',
      user: mockOwnerUser as any,
      loading: false,
      selectedOutlet: mockOwnerUser.memberships[0] as any,
      setSelectedOutletId: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });

    vi.spyOn(apiClient, 'fetchOwnerSubscriptionSummary').mockResolvedValue(limitReachedSummary);

    render(
      <BrowserRouter>
        <SubscriptionSummaryView />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('support-cta-banner')).toBeDefined();
    });

    expect(screen.getByText('Limit Reached')).toBeDefined();
    expect(screen.getByText(/reached your limit of 3 outlet\(s\)/i)).toBeDefined();
  });

  it('restricts access when user has only manager role and no owner membership', () => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      token: 'manager-token',
      user: mockManagerUser as any,
      loading: false,
      selectedOutlet: mockManagerUser.memberships[0] as any,
      setSelectedOutletId: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <BrowserRouter>
        <SubscriptionSummaryView />
      </BrowserRouter>
    );

    expect(screen.getByText('Owner Access Required')).toBeDefined();
    expect(screen.getByText(/Subscription and billing information is restricted to business owners/i)).toBeDefined();
    expect(screen.getByText('Return to Menu Management')).toBeDefined();
  });

  it('displays error state with retry option when API fails', async () => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      token: 'valid-token',
      user: mockOwnerUser as any,
      loading: false,
      selectedOutlet: mockOwnerUser.memberships[0] as any,
      setSelectedOutletId: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });

    vi.spyOn(apiClient, 'fetchOwnerSubscriptionSummary')
      .mockRejectedValueOnce(new Error('Network error: unable to reach API'))
      .mockResolvedValueOnce(sampleActiveSummary);

    render(
      <BrowserRouter>
        <SubscriptionSummaryView />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Unable to load subscription')).toBeDefined();
    });

    expect(screen.getByText('Network error: unable to reach API')).toBeDefined();

    const retryBtn = screen.getByText('Try Again');
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByText('Growth POS')).toBeDefined();
    });
  });
});
