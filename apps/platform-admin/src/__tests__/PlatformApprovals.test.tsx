import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PlatformApprovals } from '../features/platform-admin/PlatformApprovals';
import {
  PlatformApprovalRequestsResponse,
  PlatformApprovalRequestDetail,
} from '@roms/shared-types';
import * as apiClient from '@roms/api-client';

describe('PlatformApprovals Component (Stitch Master-Detail Redesign)', () => {
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
        request_type: 'operator_creation',
        target_entity_type: 'operator',
        target_entity_id: null,
        status: 'approved',
        execution_status: 'succeeded',
        justification: 'Weekend rush coverage',
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

  it('renders master-detail layout with requests and automatically selects first item on desktop', async () => {
    vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);
    vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockResolvedValue(sampleDetail);

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      // Check left pane items
      expect(screen.getAllByText('Create business').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Alice Admin').length).toBeGreaterThan(0);
    });

    // Check status badges
    expect(screen.getAllByText('Pending').length).toBeGreaterThan(0);

    // Check right pane detail auto-loaded
    await waitFor(() => {
      expect(screen.getByText(/What will happen:/i)).toBeDefined();
      expect(screen.getAllByText(/Himalayan Delight/).length).toBeGreaterThan(0);
      expect(screen.getByText('Verified legal entity documentation.')).toBeDefined();
    });
  });

  it('filters by request type and switches tabs', async () => {
    const fetchSpy = vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);
    vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockResolvedValue(sampleDetail);

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      expect(screen.getAllByText('Create business').length).toBeGreaterThan(0);
    });

    // Filter by type
    const typeSelect = screen.getByLabelText('Filter by request type');
    fireEvent.change(typeSelect, { target: { value: 'business_creation' } });

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        'valid-token',
        expect.objectContaining({ request_type: 'business_creation', status: 'pending' })
      );
    });

    // Switch to history tab
    fireEvent.click(screen.getByRole('button', { name: 'History' }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        'valid-token',
        expect.objectContaining({ status: undefined })
      );
    });
  });

  it('selecting a different item in the list loads its details into the right pane', async () => {
    vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);
    const detailSpy = vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockImplementation(async (_, id) => {
      if (id === 'req-2') {
        return {
          ...sampleApprovalsResponse.items[1],
          payload_snapshot: { email: 'arun@example.com', display_name: 'Arun Kumar' },
          decision_reason: 'Approved for coverage',
          execution_started_at: null,
          execution_completed_at: null,
          execution_error: null,
          execution_details_json: null,
          parent_request_id: null,
          clarifications: [],
        };
      }
      return sampleDetail;
    });

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      expect(screen.getAllByText('Create business').length).toBeGreaterThan(0);
    });

    // Switch to history or search to make req-2 visible in list
    fireEvent.click(screen.getByRole('button', { name: 'History' }));

    await waitFor(() => {
      expect(screen.getByText('Bob Owner ·')).toBeDefined();
    });

    // Click on row 2
    fireEvent.click(screen.getByText('Bob Owner ·'));

    await waitFor(() => {
      expect(detailSpy).toHaveBeenCalledWith('valid-token', 'req-2');
      expect(screen.getAllByText(/Arun Kumar/).length).toBeGreaterThan(0);
      expect(screen.getByText('Approved for coverage')).toBeDefined();
    });
  });

  it('eligible role sees Approve and Reject buttons for pending request', async () => {
    vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);
    vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockResolvedValue(sampleDetail);

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Approve' })).toBeDefined();
      expect(screen.getByRole('button', { name: 'Reject' })).toBeDefined();
    });
  });

  it('operator sees read-only banner and does not see decision action buttons', async () => {
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
      expect(screen.getByText(/Platform Operators can track and inspect approval requests/i)).toBeDefined();
      expect(screen.getByText('Only Admins and Owners can decide on requests.')).toBeDefined();
    });

    expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Reject' })).toBeNull();
  });

  it('approving a request opens confirmation modal and submits decision', async () => {
    vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);
    vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockResolvedValue(sampleDetail);
    const decideSpy = vi.spyOn(apiClient, 'decidePlatformApprovalRequest').mockResolvedValue({
      ...sampleDetail,
      status: 'approved',
      execution_status: 'succeeded',
      decision_reason: 'Approved by platform administrator',
    });

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Approve' })).toBeDefined();
    });

    // Click Approve button to open modal
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));

    expect(screen.getByRole('dialog')).toBeDefined();
    expect(screen.getAllByText(/Approve request/i).length).toBeGreaterThan(0);

    // Confirm
    fireEvent.click(screen.getByRole('button', { name: 'Approve request' }));

    await waitFor(() => {
      expect(decideSpy).toHaveBeenCalledWith('valid-token', 'req-1', {
        decision: 'approve',
        reason: 'Approved by platform administrator',
      });
    });
  });

  it('rejecting a request strictly requires a reason', async () => {
    vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);
    vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockResolvedValue(sampleDetail);
    const decideSpy = vi.spyOn(apiClient, 'decidePlatformApprovalRequest');

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Reject' })).toBeDefined();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Reject' }));

    // Try submitting empty reason
    fireEvent.click(screen.getByRole('button', { name: 'Reject request' }));

    expect(
      screen.getByText('A non-empty reason is strictly required when rejecting an approval request.')
    ).toBeDefined();
    expect(decideSpy).not.toHaveBeenCalled();

    // Fill valid reason
    const textarea = screen.getByLabelText(/Reason for rejection/i);
    fireEvent.change(textarea, { target: { value: 'Incomplete KYC documentation.' } });

    fireEvent.click(screen.getByRole('button', { name: 'Reject request' }));

    await waitFor(() => {
      expect(decideSpy).toHaveBeenCalledWith('valid-token', 'req-1', {
        decision: 'reject',
        reason: 'Incomplete KYC documentation.',
      });
    });
  });

  it('presents backend 403 error safely in alert banner without state corruption', async () => {
    vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(sampleApprovalsResponse);
    vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockResolvedValue(sampleDetail);
    const err: any = new Error('Platform Administrators cannot self-approve requests of this type.');
    err.status = 403;
    vi.spyOn(apiClient, 'decidePlatformApprovalRequest').mockRejectedValue(err);

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Approve' })).toBeDefined();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    fireEvent.click(screen.getByRole('button', { name: 'Approve request' }));

    await waitFor(() => {
      expect(
        screen.getByText('Platform Administrators cannot self-approve requests of this type.')
      ).toBeDefined();
    });
  });

  it('handles COMMIT_OUTCOME_UNCERTAIN without auto-posting again and provides verification action', async () => {
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
      expect(screen.getByRole('button', { name: 'Approve' })).toBeDefined();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    fireEvent.click(screen.getByRole('button', { name: 'Approve request' }));

    await waitFor(() => {
      expect(decideSpy).toHaveBeenCalledTimes(1);
      expect(detailSpy).toHaveBeenCalledTimes(2);
      expect(screen.getByText('Ambiguous Commit State')).toBeDefined();
    });
  });

  it('renders useful empty state when no request is selected', async () => {
    vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    });

    render(<PlatformApprovals token="valid-token" />);

    await waitFor(() => {
      expect(screen.getByText('Select a request to review')).toBeDefined();
      expect(screen.getByText('No requests found')).toBeDefined();
    });
  });
describe('State Consistency & Regression Tests (Fix 1 & Fix 2)', () => {
    const twoPendingResponse: PlatformApprovalRequestsResponse = {
      items: [
        {
          ...sampleApprovalsResponse.items[0],
          id: 'req-1',
          status: 'pending',
          requester_display_name: 'Alice Admin',
          requester_email: 'alice@platform.com',
          request_type: 'business_creation',
        },
        {
          ...sampleApprovalsResponse.items[1],
          id: 'req-2',
          status: 'pending',
          requester_display_name: 'Beta Requester',
          requester_email: 'bob@platform.com',
          request_type: 'operator_creation',
        },
      ],
      total: 2,
      limit: 50,
      offset: 0,
    };

    const detailA: PlatformApprovalRequestDetail = {
      ...twoPendingResponse.items[0],
      payload_snapshot: { name: 'Alpha Bistro', owner_email: 'alpha@bistro.com' },
      decision_reason: null,
      execution_started_at: null,
      execution_completed_at: null,
      execution_error: null,
      execution_details_json: null,
      parent_request_id: null,
      clarifications: [],
    };

    const detailB: PlatformApprovalRequestDetail = {
      ...twoPendingResponse.items[1],
      payload_snapshot: { display_name: 'Beta Operator', email: 'beta@operator.com' },
      decision_reason: null,
      execution_started_at: null,
      execution_completed_at: null,
      execution_error: null,
      execution_details_json: null,
      parent_request_id: null,
      clarifications: [],
    };

    function createDeferred<T>() {
      let resolve!: (val: T) => void;
      let reject!: (err: any) => void;
      const promise = new Promise<T>((res, rej) => {
        resolve = res;
        reject = rej;
      });
      return { promise, resolve, reject };
    }

    it('Fix 1: search filtering excluding selected request A automatically selects and displays B', async () => {
      vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(twoPendingResponse);
      vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockImplementation(async (_, id) => {
        if (id === 'req-1') return detailA;
        if (id === 'req-2') return detailB;
        throw new Error('Not found');
      });

      render(<PlatformApprovals token="valid-token" />);

      // Initially request A (Alpha Bistro) is selected
      await waitFor(() => {
        expect(screen.getAllByText(/Alpha Bistro/).length).toBeGreaterThan(0);
      });

      // Filter search to "Beta" which excludes A and keeps B
      const searchInput = screen.getByLabelText('Search approval requests');
      fireEvent.change(searchInput, { target: { value: 'Beta' } });

      // Request B (Beta Operator) must now be auto-selected and displayed in detail pane
      await waitFor(() => {
        expect(screen.getAllByText(/Beta Operator/).length).toBeGreaterThan(0);
      });

      // Request A must no longer be displayed in detail pane
      expect(screen.queryByText(/Alpha Bistro/)).toBeNull();
    });

    it('Fix 1: search query matching no requests clears detail pane and shows empty state', async () => {
      vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(twoPendingResponse);
      vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockResolvedValue(detailA);

      render(<PlatformApprovals token="valid-token" />);

      await waitFor(() => {
        expect(screen.getAllByText(/Alpha Bistro/).length).toBeGreaterThan(0);
      });

      // Enter search query that matches no items
      const searchInput = screen.getByLabelText('Search approval requests');
      fireEvent.change(searchInput, { target: { value: 'NonExistentXYZQuery' } });

      await waitFor(() => {
        expect(screen.getByText('No requests found')).toBeDefined();
        expect(screen.getByText('Select a request to review')).toBeDefined();
      });

      // Excluded request must not remain displayed in detail pane
      expect(screen.queryByText(/Alpha Bistro/)).toBeNull();
    });

    it('Fix 2: out-of-order detail responses do not overwrite the currently selected request', async () => {
      const deferredA = createDeferred<PlatformApprovalRequestDetail>();
      const deferredB = createDeferred<PlatformApprovalRequestDetail>();

      vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(twoPendingResponse);
      vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockImplementation((_, id) => {
        if (id === 'req-1') return deferredA.promise;
        if (id === 'req-2') return deferredB.promise;
        return Promise.reject(new Error('Unknown ID'));
      });

      render(<PlatformApprovals token="valid-token" />);

      // On initial render, req-1 is selected and deferredA is in flight
      await waitFor(() => {
        expect(screen.getByText('Beta Requester ·')).toBeDefined();
      });

      // Rapidly click row 2 (req-2) before deferredA has resolved
      fireEvent.click(screen.getByText('Beta Requester ·'));

      // Both deferredA and deferredB are now in-flight.
      // Resolve B FIRST:
      deferredB.resolve(detailB);

      await waitFor(() => {
        expect(screen.getAllByText(/Beta Operator/).length).toBeGreaterThan(0);
      });

      // Resolve A AFTERWARD (late out-of-order response):
      deferredA.resolve(detailA);

      // Verify B remains displayed and was NOT overwritten by late A response
      await new Promise((r) => setTimeout(r, 50));
      expect(screen.getAllByText(/Beta Operator/).length).toBeGreaterThan(0);
      expect(screen.queryByText(/Alpha Bistro/)).toBeNull();
    });

    it('Fix 2: obsolete response cannot restore detail after selection is cleared by filter', async () => {
      const deferredA = createDeferred<PlatformApprovalRequestDetail>();

      vi.spyOn(apiClient, 'fetchPlatformApprovals').mockResolvedValue(twoPendingResponse);
      vi.spyOn(apiClient, 'fetchPlatformApprovalDetail').mockImplementation((_, id) => {
        if (id === 'req-1') return deferredA.promise;
        return Promise.reject(new Error('Unknown ID'));
      });

      render(<PlatformApprovals token="valid-token" />);

      await waitFor(() => {
        expect(screen.getByText('Alice Admin ·')).toBeDefined();
      });

      // Enter search query matching nothing before deferredA resolves
      const searchInput = screen.getByLabelText('Search approval requests');
      fireEvent.change(searchInput, { target: { value: 'NonExistentSearch' } });

      await waitFor(() => {
        expect(screen.getByText('Select a request to review')).toBeDefined();
      });

      // Resolve deferredA now that selection has been cleared
      deferredA.resolve(detailA);

      await new Promise((r) => setTimeout(r, 50));

      // Right pane must STILL show empty state, not restore stale detailA
      expect(screen.getByText('Select a request to review')).toBeDefined();
      expect(screen.queryByText(/Alpha Bistro/)).toBeNull();
    });
  });
});
