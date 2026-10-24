import uuid
from datetime import timedelta
from unittest.mock import patch
import pytest
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.exc import OperationalError

from app.db.base import utc_now
from app.modules.approvals.models import (
    ApprovalRequest,
    ApprovalClarification,
    ApprovalStatus,
    ExecutionStatus,
)
from app.modules.approvals.service import (
    create_approval_request,
    decide_approval_request,
    withdraw_approval_request,
    add_request_clarification,
    check_and_expire_requests,
)
from app.modules.approvals.execution import execute_approval_request
from app.modules.staff.models import User
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.audit.models import AuditLog
from app.core.errors import (
    ValidationError,
    ForbiddenError,
    NotFoundError,
    CommitOutcomeUncertainError,
)


@pytest.fixture
def test_users(db_session: Session):
    owner = User(
        email="owner_actor@test.com",
        password_hash="dummyhash",
        display_name="Platform Owner",
        status="active",
        platform_role="owner",
        is_platform_admin=True,
    )
    admin1 = User(
        email="admin_actor1@test.com",
        password_hash="dummyhash",
        display_name="Admin One",
        status="active",
        platform_role="admin",
        is_platform_admin=True,
    )
    admin2 = User(
        email="admin_actor2@test.com",
        password_hash="dummyhash",
        display_name="Admin Two",
        status="active",
        platform_role="admin",
        is_platform_admin=True,
    )
    operator = User(
        email="operator_actor@test.com",
        password_hash="dummyhash",
        display_name="Operator User",
        status="active",
        platform_role="operator",
        is_platform_admin=False,
    )
    db_session.add_all([owner, admin1, admin2, operator])
    db_session.commit()
    return {"owner": owner, "admin1": admin1, "admin2": admin2, "operator": operator}


def test_create_approval_request_lifecycle(db_session: Session, test_users):
    op = test_users["operator"]
    payload = {
        "business_id": str(uuid.uuid4()),
        "name": "New Outlet Alpha",
        "public_slug": "new-outlet-alpha",
        "currency": "INR",
        "timezone": "Asia/Kolkata",
    }
    req = create_approval_request(
        db=db_session,
        requester=op,
        request_type="outlet_creation",
        target_entity_type="outlet",
        payload=payload,
        justification="Expanding to new market",
        idempotency_key="idemp_outlet_alpha",
    )
    assert req.id is not None
    assert req.status == ApprovalStatus.PENDING
    assert req.execution_status == ExecutionStatus.NOT_STARTED
    assert req.requester_user_id == op.id
    assert req.payload_snapshot["name"] == "New Outlet Alpha"

    # Verify idempotency key returns exact same record
    dup_req = create_approval_request(
        db=db_session,
        requester=op,
        request_type="outlet_creation",
        target_entity_type="outlet",
        payload=payload,
        idempotency_key="idemp_outlet_alpha",
    )
    assert dup_req.id == req.id


def test_approval_decision_requires_non_empty_reason(db_session: Session, test_users):
    op = test_users["operator"]
    admin = test_users["admin1"]
    req = create_approval_request(
        db=db_session,
        requester=op,
        request_type="outlet_creation",
        target_entity_type="outlet",
        payload={"name": "Reason Test", "public_slug": "reason-test", "business_id": str(uuid.uuid4())},
    )
    with pytest.raises(ValidationError, match="non-empty reason is required"):
        decide_approval_request(db=db_session, request_id=req.id, approver=admin, decision="approve", reason="  ")


def test_prohibited_self_approval_and_owner_exception(db_session: Session, test_users):
    admin = test_users["admin1"]
    owner = test_users["owner"]

    # 1. Admin cannot self-approve sensitive outlet creation request
    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="outlet_creation",
        target_entity_type="outlet",
        payload={"name": "Admin Outlet", "public_slug": "admin-outlet", "business_id": str(uuid.uuid4())},
    )
    with pytest.raises(ForbiddenError, match="cannot self-approve"):
        decide_approval_request(db=db_session, request_id=req.id, approver=admin, decision="approve", reason="Self approve")

    # 2. Owner CAN self-approve the same request
    owner_req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="outlet_creation",
        target_entity_type="outlet",
        payload={"name": "Owner Outlet", "public_slug": "owner-outlet", "business_id": str(uuid.uuid4())},
    )
    decided = decide_approval_request(
        db=db_session,
        request_id=owner_req.id,
        approver=owner,
        decision="approve",
        reason="Owner self approval permitted",
        auto_execute=False,
    )
    assert decided.status == ApprovalStatus.APPROVED
    assert decided.approver_user_id == owner.id


def test_confirmed_admin_self_approval_exceptions(db_session: Session, test_users):
    admin = test_users["admin1"]

    # Admin CAN self-approve business_creation
    biz_req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Self Approved Biz", "owner_email": "newowner@test.com", "owner_display_name": "New Owner"},
    )
    decided = decide_approval_request(
        db=db_session,
        request_id=biz_req.id,
        approver=admin,
        decision="approve",
        reason="Self approved per policy",
        auto_execute=False,
    )
    assert decided.status == ApprovalStatus.APPROVED


def test_withdrawal_ownership_and_lifecycle_restriction(db_session: Session, test_users):
    op = test_users["operator"]
    admin = test_users["admin1"]
    req = create_approval_request(
        db=db_session,
        requester=op,
        request_type="outlet_creation",
        target_entity_type="outlet",
        payload={"name": "Withdraw Outlet", "public_slug": "withdraw-outlet", "business_id": str(uuid.uuid4())},
    )

    # Admin cannot withdraw operator's request
    with pytest.raises(ForbiddenError, match="Only the original requester can withdraw"):
        withdraw_approval_request(db=db_session, request_id=req.id, actor=admin)

    # Requester can withdraw
    withdrawn = withdraw_approval_request(db=db_session, request_id=req.id, actor=op, reason="No longer needed")
    assert withdrawn.status == ApprovalStatus.WITHDRAWN

    # Cannot withdraw already withdrawn request
    with pytest.raises(ValidationError, match="Cannot withdraw approval request with status"):
        withdraw_approval_request(db=db_session, request_id=req.id, actor=op)


def test_clarification_thread_and_needs_information_state(db_session: Session, test_users):
    op = test_users["operator"]
    admin = test_users["admin1"]
    req = create_approval_request(
        db=db_session,
        requester=op,
        request_type="outlet_creation",
        target_entity_type="outlet",
        payload={"name": "Clarify Outlet", "public_slug": "clarify-outlet", "business_id": str(uuid.uuid4())},
    )

    # Admin asks a question -> transitions request to needs_information
    clarification = add_request_clarification(
        db=db_session,
        request_id=req.id,
        actor=admin,
        clarification_type="question",
        message="What is the planned opening date?",
    )
    db_session.refresh(req)
    assert req.status == ApprovalStatus.NEEDS_INFORMATION
    assert clarification.message == "What is the planned opening date?"

    # Requester responds
    resp = add_request_clarification(
        db=db_session,
        request_id=req.id,
        actor=op,
        clarification_type="response",
        message="Opening on November 1st.",
    )
    db_session.refresh(req)
    assert len(req.clarifications) == 2


def test_14_day_expiry_and_decision_block(db_session: Session, test_users):
    op = test_users["operator"]
    admin = test_users["admin1"]
    req = create_approval_request(
        db=db_session,
        requester=op,
        request_type="outlet_creation",
        target_entity_type="outlet",
        payload={"name": "Expiry Outlet", "public_slug": "expiry-outlet", "business_id": str(uuid.uuid4())},
    )

    # Simulate passing of 15 days
    req.expires_at = utc_now() - timedelta(days=1)
    db_session.commit()

    # Attempting to decide raises ValidationError and marks request expired
    with pytest.raises(ValidationError, match="has expired and can no longer be decided"):
        decide_approval_request(db=db_session, request_id=req.id, approver=admin, decision="approve", reason="Late approval")

    db_session.refresh(req)
    assert req.status == ApprovalStatus.EXPIRED


def test_atomic_execution_and_audit_failure_probe(db_session: Session, test_users):
    admin = test_users["admin1"]
    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Atomic Audit Biz", "owner_email": "atomic_owner@test.com", "owner_display_name": "Atomic Owner"},
    )
    # Approve without auto-execute
    decide_approval_request(db=db_session, request_id=req.id, approver=admin, decision="approve", reason="Approved", auto_execute=False)

    # Execute with audit_fail_probe=True simulating failure to record durable audit
    with pytest.raises(RuntimeError, match="Simulated durable audit persistence failure"):
        execute_approval_request(db=db_session, request_id=req.id, actor_user_id=admin.id, audit_fail_probe=True)

    # Verify domain business creation rolled back
    biz = db_session.query(Business).filter(Business.name == "Atomic Audit Biz").first()
    assert biz is None

    # Verify approval status remains APPROVED and execution_status is FAILED
    db_session.refresh(req)
    assert req.status == ApprovalStatus.APPROVED
    assert req.execution_status == ExecutionStatus.FAILED
    assert "Simulated durable audit persistence failure" in req.execution_error


def test_successful_domain_execution_persists_mutation(db_session: Session, test_users):
    admin = test_users["admin1"]
    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Successful Exec Biz", "owner_email": "success_owner@test.com", "owner_display_name": "Success Owner"},
    )
    # Decide with auto_execute=True
    decided = decide_approval_request(
        db=db_session,
        request_id=req.id,
        approver=admin,
        decision="approve",
        reason="Approved for execution",
        auto_execute=True,
    )
    assert decided.status == ApprovalStatus.APPROVED
    assert decided.execution_status == ExecutionStatus.SUCCEEDED
    assert decided.execution_details_json["name"] == "Successful Exec Biz"

    # Domain business genuinely exists
    biz = db_session.query(Business).filter(Business.name == "Successful Exec Biz").first()
    assert biz is not None
    assert biz.status == "active"


def test_concurrent_decisions_second_fails_with_validation_error(db_session: Session, test_users):
    """
    Verifies that when two approvers concurrently attempt to decide a pending request,
    the first committed decision wins and the second fails closed.
    """
    op = test_users["operator"]
    admin1 = test_users["admin1"]
    admin2 = test_users["admin2"]

    req = create_approval_request(
        db=db_session,
        requester=op,
        request_type="outlet_creation",
        target_entity_type="outlet",
        payload={"name": "Race Outlet", "public_slug": "race-outlet", "business_id": str(uuid.uuid4())},
    )

    bind = db_session.get_bind()
    session1 = Session(bind)
    session2 = Session(bind)
    try:
        # Session 1 decides and commits first
        decide_approval_request(
            db=session1,
            request_id=req.id,
            approver=admin1,
            decision="approve",
            reason="Approved by Admin 1",
            auto_execute=False,
        )

        # Session 2 attempts to decide the same request
        with pytest.raises(ValidationError, match="Cannot decide approval request with status 'approved'"):
            decide_approval_request(
                db=session2,
                request_id=req.id,
                approver=admin2,
                decision="reject",
                reason="Rejected by Admin 2",
                auto_execute=False,
            )
    finally:
        session1.close()
        session2.close()


def test_retry_of_failed_execution_succeeds(db_session: Session, test_users):
    """
    Verifies that a request whose domain execution failed can be safely retried without reapproval.
    """
    admin = test_users["admin1"]
    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Retry Biz", "owner_email": "retry_owner@test.com", "owner_display_name": "Retry Owner"},
    )
    # Approve without auto-execute
    decide_approval_request(
        db=db_session,
        request_id=req.id,
        approver=admin,
        decision="approve",
        reason="Initial Approval",
        auto_execute=False,
    )

    # First attempt fails via audit probe
    with pytest.raises(RuntimeError):
        execute_approval_request(db=db_session, request_id=req.id, actor_user_id=admin.id, audit_fail_probe=True)

    db_session.refresh(req)
    assert req.status == ApprovalStatus.APPROVED
    assert req.execution_status == ExecutionStatus.FAILED
    assert req.retry_count == 1

    # Retry without probe succeeds
    retried = execute_approval_request(db=db_session, request_id=req.id, actor_user_id=admin.id, audit_fail_probe=False)
    assert retried.status == ApprovalStatus.APPROVED
    assert retried.execution_status == ExecutionStatus.SUCCEEDED
    assert retried.retry_count == 2
    assert retried.execution_error is None

    # Verify domain entity was created
    biz = db_session.query(Business).filter(Business.name == "Retry Biz").first()
    assert biz is not None


def test_admin_cannot_suspend_or_demote_admin(db_session: Session, test_users):
    """
    Verifies that Platform Administrators cannot submit or approve suspension/demotion of fellow Admins.
    """
    admin1 = test_users["admin1"]
    admin2 = test_users["admin2"]
    operator = test_users["operator"]

    # 1. Operator requests suspension of Admin2; Admin1 attempts to approve -> Rejected (requires Owner)
    req_suspend = create_approval_request(
        db=db_session,
        requester=operator,
        request_type="user_suspension",
        target_entity_type="user",
        payload={"target_user_id": str(admin2.id), "reason": "Dispute"},
    )
    with pytest.raises(ForbiddenError, match="Only the Platform Owner can suspend another Platform Administrator"):
        decide_approval_request(db=db_session, request_id=req_suspend.id, approver=admin1, decision="approve", reason="Approve suspension")

    # 2. Operator requests demotion of Admin2; Admin1 attempts to approve -> Rejected (requires Owner)
    req_demote = create_approval_request(
        db=db_session,
        requester=operator,
        request_type="user_role_change",
        target_entity_type="user",
        payload={"target_user_id": str(admin2.id), "new_platform_role": "operator"},
    )
    with pytest.raises(ForbiddenError, match="Role changes involving Platform Administrator privileges require Platform Owner"):
        decide_approval_request(db=db_session, request_id=req_demote.id, approver=admin1, decision="approve", reason="Approve demotion")


def test_check_and_expire_batch_job(db_session: Session, test_users):
    """
    Verifies that check_and_expire_requests correctly sweeps expired requests and creates audit records.
    """
    op = test_users["operator"]
    req = create_approval_request(
        db=db_session,
        requester=op,
        request_type="outlet_creation",
        target_entity_type="outlet",
        payload={"name": "Sweep Outlet", "public_slug": "sweep-outlet", "business_id": str(uuid.uuid4())},
    )
    # Fast-forward expiry
    req.expires_at = utc_now() - timedelta(days=2)
    db_session.commit()

    count = check_and_expire_requests(db=db_session)
    assert count >= 1

    db_session.refresh(req)
    assert req.status == ApprovalStatus.EXPIRED


def test_confirmed_db_constraint_abort_results_in_failed(db_session: Session, test_users):
    """
    Scenario 1: Confirmed database constraint abort
    results in FAILED, increments retry_count, stores sanitized diagnostic, and preserves APPROVED.
    """
    owner = test_users["owner"]
    req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Constraint Biz", "owner_email": "constraint_owner@test.com", "owner_display_name": "Owner"},
    )
    decide_approval_request(db=db_session, request_id=req.id, approver=owner, decision="approve", reason="Approved", auto_execute=False)

    with patch("app.modules.approvals.execution._dispatch_domain_operation") as mock_dispatch:
        mock_dispatch.side_effect = ValidationError("Invalid business attribute: name violates naming constraint.")
        with pytest.raises(ValidationError):
            execute_approval_request(db=db_session, request_id=req.id, actor_user_id=owner.id)

    db_session.refresh(req)
    assert req.status == ApprovalStatus.APPROVED
    assert req.execution_status == ExecutionStatus.FAILED
    assert req.retry_count == 1
    assert "violates naming constraint" in req.execution_error


def test_lost_commit_acknowledgement_preserves_succeeded(db_session: Session, test_users):
    """
    Scenario 2: Lost COMMIT acknowledgement where authoritative row is SUCCEEDED preserves success and returns request.
    """
    owner = test_users["owner"]
    req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Lost ACK Biz", "owner_email": "lostack@test.com", "owner_display_name": "Lost Ack Owner"},
    )
    decide_approval_request(db=db_session, request_id=req.id, approver=owner, decision="approve", reason="Approved", auto_execute=False)

    original_commit = db_session.commit
    commit_call_count = 0

    def mock_commit():
        nonlocal commit_call_count
        commit_call_count += 1
        if commit_call_count == 1:
            req.execution_status = ExecutionStatus.SUCCEEDED
            original_commit()
            raise OperationalError("server closed the connection unexpectedly (lost ACK)", None, None)
        original_commit()

    with patch.object(db_session, "commit", side_effect=mock_commit):
        result = execute_approval_request(db=db_session, request_id=req.id, actor_user_id=owner.id)

    db_session.refresh(req)
    assert result.execution_status == ExecutionStatus.SUCCEEDED
    assert req.execution_status == ExecutionStatus.SUCCEEDED
    assert req.status == ApprovalStatus.APPROVED


def test_recovery_when_db_unavailable_raises_commit_outcome_uncertain(db_session: Session, test_users):
    """
    Scenario 3: Commit transport error where DB is completely unreachable during recovery
    raises CommitOutcomeUncertainError without mutating row state.
    """
    owner = test_users["owner"]
    req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Unreachable DB Biz", "owner_email": "unreach@test.com", "owner_display_name": "Unreach Owner"},
    )
    decide_approval_request(db=db_session, request_id=req.id, approver=owner, decision="approve", reason="Approved", auto_execute=False)

    initial_retries = req.retry_count
    commit_failed = False
    original_commit = db_session.commit
    original_query = db_session.query

    def failing_commit():
        nonlocal commit_failed
        commit_failed = True
        raise OperationalError("Connection reset by peer during commit", None, None)

    def conditional_query(*args, **kwargs):
        if commit_failed:
            raise OperationalError("Database connection refused during recovery", None, None)
        return original_query(*args, **kwargs)

    with patch.object(db_session, "commit", side_effect=failing_commit), \
         patch.object(db_session, "query", side_effect=conditional_query):
        with pytest.raises(CommitOutcomeUncertainError) as exc_info:
            execute_approval_request(db=db_session, request_id=req.id, actor_user_id=owner.id)

    assert "Commit outcome uncertain" in str(exc_info.value)
    db_session.rollback()
    db_session.refresh(req)
    # Row must remain NOT_STARTED, never speculative FAILED or BLOCKED
    assert req.execution_status == ExecutionStatus.NOT_STARTED
    assert req.status == ApprovalStatus.APPROVED
    assert req.retry_count == initial_retries


def test_ambiguous_commit_with_not_started_read_raises_commit_outcome_uncertain(db_session: Session, test_users):
    """
    Scenario 4: Ambiguous transport error during commit where fresh read shows NOT_STARTED
    raises CommitOutcomeUncertainError and does not claim rollback or auto-replay.
    """
    owner = test_users["owner"]
    req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Ambiguous Biz", "owner_email": "ambiguous@test.com", "owner_display_name": "Ambiguous Owner"},
    )
    decide_approval_request(db=db_session, request_id=req.id, approver=owner, decision="approve", reason="Approved", auto_execute=False)

    def failing_commit():
        raise OperationalError("Transport timeout on commit", None, None)

    with patch.object(db_session, "commit", side_effect=failing_commit):
        with pytest.raises(CommitOutcomeUncertainError):
            execute_approval_request(db=db_session, request_id=req.id, actor_user_id=owner.id)

    db_session.refresh(req)
    # Does NOT mark FAILED; preserves uncertainty; leaves row in previous committed state
    assert req.execution_status == ExecutionStatus.NOT_STARTED
    assert req.status == ApprovalStatus.APPROVED


def test_unlinked_matching_entity_collision_transitions_to_blocked(db_session: Session, test_users):
    """
    Scenario 5: Unlinked matching-entity collision (e.g. outlet public slug already exists)
    transitions request to BLOCKED with CONFLICT_UNLINKED_ENTITY_EXISTS.
    """
    owner = test_users["owner"]
    biz = Business(name="Outlet Collision Biz", status="active")
    db_session.add(biz)
    db_session.flush()

    pre_outlet = Outlet(name="PreExisting Outlet", public_slug="taken-slug", business_id=biz.id, status="active")
    db_session.add(pre_outlet)
    db_session.commit()

    req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="outlet_creation",
        target_entity_type="outlet",
        business_id=biz.id,
        payload={"name": "New Outlet With Taken Slug", "public_slug": "taken-slug", "business_id": str(biz.id)},
    )
    decide_approval_request(db=db_session, request_id=req.id, approver=owner, decision="approve", reason="Approved", auto_execute=False)

    with pytest.raises(ValidationError, match="already in use"):
        execute_approval_request(db=db_session, request_id=req.id, actor_user_id=owner.id)

    db_session.refresh(req)
    assert req.status == ApprovalStatus.APPROVED
    assert req.execution_status == ExecutionStatus.BLOCKED
    assert "CONFLICT_UNLINKED_ENTITY_EXISTS" in req.execution_error


def test_confirmed_domain_validation_failure_becomes_failed(db_session: Session, test_users):
    """
    Scenario 6: Confirmed domain validation failure (precondition check) cleanly marks FAILED,
    preserves status = APPROVED, and records sanitized error.
    """
    owner = test_users["owner"]
    req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Domain Fail Biz", "owner_email": "fail@test.com", "owner_display_name": "Fail Owner"},
    )
    decide_approval_request(db=db_session, request_id=req.id, approver=owner, decision="approve", reason="Approved", auto_execute=False)

    with patch("app.modules.approvals.execution.platform_service.create_platform_business") as mock_create:
        mock_create.side_effect = ValidationError("Invalid business currency configuration.")
        with pytest.raises(ValidationError):
            execute_approval_request(db=db_session, request_id=req.id, actor_user_id=owner.id)

    db_session.refresh(req)
    assert req.status == ApprovalStatus.APPROVED
    assert req.execution_status == ExecutionStatus.FAILED
    assert req.retry_count == 1
    assert "Invalid business currency" in req.execution_error


def test_re_executing_succeeded_request_is_idempotent(db_session: Session, test_users):
    """
    Scenario 7: Re-executing a SUCCEEDED request returns idempotently without re-dispatching
    or incrementing retries.
    """
    owner = test_users["owner"]
    req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Idempotent Biz", "owner_email": "idemp@test.com", "owner_display_name": "Idemp Owner"},
    )
    decide_approval_request(db=db_session, request_id=req.id, approver=owner, decision="approve", reason="Approved", auto_execute=True)

    db_session.refresh(req)
    assert req.execution_status == ExecutionStatus.SUCCEEDED
    retries_before = req.retry_count

    res = execute_approval_request(db=db_session, request_id=req.id, actor_user_id=owner.id)
    assert res.execution_status == ExecutionStatus.SUCCEEDED
    db_session.refresh(req)
    assert req.retry_count == retries_before


def test_unauthorized_execution_leaves_protected_state_untouched(db_session: Session, test_users):
    """
    Scenario 8: Unauthorized execution of an Owner-only request by an Admin raises ForbiddenError
    and leaves approval status, execution status, retry count, and timestamps completely untouched.
    """
    owner = test_users["owner"]
    admin = test_users["admin1"]

    # Suspended user target for reactivation
    suspended_target = User(
        email="reactivate_target@test.com",
        password_hash="dummy",
        display_name="Suspended User",
        status="suspended",
    )
    db_session.add(suspended_target)
    db_session.commit()

    req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="user_reactivation",
        target_entity_type="user",
        payload={"target_user_id": str(suspended_target.id), "reason": "Owner requested reactivation"},
    )
    decide_approval_request(db=db_session, request_id=req.id, approver=owner, decision="approve", reason="Approved", auto_execute=False)

    db_session.refresh(req)
    assert req.status == ApprovalStatus.APPROVED
    assert req.execution_status == ExecutionStatus.NOT_STARTED
    assert req.retry_count == 0
    assert req.execution_started_at is None
    assert req.execution_completed_at is None

    # Admin attempts to execute Owner-only user_reactivation
    with pytest.raises(ForbiddenError, match="Platform Owner privileges are required"):
        execute_approval_request(db=db_session, request_id=req.id, actor_user_id=admin.id)

    db_session.refresh(req)
    # Must remain completely untouched
    assert req.status == ApprovalStatus.APPROVED
    assert req.execution_status == ExecutionStatus.NOT_STARTED
    assert req.retry_count == 0
    assert req.execution_started_at is None
    assert req.execution_completed_at is None
    assert req.execution_error is None


def test_executing_blocked_request_rejected_pending_reconciliation(db_session: Session, test_users):
    """
    Scenario 9: Attempting to execute a BLOCKED request raises ValidationError.
    """
    owner = test_users["owner"]
    req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Blocked Biz", "owner_email": "blocked@test.com", "owner_display_name": "Blocked Owner"},
    )
    decide_approval_request(db=db_session, request_id=req.id, approver=owner, decision="approve", reason="Approved", auto_execute=False)

    req.execution_status = ExecutionStatus.BLOCKED
    db_session.commit()

    with pytest.raises(ValidationError, match="blocked pending reconciliation"):
        execute_approval_request(db=db_session, request_id=req.id, actor_user_id=owner.id)


def test_audit_record_failure_prevents_domain_commit(db_session: Session, test_users):
    """
    Scenario 10: Failure to persist required audit record rolls back domain changes and prevents commit.
    """
    owner = test_users["owner"]
    req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Audit Fail Biz", "owner_email": "auditfail@test.com", "owner_display_name": "Audit Fail Owner"},
    )
    decide_approval_request(db=db_session, request_id=req.id, approver=owner, decision="approve", reason="Approved", auto_execute=False)

    with pytest.raises(RuntimeError, match="Simulated durable audit persistence failure"):
        execute_approval_request(db=db_session, request_id=req.id, actor_user_id=owner.id, audit_fail_probe=True)

    biz = db_session.query(Business).filter(Business.name == "Audit Fail Biz").first()
    assert biz is None


def test_admin_operator_creation_and_self_approval_executes(db_session: Session, test_users):
    """
    Scenario 1: Platform Admin creates an Operator, self-approves, and auto-executes successfully.
    Verifies that operator creation is NOT Owner-only and executes normally.
    """
    admin = test_users["admin1"]
    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="operator_creation",
        target_entity_type="user",
        payload={"email": "operator_admin_created@test.com", "display_name": "Op By Admin"},
    )

    # Admin self-approves with auto_execute=True
    decided_req = decide_approval_request(
        db=db_session,
        request_id=req.id,
        approver=admin,
        decision="approve",
        reason="Approved and provisioned by Admin",
        auto_execute=True,
    )

    db_session.refresh(decided_req)
    assert decided_req.status == ApprovalStatus.APPROVED
    assert decided_req.execution_status == ExecutionStatus.SUCCEEDED
    assert decided_req.execution_details_json is not None
    assert "operator_id" in decided_req.execution_details_json

    # Verify user exists in DB with operator role
    new_op = db_session.query(User).filter(User.email == "operator_admin_created@test.com").first()
    assert new_op is not None
    assert new_op.platform_role == "operator"
    assert new_op.is_platform_admin is False


def test_admin_operator_revocation_executes_with_audit(db_session: Session, test_users):
    """
    Scenario 2: Platform Admin requests, approves, and executes revocation of an Operator.
    """
    admin = test_users["admin1"]
    operator_user = test_users["operator"]

    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="operator_revocation",
        target_entity_type="user",
        payload={"target_user_id": str(operator_user.id), "target_email": operator_user.email},
    )

    decided_req = decide_approval_request(
        db=db_session,
        request_id=req.id,
        approver=admin,
        decision="approve",
        reason="Admin revoking operator",
        auto_execute=True,
    )

    db_session.refresh(decided_req)
    assert decided_req.status == ApprovalStatus.APPROVED
    assert decided_req.execution_status == ExecutionStatus.SUCCEEDED

    db_session.refresh(operator_user)
    assert operator_user.platform_role is None
    assert operator_user.is_platform_admin is False


def test_admin_suspension_of_operator_executes(db_session: Session, test_users):
    """
    Scenario 3: Platform Admin requests, self-approves, and executes suspension of an Operator.
    Verifies that operator suspension is authorized for Admin self-approval under confirmed policy.
    """
    admin1 = test_users["admin1"]
    operator_user = test_users["operator"]

    req = create_approval_request(
        db=db_session,
        requester=admin1,
        request_type="user_suspension",
        target_entity_type="user",
        payload={"target_user_id": str(operator_user.id), "reason": "Operator policy violation"},
    )

    decided_req = decide_approval_request(
        db=db_session,
        request_id=req.id,
        approver=admin1,
        decision="approve",
        reason="Approved suspension",
        auto_execute=True,
    )

    db_session.refresh(decided_req)
    assert decided_req.status == ApprovalStatus.APPROVED
    assert decided_req.execution_status == ExecutionStatus.SUCCEEDED

    db_session.refresh(operator_user)
    assert operator_user.status == "suspended"


def test_admin_blocked_from_suspending_admin_at_execution(db_session: Session, test_users):
    """
    Scenario 4: An approved request to suspend a Platform Admin CANNOT be executed by another Admin.
    Only the Platform Owner has execution authority over fellow Admins.
    """
    owner = test_users["owner"]
    admin1 = test_users["admin1"]
    admin2 = test_users["admin2"]

    req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="user_suspension",
        target_entity_type="user",
        payload={"target_user_id": str(admin2.id), "reason": "Admin investigation"},
    )
    decide_approval_request(db=db_session, request_id=req.id, approver=owner, decision="approve", reason="Approved", auto_execute=False)

    # Admin1 attempts to execute suspension of Admin2 -> Rejected with ForbiddenError
    with pytest.raises(ForbiddenError, match="Only the Platform Owner can execute suspension of a Platform Administrator"):
        execute_approval_request(db=db_session, request_id=req.id, actor_user_id=admin1.id)

    db_session.refresh(req)
    # State remains completely untouched
    assert req.status == ApprovalStatus.APPROVED
    assert req.execution_status == ExecutionStatus.NOT_STARTED
    assert req.retry_count == 0

    db_session.refresh(admin2)
    assert admin2.status == "active"


def test_owner_only_demotion_of_existing_admin_at_execution(db_session: Session, test_users):
    """
    Scenario 5: An approved request to demote an existing Platform Admin to Operator
    CANNOT be executed by another Admin; only the Owner may execute it.
    """
    owner = test_users["owner"]
    admin1 = test_users["admin1"]
    admin2 = test_users["admin2"]

    req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="user_role_change",
        target_entity_type="user",
        payload={"target_user_id": str(admin2.id), "new_platform_role": "operator"},
    )
    decide_approval_request(db=db_session, request_id=req.id, approver=owner, decision="approve", reason="Approved demotion", auto_execute=False)

    # Admin1 attempts to execute demotion of Admin2 -> Rejected with ForbiddenError
    with pytest.raises(ForbiddenError, match="Role changes involving Platform Administrator privileges require Platform Owner"):
        execute_approval_request(db=db_session, request_id=req.id, actor_user_id=admin1.id)

    db_session.refresh(req)
    assert req.status == ApprovalStatus.APPROVED
    assert req.execution_status == ExecutionStatus.NOT_STARTED
    assert req.retry_count == 0

    db_session.refresh(admin2)
    assert admin2.platform_role == "admin"
    assert admin2.is_platform_admin is True


def test_no_public_dispatcher_bypass_in_approvals_module(db_session: Session, test_users):
    """
    Scenario 6: Verifies that dispatch_domain_operation is NOT exported publicly in app.modules.approvals.__all__,
    and direct call to internal _dispatch_domain_operation on an unapproved request raises ForbiddenError.
    """
    import app.modules.approvals as approvals_mod
    from app.modules.approvals.execution import _dispatch_domain_operation

    assert "dispatch_domain_operation" not in approvals_mod.__all__

    owner = test_users["owner"]
    pending_req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Bypass Biz", "owner_email": "bypass@test.com", "owner_display_name": "Bypass Owner"},
    )

    with pytest.raises(ForbiddenError, match="Cannot dispatch request with status 'pending'"):
        _dispatch_domain_operation(db=db_session, request=pending_req, actor_user_id=owner.id)


def test_admin_promotes_operator_to_admin_and_self_approves_executes(db_session: Session, test_users):
    """
    Case 2: Platform Admin promotes an existing Operator to Admin and self-approves successfully.
    Target is currently an Operator, so Admin self-approval and auto-execution are authorized.
    """
    admin = test_users["admin1"]
    operator_user = test_users["operator"]

    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="user_role_change",
        target_entity_type="user",
        payload={"target_user_id": str(operator_user.id), "new_platform_role": "admin"},
    )

    decided = decide_approval_request(
        db=db_session,
        request_id=req.id,
        approver=admin,
        decision="approve",
        reason="Promoting trusted operator to administrator",
        auto_execute=True,
    )

    db_session.refresh(decided)
    assert decided.status == ApprovalStatus.APPROVED
    assert decided.execution_status == ExecutionStatus.SUCCEEDED

    db_session.refresh(operator_user)
    assert operator_user.platform_role == "admin"
    assert operator_user.is_platform_admin is True


def test_admin_cannot_self_approve_admin_creation_or_promotion_of_non_operator(db_session: Session, test_users):
    """
    Case 3: Platform Admin cannot self-approve creation/provisioning of an Admin or promotion of a non-operator.
    """
    admin = test_users["admin1"]
    # Create a regular staff user with no platform role
    regular_user = User(
        id=uuid.uuid4(),
        email="regular_staff@test.com",
        password_hash="dummyhash",
        display_name="Regular Staff",
        status="active",
        platform_role=None,
        is_platform_admin=False,
    )
    db_session.add(regular_user)
    db_session.flush()

    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="user_role_change",
        target_entity_type="user",
        payload={"target_user_id": str(regular_user.id), "new_platform_role": "admin"},
    )

    with pytest.raises(ForbiddenError, match="Promoting a non-operator to Platform Administrator requires Platform Owner final approval"):
        decide_approval_request(
            db=db_session,
            request_id=req.id,
            approver=admin,
            decision="approve",
            reason="Self-approving promotion of non-operator",
        )


def test_admin_cannot_self_approve_role_change_targeting_admin(db_session: Session, test_users):
    """
    Case 4: Platform Admin cannot self-approve a role change targeting an existing Admin.
    """
    admin1 = test_users["admin1"]
    admin2 = test_users["admin2"]

    req = create_approval_request(
        db=db_session,
        requester=admin1,
        request_type="user_role_change",
        target_entity_type="user",
        payload={"target_user_id": str(admin2.id), "new_platform_role": "operator"},
    )

    with pytest.raises(ForbiddenError, match="Role changes involving Platform Administrator privileges require Platform Owner final approval"):
        decide_approval_request(
            db=db_session,
            request_id=req.id,
            approver=admin1,
            decision="approve",
            reason="Demoting fellow admin",
        )


def test_admin_cannot_approve_role_change_targeting_owner(db_session: Session, test_users):
    """
    Case 5 & 6: Platform Admin cannot approve a role change targeting the Platform Owner.
    Must be rejected at decision time, keeping the request in pending status.
    """
    admin = test_users["admin1"]
    owner = test_users["owner"]

    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="user_role_change",
        target_entity_type="user",
        payload={"target_user_id": str(owner.id), "new_platform_role": "operator"},
    )

    with pytest.raises(ForbiddenError, match="Role changes targeting the Platform Owner require Platform Owner authority"):
        decide_approval_request(
            db=db_session,
            request_id=req.id,
            approver=admin,
            decision="approve",
            reason="Attempting to demote Owner",
        )

    db_session.refresh(req)
    assert req.status == ApprovalStatus.PENDING
    assert req.execution_status == ExecutionStatus.NOT_STARTED


def test_admin_cannot_suspend_or_revoke_admin(db_session: Session, test_users):
    """
    Case 9: Platform Admin cannot suspend or revoke another Admin.
    """
    admin1 = test_users["admin1"]
    admin2 = test_users["admin2"]

    # Suspension
    req_suspend = create_approval_request(
        db=db_session,
        requester=admin1,
        request_type="user_suspension",
        target_entity_type="user",
        payload={"target_user_id": str(admin2.id), "reason": "Dispute"},
    )
    with pytest.raises(ForbiddenError, match="Only the Platform Owner can suspend another Platform Administrator"):
        decide_approval_request(db=db_session, request_id=req_suspend.id, approver=admin1, decision="approve", reason="Approve")

    # Revocation
    req_revoke = create_approval_request(
        db=db_session,
        requester=admin1,
        request_type="operator_revocation",
        target_entity_type="user",
        payload={"target_user_id": str(admin2.id), "target_email": admin2.email},
    )
    with pytest.raises(ForbiddenError, match="Platform Administrators cannot revoke administrator privileges"):
        decide_approval_request(db=db_session, request_id=req_revoke.id, approver=admin1, decision="approve", reason="Approve")


def test_admin_cannot_suspend_or_revoke_owner(db_session: Session, test_users):
    """
    Case 10: Platform Admin cannot suspend or revoke the Platform Owner.
    """
    admin = test_users["admin1"]
    owner = test_users["owner"]

    # Suspension
    req_suspend = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="user_suspension",
        target_entity_type="user",
        payload={"target_user_id": str(owner.id), "reason": "Owner dispute"},
    )
    with pytest.raises(ForbiddenError, match="Only the Platform Owner can suspend another Platform Administrator"):
        decide_approval_request(db=db_session, request_id=req_suspend.id, approver=admin, decision="approve", reason="Approve")

    # Revocation
    req_revoke = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="operator_revocation",
        target_entity_type="user",
        payload={"target_user_id": str(owner.id), "target_email": owner.email},
    )
    with pytest.raises(ForbiddenError, match="Platform Administrators cannot alter privileges of the Platform Owner"):
        decide_approval_request(db=db_session, request_id=req_revoke.id, approver=admin, decision="approve", reason="Approve")


def test_target_role_change_after_creation_fails_closed(db_session: Session, test_users):
    """
    Case 11: A target whose role changes after request creation is revalidated before approval/execution,
    and authorization fails closed.
    """
    admin = test_users["admin1"]
    target = test_users["operator"]

    # Request created when target is an Operator
    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="user_suspension",
        target_entity_type="user",
        payload={"target_user_id": str(target.id), "reason": "Investigation"},
    )

    # Concurrently / subsequently, target is promoted to Admin in DB
    target.platform_role = "admin"
    target.is_platform_admin = True
    db_session.flush()

    # Admin attempts to self-approve / decide the pending request -> Revalidation discovers target is now Admin
    with pytest.raises(ForbiddenError, match="Only the Platform Owner can suspend another Platform Administrator"):
        decide_approval_request(
            db=db_session,
            request_id=req.id,
            approver=admin,
            decision="approve",
            reason="Approving suspension",
        )

    db_session.refresh(req)
    assert req.status == ApprovalStatus.PENDING
    assert req.execution_status == ExecutionStatus.NOT_STARTED


def test_payload_unsupported_role_fields_rejected(db_session: Session, test_users):
    """
    Case 12: Payload manipulation using unsupported role fields cannot bypass sanitization or authorization.
    """
    admin = test_users["admin1"]
    operator_user = test_users["operator"]

    # 1. Unsupported field 'new_role' rejected by sanitization allowlist
    with pytest.raises(ValueError, match="Payload for request type 'user_role_change' contains unauthorized fields:.*new_role"):
        create_approval_request(
            db=db_session,
            requester=admin,
            request_type="user_role_change",
            target_entity_type="user",
            payload={"target_user_id": str(operator_user.id), "new_role": "admin"},
        )

    # 2. Attempting to set new_platform_role to 'owner' rejected
    req_owner = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="user_role_change",
        target_entity_type="user",
        payload={"target_user_id": str(operator_user.id), "new_platform_role": "owner"},
    )
    with pytest.raises(ForbiddenError, match="Platform Owner role can only be transferred via the dedicated owner transfer process"):
        decide_approval_request(
            db=db_session,
            request_id=req_owner.id,
            approver=admin,
            decision="approve",
            reason="Promoting to owner",
        )


def test_operator_self_suspension_rejected(db_session: Session, test_users):
    """
    Case 13: Operator self-suspension remains unavailable through the existing authorization path.
    """
    operator_user = test_users["operator"]

    # 1. Operator cannot submit user suspension for themselves
    with pytest.raises(ForbiddenError, match="Users cannot initiate self-suspension"):
        create_approval_request(
            db=db_session,
            requester=operator_user,
            request_type="user_suspension",
            target_entity_type="user",
            payload={"target_user_id": str(operator_user.id), "reason": "Self-suspend"},
        )

    # 2. Operator cannot directly suspend via platform_service
    from app.modules.businesses.platform_service import suspend_platform_user
    with pytest.raises(ForbiddenError, match="Platform Administrator or Owner privileges are required"):
        suspend_platform_user(
            db=db_session,
            target_user_id=operator_user.id,
            actor_user_id=operator_user.id,
        )


def test_owner_authorized_flows_succeed(db_session: Session, test_users):
    """
    Case 14: Existing Owner-authorized flows continue to work (e.g. Owner demotes Admin, Owner suspends Operator).
    """
    owner = test_users["owner"]
    admin2 = test_users["admin2"]

    # Owner creates, approves, and executes demoting an Admin to Operator
    req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="user_role_change",
        target_entity_type="user",
        payload={"target_user_id": str(admin2.id), "new_platform_role": "operator"},
    )

    decided = decide_approval_request(
        db=db_session,
        request_id=req.id,
        approver=owner,
        decision="approve",
        reason="Owner demoting admin to operator",
        auto_execute=True,
    )

    db_session.refresh(decided)
    assert decided.status == ApprovalStatus.APPROVED
    assert decided.execution_status == ExecutionStatus.SUCCEEDED

    db_session.refresh(admin2)
    assert admin2.platform_role == "operator"
    assert admin2.is_platform_admin is False



