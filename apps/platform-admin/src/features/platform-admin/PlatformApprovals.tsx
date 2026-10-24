import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  PlatformApprovalRequestItem,
  PlatformApprovalRequestDetail,
  PlatformApprovalDecisionPayload,
} from '@roms/shared-types';
import {
  fetchPlatformApprovals,
  fetchPlatformApprovalDetail,
  decidePlatformApprovalRequest,
  useAuth,
} from '@roms/api-client';
import {
  RefreshCw,
  Eye,
  MessageSquare,
  AlertCircle,
  CheckCircle2,
  XCircle,
  AlertTriangle,
} from 'lucide-react';
import {
  Button,
  DataTable,
  Drawer,
  StatusBadge,
  StateBlock,
  ConfirmDialog,
  opsSelectClass,
  opsInputClass,
  type DataTableColumn,
  type StatusTone,
} from '../../components/ops-ui';

interface PlatformApprovalsProps {
  token: string | null;
}

const STATUS_TONES: Record<string, StatusTone> = {
  pending: 'pending',
  needs_information: 'pending',
  approved: 'active',
  rejected: 'critical',
  withdrawn: 'neutral',
  expired: 'neutral',
};

const REQUEST_TYPE_LABELS: Record<string, string> = {
  business_creation: 'Business Creation',
  outlet_creation: 'Outlet Creation',
  user_role_change: 'User Role Change',
  subscription_change: 'Subscription Change',
  operator_creation: 'Operator Provisioning',
  operator_revocation: 'Operator Revocation',
  user_suspension: 'User Suspension',
  user_reactivation: 'User Reactivation',
  entitlement_override: 'Entitlement Override',
};

export const PlatformApprovals: React.FC<PlatformApprovalsProps> = ({ token }) => {
  const { user } = useAuth();
  const [requests, setRequests] = useState<PlatformApprovalRequestItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [limit, setLimit] = useState<number>(50);
  const [offset, setOffset] = useState<number>(0);

  // Filters
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [selectedRequestType, setSelectedRequestType] = useState<string>('');

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Detail drawer state
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);
  const [detail, setDetail] = useState<PlatformApprovalRequestDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // Decision state
  const [decisionModalType, setDecisionModalType] = useState<'approve' | 'reject' | null>(null);
  const [decisionReason, setDecisionReason] = useState<string>('');
  const [decisionReasonError, setDecisionReasonError] = useState<string | null>(null);
  const [isSubmittingDecision, setIsSubmittingDecision] = useState<boolean>(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);

  // Uncertain commit state
  const [uncertainOutcomeWarning, setUncertainOutcomeWarning] = useState<string | null>(null);
  const [isResolvingUncertainty, setIsResolvingUncertainty] = useState<boolean>(false);

  // In-flight submission lock to prevent double-click / concurrent submits
  const isSubmittingRef = useRef<boolean>(false);

  // Determine user eligibility to see mutation controls (Admin or Owner, not Operator)
  const isDecisionEligibleUser = Boolean(
    user && (user.platform_role === 'owner' || user.platform_role === 'admin' || user.is_platform_admin)
  );

  const loadRequests = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      setError(null);
      const data = await fetchPlatformApprovals(token, {
        limit,
        offset,
        status: selectedStatus || undefined,
        request_type: selectedRequestType || undefined,
      });
      setRequests(data?.items || []);
      setTotal(data?.total || 0);
    } catch (err: any) {
      setError(err.message || 'Failed to load approval requests.');
    } finally {
      setLoading(false);
    }
  }, [token, limit, offset, selectedStatus, selectedRequestType]);

  useEffect(() => {
    loadRequests();
  }, [loadRequests]);

  const loadDetail = useCallback(
    async (requestId: string) => {
      if (!token) return;
      try {
        setDetailLoading(true);
        setDetailError(null);
        const data = await fetchPlatformApprovalDetail(token, requestId);
        setDetail(data);
      } catch (err: any) {
        setDetailError(err.message || 'Failed to load request details.');
      } finally {
        setDetailLoading(false);
      }
    },
    [token]
  );

  const handleOpenDetail = (reqId: string) => {
    setSelectedRequestId(reqId);
    setDecisionError(null);
    setUncertainOutcomeWarning(null);
    loadDetail(reqId);
  };

  const handleCloseDetail = () => {
    if (isSubmittingDecision || isResolvingUncertainty) return;
    setSelectedRequestId(null);
    setDetail(null);
    setDetailError(null);
    setDecisionModalType(null);
    setDecisionReason('');
    setDecisionReasonError(null);
    setDecisionError(null);
    setUncertainOutcomeWarning(null);
  };

  const handleStatusChange = (status: string) => {
    setSelectedStatus(status);
    setOffset(0);
  };

  const handleRequestTypeChange = (reqType: string) => {
    setSelectedRequestType(reqType);
    setOffset(0);
  };

  const handleResetFilters = () => {
    setSelectedStatus('');
    setSelectedRequestType('');
    setOffset(0);
  };

  const formatDate = (iso: string | null | undefined): string => {
    if (!iso) return 'N/A';
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  };

  const formatShortDate = (iso: string | null | undefined): string => {
    if (!iso) return 'N/A';
    return new Date(iso).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  // Open Decision Confirmation Modal
  const handleOpenDecisionModal = (type: 'approve' | 'reject') => {
    setDecisionModalType(type);
    setDecisionReason(type === 'approve' ? 'Approved by platform administrator' : '');
    setDecisionReasonError(null);
    setDecisionError(null);
  };

  // Close Decision Modal
  const handleCloseDecisionModal = () => {
    if (isSubmittingDecision) return;
    setDecisionModalType(null);
    setDecisionReason('');
    setDecisionReasonError(null);
    setDecisionError(null);
  };

  // Submit Decision
  const handleConfirmDecision = async () => {
    if (!token || !detail || !decisionModalType) return;
    if (isSubmittingRef.current || isSubmittingDecision) return;

    const trimmedReason = decisionReason.trim();
    if (decisionModalType === 'reject' && !trimmedReason) {
      setDecisionReasonError('A non-empty reason is strictly required when rejecting an approval request.');
      return;
    }

    const payload: PlatformApprovalDecisionPayload = {
      decision: decisionModalType,
      reason: trimmedReason || 'Approved by platform administrator',
    };

    isSubmittingRef.current = true;
    setIsSubmittingDecision(true);
    setDecisionError(null);
    setDecisionReasonError(null);
    setUncertainOutcomeWarning(null);

    try {
      const updatedDetail = await decidePlatformApprovalRequest(token, detail.id, payload);

      // Successfully resolved
      setDetail(updatedDetail);
      setDecisionModalType(null);
      setDecisionReason('');
      // Refresh the queue so list reflects authoritative status
      loadRequests();
    } catch (err: any) {
      // Check for COMMIT_OUTCOME_UNCERTAIN (HTTP 503)
      if (err.code === 'COMMIT_OUTCOME_UNCERTAIN' || err.status === 503) {
        setUncertainOutcomeWarning(
          'A connection interruption occurred while committing the decision. Verifying authoritative outcome…'
        );
        setDecisionModalType(null);

        // Initiate authoritative resolution without re-submitting POST
        setIsResolvingUncertainty(true);
        try {
          const reloadedDetail = await fetchPlatformApprovalDetail(token, detail.id);
          setDetail(reloadedDetail);
          loadRequests();

          if (reloadedDetail.status === 'pending' || reloadedDetail.status === 'needs_information') {
            setUncertainOutcomeWarning(
              'Authoritative check confirmed the request remains pending. The previous attempt was not committed.'
            );
          } else {
            setUncertainOutcomeWarning(null); // Resolved to a terminal/decided state cleanly
          }
        } catch {
          setUncertainOutcomeWarning(
            'Unable to confirm commit outcome because the API is currently unreachable. Please refresh later before deciding again.'
          );
        } finally {
          setIsResolvingUncertainty(false);
        }
      } else {
        // Ordinary validation or authorization error (e.g. 403, 422)
        setDecisionError(err.message || 'Failed to submit decision.');
      }
    } finally {
      isSubmittingRef.current = false;
      setIsSubmittingDecision(false);
    }
  };

  const isRequestDecisionEligible = Boolean(
    detail && (detail.status === 'pending' || detail.status === 'needs_information')
  );

  const columns: DataTableColumn<PlatformApprovalRequestItem>[] = [
    {
      key: 'created_at',
      header: 'Requested At',
      width: 'w-36',
      render: (req) => (
        <span className="whitespace-nowrap font-mono text-xs text-ops-text-secondary">
          {formatDate(req.created_at)}
        </span>
      ),
    },
    {
      key: 'request_type',
      header: 'Type',
      width: 'w-48',
      render: (req) => (
        <div>
          <span className="text-[13px] font-medium text-ops-text-primary">
            {REQUEST_TYPE_LABELS[req.request_type] || req.request_type}
          </span>
          <div className="font-mono text-[11px] text-ops-text-muted">{req.target_entity_type}</div>
        </div>
      ),
    },
    {
      key: 'requester',
      header: 'Requester',
      width: 'w-48',
      render: (req) => (
        <div>
          <span className="text-[13px] font-medium text-ops-text-primary">
            {req.requester_display_name || req.requester_email || 'Unknown'}
          </span>
          {req.requester_email && req.requester_display_name && (
            <div className="text-[11px] text-ops-text-secondary truncate">{req.requester_email}</div>
          )}
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Approval Status',
      width: 'w-32',
      render: (req) => {
        const tone = STATUS_TONES[req.status] || 'neutral';
        return <StatusBadge tone={tone} label={req.status} />;
      },
    },
    {
      key: 'execution_status',
      header: 'Execution',
      width: 'w-28',
      render: (req) => (
        <span className="font-mono text-xs text-ops-text-secondary capitalize">
          {req.execution_status.replace(/_/g, ' ')}
        </span>
      ),
    },
    {
      key: 'expires_at',
      header: 'Expires',
      width: 'w-28',
      render: (req) => (
        <span className="whitespace-nowrap text-xs text-ops-text-secondary">
          {formatShortDate(req.expires_at)}
        </span>
      ),
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      width: 'w-24',
      render: (req) => (
        <Button
          variant="ghost"
          className="text-xs py-1 px-2 text-ops-accent hover:text-ops-accent-hover"
          onClick={() => handleOpenDetail(req.id)}
          aria-label={`Inspect request ${req.id}`}
        >
          <Eye className="h-3.5 w-3.5 mr-1" aria-hidden="true" />
          Inspect
        </Button>
      ),
    },
  ];

  const hasActiveFilters = Boolean(selectedStatus || selectedRequestType);

  return (
    <div className="flex flex-col gap-6">
      {/* Page Header */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-ops-text-primary">Approval Requests</h1>
          <p className="text-xs text-ops-text-secondary mt-0.5">
            Four-eyes governance and review queue for privileged platform operations.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={loadRequests}
            disabled={loading}
            className="text-xs"
            aria-label="Refresh approval queue"
          >
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-col gap-3 rounded-md border border-ops-border bg-ops-canvas p-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex flex-wrap items-end gap-3">
          {/* Status Filter */}
          <div className="flex flex-col gap-1">
            <label
              htmlFor="approval-status-filter"
              className="text-[11px] font-semibold uppercase tracking-wider text-ops-text-secondary"
            >
              Status
            </label>
            <select
              id="approval-status-filter"
              value={selectedStatus}
              onChange={(e) => handleStatusChange(e.target.value)}
              className={`${opsSelectClass} max-w-[200px]`}
              aria-label="Filter by approval status"
            >
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="needs_information">Needs Information</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="withdrawn">Withdrawn</option>
              <option value="expired">Expired</option>
            </select>
          </div>

          {/* Request Type Filter */}
          <div className="flex flex-col gap-1">
            <label
              htmlFor="approval-type-filter"
              className="text-[11px] font-semibold uppercase tracking-wider text-ops-text-secondary"
            >
              Type
            </label>
            <select
              id="approval-type-filter"
              value={selectedRequestType}
              onChange={(e) => handleRequestTypeChange(e.target.value)}
              className={`${opsSelectClass} max-w-[220px]`}
              aria-label="Filter by request type"
            >
              <option value="">All Types</option>
              <option value="business_creation">Business Creation</option>
              <option value="outlet_creation">Outlet Creation</option>
              <option value="user_role_change">User Role Change</option>
              <option value="subscription_change">Subscription Change</option>
              <option value="operator_creation">Operator Provisioning</option>
              <option value="operator_revocation">Operator Revocation</option>
              <option value="user_suspension">User Suspension</option>
              <option value="user_reactivation">User Reactivation</option>
              <option value="entitlement_override">Entitlement Override</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label
              htmlFor="page-size-select"
              className="text-[11px] font-semibold uppercase tracking-wider text-ops-text-secondary"
            >
              Page Size
            </label>
            <select
              id="page-size-select"
              value={limit}
              onChange={(e) => {
                setLimit(Number(e.target.value));
                setOffset(0);
              }}
              className={`${opsSelectClass} max-w-[130px]`}
            >
              <option value={10}>10 per page</option>
              <option value={25}>25 per page</option>
              <option value={50}>50 per page</option>
              <option value={100}>100 per page</option>
            </select>
          </div>
        </div>

        {hasActiveFilters && (
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              onClick={handleResetFilters}
              className="text-xs text-ops-error hover:bg-ops-status-critical-bg"
            >
              Reset filters
            </Button>
            <span className="text-xs text-ops-text-secondary">Showing filtered results</span>
          </div>
        )}
      </div>

      {/* Global Error Banner */}
      {error && (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 rounded-md border border-ops-border bg-ops-status-critical-bg p-4 text-xs text-ops-status-critical-text"
        >
          <div>
            <div className="font-semibold">Failed to load approvals</div>
            <div>{error}</div>
          </div>
          <Button variant="secondary" onClick={loadRequests}>
            Try again
          </Button>
        </div>
      )}

      {/* Main Table / State Container */}
      <div className="overflow-hidden rounded-md border border-ops-border bg-white">
        {loading ? (
          <div className="py-12">
            <StateBlock
              variant="loading"
              title="Loading approval queue"
              description="Fetching requests from governance service…"
            />
          </div>
        ) : requests.length === 0 ? (
          <div className="py-12">
            <StateBlock
              variant="empty"
              title="No approval requests found"
              description={
                hasActiveFilters
                  ? 'No requests match your current filters. Try resetting the filters.'
                  : 'There are currently no approval requests in the governance queue.'
              }
              actionLabel={hasActiveFilters ? 'Reset filters' : undefined}
              onAction={hasActiveFilters ? handleResetFilters : undefined}
            />
          </div>
        ) : (
          <DataTable
            columns={columns}
            rows={requests}
            rowKey={(req) => req.id}
            minWidth="900px"
            footer={
              <div className="flex w-full items-center justify-between px-2 py-1">
                <span className="text-xs text-ops-text-secondary">
                  Showing{' '}
                  <span className="font-medium text-ops-text-primary">
                    {total === 0 ? 0 : offset + 1}–{Math.min(offset + limit, total)}
                  </span>{' '}
                  of <span className="font-medium text-ops-text-primary">{total}</span> records
                </span>
                <div className="flex items-center gap-1.5">
                  <Button
                    variant="secondary"
                    className="h-7 px-2 text-xs"
                    onClick={() => setOffset((prev) => Math.max(0, prev - limit))}
                    disabled={offset === 0 || loading}
                  >
                    {'< Previous'}
                  </Button>
                  <Button
                    variant="secondary"
                    className="h-7 px-2 text-xs"
                    onClick={() => setOffset((prev) => prev + limit)}
                    disabled={offset + limit >= total || loading}
                  >
                    {'Next >'}
                  </Button>
                </div>
              </div>
            }
          />
        )}
      </div>

      {/* Request Detail Drawer */}
      <Drawer
        open={selectedRequestId !== null}
        onClose={handleCloseDetail}
        title="Approval Request Details"
        subtitle={selectedRequestId ? `ID: ${selectedRequestId}` : undefined}
        closeAriaLabel="Close drawer"
        footer={
          isDecisionEligibleUser && isRequestDecisionEligible ? (
            <div className="flex w-full items-center justify-between gap-3">
              <span className="text-xs text-ops-text-secondary">Action required:</span>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  className="text-xs text-ops-status-critical-text hover:bg-ops-status-critical-bg"
                  onClick={() => handleOpenDecisionModal('reject')}
                  disabled={isSubmittingDecision || isResolvingUncertainty || Boolean(uncertainOutcomeWarning)}
                >
                  <XCircle className="h-3.5 w-3.5 mr-1" />
                  Reject Request
                </Button>
                <Button
                  variant="primary"
                  className="text-xs"
                  onClick={() => handleOpenDecisionModal('approve')}
                  disabled={isSubmittingDecision || isResolvingUncertainty || Boolean(uncertainOutcomeWarning)}
                >
                  <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                  Approve Request
                </Button>
              </div>
            </div>
          ) : undefined
        }
      >
        {detailLoading ? (
          <div className="py-12">
            <StateBlock
              variant="loading"
              title="Loading request detail"
              description="Retrieving details and audit lineage…"
            />
          </div>
        ) : detailError ? (
          <div className="py-12">
            <StateBlock
              variant="error"
              title="Unable to load details"
              description={detailError}
              actionLabel="Retry"
              onAction={() => selectedRequestId && loadDetail(selectedRequestId)}
            />
          </div>
        ) : detail ? (
          <div className="space-y-6 text-sm">
            {/* Uncertain Commit Warning Banner */}
            {uncertainOutcomeWarning && (
              <div
                role="alert"
                className="flex flex-col gap-2 rounded-lg border border-ops-status-pending-text/30 bg-ops-status-pending-bg p-3.5 text-xs text-ops-status-pending-text"
              >
                <div className="flex items-center gap-1.5 font-semibold">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-ops-status-pending-text" />
                  <span>Ambiguous Transaction Outcome</span>
                </div>
                <p className="leading-relaxed">{uncertainOutcomeWarning}</p>
                <div className="mt-1 flex items-center gap-2">
                  <Button
                    variant="secondary"
                    className="h-7 px-2.5 text-xs bg-white text-ops-text-primary"
                    disabled={isResolvingUncertainty}
                    onClick={() => selectedRequestId && loadDetail(selectedRequestId)}
                  >
                    <RefreshCw className={`h-3 w-3 mr-1 ${isResolvingUncertainty ? 'animate-spin' : ''}`} />
                    Verify State
                  </Button>
                </div>
              </div>
            )}

            {/* Ordinary Decision Error Banner */}
            {decisionError && (
              <div
                role="alert"
                className="flex items-start justify-between gap-2 rounded-lg border border-ops-status-critical-bg bg-ops-status-critical-bg/10 p-3 text-xs text-ops-status-critical-text"
              >
                <div>
                  <div className="font-semibold">Decision Not Permitted</div>
                  <div className="mt-0.5">{decisionError}</div>
                </div>
                <Button variant="ghost" className="h-6 px-1.5 text-xs" onClick={() => setDecisionError(null)}>
                  Dismiss
                </Button>
              </div>
            )}

            {/* Header / Summary Status Banner */}
            <div className="rounded-lg border border-ops-border bg-ops-canvas p-4">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-medium text-ops-text-secondary">Request Status</span>
                  <div className="mt-1">
                    <StatusBadge tone={STATUS_TONES[detail.status] || 'neutral'} label={detail.status} />
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-xs font-medium text-ops-text-secondary">Execution</span>
                  <div className="mt-1 font-mono text-xs text-ops-text-primary capitalize">
                    {detail.execution_status.replace(/_/g, ' ')}
                  </div>
                </div>
              </div>

              {detail.decision_reason && (
                <div className="mt-3 pt-3 border-t border-ops-border text-xs">
                  <span className="font-medium text-ops-text-primary">Decision Reason:</span>
                  <p className="mt-1 text-ops-text-secondary">{detail.decision_reason}</p>
                </div>
              )}
            </div>

            {/* Metadata Grid */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-xs font-medium text-ops-text-secondary">Request Type</dt>
                <dd className="mt-1 text-sm font-medium text-ops-text-primary">
                  {REQUEST_TYPE_LABELS[detail.request_type] || detail.request_type}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-ops-text-secondary">Target Entity</dt>
                <dd className="mt-1 font-mono text-xs text-ops-text-primary">
                  {detail.target_entity_type} {detail.target_entity_id ? `(${detail.target_entity_id})` : ''}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-ops-text-secondary">Requester</dt>
                <dd className="mt-1 text-xs text-ops-text-primary">
                  {detail.requester_display_name || 'N/A'}{' '}
                  {detail.requester_email && (
                    <span className="text-ops-text-secondary">({detail.requester_email})</span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-ops-text-secondary">Approver</dt>
                <dd className="mt-1 text-xs text-ops-text-primary">
                  {detail.approver_display_name || detail.approver_email || 'Awaiting decision'}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-ops-text-secondary">Created</dt>
                <dd className="mt-1 font-mono text-xs text-ops-text-secondary">{formatDate(detail.created_at)}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-ops-text-secondary">Expires</dt>
                <dd className="mt-1 font-mono text-xs text-ops-text-secondary">{formatDate(detail.expires_at)}</dd>
              </div>
            </div>

            {/* Justification */}
            {detail.justification && (
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-ops-text-secondary mb-1.5">
                  Submission Justification
                </h4>
                <div className="rounded border border-ops-border bg-ops-surface p-3 text-xs text-ops-text-primary leading-relaxed">
                  {detail.justification}
                </div>
              </div>
            )}

            {/* Sanitized Payload Snapshot */}
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-ops-text-secondary mb-1.5 flex items-center justify-between">
                <span>Payload Snapshot</span>
                <span className="text-[11px] font-normal text-ops-text-muted">Sensitive data scrubbed</span>
              </h4>
              <div className="rounded border border-ops-border bg-ops-canvas p-3 font-mono text-xs text-ops-text-primary overflow-x-auto max-h-56">
                <pre>{JSON.stringify(detail.payload_snapshot, null, 2)}</pre>
              </div>
            </div>

            {/* Execution Diagnostic (if failed/blocked) */}
            {detail.execution_error && (
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-ops-status-critical-text mb-1.5 flex items-center">
                  <AlertCircle className="h-3.5 w-3.5 mr-1" />
                  Execution Diagnostic
                </h4>
                <div className="rounded border border-ops-status-critical-bg bg-ops-status-critical-bg/10 p-3 font-mono text-xs text-ops-status-critical-text">
                  {detail.execution_error}
                </div>
              </div>
            )}

            {/* Clarification Timeline */}
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-ops-text-secondary mb-2 flex items-center">
                <MessageSquare className="h-3.5 w-3.5 mr-1.5" />
                Clarification History ({detail.clarifications?.length || 0})
              </h4>
              {!detail.clarifications || detail.clarifications.length === 0 ? (
                <p className="text-xs text-ops-text-muted italic">No clarification messages recorded.</p>
              ) : (
                <div className="space-y-2.5">
                  {detail.clarifications.map((c) => (
                    <div key={c.id} className="rounded border border-ops-border bg-ops-surface p-3 text-xs">
                      <div className="flex items-center justify-between text-[11px] text-ops-text-secondary mb-1">
                        <span className="font-semibold text-ops-text-primary capitalize">
                          {c.author_display_name || c.author_email || 'Author'} ({c.clarification_type})
                        </span>
                        <span className="font-mono">{formatDate(c.created_at)}</span>
                      </div>
                      <p className="text-ops-text-primary whitespace-pre-wrap">{c.message}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : null}
      </Drawer>

      {/* Decision Confirmation Modal Dialog */}
      {decisionModalType && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(31,41,51,0.50)] p-4 animate-ops-fade-in">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="decision-modal-title"
            className="w-full max-w-md rounded-lg border border-ops-border bg-white p-5 shadow-lg"
          >
            <div className="flex items-center gap-2 text-ops-text-primary">
              {decisionModalType === 'approve' ? (
                <CheckCircle2 className="h-5 w-5 text-ops-status-active-text" />
              ) : (
                <XCircle className="h-5 w-5 text-ops-status-critical-text" />
              )}
              <h3 id="decision-modal-title" className="text-base font-semibold capitalize">
                {decisionModalType === 'approve' ? 'Approve Request' : 'Reject Request'}
              </h3>
            </div>

            <p className="mt-2 text-xs text-ops-text-secondary leading-relaxed">
              {decisionModalType === 'approve'
                ? 'Approving this request will trigger automated domain execution and durable audit logging. Are you sure you wish to proceed?'
                : 'Rejecting this request is a permanent action. Please provide a mandatory reason for the rejection.'}
            </p>

            <div className="mt-4">
              <label htmlFor="decision-reason-input" className="block text-xs font-medium text-ops-text-primary mb-1">
                Reason {decisionModalType === 'reject' && <span className="text-ops-error">*</span>}
              </label>
              <textarea
                id="decision-reason-input"
                rows={3}
                value={decisionReason}
                onChange={(e) => {
                  setDecisionReason(e.target.value);
                  if (decisionReasonError) setDecisionReasonError(null);
                }}
                disabled={isSubmittingDecision}
                placeholder={
                  decisionModalType === 'reject'
                    ? 'Enter detailed justification for rejection…'
                    : 'Optional justification note…'
                }
                className={`w-full rounded-md border p-2 text-xs text-ops-text-primary focus:outline-none focus:ring-2 ${
                  decisionReasonError
                    ? 'border-ops-error focus:ring-ops-error'
                    : 'border-ops-border focus:ring-ops-accent-focus'
                }`}
              />
              {decisionReasonError && (
                <p className="mt-1 text-xs text-ops-error font-medium">{decisionReasonError}</p>
              )}
            </div>

            {decisionError && (
              <div
                role="alert"
                className="mt-3 rounded border border-ops-status-critical-bg bg-ops-status-critical-bg/10 p-2.5 text-xs text-ops-status-critical-text"
              >
                {decisionError}
              </div>
            )}

            <div className="mt-5 flex items-center justify-end gap-2.5">
              <Button
                variant="secondary"
                onClick={handleCloseDecisionModal}
                disabled={isSubmittingDecision}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                variant={decisionModalType === 'approve' ? 'primary' : 'critical'}
                onClick={handleConfirmDecision}
                disabled={isSubmittingDecision}
                className="text-xs"
              >
                {isSubmittingDecision
                  ? 'Submitting…'
                  : decisionModalType === 'approve'
                  ? 'Confirm Approval'
                  : 'Confirm Rejection'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
