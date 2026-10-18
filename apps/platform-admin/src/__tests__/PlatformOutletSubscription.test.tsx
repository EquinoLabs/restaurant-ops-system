import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { OutletDetailPage } from '../features/platform-admin/OutletDetailPage';
import { PlatformOutletDetail, PlatformBusinessEntitlementsResponse } from '@roms/shared-types';
import * as apiClient from '@roms/api-client';
import * as outletSubApi from '../features/platform-admin/outletSubscriptionApi';

const mockUseAuth = vi.fn();

vi.mock('@roms/api-client', async () => {
  const actual = await vi.importActual('@roms/api-client');
  return {
    ...actual,
    useAuth: () => mockUseAuth(),
    fetchPlatformOutlet: vi.fn(),
    updatePlatformOutletProfile: vi.fn(),
    fetchBusinessEntitlements: vi.fn(),
  };
});

vi.mock('../features/platform-admin/outletSubscriptionApi', () => ({
  updatePlatformOutletSubscription: vi.fn(),
}));

const sampleOutlet: PlatformOutletDetail = {
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
  business_name: 'Valley Retreat',
};

const sampleEntitlements: PlatformBusinessEntitlementsResponse = {
  business_id: 'biz-1',
  outlet_id: 'o-1',
  subscription: {
    plan_code: 'growth_pos',
    plan_name: 'Growth POS',
    status: 'active',
    resolved_status: 'active',
    trial_ends_at: null,
    current_period_start: '2026-01-01T00:00:00Z',
    current_period_end: '2027-01-01T00:00:00Z',
    cancel_at_period_end: false,
    scope: 'outlet',
  },
  features: [
    {
      feature_code: 'pos_orders',
      feature_name: 'POS Ordering',
      category: 'operations',
      authorized: true,
      limit_value: null,
      limit_type: 'boolean',
      reason: 'plan_default',
      source: 'plan',
      scope: 'outlet',
    },
  ],
};

function renderOutletDetail() {
  return render(
    <MemoryRouter initialEntries={['/platform/outlets/o-1']}>
      <Routes>
        <Route path="/platform/outlets/:outletId" element={<OutletDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('OutletDetailPage - Outlet Subscription Management', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      token: 'tok-123',
      user: { is_platform_admin: true, platform_role: 'admin' },
    });
    (apiClient.fetchPlatformOutlet as any).mockResolvedValue(sampleOutlet);
    (apiClient.fetchBusinessEntitlements as any).mockResolvedValue(sampleEntitlements);
    (outletSubApi.updatePlatformOutletSubscription as any).mockResolvedValue({
      id: 'sub-1',
      outlet_id: 'o-1',
      status: 'active',
      is_current: true,
    });
  });

  it('renders "Manage Subscription" button for admin and opens the drawer', async () => {
    renderOutletDetail();

    fireEvent.click(await screen.findByText('Subscription & Entitlements'));

    const manageBtn = await screen.findByRole('button', { name: 'Manage Subscription' });
    expect(manageBtn).toBeDefined();

    fireEvent.click(manageBtn);

    expect(await screen.findByText('Manage Outlet Subscription')).toBeDefined();
    expect(screen.getByLabelText(/Lifecycle Action/i)).toBeDefined();
  });

  it('hides "Manage Subscription" button for operators', async () => {
    mockUseAuth.mockReturnValue({
      token: 'tok-123',
      user: { is_platform_admin: false, platform_role: 'operator' },
    });

    renderOutletDetail();

    fireEvent.click(await screen.findByText('Subscription & Entitlements'));

    await waitFor(() => {
      expect(screen.getByText('Growth POS')).toBeDefined();
    });

    expect(screen.queryByRole('button', { name: 'Manage Subscription' })).toBeNull();
  });

  it('submits a mid-term plan change directly without confirmation prompt', async () => {
    renderOutletDetail();

    fireEvent.click(await screen.findByText('Subscription & Entitlements'));
    fireEvent.click(await screen.findByRole('button', { name: 'Manage Subscription' }));

    const actionSelect = await screen.findByLabelText(/Lifecycle Action/i);
    fireEvent.change(actionSelect, { target: { value: 'change_plan' } });

    const planSelect = screen.getByLabelText(/Plan/i);
    fireEvent.change(planSelect, { target: { value: 'pro_kds' } });

    const applyBtn = screen.getByRole('button', { name: 'Apply Action' });
    fireEvent.click(applyBtn);

    await waitFor(() => {
      expect(outletSubApi.updatePlatformOutletSubscription).toHaveBeenCalledWith(
        'o-1',
        {
          action_type: 'change_plan',
          plan_code: 'pro_kds',
        },
        'tok-123'
      );
    });

    // Verify refresh was triggered
    expect(apiClient.fetchBusinessEntitlements).toHaveBeenCalledTimes(2);
  });

  it('requires confirmation prompt for immediate cancellation with reason', async () => {
    renderOutletDetail();

    fireEvent.click(await screen.findByText('Subscription & Entitlements'));
    fireEvent.click(await screen.findByRole('button', { name: 'Manage Subscription' }));

    const actionSelect = await screen.findByLabelText(/Lifecycle Action/i);
    fireEvent.change(actionSelect, { target: { value: 'cancel_immediately' } });

    const reasonInput = screen.getByLabelText(/Administrative Reason/i);
    fireEvent.change(reasonInput, { target: { value: 'Customer closed down outlet' } });

    const applyBtn = screen.getByRole('button', { name: 'Apply Action' });
    fireEvent.click(applyBtn);

    // Confirmation dialog should appear
    expect(await screen.findByText('Cancel Subscription Immediately')).toBeDefined();
    expect(screen.getByText(/type CANCEL below/i)).toBeDefined();

    // Type CANCEL in the dialog input
    const confirmInput = screen.getByPlaceholderText('CANCEL');
    fireEvent.change(confirmInput, { target: { value: 'CANCEL' } });

    const confirmBtn = screen.getByRole('button', { name: 'Cancel Immediately' });
    expect(confirmBtn).not.toBeNull();
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(outletSubApi.updatePlatformOutletSubscription).toHaveBeenCalledWith(
        'o-1',
        {
          action_type: 'cancel_immediately',
          reason: 'Customer closed down outlet',
        },
        'tok-123'
      );
    });
  });

  it('requires confirmation prompt for committing a new annual term', async () => {
    renderOutletDetail();

    fireEvent.click(await screen.findByText('Subscription & Entitlements'));
    fireEvent.click(await screen.findByRole('button', { name: 'Manage Subscription' }));

    const actionSelect = await screen.findByLabelText(/Lifecycle Action/i);
    fireEvent.change(actionSelect, { target: { value: 'change_plan_new_term' } });

    const applyBtn = screen.getByRole('button', { name: 'Apply Action' });
    fireEvent.click(applyBtn);

    // Confirmation dialog should appear for new annual term
    expect(await screen.findByText('Commit New Annual Subscription Term')).toBeDefined();
    expect(screen.getByText(/type CONFIRM below/i)).toBeDefined();

    const confirmInput = screen.getByPlaceholderText('CONFIRM');
    fireEvent.change(confirmInput, { target: { value: 'CONFIRM' } });

    const confirmBtn = screen.getByRole('button', { name: 'Confirm New Term' });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(outletSubApi.updatePlatformOutletSubscription).toHaveBeenCalledWith(
        'o-1',
        expect.objectContaining({
          action_type: 'change_plan_new_term',
        }),
        'tok-123'
      );
    });
  });

  it('displays backend error message on failure', async () => {
    (outletSubApi.updatePlatformOutletSubscription as any).mockRejectedValue(
      new Error('current_period_end must be strictly in the future.')
    );

    renderOutletDetail();

    fireEvent.click(await screen.findByText('Subscription & Entitlements'));
    fireEvent.click(await screen.findByRole('button', { name: 'Manage Subscription' }));

    const actionSelect = await screen.findByLabelText(/Lifecycle Action/i);
    fireEvent.change(actionSelect, { target: { value: 'change_plan' } });

    const applyBtn = screen.getByRole('button', { name: 'Apply Action' });
    fireEvent.click(applyBtn);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeDefined();
      expect(
        screen.getByText('current_period_end must be strictly in the future.')
      ).toBeDefined();
    });
  });

  describe('Scheduled cancellation display & actions (Task A)', () => {
    it('displays distinct pending-cancellation status badge and effective date when cancel_at_period_end is true', async () => {
      (apiClient.fetchBusinessEntitlements as any).mockResolvedValue({
        ...sampleEntitlements,
        subscription: {
          ...sampleEntitlements.subscription,
          resolved_status: 'active',
          cancel_at_period_end: true,
          current_period_end: '2027-01-01T00:00:00Z',
        },
      });

      renderOutletDetail();

      fireEvent.click(await screen.findByText('Subscription & Entitlements'));

      await waitFor(() => {
        expect(screen.getByText('Active — cancellation scheduled')).toBeDefined();
        expect(screen.getByText(/Effective on/i)).toBeDefined();
      });
    });

    it('shows "Revoke Scheduled Cancellation" and hides "Schedule Cancellation" when cancellation is scheduled', async () => {
      (apiClient.fetchBusinessEntitlements as any).mockResolvedValue({
        ...sampleEntitlements,
        subscription: {
          ...sampleEntitlements.subscription,
          resolved_status: 'active',
          cancel_at_period_end: true,
          current_period_end: '2027-01-01T00:00:00Z',
        },
      });

      renderOutletDetail();

      fireEvent.click(await screen.findByText('Subscription & Entitlements'));
      fireEvent.click(await screen.findByRole('button', { name: 'Manage Subscription' }));

      const actionSelect = await screen.findByLabelText(/Lifecycle Action/i);
      const options = Array.from(actionSelect.querySelectorAll('option')).map((o) => o.value);

      expect(options).toContain('revoke_scheduled_cancellation');
      expect(options).not.toContain('schedule_cancellation');
    });

    it('shows "Schedule Cancellation" and hides "Revoke Scheduled Cancellation" when no cancellation is scheduled', async () => {
      (apiClient.fetchBusinessEntitlements as any).mockResolvedValue({
        ...sampleEntitlements,
        subscription: {
          ...sampleEntitlements.subscription,
          resolved_status: 'active',
          cancel_at_period_end: false,
          current_period_end: '2027-01-01T00:00:00Z',
        },
      });

      renderOutletDetail();

      fireEvent.click(await screen.findByText('Subscription & Entitlements'));
      fireEvent.click(await screen.findByRole('button', { name: 'Manage Subscription' }));

      const actionSelect = await screen.findByLabelText(/Lifecycle Action/i);
      const options = Array.from(actionSelect.querySelectorAll('option')).map((o) => o.value);

      expect(options).toContain('schedule_cancellation');
      expect(options).not.toContain('revoke_scheduled_cancellation');
    });

    it('displays ordinary Active and Cancelled states without pending cancellation text', async () => {
      (apiClient.fetchBusinessEntitlements as any).mockResolvedValue({
        ...sampleEntitlements,
        subscription: {
          ...sampleEntitlements.subscription,
          resolved_status: 'active',
          cancel_at_period_end: false,
        },
      });

      const { unmount } = renderOutletDetail();
      fireEvent.click(await screen.findByText('Subscription & Entitlements'));

      await waitFor(() => {
        expect(screen.getByText('Active')).toBeDefined();
        expect(screen.queryByText('Active — cancellation scheduled')).toBeNull();
      });

      unmount();

      (apiClient.fetchBusinessEntitlements as any).mockResolvedValue({
        ...sampleEntitlements,
        subscription: {
          ...sampleEntitlements.subscription,
          resolved_status: 'cancelled',
          cancel_at_period_end: false,
        },
      });

      renderOutletDetail();
      fireEvent.click(await screen.findByText('Subscription & Entitlements'));

      await waitFor(() => {
        expect(screen.getByText('Cancelled')).toBeDefined();
        expect(screen.queryByText(/cancellation scheduled/i)).toBeNull();
      });
    });
  });

  describe('Datetime semantics & payload serialization (Task B)', () => {
    it('omits optional period-end override when left blank so backend computes the 1-year term', async () => {
      renderOutletDetail();

      fireEvent.click(await screen.findByText('Subscription & Entitlements'));
      fireEvent.click(await screen.findByRole('button', { name: 'Manage Subscription' }));

      const actionSelect = await screen.findByLabelText(/Lifecycle Action/i);
      fireEvent.change(actionSelect, { target: { value: 'renew' } });

      const applyBtn = screen.getByRole('button', { name: 'Apply Action' });
      fireEvent.click(applyBtn);

      await waitFor(() => {
        expect(outletSubApi.updatePlatformOutletSubscription).toHaveBeenCalledWith(
          'o-1',
          {
            action_type: 'renew',
            plan_code: 'growth_pos',
          },
          'tok-123'
        );
      });
    });

    it('correctly serializes Asia/Kolkata local datetime-local values to UTC ISO string', async () => {
      renderOutletDetail();

      fireEvent.click(await screen.findByText('Subscription & Entitlements'));
      fireEvent.click(await screen.findByRole('button', { name: 'Manage Subscription' }));

      const actionSelect = await screen.findByLabelText(/Lifecycle Action/i);
      fireEvent.change(actionSelect, { target: { value: 'renew' } });

      // Simulate entering an explicit period start and end
      const startInput = screen.getByLabelText(/Period Start Date Override/i);
      const endInput = screen.getByLabelText(/Period End Date Override/i);

      fireEvent.change(startInput, { target: { value: '2026-06-01T10:00' } });
      fireEvent.change(endInput, { target: { value: '2027-06-01T10:00' } });

      const applyBtn = screen.getByRole('button', { name: 'Apply Action' });
      fireEvent.click(applyBtn);

      await waitFor(() => {
        const expectedStartUtc = new Date('2026-06-01T10:00').toISOString();
        const expectedEndUtc = new Date('2027-06-01T10:00').toISOString();

        expect(outletSubApi.updatePlatformOutletSubscription).toHaveBeenCalledWith(
          'o-1',
          expect.objectContaining({
            action_type: 'renew',
            current_period_start: expectedStartUtc,
            current_period_end: expectedEndUtc,
          }),
          'tok-123'
        );
      });
    });

    it('preserves boundary datetime conversion for leap-year case (Feb 29)', async () => {
      renderOutletDetail();

      fireEvent.click(await screen.findByText('Subscription & Entitlements'));
      fireEvent.click(await screen.findByRole('button', { name: 'Manage Subscription' }));

      const actionSelect = await screen.findByLabelText(/Lifecycle Action/i);
      fireEvent.change(actionSelect, { target: { value: 'renew' } });

      const startInput = screen.getByLabelText(/Period Start Date Override/i);
      fireEvent.change(startInput, { target: { value: '2028-02-29T14:30' } });

      const applyBtn = screen.getByRole('button', { name: 'Apply Action' });
      fireEvent.click(applyBtn);

      await waitFor(() => {
        const expectedStartUtc = new Date('2028-02-29T14:30').toISOString();
        expect(outletSubApi.updatePlatformOutletSubscription).toHaveBeenCalledWith(
          'o-1',
          expect.objectContaining({
            action_type: 'renew',
            current_period_start: expectedStartUtc,
          }),
          'tok-123'
        );
      });
    });
  });
});
