"""Approval workflow core service and state machine.

Manages the lifecycle of approval requests:
- Submission & validation
- Approval & Rejection (with non-empty reason)
- Withdrawal (by requester only)
- Clarification requests & responses
- Expiry after 14 days
- Integration with execution service
"""
import uuid
from datetime import timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.base import utc_now
from app.modules.subscriptions.service import ensure_utc
from app.modules.approvals.models import (
    ApprovalRequest,
    ApprovalClarification,
    ApprovalStatus,
    ExecutionStatus,
)
from app.modules.approvals.sanitization import (
    validate_and_sanitize_payload,
    contains_forbidden_keys,
)
from app.modules.approvals.policies import (
    get_effective_platform_role,
    check_can_create_request,
    check_approver_eligibility,
)
from app.modules.approvals.execution import execute_approval_request
from app.modules.audit.service import log_audit
from app.core.errors import (
    ValidationError,
    NotFoundError,
    ForbiddenError,
)
from app.modules.staff.models import User


def _lock_approval_request(db: Session, request_id: uuid.UUID) -> Optional[ApprovalRequest]:
    """
    Acquires row-level pessimistic lock on PostgreSQL dialect, ordinary query on SQLite.
    """
    if db.bind and db.bind.dialect.name == "postgresql":
        return db.query(ApprovalRequest).with_for_update().filter(ApprovalRequest.id == request_id).first()
    return db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()


def create_approval_request(
    db: Session,
    requester: User,
    request_type: str,
    target_entity_type: str,
    payload: Dict[str, Any],
    justification: Optional[str] = None,
    target_entity_id: Optional[uuid.UUID] = None,
    business_id: Optional[uuid.UUID] = None,
    outlet_id: Optional[uuid.UUID] = None,
    parent_request_id: Optional[uuid.UUID] = None,
    idempotency_key: Optional[str] = None,
) -> ApprovalRequest:
    """
    Creates and persists a new approval request in 'pending' status with 'not_started' execution.
    Enforces payload allowlist, sensitive-data scrub, and authorization rules.
    """
    check_can_create_request(requester, request_type, payload)

    # Sanitize and validate payload snapshot
    sanitized_payload = validate_and_sanitize_payload(request_type, payload)

    now = utc_now()
    expires_at = now + timedelta(days=14)

    # Check idempotency key if supplied
    if idempotency_key:
        existing = (
            db.query(ApprovalRequest)
            .filter(ApprovalRequest.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing

    req = ApprovalRequest(
        business_id=business_id,
        outlet_id=outlet_id,
        requester_user_id=requester.id,
        request_type=request_type,
        target_entity_type=target_entity_type,
        target_entity_id=target_entity_id,
        status=ApprovalStatus.PENDING,
        execution_status=ExecutionStatus.NOT_STARTED,
        payload_snapshot=sanitized_payload,
        justification=justification.strip() if justification else None,
        expires_at=expires_at,
        parent_request_id=parent_request_id,
        idempotency_key=idempotency_key,
    )
    db.add(req)
    db.flush()

    # Durable audit record
    log_audit(
        db=db,
        business_id=business_id,
        outlet_id=outlet_id,
        actor_user_id=requester.id,
        action="approval.request.create",
        entity_type="approval_request",
        entity_id=req.id,
        metadata_json={
            "outcome": "success",
            "request_type": request_type,
            "target_entity_type": target_entity_type,
            "expires_at": expires_at.isoformat(),
        },
    )
    db.commit()
    db.refresh(req)
    return req


def decide_approval_request(
    db: Session,
    request_id: uuid.UUID,
    approver: User,
    decision: str,  # 'approve' or 'reject'
    reason: str,
    auto_execute: bool = True,
) -> ApprovalRequest:
    """
    Decides a pending or needs_information approval request.
    - Locks row with SELECT ... FOR UPDATE on PostgreSQL.
    - Verifies non-empty reason.
    - Validates 14-day expiry.
    - Checks approver authority and self-approval constraints.
    - Updates status to 'approved' or 'rejected'.
    - If approved and auto_execute=True, triggers domain execution.
    """
    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise ValidationError("A non-empty reason is required to decide an approval request.")

    if decision not in ("approve", "reject"):
        raise ValidationError(f"Invalid decision '{decision}'. Must be 'approve' or 'reject'.")

    req = _lock_approval_request(db, request_id)
    if not req:
        raise NotFoundError(f"Approval request '{request_id}' not found.")

    now = utc_now()

    # Check 14-day expiry
    if req.expires_at and now >= ensure_utc(req.expires_at):
        req.status = ApprovalStatus.EXPIRED
        db.commit()
        raise ValidationError("This approval request has expired and can no longer be decided.")

    # State validation
    if req.status not in (ApprovalStatus.PENDING, ApprovalStatus.NEEDS_INFORMATION):
        raise ValidationError(
            f"Cannot decide approval request with status '{req.status}'. Only pending or needs_information requests can be decided."
        )

    # Authority and self-approval validation
    check_approver_eligibility(db, approver, req)

    # Apply decision
    target_status = ApprovalStatus.APPROVED if decision == "approve" else ApprovalStatus.REJECTED
    req.status = target_status
    req.approver_user_id = approver.id
    req.decided_at = now
    req.decision_reason = clean_reason
    db.flush()

    # Audit log entry
    log_audit(
        db=db,
        business_id=req.business_id,
        outlet_id=req.outlet_id,
        actor_user_id=approver.id,
        action=f"approval.request.{decision}",
        entity_type="approval_request",
        entity_id=req.id,
        metadata_json={
            "outcome": "success",
            "decision": decision,
            "reason": clean_reason,
            "request_type": req.request_type,
        },
    )
    db.commit()
    db.refresh(req)

    # If approved and auto_execute requested, run execution engine
    if target_status == ApprovalStatus.APPROVED and auto_execute:
        # Owner-only execution enforcement: if approved by an Admin, bypass auto-execution
        owner_only_types = {
            "user_reactivation",
            "entitlement_override",
        }
        approver_role = get_effective_platform_role(approver)
        is_owner_only = req.request_type in owner_only_types

        if req.request_type == "user_suspension":
            payload = req.payload_snapshot or {}
            target_uid = payload.get("target_user_id") or payload.get("user_id")
            target_user = None
            if target_uid:
                try:
                    target_user = db.query(User).filter(User.id == uuid.UUID(str(target_uid))).first()
                except (ValueError, TypeError):
                    pass
            target_role = get_effective_platform_role(target_user) if target_user else None
            is_target_privileged = (target_user.is_platform_admin or target_role in ("admin", "owner")) if target_user else False
            if is_target_privileged:
                is_owner_only = True

        if req.request_type == "user_role_change":
            payload = req.payload_snapshot or {}
            new_role = payload.get("new_platform_role")
            target_uid = payload.get("target_user_id") or payload.get("user_id")
            target_user = None
            if target_uid:
                try:
                    target_user = db.query(User).filter(User.id == uuid.UUID(str(target_uid))).first()
                except (ValueError, TypeError):
                    pass
            target_role = get_effective_platform_role(target_user) if target_user else None
            is_target_privileged = (target_user.is_platform_admin or target_role in ("admin", "owner")) if target_user else False
            # Promoting an existing Operator to Admin is permitted for Admin auto-execution.
            # Modifying an existing Admin/Owner or promoting a non-operator requires Owner execution.
            if is_target_privileged or (new_role == "admin" and target_role != "operator"):
                is_owner_only = True

        if is_owner_only and approver_role != "owner":
            req.execution_details_json = {"note": "Awaiting Platform Owner execution."}
            db.commit()
            db.refresh(req)
            return req

        return execute_approval_request(db=db, request_id=req.id, actor_user_id=approver.id)

    return req


def withdraw_approval_request(
    db: Session,
    request_id: uuid.UUID,
    actor: User,
    reason: Optional[str] = None,
) -> ApprovalRequest:
    """
    Withdraws a pending approval request.
    Strictly restricted to the original requester.
    """
    req = _lock_approval_request(db, request_id)
    if not req:
        raise NotFoundError(f"Approval request '{request_id}' not found.")

    if req.requester_user_id != actor.id:
        raise ForbiddenError("Only the original requester can withdraw an approval request.")

    if req.status not in (ApprovalStatus.PENDING, ApprovalStatus.NEEDS_INFORMATION):
        raise ValidationError(
            f"Cannot withdraw approval request with status '{req.status}'. Only pending requests can be withdrawn."
        )

    req.status = ApprovalStatus.WITHDRAWN
    req.decision_reason = reason.strip() if reason else "Withdrawn by requester"
    req.decided_at = utc_now()
    db.flush()

    log_audit(
        db=db,
        business_id=req.business_id,
        outlet_id=req.outlet_id,
        actor_user_id=actor.id,
        action="approval.request.withdraw",
        entity_type="approval_request",
        entity_id=req.id,
        metadata_json={
            "outcome": "success",
            "reason": req.decision_reason,
        },
    )
    db.commit()
    db.refresh(req)
    return req


def add_request_clarification(
    db: Session,
    request_id: uuid.UUID,
    actor: User,
    clarification_type: str,  # 'question', 'response', 'note'
    message: str,
) -> ApprovalClarification:
    """
    Appends an immutable clarification note or question to an active request.
    If an approver asks a question, updates request status to 'needs_information'.
    """
    clean_msg = (message or "").strip()
    if not clean_msg:
        raise ValidationError("Clarification message cannot be empty.")

    if clarification_type not in ("question", "response", "note"):
        raise ValidationError(f"Invalid clarification_type '{clarification_type}'.")

    req = _lock_approval_request(db, request_id)
    if not req:
        raise NotFoundError(f"Approval request '{request_id}' not found.")

    if req.status in ApprovalStatus.TERMINAL_STATUSES:
        raise ValidationError(f"Cannot add clarification to terminal approval request with status '{req.status}'.")

    role = get_effective_platform_role(actor)
    is_requester = (actor.id == req.requester_user_id)
    is_admin_or_owner = role in ("owner", "admin")

    if not is_requester and not is_admin_or_owner:
        raise ForbiddenError("You are not authorized to participate in this approval clarification thread.")

    # Status transition to needs_information if question asked
    if clarification_type == "question":
        if not is_admin_or_owner:
            raise ForbiddenError("Only platform administrators or owners can request clarification questions.")
        req.status = ApprovalStatus.NEEDS_INFORMATION

    clarification = ApprovalClarification(
        approval_request_id=req.id,
        author_user_id=actor.id,
        clarification_type=clarification_type,
        message=clean_msg,
    )
    db.add(clarification)
    db.flush()

    log_audit(
        db=db,
        business_id=req.business_id,
        outlet_id=req.outlet_id,
        actor_user_id=actor.id,
        action=f"approval.clarification.{clarification_type}",
        entity_type="approval_request",
        entity_id=req.id,
        metadata_json={
            "outcome": "success",
            "clarification_id": str(clarification.id),
            "clarification_type": clarification_type,
        },
    )
    db.commit()
    db.refresh(clarification)
    return clarification


def check_and_expire_requests(db: Session) -> int:
    """
    Batch utility checking and transitioning pending requests that exceeded the 14-day SLA deadline.
    Returns the count of expired requests.
    """
    now = utc_now()
    pending_expired = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.status.in_([ApprovalStatus.PENDING, ApprovalStatus.NEEDS_INFORMATION]),
            ApprovalRequest.expires_at <= now,
        )
        .all()
    )

    count = 0
    for req in pending_expired:
        req.status = ApprovalStatus.EXPIRED
        log_audit(
            db=db,
            business_id=req.business_id,
            outlet_id=req.outlet_id,
            actor_user_id=None,
            action="approval.request.expired",
            entity_type="approval_request",
            entity_id=req.id,
            metadata_json={"outcome": "expired", "expired_at": now.isoformat()},
        )
        count += 1

    if count > 0:
        db.commit()

    return count


def _is_request_visible_to_role(req: ApprovalRequest, role: str, actor_id: uuid.UUID) -> bool:
    """
    Evaluates whether an approval request is visible to the given platform actor.
    - Owner: Visible (full platform governance visibility).
    - Admin: Visible if not targeting Platform Owner privileges.
    - Operator: Visible only if created by the operator or relevant to ordinary tenant operations
      (business_creation, outlet_creation, subscription_change).
    """
    if role == "owner":
        return True

    # Check target entity sensitivity for Admins
    if role == "admin":
        # Sensitive Platform Owner transitions or actions are strictly Owner-visible
        if req.request_type in ("user_role_change", "operator_creation"):
            payload = req.payload_snapshot or {}
            new_role = payload.get("new_platform_role")
            if new_role == "owner":
                return False
        return True

    if role == "operator":
        # Operators see requests they submitted
        if req.requester_user_id == actor_id:
            return True
        # Or ordinary tenant operational requests
        if req.request_type in ("business_creation", "outlet_creation", "subscription_change"):
            return True
        return False

    return False


def list_approval_requests(
    db: Session,
    caller: User,
    status: Optional[str] = None,
    request_type: Optional[str] = None,
    business_id: Optional[uuid.UUID] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Queries approval requests with pagination, filtering, and role-based visibility.
    Fails closed if caller is not an active Platform role.
    """
    role = get_effective_platform_role(caller)
    if not role or role not in ("owner", "admin", "operator"):
        raise ForbiddenError("Platform privileges are required to view approval requests.")

    query = db.query(ApprovalRequest)

    # Role visibility filtering
    if role == "operator":
        query = query.filter(
            (ApprovalRequest.requester_user_id == caller.id) |
            (ApprovalRequest.request_type.in_(["business_creation", "outlet_creation", "subscription_change"]))
        )
    elif role == "admin":
        # Admins see all requests except Owner-targeted role changes/transfers
        pass

    # Parameter filters
    if status:
        status_clean = status.strip().lower()
        if status_clean not in ApprovalStatus.ALL_STATUSES:
            raise ValidationError(f"Invalid status filter '{status}'. Valid statuses: {sorted(ApprovalStatus.ALL_STATUSES)}")
        query = query.filter(ApprovalRequest.status == status_clean)

    if request_type:
        request_type_clean = request_type.strip().lower()
        query = query.filter(ApprovalRequest.request_type == request_type_clean)

    if business_id:
        query = query.filter(ApprovalRequest.business_id == business_id)

    total = query.count()

    # Stable, deterministic ordering (descending created_at, tie-break on id)
    items = (
        query.order_by(ApprovalRequest.created_at.desc(), ApprovalRequest.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_approval_request(
    db: Session,
    caller: User,
    request_id: uuid.UUID,
) -> ApprovalRequest:
    """
    Retrieves a single approval request by ID with role-based visibility enforcement.
    Fails closed with NotFoundError if request does not exist or caller is not authorized to view it.
    """
    role = get_effective_platform_role(caller)
    if not role or role not in ("owner", "admin", "operator"):
        raise ForbiddenError("Platform privileges are required to view approval requests.")

    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not req:
        raise NotFoundError("Approval request not found.")

    if not _is_request_visible_to_role(req, role, caller.id):
        # Do not leak existence to unauthorized caller
        raise NotFoundError("Approval request not found.")

    return req

