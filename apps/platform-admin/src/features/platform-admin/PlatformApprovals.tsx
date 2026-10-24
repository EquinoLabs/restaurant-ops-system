import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
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
  Search,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Info,
  Lock,
  ArrowLeft,
  FileText,
  Clock,
  User as UserIcon,
  HelpCircle,
  Loader2,
} from 'lucide-react';
import { Button, StatusBadge, type StatusTone } from '../../components/ops-ui';

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
  business_creation: 'Create business',
  outlet_creation: 'Add outlet',
  user_role_change: 'Change role',
  subscription_change: 'Update subscription',
  operator_creation: 'Add operator',
  operator_revocation: 'Revoke operator',
  user_suspension: 'Suspend user',
  user_reactivation: 'Reactivate user',
  entitlement_override: 'Entitlement override',
};

export const PlatformApprovals: React.FC<PlatformApprovalsProps> = ({ token }) => {
  const { user } = useAuth();
  const [requests, setRequests] = useState<PlatformApprovalRequestItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [limit] = useState<number>(50);
  const [offset, setOffset] = useState<number>(0);

  // Filters & Tabs
  const [activeTab, setActiveTab] = useState<'pending' | 'mine' | 'history'>('pending');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedRequestType, setSelectedRequestType] = useState<string>('');

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Master-Detail Selected Request State
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);
  const [detail, setDetail] = useState<PlatformApprovalRequestDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // Mobile/Tablet responsive view mode: 'list' | 'detail'
  const [mobileView, setMobileView] = useState<'list' | 'detail'>('list');

  // Decision Modal State
  const [decisionModalType, setDecisionModalType] = useState<'approve' | 'reject' | null>(null);
  const [decisionReason, setDecisionReason] = useState<string>('');
  const [decisionReasonError, setDecisionReasonError] = useState<string | null>(null);
  const [isSubmittingDecision, setIsSubmittingDecision] = useState<boolean>(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);

  // Uncertain commit state
  const [uncertainOutcomeWarning, setUncertainOutcomeWarning] = useState<string | null>(null);
  const [isResolvingUncertainty, setIsResolvingUncertainty] = useState<boolean>(false);

  const isSubmittingRef = useRef<boolean>(false);

  // Authorization flags
  const isOperator = user?.platform_role === 'operator';
  const isPrivilegedUser = Boolean(
    user && (user.platform_role === 'owner' || user.platform_role === 'admin' || user.is_platform_admin)
  );

  // Determine query parameters based on active tab
  const computedStatus = useMemo(() => {
    if (activeTab === 'pending') return 'pending';
    if (activeTab === 'history') return ''; // All decided statuses
    return '';
  }, [activeTab]);

  // Extract display target label from item or payload
  const getTargetTitle = useCallback(
    (req: PlatformApprovalRequestItem | PlatformApprovalRequestDetail): string => {
      const payload = (req as PlatformApprovalRequestDetail).payload_snapshot || {};
      if (req.request_type === 'operator_creation') {
        const name = payload.display_name || payload.email || 'New Operator';
        return name;
      }
      if (req.request_type === 'business_creation') {
        return payload.name || payload.legal_name || 'New Business';
      }
      if (req.request_type === 'outlet_creation') {
        return payload.name || 'New Outlet';
      }
      if (req.request_type === 'subscription_change') {
        return payload.plan_code ? `Plan ${payload.plan_code}` : 'Subscription Update';
      }
      if (req.request_type === 'user_role_change') {
        return payload.new_platform_role ? `Role → ${payload.new_platform_role}` : 'User Role';
      }
      return req.target_entity_type;
    },
    []
  );

  const loadRequests = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      setError(null);
      const data = await fetchPlatformApprovals(token, {
        limit,
        offset,
        status: computedStatus || undefined,
        request_type: selectedRequestType || undefined,
      });
      const items = data?.items || [];
      setRequests(items);
      setTotal(data?.total || 0);
    } catch (err: any) {
      setError(err.message || 'Failed to load approval requests.');
    } finally {
      setLoading(false);
    }
  }, [token, limit, offset, computedStatus, selectedRequestType]);

  useEffect(() => {
    loadRequests();
  }, [loadRequests]);

  // Filter requests client-side for search query and 'mine' tab
  const displayedRequests = useMemo(() => {
    let result = requests;

    if (activeTab === 'mine' && user?.id) {
      result = result.filter((req) => req.requester_user_id === user.id);
    } else if (activeTab === 'history') {
      result = result.filter((req) => req.status !== 'pending' && req.status !== 'needs_information');
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter((req) => {
        const idMatch = req.id.toLowerCase().includes(q);
        const typeMatch = (REQUEST_TYPE_LABELS[req.request_type] || req.request_type).toLowerCase().includes(q);
        const reqNameMatch = (req.requester_display_name || '').toLowerCase().includes(q);
        const reqEmailMatch = (req.requester_email || '').toLowerCase().includes(q);
        const entityMatch = (req.target_entity_id || '').toLowerCase().includes(q);
        const targetTitleMatch = getTargetTitle(req).toLowerCase().includes(q);
        return idMatch || typeMatch || reqNameMatch || reqEmailMatch || entityMatch || targetTitleMatch;
      });
    }

    return result;
  }, [requests, activeTab, user?.id, searchQuery, getTargetTitle]);

  // Synchronize selectedRequestId with displayedRequests (Fix 1)
  useEffect(() => {
    if (loading) return;

    if (displayedRequests.length > 0) {
      const isCurrentInList = selectedRequestId
        ? displayedRequests.some((req) => req.id === selectedRequestId)
        : false;

      if (!isCurrentInList) {
        setSelectedRequestId(displayedRequests[0].id);
      }
    } else {
      if (selectedRequestId !== null) {
        setSelectedRequestId(null);
      }
      setMobileView('list');
    }
  }, [displayedRequests, selectedRequestId, loading]);

  // Monotonically increasing sequence ID to prevent out-of-order responses from overwriting detail (Fix 2)
  const detailSeqRef = useRef<number>(0);

  // Load detailed record whenever selectedRequestId changes
  const loadDetail = useCallback(
    async (requestId: string) => {
      if (!token) return;
      const currentSeq = ++detailSeqRef.current;
      setDetail(null);
      setDetailLoading(true);
      setDetailError(null);

      try {
        const data = await fetchPlatformApprovalDetail(token, requestId);
        if (detailSeqRef.current === currentSeq) {
          setDetail(data);
        }
      } catch (err: any) {
        if (detailSeqRef.current === currentSeq) {
          setDetailError(err?.message || 'Failed to load request details.');
        }
      } finally {
        if (detailSeqRef.current === currentSeq) {
          setDetailLoading(false);
        }
      }
    },
    [token]
  );

  useEffect(() => {
    setDecisionError(null);
    setUncertainOutcomeWarning(null);

    if (selectedRequestId) {
      loadDetail(selectedRequestId);
    } else {
      detailSeqRef.current += 1;
      setDetail(null);
      setDetailLoading(false);
      setDetailError(null);
    }
  }, [selectedRequestId, loadDetail]);

  // Component cleanup: invalidate any pending detail requests on unmount
  useEffect(() => {
    return () => {
      detailSeqRef.current += 1;
    };
  }, []);

  const handleSelectRow = (reqId: string) => {
    setSelectedRequestId(reqId);
    setDecisionError(null);
    setUncertainOutcomeWarning(null);
    setMobileView('detail');
  };

  // Decision Modal Handlers
  const handleOpenDecisionModal = (type: 'approve' | 'reject') => {
    if (!detail || !selectedRequestId || detail.id !== selectedRequestId) return;
    setDecisionModalType(type);
    setDecisionReason(type === 'approve' ? 'Approved by platform administrator' : '');
    setDecisionReasonError(null);
    setDecisionError(null);
  };

  const handleCloseDecisionModal = () => {
    if (isSubmittingDecision) return;
    setDecisionModalType(null);
    setDecisionReason('');
    setDecisionReasonError(null);
    setDecisionError(null);
  };

  const handleConfirmDecision = async () => {
    if (!token || !detail || !selectedRequestId || detail.id !== selectedRequestId || !decisionModalType) return;
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
      setDetail(updatedDetail);
      setDecisionModalType(null);
      setDecisionReason('');
      await loadRequests();
    } catch (err: any) {
      if (err.code === 'COMMIT_OUTCOME_UNCERTAIN' || err.status === 503) {
        setUncertainOutcomeWarning(
          'A connection interruption occurred while committing the decision. Verifying authoritative outcome…'
        );
        setDecisionModalType(null);
        setIsResolvingUncertainty(true);
        try {
          await loadRequests();
          if (selectedRequestId) {
            await loadDetail(selectedRequestId);
          }
        } finally {
          setIsResolvingUncertainty(false);
        }
      } else {
        const errorMsg =
          err?.details?.message || err?.message || 'Failed to submit approval decision. Please check authorization.';
        setDecisionError(errorMsg);
      }
    } finally {
      setIsSubmittingDecision(false);
      isSubmittingRef.current = false;
    }
  };

  // Helper to format short IDs like "#b8d7a123"
  const formatShortId = (id: string | null | undefined): string => {
    if (!id) return '';
    return `#${id.slice(0, 8)}`;
  };

  const formatDate = (iso: string | null | undefined): string => {
    if (!iso) return 'N/A';
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  };

  // Impact summary generator ("What will happen")
  const renderImpactSummary = (reqDetail: PlatformApprovalRequestDetail) => {
    const p = reqDetail.payload_snapshot || {};
    const reqType = reqDetail.request_type;
    const isPending = reqDetail.status === 'pending' || reqDetail.status === 'needs_information';

    let impactText: React.ReactNode = null;

    if (reqType === 'operator_creation') {
      const isExisting = Boolean(p.target_user_id || p.user_id);
      if (isExisting) {
        impactText = (
          <>
            {isPending ? 'If approved, ' : 'Approved: '}the existing user (
            <code className="rounded bg-ops-canvas px-1 py-0.5 font-mono text-xs text-ops-text-primary">
              {p.target_user_id || p.user_id}
            </code>
            ) will be granted the <strong>Platform Operator</strong> role without altering credentials.
          </>
        );
      } else {
        impactText = (
          <>
            {isPending ? 'If approved, ' : 'Approved: '}a new Platform Operator account will be provisioned for{' '}
            <strong>{p.display_name || 'Operator'}</strong> (
            <span className="text-ops-text-secondary">{p.email}</span>) with an automatically generated secure
            temporary credential delivered to the local environment.
          </>
        );
      }
    } else if (reqType === 'business_creation') {
      impactText = (
        <>
          {isPending ? 'If approved, ' : 'Approved: '}a new business account and root environment will be provisioned
          for <strong>{p.name || 'Business'}</strong>
          {p.owner_email ? ` with designated owner (${p.owner_email})` : ''}.
        </>
      );
    } else if (reqType === 'outlet_creation') {
      impactText = (
        <>
          {isPending ? 'If approved, ' : 'Approved: '}a new operational outlet <strong>{p.name || 'Outlet'}</strong>{' '}
          will be created under business{' '}
          <code className="rounded bg-ops-canvas px-1 py-0.5 font-mono text-xs">{p.business_id}</code>.
        </>
      );
    } else if (reqType === 'subscription_change') {
      impactText = (
        <>
          {isPending ? 'If approved, ' : 'Approved: '}the commercial subscription for business{' '}
          <code className="rounded bg-ops-canvas px-1 py-0.5 font-mono text-xs">{p.business_id}</code> will be updated
          to plan <strong>{p.plan_code || 'updated plan'}</strong> ({p.billing_interval || 'annual'}).
        </>
      );
    } else if (reqType === 'user_suspension') {
      impactText = (
        <>
          {isPending ? 'If approved, ' : 'Approved: '}user account{' '}
          <code className="rounded bg-ops-canvas px-1 py-0.5 font-mono text-xs">{p.target_user_id}</code> will be
          suspended immediately, revoking active session tokens.
        </>
      );
    } else if (reqType === 'user_reactivation') {
      impactText = (
        <>
          {isPending ? 'If approved, ' : 'Approved: '}suspended user account{' '}
          <code className="rounded bg-ops-canvas px-1 py-0.5 font-mono text-xs">{p.target_user_id}</code> will be
          reactivated with active login permissions.
        </>
      );
    } else if (reqType === 'user_role_change') {
      impactText = (
        <>
          {isPending ? 'If approved, ' : 'Approved: '}the platform role for user{' '}
          <code className="rounded bg-ops-canvas px-1 py-0.5 font-mono text-xs">{p.target_user_id}</code> will be
          changed to <strong>{p.new_platform_role}</strong>.
        </>
      );
    } else {
      impactText = (
        <>
          {isPending ? 'If approved, ' : 'Approved: '}the requested{' '}
          <strong>{REQUEST_TYPE_LABELS[reqType] || reqType}</strong> operation will be executed through the
          centralized execution boundary.
        </>
      );
    }

    return (
      <div className="flex items-start gap-2.5 rounded-md border border-ops-border bg-white p-3 text-xs leading-relaxed text-ops-text-primary">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-ops-accent" aria-hidden="true" />
        <div>
          <strong className="font-semibold text-ops-text-primary">What will happen: </strong>
          {impactText}
        </div>
      </div>
    );
  };

  const isRequestPending = detail?.status === 'pending' || detail?.status === 'needs_information';

  return (
    <div className="flex flex-col gap-4">
      {/* Top Page Header (Stitch Specification) */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ops-text-primary">Approvals</h1>
          <p className="text-xs text-ops-text-secondary mt-0.5">
            {isOperator ? 'Track the requests you have submitted.' : 'Review and decide on pending requests.'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={loadRequests}
            disabled={loading}
            className="h-8 text-xs font-medium"
            aria-label="Refresh approvals list"
          >
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Operator Read-Only Governance Disclaimer Banner */}
      {isOperator && (
        <div
          role="note"
          className="flex items-center gap-2.5 rounded-md border border-ops-border bg-[#F6F7F9] p-3 text-xs text-ops-text-secondary"
        >
          <Lock className="h-4 w-4 shrink-0 text-ops-text-secondary" aria-hidden="true" />
          <span>
            <strong>Read-only access:</strong> Platform Operators can track and inspect approval requests, but cannot
            approve, reject, or execute privileged requests.
          </span>
        </div>
      )}

      {/* Global Error Banner */}
      {error && (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 rounded-md border border-ops-status-critical-bg bg-ops-status-critical-bg/15 p-3 text-xs text-ops-status-critical-text"
        >
          <div>
            <span className="font-semibold">Error: </span>
            {error}
          </div>
          <Button variant="secondary" onClick={loadRequests} className="h-7 text-xs">
            Retry
          </Button>
        </div>
      )}

      {/* Toolbar row: Search, Status tabs, and Type filter */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2 flex-1">
          {/* Search Input */}
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-ops-text-secondary" aria-hidden="true" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name, email, or requester"
              aria-label="Search approval requests"
              className="h-8 w-full rounded-md border border-ops-border bg-white pl-8 pr-3 text-xs text-ops-text-primary placeholder:text-ops-text-disabled focus:border-ops-accent focus:outline-none focus:ring-1 focus:ring-ops-accent-focus"
            />
          </div>

          {/* Status Tabs Segmented Control */}
          <div className="inline-flex h-8 items-center rounded-md bg-[#EEF0F3] p-0.5">
            <button
              type="button"
              onClick={() => setActiveTab('pending')}
              className={`flex h-7 items-center gap-1.5 rounded px-2.5 text-xs font-medium transition-colors ${
                activeTab === 'pending'
                  ? 'bg-white text-ops-text-primary shadow-sm'
                  : 'text-ops-text-secondary hover:text-ops-text-primary'
              }`}
            >
              <span>Pending</span>
              <span className="rounded-full bg-[#FFF4DB] px-1.5 py-0.2 text-[10px] font-semibold text-[#8A5A00]">
                {requests.filter((r) => r.status === 'pending').length}
              </span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('mine')}
              className={`h-7 rounded px-2.5 text-xs font-medium transition-colors ${
                activeTab === 'mine'
                  ? 'bg-white text-ops-text-primary shadow-sm'
                  : 'text-ops-text-secondary hover:text-ops-text-primary'
              }`}
            >
              Mine
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('history')}
              className={`h-7 rounded px-2.5 text-xs font-medium transition-colors ${
                activeTab === 'history'
                  ? 'bg-white text-ops-text-primary shadow-sm'
                  : 'text-ops-text-secondary hover:text-ops-text-primary'
              }`}
            >
              History
            </button>
          </div>
        </div>

        {/* Type Filter Dropdown */}
        <div className="flex items-center gap-2">
          <div className="relative">
            <select
              id="approval-type-filter"
              value={selectedRequestType}
              onChange={(e) => {
                setSelectedRequestType(e.target.value);
                setOffset(0);
              }}
              className="h-8 appearance-none rounded-md border border-ops-border bg-white pl-2.5 pr-8 text-xs font-medium text-ops-text-primary focus:border-ops-accent focus:outline-none focus:ring-1 focus:ring-ops-accent-focus"
              aria-label="Filter by request type"
            >
              <option value="">Request type: All types</option>
              <option value="operator_creation">Add operator</option>
              <option value="business_creation">Create business</option>
              <option value="outlet_creation">Add outlet</option>
              <option value="subscription_change">Update subscription</option>
              <option value="user_role_change">Change user role</option>
              <option value="user_suspension">Suspend user</option>
              <option value="user_reactivation">Reactivate user</option>
            </select>
            <ChevronDown
              className="pointer-events-none absolute right-2.5 top-2.5 h-3.5 w-3.5 text-ops-text-secondary"
              aria-hidden="true"
            />
          </div>
        </div>
      </div>

      {/* MASTER-DETAIL SPLIT CONTAINER (Desktop: 38% / 62% | Responsive: Stacked) */}
      <div className="flex min-h-[580px] flex-col overflow-hidden rounded-md border border-ops-border bg-white md:flex-row">
        {/* =========================================================================
            LEFT PANE: Request List (~38% width on desktop)
            ========================================================================= */}
        <div
          className={`flex w-full flex-col border-b border-ops-border md:w-[38%] md:min-w-[320px] md:border-b-0 md:border-r ${
            mobileView === 'detail' ? 'hidden md:flex' : 'flex'
          }`}
        >
          {/* Pane Header */}
          <div className="flex h-9 items-center justify-between border-b border-ops-border bg-[#F6F7F9] px-4 text-[11px] font-semibold uppercase tracking-wider text-ops-text-secondary">
            <span>Request / Target</span>
            <span>Status</span>
          </div>

          {/* List Content */}
          <div className="flex-1 divide-y divide-ops-border overflow-y-auto">
            {loading ? (
              <div className="flex flex-col items-center justify-center p-8 text-xs text-ops-text-secondary">
                <Loader2 className="mb-2 h-5 w-5 animate-spin text-ops-accent" />
                <span>Loading approval requests…</span>
              </div>
            ) : displayedRequests.length === 0 ? (
              <div className="p-8 text-center text-xs text-ops-text-secondary">
                <FileText className="mx-auto mb-2 h-6 w-6 text-ops-text-disabled" />
                <p className="font-medium text-ops-text-primary">No requests found</p>
                <p className="mt-1">There are no approval requests matching your selection.</p>
              </div>
            ) : (
              displayedRequests.map((req) => {
                const isSelected = req.id === selectedRequestId;
                const typeLabel = REQUEST_TYPE_LABELS[req.request_type] || req.request_type;
                const targetTitle = getTargetTitle(req);

                return (
                  <div
                    key={req.id}
                    onClick={() => handleSelectRow(req.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        handleSelectRow(req.id);
                      }
                    }}
                    className={`flex cursor-pointer items-center justify-between p-3.5 transition-colors ${
                      isSelected
                        ? 'border-l-2 border-ops-accent bg-[#F6F7F9]'
                        : 'hover:bg-ops-canvas active:bg-[#EEF0F3]'
                    }`}
                  >
                    <div className="flex flex-col gap-1 pr-2 overflow-hidden">
                      <div className="flex items-center gap-1.5 overflow-hidden">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-medium whitespace-nowrap ${
                            isSelected
                              ? 'border border-[#D1E1FF] bg-[#EDF4FF] text-ops-accent'
                              : 'border border-ops-border bg-[#F6F7F9] text-ops-text-secondary'
                          }`}
                        >
                          {typeLabel}
                        </span>
                        <span className="truncate text-xs font-semibold text-ops-text-primary">{targetTitle}</span>
                      </div>
                      <div className="text-[11px] text-ops-text-secondary truncate">
                        {req.requester_display_name || req.requester_email || 'Requester'} ·{' '}
                        <span className="font-mono">{formatShortId(req.id)}</span>
                      </div>
                    </div>
                    <div className="shrink-0">
                      <StatusBadge tone={STATUS_TONES[req.status] || 'neutral'} label={req.status} />
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Left Pane Footer Counter */}
          <div className="flex h-8 items-center justify-between border-t border-ops-border bg-[#F6F7F9] px-4 text-[11px] text-ops-text-secondary">
            <span>Showing {displayedRequests.length} requests</span>
            <span>Page 1 of {Math.max(1, Math.ceil(total / limit))}</span>
          </div>
        </div>

        {/* =========================================================================
            RIGHT PANE: Request Details & Action Pane (~62% width on desktop)
            ========================================================================= */}
        <div
          className={`flex w-full flex-col md:w-[62%] md:min-w-[400px] ${
            mobileView === 'list' ? 'hidden md:flex' : 'flex'
          }`}
        >
          {/* Mobile Back Button */}
          <div className="flex items-center border-b border-ops-border p-2 md:hidden">
            <Button
              variant="ghost"
              className="h-8 gap-1.5 text-xs text-ops-accent"
              onClick={() => setMobileView('list')}
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Back to requests</span>
            </Button>
          </div>

          {detailLoading ? (
            <div className="flex flex-1 flex-col items-center justify-center p-12 text-xs text-ops-text-secondary">
              <Loader2 className="mb-2 h-6 w-6 animate-spin text-ops-accent" />
              <span>Loading request details…</span>
            </div>
          ) : detailError ? (
            <div className="flex flex-1 flex-col items-center justify-center p-10 text-center">
              <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full border border-ops-status-critical-bg bg-ops-status-critical-bg/15 text-ops-status-critical-text">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <h3 className="text-sm font-semibold text-ops-text-primary">Failed to load request</h3>
              <p className="mt-1 max-w-[280px] text-xs text-ops-status-critical-text">{detailError}</p>
              {selectedRequestId && (
                <Button
                  variant="secondary"
                  className="mt-3 h-7 text-xs"
                  onClick={() => loadDetail(selectedRequestId)}
                >
                  <RefreshCw className="mr-1.5 h-3 w-3" />
                  Retry
                </Button>
              )}
            </div>
          ) : !selectedRequestId || !detail || detail.id !== selectedRequestId ? (
            /* Nothing Selected Empty State */
            <div className="flex flex-1 flex-col items-center justify-center p-10 text-center">
              <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full border border-ops-border bg-[#F6F7F9]">
                <FileText className="h-5 w-5 text-ops-text-secondary" />
              </div>
              <h3 className="text-sm font-semibold text-ops-text-primary">Select a request to review</h3>
              <p className="mt-1 max-w-[280px] text-xs text-ops-text-secondary">
                Choose an item from the left panel to inspect request parameters and make a decision.
              </p>
            </div>
          ) : (
            /* Detail Content Body */
            <div className="flex flex-1 flex-col overflow-hidden">
              <div className="flex-1 space-y-5 overflow-y-auto p-6 text-xs text-ops-text-primary">
                {/* Detail Header */}
                <div className="flex items-start justify-between border-b border-ops-border pb-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-base font-semibold text-ops-text-primary">
                        {(REQUEST_TYPE_LABELS[detail.request_type] || detail.request_type)}: {getTargetTitle(detail)}
                      </h2>
                      <StatusBadge tone={STATUS_TONES[detail.status] || 'neutral'} label={detail.status} />
                    </div>
                    <div className="mt-1 text-xs text-ops-text-secondary">
                      Request <span className="font-mono">{formatShortId(detail.id)}</span> · submitted{' '}
                      <span className="font-mono">{formatDate(detail.created_at)}</span>
                    </div>
                  </div>
                </div>

                {/* Uncertain Transaction Outcome Alert */}
                {uncertainOutcomeWarning && (
                  <div
                    role="alert"
                    className="rounded-md border border-ops-status-pending-text bg-ops-status-pending-bg p-3 text-xs text-ops-status-pending-text"
                  >
                    <div className="flex items-center gap-1.5 font-semibold">
                      <AlertTriangle className="h-4 w-4 shrink-0" />
                      <span>Ambiguous Commit State</span>
                    </div>
                    <p className="mt-1 leading-relaxed">{uncertainOutcomeWarning}</p>
                    <div className="mt-2">
                      <Button
                        variant="secondary"
                        className="h-7 text-xs bg-white text-ops-text-primary"
                        onClick={() => loadDetail(detail.id)}
                        disabled={isResolvingUncertainty}
                      >
                        <RefreshCw className={`h-3 w-3 mr-1 ${isResolvingUncertainty ? 'animate-spin' : ''}`} />
                        Verify Authoritative State
                      </Button>
                    </div>
                  </div>
                )}

                {/* Decision Error Alert */}
                {decisionError && (
                  <div
                    role="alert"
                    className="flex items-start justify-between gap-2 rounded-md border border-ops-status-critical-bg bg-ops-status-critical-bg/15 p-3 text-xs text-ops-status-critical-text"
                  >
                    <div>
                      <div className="font-semibold">Action Not Permitted</div>
                      <div className="mt-0.5">{decisionError}</div>
                    </div>
                    <Button variant="ghost" className="h-6 px-1.5 text-xs" onClick={() => setDecisionError(null)}>
                      Dismiss
                    </Button>
                  </div>
                )}

                {/* "What will happen" Plain-English Impact Section */}
                {renderImpactSummary(detail)}

                {/* Decision Reason Banner if already decided */}
                {detail.decision_reason && (
                  <div className="rounded-md border border-ops-border bg-[#F6F7F9] p-3 text-xs">
                    <span className="font-semibold text-ops-text-primary">Decision Reason: </span>
                    <span className="text-ops-text-secondary">{detail.decision_reason}</span>
                  </div>
                )}

                {/* Structured Definition List */}
                <div className="divide-y divide-ops-divider text-xs">
                  <div className="flex py-2.5">
                    <span className="w-36 text-ops-text-secondary">Request type</span>
                    <span className="font-medium text-ops-text-primary">
                      {REQUEST_TYPE_LABELS[detail.request_type] || detail.request_type}
                    </span>
                  </div>

                  <div className="flex items-center py-2.5">
                    <span className="w-36 text-ops-text-secondary">Requested by</span>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-ops-text-primary">
                        {detail.requester_display_name || 'Requester'}
                      </span>
                      {detail.requester_email && (
                        <span className="text-ops-text-secondary">({detail.requester_email})</span>
                      )}
                    </div>
                  </div>

                  {detail.justification && (
                    <div className="flex py-2.5">
                      <span className="w-36 text-ops-text-secondary">Requester note</span>
                      <span className="flex-1 text-ops-text-primary italic">“{detail.justification}”</span>
                    </div>
                  )}

                  <div className="flex py-2.5">
                    <span className="w-36 text-ops-text-secondary">Approver required</span>
                    <span className="font-medium text-ops-text-primary">
                      {detail.request_type === 'user_reactivation' ? 'Platform Owner only' : 'Admin or Owner'}
                    </span>
                  </div>

                  <div className="flex py-2.5">
                    <span className="w-36 text-ops-text-secondary">Target entity</span>
                    <span className="font-mono text-ops-text-primary">
                      {detail.target_entity_type} {detail.target_entity_id ? `(${detail.target_entity_id})` : ''}
                    </span>
                  </div>

                  <div className="flex py-2.5">
                    <span className="w-36 text-ops-text-secondary">Execution status</span>
                    <span className="font-mono capitalize text-ops-text-primary">
                      {detail.execution_status.replace(/_/g, ' ')}
                    </span>
                  </div>

                  <div className="flex py-2.5">
                    <span className="w-36 text-ops-text-secondary">Submitted</span>
                    <span className="font-mono text-ops-text-secondary">{formatDate(detail.created_at)}</span>
                  </div>

                  {detail.expires_at && (
                    <div className="flex py-2.5">
                      <span className="w-36 text-ops-text-secondary">Expires</span>
                      <span className="font-mono text-ops-text-secondary">{formatDate(detail.expires_at)}</span>
                    </div>
                  )}
                </div>

                {/* Collapsible Sanitized Request Payload Snapshot */}
                <div className="mt-3">
                  <details className="rounded-md border border-ops-border bg-white text-xs overflow-hidden">
                    <summary className="flex cursor-pointer items-center justify-between bg-[#F6F7F9] px-3.5 py-2.5 font-semibold text-ops-text-primary select-none">
                      <div className="flex items-center gap-2">
                        <FileText className="h-3.5 w-3.5 text-ops-text-secondary" />
                        <span>Request payload snapshot</span>
                      </div>
                      <span className="text-[11px] font-normal text-ops-text-secondary">application/json</span>
                    </summary>
                    <div className="border-t border-ops-border bg-[#F6F7F9] p-3">
                      <pre className="overflow-x-auto font-mono text-[11px] leading-relaxed text-ops-text-primary">
                        {JSON.stringify(detail.payload_snapshot, null, 2)}
                      </pre>
                    </div>
                  </details>
                </div>

                {/* Clarification Timeline History */}
                {detail.clarifications && detail.clarifications.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <h4 className="font-semibold text-ops-text-primary">
                      Clarification History ({detail.clarifications.length})
                    </h4>
                    <div className="space-y-2">
                      {detail.clarifications.map((c) => (
                        <div key={c.id} className="rounded border border-ops-border bg-ops-canvas p-2.5 text-xs">
                          <div className="flex items-center justify-between text-[11px] text-ops-text-secondary mb-1">
                            <span className="font-semibold text-ops-text-primary">
                              {c.author_display_name || c.author_email || 'Author'} ({c.clarification_type})
                            </span>
                            <span className="font-mono">{formatDate(c.created_at)}</span>
                          </div>
                          <p className="text-ops-text-primary">{c.message}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* STICKY DETAIL FOOTER: Action buttons or Read-only notice */}
              <div className="flex h-14 items-center justify-between border-t border-ops-border bg-white px-6">
                {isOperator ? (
                  /* Operator Read-Only Footer */
                  <div className="flex items-center gap-2 text-xs font-medium text-ops-text-secondary">
                    <Lock className="h-4 w-4 shrink-0" aria-hidden="true" />
                    <span>Only Admins and Owners can decide on requests.</span>
                  </div>
                ) : isPrivilegedUser && isRequestPending ? (
                  /* Privileged Admin/Owner Active Controls */
                  <>
                    <span className="text-xs text-ops-text-secondary">A reason is required to reject.</span>
                    <div className="flex items-center gap-2.5">
                      <button
                        type="button"
                        onClick={() => handleOpenDecisionModal('reject')}
                        className="inline-flex h-8 items-center justify-center rounded-md border border-[#F8D7DA] bg-white px-3 text-xs font-medium text-[#B42318] hover:bg-[#FDECEA] transition-colors"
                      >
                        Reject
                      </button>
                      <button
                        type="button"
                        onClick={() => handleOpenDecisionModal('approve')}
                        className="inline-flex h-8 items-center justify-center rounded-md border border-ops-accent bg-ops-accent px-3 text-xs font-medium text-white hover:bg-ops-accent-hover transition-colors"
                      >
                        Approve
                      </button>
                    </div>
                  </>
                ) : (
                  /* Decided or Expired State Notice */
                  <div className="flex items-center gap-2 text-xs text-ops-text-secondary">
                    <CheckCircle2 className="h-4 w-4 text-ops-text-disabled" />
                    <span>This request has been decided and is no longer pending action.</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* DECISION CONFIRMATION MODAL (Reject requires reason, Approve has default reason) */}
      {decisionModalType && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(15,23,42,0.40)] p-4 animate-ops-fade-in">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="decision-modal-title"
            className="w-full max-w-md rounded-md border border-ops-border bg-white shadow-xl overflow-hidden"
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-ops-border px-5 py-4">
              <div className="flex items-center gap-2">
                <div
                  className={`flex h-6 w-6 items-center justify-center rounded-full ${
                    decisionModalType === 'approve'
                      ? 'bg-ops-status-active-bg text-ops-status-active-text'
                      : 'bg-[#FDECEA] text-[#B42318]'
                  }`}
                >
                  {decisionModalType === 'approve' ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    <XCircle className="h-4 w-4" />
                  )}
                </div>
                <h3 id="decision-modal-title" className="text-sm font-semibold text-ops-text-primary capitalize">
                  {decisionModalType === 'approve' ? 'Approve request' : 'Reject request'}
                </h3>
              </div>
              <button
                type="button"
                onClick={handleCloseDecisionModal}
                disabled={isSubmittingDecision}
                className="text-ops-text-secondary hover:text-ops-text-primary"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 text-xs text-ops-text-primary">
              <p className="text-ops-text-secondary leading-relaxed">
                You are {decisionModalType === 'approve' ? 'approving' : 'rejecting'} request{' '}
                <strong className="font-mono text-ops-text-primary">
                  {detail ? formatShortId(detail.id) : ''}
                </strong>{' '}
                ({detail ? getTargetTitle(detail) : ''}).
              </p>

              <div className="mt-4">
                <label htmlFor="decision-reason-input" className="block font-semibold text-ops-text-primary mb-1">
                  Reason for {decisionModalType === 'approve' ? 'approval' : 'rejection'}{' '}
                  {decisionModalType === 'reject' && <span className="text-[#B42318]">*</span>}
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
                      ? 'Explain why this request is being rejected so the requester can adjust…'
                      : 'Optional justification note…'
                  }
                  className={`w-full rounded-md border p-2.5 text-xs text-ops-text-primary focus:outline-none focus:ring-1 ${
                    decisionReasonError
                      ? 'border-ops-error focus:ring-ops-error'
                      : 'border-ops-border focus:ring-ops-accent-focus'
                  }`}
                />
                {decisionReasonError && (
                  <p className="mt-1 text-xs text-ops-error font-medium">{decisionReasonError}</p>
                )}
                <span className="mt-1 block text-[11px] text-ops-text-secondary">
                  This comment is permanently recorded in the platform audit log.
                </span>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-end gap-2 border-t border-ops-border bg-[#F6F7F9] px-5 py-3">
              <Button
                variant="secondary"
                onClick={handleCloseDecisionModal}
                disabled={isSubmittingDecision}
                className="h-8 text-xs font-medium"
              >
                Cancel
              </Button>
              <button
                type="button"
                onClick={handleConfirmDecision}
                disabled={isSubmittingDecision}
                className={`inline-flex h-8 items-center justify-center rounded-md px-3 text-xs font-medium transition-colors ${
                  decisionModalType === 'approve'
                    ? 'bg-ops-accent text-white hover:bg-ops-accent-hover'
                    : 'border border-[#F8D7DA] bg-white text-[#B42318] hover:bg-[#FDECEA]'
                }`}
              >
                {isSubmittingDecision
                  ? 'Submitting…'
                  : decisionModalType === 'approve'
                  ? 'Approve request'
                  : 'Reject request'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
export default PlatformApprovals;
