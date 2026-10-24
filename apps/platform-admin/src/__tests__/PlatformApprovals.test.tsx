import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PlatformApprovals } from '../features/platform-admin/PlatformApprovals';
import {
  PlatformApprovalRequestsResponse,
  PlatformApprovalRequestDetail,
} from '@roms/shared-types';
import * as apiClient from '@roms/api-client';

describe('PlatformApprovals Component', () => {
  const sampleApprovalsResponse: PlatformApprovalRequestsResponse = {
    items: [
      {
        id: 'req-1',
        business_id: 'biz-1',
        outlet_id: null,
        requester_user_id: 'user-admin',
        requester_display_name: 'Alice Admin',
        requester_email: 'alice@platform.com',
        approver_user_id: null,
        approver_display_name: null,
        approver_email: null,
        request_type: 'business_creation',
        target_entity_type: 'business',
        target_entity_id: 'biz-1',
        status: 'pending',
        execution_status: 'not_started',
        justification: 'New franchise onboarding',
        expires_at: '2026-11-10T12:00:00Z',
        decided_at: null,
        created_at: '2026-10-24T10:00:00Z',
        updated_at: '2026-10-24T10:00:00Z',
      },
      {
        id: 'req-2',
        business_id: null,
        outlet_id: null,
        requester_user_id: 'user-owner',
        requester_display_name: 'Bob Owner',
        requester_email: 'owner@platform.com',
        approver_user_id: 'user-owner',
        approver_display_name: 'Bob Owner',
        approver_email: 'owner@platform.com',
        request_type: 'user_suspension',
        target_entity_type: 'user',
        target_entity_id: 'user-bad',
        status: 'approved',
        execution_status: 'succeeded',
        justification: 'Security policy violation',
        expires_at: '2026-11-10T12:00:00Z',
        decided_at: '2026-10-24T11:00:00Z',
        created_at: '2026-10-24T09:00:00Z',
        updated_at: '2026-10-24T11:00:00Z',
      },
    ],
    total: 2,
    limit: 50,
    offset: 0,
  };

  const sampleDetail: PlatformApprovalRequestDetail = {
    ...sampleApprovalsResponse.items[0],
    payload_snapshot: {
      name: 'Himalayan Delight',
      owner_email: 'owner@himalayan.com',
      owner_display_name: 'Tenzing Norgay',
    },
    decision_reason: null,
    execution_started_at: null,
    execution_completed_at: null,
    execution_error: null,
    execution_details_json: null,
    parent_request_id: null,
    clarifications: [
      {
        id: 'clar-1',
        approval_request_id: 'req-1',
        author_user_id: 'user-owner',
        author_email: 'owner@platform.com',
        author_display_name: 'Bob Owner',
        clarification_type: 'note',
        message: 'Verified legal entity documentation.',
        created_at: '2026-10-24T10:30:00Z',
      },
    ],
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    // Default auth as Platform Admin
    vi.spyOn(apiClient, 'useAuth').mockReturnValue({
      user: {
        id: 'user-admin',
        email: 'alice@platform.com',
        display_name: 'Alice Admin',
        platform_role: 'admin',
        is_platform_admin: true,
      } as any,
      token: 'valid-token',
      loading: false,
      login: vi.fn(),
      logout: vi.fn(),
    });
  });

  it('renders approval list and status badges correctly', async () => {
    vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);

    render(<PlatformApprovals token="valid-token" />);

    expect(screen.getByText('Loading approval queue')).toBeDefined();

    await waitFor(() => {
      expect(screen.getAllByText('Business Creation').length).toBeGreaterThan(0);
      expect(screen.getAllByText('User Suspension').length).toBeGreaterThan(0);
      expect(screen.getByText('Alice Admin')).toBeDefined();
      expect(screen.getByText('Bob Owner')).toBeDefined();
    });

    expect(screen.getByText('Pending')).toBeDefined();
    expect(screen.getByText('Approved')).toBeDefined();
  });

  it('filters by status and request type', async () => {
    const fetchSpy = vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      expect(screen.getAllByText('Business Creation').length).toBeGreaterThan(0);
    });

    const statusSelect = screen.getByLabelText('Status');
    fireEvent.change(statusSelect, { target: { value: 'pending' } });

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith('valid-token', expect.objectContaining({ status: 'pending', offset: 0 }));
    });

    const typeSelect = screen.getByLabelText('Type');
    fireEvent.change(typeSelect, { target: { value: 'business_creation' } });

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        'valid-token',
        expect.objectContaining({ status: 'pending', request_type: 'business_creation', offset: 0 })
      );
    });
  });

  it('opens and inspects request detail in drawer', async () => {
    vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);
    const detailSpy = vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockResolvedValue(sampleDetail);

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      expect(screen.getAllByText('Business Creation').length).toBeGreaterThan(0);
    });

    const inspectButtons = screen.getAllByRole('button', { name: /Inspect/i });
    fireEvent.click(inspectButtons[0]);

    await waitFor(() => {
      expect(detailSpy).toHaveBeenCalledWith('valid-token', 'req-1');
      expect(screen.getByText('Approval Request Details')).toBeDefined();
      expect(screen.getByText('New franchise onboarding')).toBeDefined();
      expect(screen.getByText(/Himalayan Delight/)).toBeDefined();
      expect(screen.getByText('Verified legal entity documentation.')).toBeDefined();
    });

    // Close drawer
    const closeBtn = screen.getByLabelText('Close drawer');
    fireEvent.click(closeBtn);

    await waitFor(() => {
      expect(screen.queryByText('Approval Request Details')).toBeNull();
    });
  });

  it('eligible role sees decision controls for a decision-eligible request', async () => {
    vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);
    vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockResolvedValue(sampleDetail);

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      expect(screen.getAllByText('Business Creation').length).toBeGreaterThan(0);
    });

    const inspectButtons = screen.getAllByRole('button', { name: /Inspect/i });
    fireEvent.click(inspectButtons[0]);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Approve Request/i })).toBeDefined();
      expect(screen.getByRole('button', { name: /Reject Request/i })).toBeDefined();
    });
  });

  it('operator does not see decision controls', async () => {
    // Mock user as Operator
    vi.spyOn(apiClient, 'useAuth').mockReturnValue({
      user: {
        id: 'user-op',
        email: 'op@platform.com',
        display_name: 'Test Operator',
        platform_role: 'operator',
        is_platform_admin: false,
      } as any,
      token: 'valid-token',
      loading: false,
      login: vi.fn(),
      logout: vi.fn(),
    });

    vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);
    vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockResolvedValue(sampleDetail);

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      expect(screen.getAllByText('Business Creation').length).toBeGreaterThan(0);
    });

    const inspectButtons = screen.getAllByRole('button', { name: /Inspect/i });
    fireEvent.click(inspectButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Approval Request Details')).toBeDefined();
    });

    // Mutation buttons must NOT exist for operator
    expect(screen.queryByRole('button', { name: /Approve Request/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /Reject Request/i })).toBeNull();
  });

  it('approve submits the correct request and refreshes authoritative state', async () => {
    const listSpy = vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);
    vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockResolvedValue(sampleDetail);
    const decideSpy = vi.spyOn(apiClient, 'decidePlatformApprovalRequest').mockResolvedValue({
      ...sampleDetail,
      status: 'approved',
      execution_status: 'succeeded',
      decision_reason: 'Approved by platform administrator',
    });

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      expect(screen.getAllByText('Business Creation').length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getAllByRole('button', { name: /Inspect/i })[0]);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Approve Request/i })).toBeDefined();
    });

    // Click Approve Request in drawer footer
    fireEvent.click(screen.getByRole('button', { name: /Approve Request/i }));

    // Confirm dialog opens
    expect(screen.getByRole('heading', { name: /Approve Request/i })).toBeDefined();

    // Confirm approval
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Approval' }));

    await waitFor(() => {
      expect(decideSpy).toHaveBeenCalledWith('valid-token', 'req-1', {
        decision: 'approve',
        reason: 'Approved by platform administrator',
      });
      expect(listSpy).toHaveBeenCalledTimes(2); // Initial + reload on success
    });
  });

  it('reject requires a non-whitespace reason', async () => {
    vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);
    vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockResolvedValue(sampleDetail);
    const decideSpy = vi.spyOn(apiClient, 'decidePlatformApprovalRequest');

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      expect(screen.getAllByText('Business Creation').length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getAllByRole('button', { name: /Inspect/i })[0]);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Reject Request/i })).toBeDefined();
    });

    fireEvent.click(screen.getByRole('button', { name: /Reject Request/i }));

    // Try submitting with empty reason
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Rejection' }));

    expect(
      screen.getByText('A non-empty reason is strictly required when rejecting an approval request.')
    ).toBeDefined();
    expect(decideSpy).not.toHaveBeenCalled();

    // Try submitting with whitespace only
    const textarea = screen.getByLabelText(/Reason/i);
    fireEvent.change(textarea, { target: { value: '    \t  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Rejection' }));

    expect(
      screen.getByText('A non-empty reason is strictly required when rejecting an approval request.')
    ).toBeDefined();
    expect(decideSpy).not.toHaveBeenCalled();
  });

  it('reject submits the entered reason', async () => {
    vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);
    vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockResolvedValue(sampleDetail);
    const decideSpy = vi.spyOn(apiClient, 'decidePlatformApprovalRequest').mockResolvedValue({
      ...sampleDetail,
      status: 'rejected',
      decision_reason: 'Incomplete franchise KYC documentation.',
    });

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      expect(screen.getAllByText('Business Creation').length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getAllByRole('button', { name: /Inspect/i })[0]);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Reject Request/i })).toBeDefined();
    });

    fireEvent.click(screen.getByRole('button', { name: /Reject Request/i }));

    const textarea = screen.getByLabelText(/Reason/i);
    fireEvent.change(textarea, { target: { value: 'Incomplete franchise KYC documentation.' } });

    fireEvent.click(screen.getByRole('button', { name: 'Confirm Rejection' }));

    await waitFor(() => {
      expect(decideSpy).toHaveBeenCalledWith('valid-token', 'req-1', {
        decision: 'reject',
        reason: 'Incomplete franchise KYC documentation.',
      });
    });
  });

  it('backend 403 error is presented safely without altering status', async () => {
    vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);
    vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockResolvedValue(sampleDetail);
    const err: any = new Error('Platform Administrators cannot self-approve requests of this type.');
    err.status = 403;
    vi.spyOn(apiClient, 'decidePlatformApprovalRequest').mockRejectedValue(err);

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      expect(screen.getAllByText('Business Creation').length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getAllByRole('button', { name: /Inspect/i })[0]);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Approve Request/i })).toBeDefined();
    });

    fireEvent.click(screen.getByRole('button', { name: /Approve Request/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Approval' }));

    await waitFor(() => {
      expect(
        screen.getAllByText('Platform Administrators cannot self-approve requests of this type.').length
      ).toBeGreaterThan(0);
    });

    // Status remains unchanged
    expect(screen.getByText('Pending')).toBeDefined();
  });

  it('COMMIT_OUTCOME_UNCERTAIN does not cause an automatic second POST and disables controls', async () => {
    vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);
    const detailSpy = vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockResolvedValue(sampleDetail);

    const uncertainErr: any = new Error(
      'Commit outcome uncertain: transport error during commit acknowledgment. Request state preserved.'
    );
    uncertainErr.status = 503;
    uncertainErr.code = 'COMMIT_OUTCOME_UNCERTAIN';
    const decideSpy = vi.spyOn(apiClient, 'decidePlatformApprovalRequest').mockRejectedValue(uncertainErr);

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      expect(screen.getAllByText('Business Creation').length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getAllByRole('button', { name: /Inspect/i })[0]);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Approve Request/i })).toBeDefined();
    });

    fireEvent.click(screen.getByRole('button', { name: /Approve Request/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Approval' }));

    await waitFor(() => {
      // Must NOT submit second POST
      expect(decideSpy).toHaveBeenCalledTimes(1);
      // Calls detail fetch to resolve authoritative outcome
      expect(detailSpy).toHaveBeenCalledTimes(2);
      // Warning banner displayed
      expect(screen.getByText('Ambiguous Transaction Outcome')).toBeDefined();
    });

    // Buttons must have disabled attribute while ambiguous
    expect(screen.getByRole('button', { name: /Approve Request/i }).hasAttribute('disabled')).toBe(true);
    expect(screen.getByRole('button', { name: /Reject Request/i }).hasAttribute('disabled')).toBe(true);
  });
});
