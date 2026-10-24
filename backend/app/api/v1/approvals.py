"""FastAPI endpoints for Platform Approval workflow read-only integration.

Provides secured endpoints for Platform Owner, Admin, and Operator users to list
and retrieve approval requests with role-based visibility and sensitive-field protection.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import RequirePlatformRole
from app.modules.staff.models import User
from app.modules.approvals.service import (
    list_approval_requests,
    get_approval_request,
    decide_approval_request,
)
from app.modules.approvals.schemas import (
    ApprovalRequestsListResponse,
    ApprovalRequestItemOut,
    ApprovalRequestDetailOut,
    ApprovalClarificationItemOut,
    ApprovalDecisionRequest,
)

router = APIRouter(prefix="/platform/approvals", tags=["platform-approvals"])


def _serialize_request_item(req) -> ApprovalRequestItemOut:
    return ApprovalRequestItemOut(
        id=req.id,
        business_id=req.business_id,
        outlet_id=req.outlet_id,
        requester_user_id=req.requester_user_id,
        requester_email=req.requester.email if req.requester else None,
        requester_display_name=req.requester.display_name if req.requester else None,
        approver_user_id=req.approver_user_id,
        approver_email=req.approver.email if req.approver else None,
        approver_display_name=req.approver.display_name if req.approver else None,
        request_type=req.request_type,
        target_entity_type=req.target_entity_type,
        target_entity_id=req.target_entity_id,
        status=req.status,
        execution_status=req.execution_status,
        justification=req.justification,
        expires_at=req.expires_at,
        decided_at=req.decided_at,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


def _serialize_request_detail(req) -> ApprovalRequestDetailOut:
    clarifications = []
    if req.clarifications:
        for c in req.clarifications:
            clarifications.append(
                ApprovalClarificationItemOut(
                    id=c.id,
                    approval_request_id=c.approval_request_id,
                    author_user_id=c.author_user_id,
                    author_email=c.author.email if c.author else None,
                    author_display_name=c.author.display_name if c.author else None,
                    clarification_type=c.clarification_type,
                    message=c.message,
                    created_at=c.created_at,
                )
            )

    return ApprovalRequestDetailOut(
        id=req.id,
        business_id=req.business_id,
        outlet_id=req.outlet_id,
        requester_user_id=req.requester_user_id,
        requester_email=req.requester.email if req.requester else None,
        requester_display_name=req.requester.display_name if req.requester else None,
        approver_user_id=req.approver_user_id,
        approver_email=req.approver.email if req.approver else None,
        approver_display_name=req.approver.display_name if req.approver else None,
        request_type=req.request_type,
        target_entity_type=req.target_entity_type,
        target_entity_id=req.target_entity_id,
        status=req.status,
        execution_status=req.execution_status,
        justification=req.justification,
        expires_at=req.expires_at,
        decided_at=req.decided_at,
        created_at=req.created_at,
        updated_at=req.updated_at,
        payload_snapshot=req.payload_snapshot or {},
        decision_reason=req.decision_reason,
        execution_started_at=req.execution_started_at,
        execution_completed_at=req.execution_completed_at,
        execution_error=req.execution_error,
        execution_details_json=req.execution_details_json,
        parent_request_id=req.parent_request_id,
        clarifications=clarifications,
    )


@router.get(
    "",
    response_model=ApprovalRequestsListResponse,
    summary="List approval requests",
    description="Returns a paginated list of approval requests filtered by status, request_type, or business. Visibility is governed by the caller's platform role.",
)
def list_approvals_endpoint(
    status: Optional[str] = Query(None, description="Filter by approval status (e.g. pending, approved, rejected, etc.)"),
    request_type: Optional[str] = Query(None, description="Filter by request type"),
    business_id: Optional[uuid.UUID] = Query(None, description="Filter by business ID"),
    limit: int = Query(50, ge=1, le=100, description="Page size limit (1-100)"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(RequirePlatformRole(["owner", "admin", "operator"])),
    db: Session = Depends(get_db),
) -> ApprovalRequestsListResponse:
    result = list_approval_requests(
        db=db,
        caller=current_user,
        status=status,
        request_type=request_type,
        business_id=business_id,
        limit=limit,
        offset=offset,
    )

    items = [_serialize_request_item(req) for req in result["items"]]
    return ApprovalRequestsListResponse(
        items=items,
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


@router.get(
    "/{request_id}",
    response_model=ApprovalRequestDetailOut,
    summary="Get approval request details",
    description="Retrieves complete sanitized details of an approval request, including payload snapshot and clarification timeline. Fails closed with 404 if not found or unauthorized.",
)
def get_approval_endpoint(
    request_id: uuid.UUID = Path(..., description="UUID of the approval request"),
    current_user: User = Depends(RequirePlatformRole(["owner", "admin", "operator"])),
    db: Session = Depends(get_db),
) -> ApprovalRequestDetailOut:
    req = get_approval_request(
        db=db,
        caller=current_user,
        request_id=request_id,
    )
    return _serialize_request_detail(req)


@router.post(
    "/{request_id}/decide",
    response_model=ApprovalRequestDetailOut,
    summary="Decide an approval request (approve or reject)",
    description="Submits an approval or rejection decision. Enforces four-eyes governance, target role revalidation, and rejection reasons. Auto-executes approved requests through the centralized execution boundary.",
)
def decide_approval_endpoint(
    request_id: uuid.UUID = Path(..., description="UUID of the approval request to decide"),
    body: ApprovalDecisionRequest = ...,
    current_user: User = Depends(RequirePlatformRole(["owner", "admin"])),
    db: Session = Depends(get_db),
) -> ApprovalRequestDetailOut:
    decided_req = decide_approval_request(
        db=db,
        request_id=request_id,
        approver=current_user,
        decision=body.decision,
        reason=body.reason,
        auto_execute=True,
    )
    return _serialize_request_detail(decided_req)

