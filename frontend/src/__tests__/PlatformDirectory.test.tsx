import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { BusinessDirectory, filterBusinesses } from '../features/platform-admin/BusinessDirectory';
import { OutletDetailDrawer } from '../features/platform-admin/OutletDetailDrawer';
import { PlatformBusiness } from '../types/platform';

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
});
