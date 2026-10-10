import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { SubscriptionsOverview, filterSubscriptions } from '../features/platform-admin/SubscriptionsOverview';
import { SubscriptionEditModal } from '../features/platform-admin/SubscriptionEditModal';
import { PlatformBusiness } from '../types/platform';
import * as apiClient from '../api/client';

describe('filterSubscriptions Helper Function', () => {
  const referenceDate = new Date('2026-10-10T12:00:00Z');

  const sampleBusinesses: PlatformBusiness[] = [
    {
      id: 'biz-1',
      name: 'Himalayan Bistro',
      status: 'active',
      subscription_status: 'trial',
      plan_name: 'starter',
      max_outlets: 2,
      trial_ends_at: '2026-10-14T12:00:00Z', // Expiring in 4 days -> Expiring soon
      outlets: [],
      created_at: '2026-10-01T00:00:00Z',
      updated_at: '2026-10-01T00:00:00Z',
    },
    {
      id: 'biz-2',
      name: 'Valley Inn',
      status: 'suspended',
      subscription_status: 'past_due',
      plan_name: 'pro',
      max_outlets: 5,
      trial_ends_at: null,
      outlets: [],
      created_at: '2026-02-01T00:00:00Z',
      updated_at: '2026-02-01T00:00:00Z',
    },
    {
      id: 'biz-3',
      name: 'Shimla Heights',
      status: 'active',
      subscription_status: 'active',
      plan_name: 'enterprise',
      max_outlets: null,
      trial_ends_at: '2026-10-14T12:00:00Z', // Active sub with legacy date -> NOT expiring trial
      outlets: [],
      created_at: '2026-03-01T00:00:00Z',
      updated_at: '2026-03-01T00:00:00Z',
    },
    {
      id: 'biz-4',
      name: 'Expired Cafe',
      status: 'active',
      subscription_status: 'trial',
      plan_name: 'starter',
      max_outlets: 1,
      trial_ends_at: '2026-10-01T12:00:00Z', // In past -> Expired trial
      outlets: [],
      created_at: '2026-09-01T00:00:00Z',
      updated_at: '2026-09-01T00:00:00Z',
    },
  ];

  it('filters by search query', () => {
    const results = filterSubscriptions(sampleBusinesses, 'Himalayan', 'all', 'all', 'all', referenceDate);
    expect(results.length).toBe(1);
    expect(results[0].id).toBe('biz-1');
  });

  it('filters by subscription status', () => {
    const pastDue = filterSubscriptions(sampleBusinesses, '', 'past_due', 'all', 'all', referenceDate);
    expect(pastDue.length).toBe(1);
    expect(pastDue[0].id).toBe('biz-2');
  });

  it('filters by operational status (keeping active vs suspended distinct)', () => {
    const suspended = filterSubscriptions(sampleBusinesses, '', 'all', 'suspended', 'all', referenceDate);
    expect(suspended.length).toBe(1);
    expect(suspended[0].id).toBe('biz-2');
  });

  it('filters trial expirations (< 7d vs expired) accurately without miscounting active/cancelled legacy dates', () => {
    const expiringSoon = filterSubscriptions(sampleBusinesses, '', 'all', 'all', 'expiring_soon', referenceDate);
    expect(expiringSoon.length).toBe(1);
    expect(expiringSoon[0].id).toBe('biz-1');

    const expired = filterSubscriptions(sampleBusinesses, '', 'all', 'all', 'expired', referenceDate);
    expect(expired.length).toBe(1);
    expect(expired[0].id).toBe('biz-4');
  });
});

describe('SubscriptionsOverview Component', () => {
  const sampleBusinesses: PlatformBusiness[] = [
    {
      id: 'biz-1',
      name: 'Pine Tree Cafe',
      status: 'active',
      subscription_status: 'trial',
      plan_name: 'starter',
      max_outlets: 2,
      trial_ends_at: '2026-10-15T00:00:00Z',
      outlets: [],
      created_at: '2026-10-01T00:00:00Z',
      updated_at: '2026-10-01T00:00:00Z',
    },
  ];

  it('renders subscriptions list with business names, plan tiers, and badges', () => {
    render(
      <SubscriptionsOverview
        businesses={sampleBusinesses}
        loading={false}
        error={null}
        token="test-token"
      />
    );

    expect(screen.getByText('Subscription & Billing Tiers')).toBeDefined();
    expect(screen.getByText('Pine Tree Cafe')).toBeDefined();
    expect(screen.getByText('starter')).toBeDefined();
    expect(screen.getAllByText('Trial').length).toBeGreaterThan(0);
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
});

describe('SubscriptionEditModal Component', () => {
  const sampleBusiness: PlatformBusiness = {
    id: 'biz-1',
    name: 'Mountain Peak Resort',
    status: 'active',
    subscription_status: 'trial',
    plan_name: 'starter',
    max_outlets: 2,
    trial_ends_at: '2026-10-20T00:00:00Z',
    outlets: [],
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
  };

  it('renders form pre-populated with existing business subscription values', () => {
    render(
      <SubscriptionEditModal
        business={sampleBusiness}
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        token="test-token"
      />
    );

    expect(screen.getByText('Manage Subscription & Status')).toBeDefined();
    expect(screen.getByText('Mountain Peak Resort')).toBeDefined();
  });

  it('validates max_outlets input (rejects values < 1)', () => {
    const { container } = render(
      <SubscriptionEditModal
        business={sampleBusiness}
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        token="test-token"
      />
    );

    const maxOutletsInput = screen.getByPlaceholderText(/e\.g\. 3/);
    fireEvent.change(maxOutletsInput, { target: { value: '-1' } });

    const form = container.querySelector('form')!;
    fireEvent.submit(form);

    expect(screen.getByText(/Max outlets limit must be a positive integer/)).toBeDefined();
  });

  it('requires confirmation step before calling subscription update API', async () => {
    const mockUpdate = vi.spyOn(apiClient, 'updatePlatformSubscription').mockResolvedValue({
      ...sampleBusiness,
      subscription_status: 'active',
      plan_name: 'pro',
    });

    const handleSuccess = vi.fn();
    const handleClose = vi.fn();

    const { container } = render(
      <SubscriptionEditModal
        business={sampleBusiness}
        isOpen={true}
        onClose={handleClose}
        onSuccess={handleSuccess}
        token="test-token"
      />
    );

    // Step 1: Submit form -> opens confirmation view
    const form = container.querySelector('form')!;
    fireEvent.submit(form);

    expect(screen.getByText('Confirm Subscription Update')).toBeDefined();
    expect(mockUpdate).not.toHaveBeenCalled();

    // Step 2: Click Confirm & Apply Changes -> triggers API call
    const confirmBtn = screen.getByRole('button', { name: /Confirm & Apply Changes/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith(
        'biz-1',
        expect.objectContaining({
          subscription_status: 'trial',
        }),
        'test-token'
      );
      expect(handleSuccess).toHaveBeenCalled();
      expect(handleClose).toHaveBeenCalled();
    });

    mockUpdate.mockRestore();
  });

  it('displays API error banner when update fails and does not call onSuccess', async () => {
    const mockUpdate = vi.spyOn(apiClient, 'updatePlatformSubscription').mockRejectedValue(
      new Error('Invalid plan parameters')
    );

    const handleSuccess = vi.fn();

    const { container } = render(
      <SubscriptionEditModal
        business={sampleBusiness}
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={handleSuccess}
        token="test-token"
      />
    );

    const form = container.querySelector('form')!;
    fireEvent.submit(form);

    fireEvent.click(screen.getByRole('button', { name: /Confirm & Apply Changes/i }));

    await waitFor(() => {
      expect(screen.getByText('Invalid plan parameters')).toBeDefined();
      expect(handleSuccess).not.toHaveBeenCalled();
    });

    mockUpdate.mockRestore();
  });
});
