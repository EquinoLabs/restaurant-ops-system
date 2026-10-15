import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { PlansCatalog } from '../features/platform-admin/PlansCatalog';
import { AddOperatorModal } from '../features/platform-admin/AddOperatorModal';
import { PlatformOwnerTransferModal } from '../features/platform-admin/PlatformOwnerTransferModal';
import * as apiClient from '@roms/api-client';
import { PlatformPlan } from '@roms/shared-types';

describe('Phase 3 Feature Tests: PlansCatalog', () => {
  const samplePlans: PlatformPlan[] = [
    {
      id: 'plan-1',
      code: 'starter_pos',
      name: 'Starter POS Tier',
      description: 'Single-outlet entry plan with fundamental POS',
      is_active: true,
      sort_order: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    {
      id: 'plan-2',
      code: 'growth_pos',
      name: 'Growth POS Tier',
      description: 'Multi-outlet plan with advanced reporting and inventory',
      is_active: true,
      sort_order: 2,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    {
      id: 'plan-3',
      code: 'legacy_tier',
      name: 'Archived Legacy Tier',
      description: 'Deprecated legacy tier',
      is_active: false,
      sort_order: 3,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders plans catalog with plan cards, status badges, and search filtering', async () => {
    vi.spyOn(apiClient, 'fetchPlatformPlans').mockResolvedValue(samplePlans);

    render(<PlansCatalog token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText('Starter POS Tier')).toBeDefined();
      expect(screen.getByText('Growth POS Tier')).toBeDefined();
      expect(screen.getByText('Archived Legacy Tier')).toBeDefined();
    });

    // Verify badges
    expect(screen.getAllByText('Active').length).toBe(2);
    expect(screen.getByText('Inactive')).toBeDefined();

    // Test search filter
    const searchInput = screen.getByPlaceholderText(/Search plans/i);
    fireEvent.change(searchInput, { target: { value: 'Growth' } });

    expect(screen.getByText('Growth POS Tier')).toBeDefined();
    expect(screen.queryByText('Starter POS Tier')).toBeNull();
  });

  it('opens and closes plan detail modal upon clicking View Details', async () => {
    vi.spyOn(apiClient, 'fetchPlatformPlans').mockResolvedValue(samplePlans);

    render(<PlansCatalog token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText('Starter POS Tier')).toBeDefined();
    });

    const viewDetailsButtons = screen.getAllByRole('button', { name: /Inspect Plan Details/i });
    fireEvent.click(viewDetailsButtons[0]);

    // Modal opens
    expect(screen.getByText('Description')).toBeDefined();
    expect(screen.getByLabelText('Close plan details')).toBeDefined();

    // Close modal
    fireEvent.click(screen.getByLabelText('Close plan details'));
    expect(screen.queryByLabelText('Close plan details')).toBeNull();
  });
});

describe('Phase 3 Feature Tests: AddOperatorModal', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('switches between Mode 1 (Promote) and Mode 2 (Create Account) and validates inputs', async () => {
    const handleClose = vi.fn();
    const handleSuccess = vi.fn();

    render(
      <AddOperatorModal
        isOpen={true}
        onClose={handleClose}
        onSuccess={handleSuccess}
        token="test-token"
      />
    );

    expect(screen.getByText('Add Platform Operator')).toBeDefined();

    // Default mode is new account
    expect(screen.getByPlaceholderText('operator@roms.com')).toBeDefined();

    // Switch to promote mode
    fireEvent.click(screen.getByText('Promote Existing User'));
    expect(screen.getByPlaceholderText('e.g. 35b83c12-bc5a-41aa-887b-50cce040caff')).toBeDefined();

    // Switch back to new account
    fireEvent.click(screen.getByText('New Account'));
    expect(screen.getByPlaceholderText('operator@roms.com')).toBeDefined();
  });

  it('calls createPlatformOperator API on submit with valid credentials', async () => {
    const createSpy = vi.spyOn(apiClient, 'createPlatformOperator').mockResolvedValue({
      id: 'op-123',
      email: 'newop@platform.com',
      display_name: 'New Operator',
      status: 'active',
      is_platform_admin: false,
      platform_role: 'operator',
      created_at: '2026-10-14T00:00:00Z',
      updated_at: '2026-10-14T00:00:00Z',
    });

    const handleSuccess = vi.fn();
    const handleClose = vi.fn();

    render(
      <AddOperatorModal
        isOpen={true}
        onClose={handleClose}
        onSuccess={handleSuccess}
        token="test-token"
      />
    );

    fireEvent.change(screen.getByPlaceholderText('operator@roms.com'), {
      target: { value: 'newop@platform.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('Minimum 8 characters'), {
      target: { value: 'password123' },
    });
    fireEvent.change(screen.getByPlaceholderText('e.g. Operations Assistant'), {
      target: { value: 'New Operator' },
    });

    fireEvent.click(screen.getByRole('button', { name: /Confirm & Add Operator/i }));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith(
        {
          email: 'newop@platform.com',
          password: 'password123',
          display_name: 'New Operator',
        },
        'test-token'
      );
      expect(handleSuccess).toHaveBeenCalled();
      expect(handleClose).toHaveBeenCalled();
    });
  });
});

describe('Phase 3 Feature Tests: PlatformOwnerTransferModal', () => {
  const sampleCandidates = [
    {
      id: 'admin-candidate-1',
      email: 'admin1@platform.com',
      display_name: 'Lead Admin',
      status: 'active',
      is_platform_admin: true,
      platform_role: 'admin',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('requires target selection and current owner password before submitting transfer', async () => {
    const transferSpy = vi.spyOn(apiClient, 'transferPlatformOwner').mockResolvedValue({
      status: 'success',
      message: 'Platform Owner transferred successfully',
    });

    const handleSuccess = vi.fn();
    const handleClose = vi.fn();

    render(
      <PlatformOwnerTransferModal
        isOpen={true}
        onClose={handleClose}
        onSuccess={handleSuccess}
        token="test-token"
        candidates={sampleCandidates}
      />
    );

    expect(screen.getByText('Transfer Platform Ownership')).toBeDefined();

    // Select candidate
    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: 'admin-candidate-1' } });

    // Enter password
    const pwdInput = screen.getByPlaceholderText('Your current account password');
    fireEvent.change(pwdInput, { target: { value: 'mypassword123' } });

    // Click confirm transfer
    fireEvent.click(screen.getByRole('button', { name: /Confirm & Relinquish Ownership/i }));

    await waitFor(() => {
      expect(transferSpy).toHaveBeenCalledWith(
        {
          target_user_id: 'admin-candidate-1',
          current_password: 'mypassword123',
        },
        'test-token'
      );
      expect(handleSuccess).toHaveBeenCalled();
      expect(handleClose).toHaveBeenCalled();
    });
  });
});
