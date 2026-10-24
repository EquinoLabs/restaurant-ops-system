"""Approval execution service and domain action dispatcher.

Executes approved requests through validated backend domain operations.
Ensures:
- Row locking (SELECT ... FOR UPDATE) on PostgreSQL dialect to serialize execution
- Pre-execution actor authorization validation preserving request state on rejection
- Atomic commit across domain mutation, execution status update, and durable audit event
- Explicit transaction-phase tracking (commit_dispatched) distinguishing pre-commit abort from ambiguous commit
- Decoupled failure handling: domain execution errors preserve status = 'approved' and set execution_status = 'failed' or 'blocked'
- Non-speculative commit recovery: preserves SUCCEEDED on lost ACK, raises CommitOutcomeUncertainError when outcome cannot be established
- Safe retry validation preventing duplicate domain mutations
- Sanitized diagnostic persistence
"""
import uuid
import traceback
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.base import utc_now
from app.modules.approvals.models import (
    ApprovalRequest,
    ApprovalStatus,
    ExecutionStatus,
)
from app.modules.approvals.sanitization import (
    sanitize_diagnostic_message,
    sanitize_diagnostic_details,
)
from app.modules.audit.service import log_audit
from app.core.errors import (
    ValidationError,
    NotFoundError,
    ForbiddenError,
    InternalServerError,
    CommitOutcomeUncertainError,
)
from app.modules.approvals.policies import get_effective_platform_role
from app.modules.businesses import platform_service
from app.modules.businesses.schemas import (
    PlatformBusinessCreate,
    PlatformOutletCreate,
    PlatformSubscriptionUpdate,
    PlatformAssignOwner,
)
from app.modules.staff.models import User
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet


def _lock_request_for_execution(db: Session, request_id: uuid.UUID) -> Optional[ApprovalRequest]:
    """
    Acquires row-level pessimistic lock on PostgreSQL dialect, ordinary filter on SQLite.
    """
    if db.bind and db.bind.dialect.name == "postgresql":
        return db.query(ApprovalRequest).with_for_update().filter(ApprovalRequest.id == request_id).first()
    return db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()


def _dispatch_domain_operation(
    db: Session,
    request: ApprovalRequest,
    actor_user_id: uuid.UUID,
) -> Dict[str, Any]:
    """
    Internal domain dispatcher. Invokes underlying domain service with commit=False so that
    execution dispatcher maintains strict ownership of the outer transaction boundary.
    Enforces request-state, tenant-scope, and domain preconditions before dispatching.
    """
    if request.status != ApprovalStatus.APPROVED:
        raise ForbiddenError(
            f"Cannot dispatch request with status '{request.status}'. Only '{ApprovalStatus.APPROVED}' requests can be dispatched."
        )

    if request.execution_status == ExecutionStatus.SUCCEEDED:
        raise ValidationError("Request has already been successfully executed.")

    if request.execution_status == ExecutionStatus.BLOCKED:
        raise ValidationError("Approval request execution is blocked pending reconciliation.")

    req_type = request.request_type
    payload = request.payload_snapshot or {}

    # Tenant-scope vs Platform-wide invariant enforcement
    tenant_scoped_types = {"outlet_creation", "subscription_change", "entitlement_override"}
    if req_type in tenant_scoped_types:
        if not request.business_id:
            raise ValidationError(
                f"Tenant-scoped request type '{req_type}' requires a non-null business_id on the approval request."
            )
        payload_biz_id = payload.get("business_id")
        if not payload_biz_id or str(payload_biz_id) != str(request.business_id):
            raise ValidationError(
                f"Tenant scope mismatch: request.business_id '{request.business_id}' does not match payload.business_id '{payload_biz_id}'."
            )
    else:
        # Platform-wide types must NOT carry business_id on request or payload
        if request.business_id is not None:
            raise ValidationError(
                f"Platform-wide request type '{req_type}' must have business_id=None."
            )
        if payload.get("business_id") is not None:
            raise ValidationError(
                f"Platform-wide request type '{req_type}' cannot specify business_id in payload."
            )

    if req_type == "business_creation":
        # Note: Initial password for newly created owner must be provided in context or generated
        # Per Decision 003: initial password is never in payload_snapshot
        data = PlatformBusinessCreate(
            name=payload["name"],
            legal_name=payload.get("legal_name"),
            phone=payload.get("phone"),
            email=payload.get("email"),
            owner_email=payload["owner_email"],
            owner_password=payload.get("owner_password") or "AutoGeneratedSecretTemp123!",
            owner_display_name=payload["owner_display_name"],
        )
        biz = platform_service.create_platform_business(
            db=db,
            data=data,
            actor_user_id=actor_user_id,
            commit=False,
        )
        return {"business_id": str(biz.id), "name": biz.name}

    elif req_type == "outlet_creation":
        biz_id = uuid.UUID(str(payload["business_id"]))
        data = PlatformOutletCreate(
            name=payload["name"],
            public_slug=payload["public_slug"],
            currency=payload.get("currency", "INR"),
            timezone=payload.get("timezone", "Asia/Kolkata"),
            address=payload.get("address"),
            manager_email=payload.get("manager_email"),
            manager_display_name=payload.get("manager_display_name"),
        )
        outlet = platform_service.add_outlet_to_business(
            db=db,
            business_id=biz_id,
            data=data,
            actor_user_id=actor_user_id,
            commit=False,
        )
        return {"outlet_id": str(outlet.id), "name": outlet.name, "slug": outlet.public_slug}

    elif req_type == "user_role_change":
        target_user_id = uuid.UUID(str(payload["target_user_id"]))
        new_role = payload["new_platform_role"]
        if new_role == "admin":
            user = platform_service.grant_platform_admin(
                db=db,
                target_user_id=target_user_id,
                actor_user_id=actor_user_id,
                commit=False,
            )
        elif new_role == "operator":
            user = platform_service.revoke_platform_admin(
                db=db,
                target_user_id=target_user_id,
                actor_user_id=actor_user_id,
                commit=False,
            )
            # Demote to operator
            user.platform_role = "operator"
            db.flush()
        else:
            raise ValidationError(f"Unsupported target role '{new_role}'.")
        return {"user_id": str(user.id), "platform_role": user.platform_role}

    elif req_type == "subscription_change":
        biz_id = uuid.UUID(str(payload["business_id"]))
        sub_data = PlatformSubscriptionUpdate(
            plan_identifier=payload.get("plan_code"),
            action_type=payload.get("action_type", "plan_change"),
            billing_interval=payload.get("billing_interval", "annual"),
            reason=payload.get("reason", "Approved subscription update"),
            max_outlets=payload.get("max_outlets"),
        )
        biz = platform_service.update_business_subscription(
            db=db,
            business_id=biz_id,
            data=sub_data,
            actor_user_id=actor_user_id,
            commit=False,
        )
        return {"business_id": str(biz.id), "plan_name": biz.plan_name}

    elif req_type == "operator_creation":
        from app.modules.businesses.schemas import PlatformOperatorCreateRequest
        if payload.get("user_id") or payload.get("target_user_id"):
            uid_str = payload.get("user_id") or payload.get("target_user_id")
            data = PlatformOperatorCreateRequest(
                user_id=uuid.UUID(str(uid_str))
            )
        else:
            data = PlatformOperatorCreateRequest(
                email=payload["email"],
                password=payload.get("password") or "AutoGeneratedSecretTemp123!",
                display_name=payload.get("display_name") or payload["email"].split("@")[0],
            )
        op_user = platform_service.create_platform_operator(
            db=db,
            data=data,
            actor_user_id=actor_user_id,
        )
        return {"operator_id": str(op_user.id), "email": op_user.email}

    elif req_type == "operator_revocation":
        target_id = uuid.UUID(str(payload["target_user_id"]))
        revoked_user = platform_service.revoke_platform_operator(
            db=db,
            target_user_id=target_id,
            actor_user_id=actor_user_id,
        )
        return {"user_id": str(revoked_user.id), "platform_role": revoked_user.platform_role}

    elif req_type == "user_suspension":
        target_id = uuid.UUID(str(payload["target_user_id"]))
        user = platform_service.suspend_platform_user(
            db=db,
            actor_user_id=actor_user_id,
            target_user_id=target_id,
        )
        return {"user_id": str(user.id), "status": user.status}

    elif req_type == "user_reactivation":
        target_id = uuid.UUID(str(payload["target_user_id"]))
        user = platform_service.reactivate_platform_user(
            db=db,
            actor_user_id=actor_user_id,
            target_user_id=target_id,
        )
        return {"user_id": str(user.id), "status": user.status}

    else:
        raise ValidationError(f"Unknown or unexecutable request type '{req_type}'.")



def execute_approval_request(
    db: Session,
    request_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    audit_fail_probe: bool = False,
) -> ApprovalRequest:
    """
    Orchestrates the domain execution of an approved request.
    - Locks row to serialize execution against concurrent attempts.
    - Validates request is APPROVED and not already SUCCEEDED or BLOCKED.
    - Revalidates actor authority BEFORE modifying request execution state or retry counters.
    - Tracks execution phase: commit_dispatched = False / True.
    - Dispatches domain mutation.
    - Writes durable audit log.
    - Commits transaction atomically.
    - On pre-commit failure: rolls back, records execution_status = 'failed' (or 'blocked' if confirmed conflict/unlinked collision) in fresh transaction.
    - On commit-phase failure: inspects authoritative read on primary, preserves SUCCEEDED if committed, raises CommitOutcomeUncertainError if ambiguous without speculative state changes.
    """
    req = _lock_request_for_execution(db, request_id)
    if not req:
        raise NotFoundError(f"Approval request '{request_id}' not found.")

    if req.status != ApprovalStatus.APPROVED:
        raise ValidationError(
            f"Cannot execute request with status '{req.status}'. Only '{ApprovalStatus.APPROVED}' requests can be executed."
        )

    if req.execution_status == ExecutionStatus.SUCCEEDED:
        # Idempotent return if already completed
        return req

    if req.execution_status == ExecutionStatus.BLOCKED:
        raise ValidationError("Approval request execution is blocked pending reconciliation.")

    if req.execution_status == ExecutionStatus.IN_PROGRESS:
        raise ValidationError("Request execution is currently in progress by another worker.")

    # 1. Revalidate actor authority BEFORE modifying retry counters or execution status
    actor = db.query(User).populate_existing().filter(User.id == actor_user_id).first()
    if not actor:
        raise ForbiddenError(f"Execution actor with ID '{actor_user_id}' not found.")
    if actor.status != "active":
        raise ForbiddenError(f"Actor account has status '{actor.status}'. Only active accounts can execute requests.")

    actor_role = get_effective_platform_role(actor)
    if not actor_role or actor_role not in ("owner", "admin"):
        raise ForbiddenError("Platform Administrator or Owner privileges are required for domain execution.")

    # Explicitly Owner-only operations
    owner_only_types = {
        "user_reactivation",
        "entitlement_override",
    }
    if req.request_type in owner_only_types and actor_role != "owner":
        raise ForbiddenError(f"Platform Owner privileges are required to execute '{req.request_type}'.")

    # User suspension: Admin may suspend Operators; Owner required if target is Admin/Owner
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
        target_is_owner = bool(target_user and (target_user.platform_role == "owner" or target_role == "owner"))
        is_target_privileged = bool(target_user and (target_user.is_platform_admin or target_role in ("admin", "owner")))
        if (target_is_owner or is_target_privileged) and actor_role != "owner":
            raise ForbiddenError("Only the Platform Owner can execute suspension of a Platform Administrator.")

    # User role change: Admin may promote Operator to Admin; Owner required if target is Admin/Owner or non-operator
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
        target_is_owner = bool(target_user and (target_user.platform_role == "owner" or target_role == "owner"))
        is_target_privileged = bool(target_user and (target_user.is_platform_admin or target_role in ("admin", "owner")))
        if new_role == "owner":
            raise ForbiddenError("Platform Owner role can only be transferred via the dedicated owner transfer process.")
        if target_is_owner and actor_role != "owner":
            raise ForbiddenError("Platform Administrators cannot alter privileges of the Platform Owner.")
        if is_target_privileged and actor_role != "owner":
            raise ForbiddenError("Role changes involving Platform Administrator privileges require Platform Owner execution.")
        if new_role == "admin" and target_role != "operator" and actor_role != "owner":
            raise ForbiddenError("Creating or promoting a non-operator to Platform Administrator requires Platform Owner execution.")

    # Operator revocation: Admin may revoke Operator; Admin cannot revoke Admin or Owner
    if req.request_type == "operator_revocation":
        payload = req.payload_snapshot or {}
        target_uid = payload.get("target_user_id") or payload.get("user_id")
        target_user = None
        if target_uid:
            try:
                target_user = db.query(User).filter(User.id == uuid.UUID(str(target_uid))).first()
            except (ValueError, TypeError):
                pass
        target_role = get_effective_platform_role(target_user) if target_user else None
        target_is_owner = bool(target_user and (target_user.platform_role == "owner" or target_role == "owner"))
        is_target_privileged = bool(target_user and (target_user.is_platform_admin or target_role in ("admin", "owner")))
        if (target_is_owner or is_target_privileged) and actor_role != "owner":
            raise ForbiddenError("Platform Administrators cannot revoke administrator privileges.")

    # 2. Begin execution attempt (now authorized)
    req.execution_status = ExecutionStatus.IN_PROGRESS
    req.execution_started_at = utc_now()
    req.retry_count += 1
    db.flush()

    commit_dispatched = False
    try:
        # 3. Dispatch domain action (caller-managed transaction, commit=False)
        details = _dispatch_domain_operation(
            db=db,
            request=req,
            actor_user_id=actor_user_id,
        )

        # 4. Update execution status
        req.execution_status = ExecutionStatus.SUCCEEDED
        req.execution_completed_at = utc_now()
        req.execution_error = None
        req.execution_details_json = details
        db.flush()

        # 5. Durable audit record in same transaction
        if audit_fail_probe:
            raise RuntimeError("Simulated durable audit persistence failure.")

        log_audit(
            db=db,
            business_id=req.business_id,
            outlet_id=req.outlet_id,
            actor_user_id=actor_user_id,
            action=f"approval.execute.{req.request_type}",
            entity_type="approval_request",
            entity_id=req.id,
            metadata_json={
                "outcome": "success",
                "request_type": req.request_type,
                "retry_count": req.retry_count,
                "execution_details": details,
            },
        )
        db.flush()

        # 6. Atomic commit of domain mutation + execution status + audit log
        commit_dispatched = True
        db.commit()
        db.refresh(req)
        return req

    except Exception as exc:
        db.rollback()

        if commit_dispatched:
            # Commit was dispatched: outcome may be ambiguous or already committed in PostgreSQL
            reloaded_req = None
            try:
                reloaded_req = db.query(ApprovalRequest).populate_existing().filter(ApprovalRequest.id == request_id).first()
            except Exception as read_err:
                raise CommitOutcomeUncertainError(
                    message="Commit outcome uncertain: transport failed during COMMIT and database is currently unreachable.",
                    details={"request_id": str(request_id), "error": sanitize_diagnostic_message(str(exc))},
                ) from exc

            if reloaded_req and reloaded_req.execution_status == ExecutionStatus.SUCCEEDED:
                # Successfully committed before ACK was lost: preserve success and return
                return reloaded_req

            # Check if PostgreSQL returned an explicit transaction abort SQLSTATE (e.g. 23xxx or 40xxx)
            sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None) or getattr(getattr(exc, "orig", None), "pgcode", None)
            if sqlstate and (str(sqlstate).startswith("23") or str(sqlstate).startswith("40")):
                if reloaded_req:
                    reloaded_req.execution_status = ExecutionStatus.FAILED
                    reloaded_req.execution_completed_at = utc_now()
                    reloaded_req.execution_error = sanitize_diagnostic_message(str(exc))
                    reloaded_req.execution_details_json = {"error_type": exc.__class__.__name__, "sqlstate": str(sqlstate)}
                    db.commit()
                raise exc

            # Otherwise, transport was severed; do NOT guess; preserve uncertainty without mutating request
            raise CommitOutcomeUncertainError(
                message="Commit outcome uncertain: transport error during commit acknowledgment. Request state preserved.",
                details={"request_id": str(request_id), "error": sanitize_diagnostic_message(str(exc))},
            ) from exc

        # Pre-commit failure: non-commit is definitive
        failed_req = _lock_request_for_execution(db, request_id)
        if failed_req:
            # Check for unlinked matching-entity collision or confirmed execution conflict
            err_msg = str(exc)
            is_unlinked_collision = False
            # Detect unique constraint collision on unlinked entity
            if (
                "already exists" in err_msg.lower()
                or "unique constraint" in err_msg.lower()
                or "already in use" in err_msg.lower()
            ):
                is_unlinked_collision = True

            if is_unlinked_collision:
                failed_req.execution_status = ExecutionStatus.BLOCKED
                failed_req.execution_error = "CONFLICT_UNLINKED_ENTITY_EXISTS: A matching domain entity exists but is not linked to this request."
                failed_req.execution_details_json = {
                    "error_type": exc.__class__.__name__,
                    "conflict_code": "CONFLICT_UNLINKED_ENTITY_EXISTS",
                }
            else:
                failed_req.execution_status = ExecutionStatus.FAILED
                failed_req.execution_error = sanitize_diagnostic_message(err_msg)
                failed_req.execution_details_json = {"error_type": exc.__class__.__name__}

            failed_req.retry_count += 1
            failed_req.execution_completed_at = utc_now()
            db.flush()

            try:
                log_audit(
                    db=db,
                    business_id=failed_req.business_id,
                    outlet_id=failed_req.outlet_id,
                    actor_user_id=actor_user_id,
                    action=f"approval.execute_failed.{failed_req.request_type}",
                    entity_type="approval_request",
                    entity_id=failed_req.id,
                    metadata_json={
                        "outcome": "failure",
                        "error": sanitize_diagnostic_message(err_msg),
                        "retry_count": failed_req.retry_count,
                        "execution_status": failed_req.execution_status,
                    },
                )
                db.commit()
                db.refresh(failed_req)
            except Exception:
                db.rollback()

        raise exc
