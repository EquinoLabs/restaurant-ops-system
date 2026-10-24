import os
import uuid
from datetime import datetime, timedelta, timezone
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.pool import StaticPool

from app.modules.approvals.models import (
    ApprovalRequest,
    ApprovalClarification,
    ApprovalStatus,
    ExecutionStatus,
)
from app.modules.approvals.sanitization import (
    validate_and_sanitize_payload,
    sanitize_diagnostic_message,
    sanitize_diagnostic_details,
    contains_forbidden_keys,
)
from app.modules.staff.models import User
from app.modules.businesses.models import Business
from app.db.base import utc_now
from tests.test_alembic_migrations import load_migration_module


def test_approval_models_in_sqlite(db_session: Session):
    # 1. Create a requester and approver
    requester = User(
        email="operator_req@test.com",
        password_hash="dummyhash",
        display_name="Requester Operator",
        status="active",
        platform_role="operator",
    )
    approver = User(
        email="admin_app@test.com",
        password_hash="dummyhash",
        display_name="Approver Admin",
        status="active",
        platform_role="admin",
        is_platform_admin=True,
    )
    db_session.add_all([requester, approver])
    db_session.commit()

    # 2. Create approval request
    now = utc_now()
    expires = now + timedelta(days=14)
    req = ApprovalRequest(
        request_type="outlet_creation",
        target_entity_type="outlet",
        requester_user_id=requester.id,
        status=ApprovalStatus.PENDING,
        execution_status=ExecutionStatus.NOT_STARTED,
        payload_snapshot={"name": "Downtown Bistro", "currency": "INR"},
        justification="Opening new location downtown",
        expires_at=expires,
        idempotency_key="idemp_key_123",
    )
    db_session.add(req)
    db_session.commit()
    db_session.refresh(req)

    assert req.id is not None
    assert req.status == ApprovalStatus.PENDING
    assert req.execution_status == ExecutionStatus.NOT_STARTED
    assert req.payload_snapshot["name"] == "Downtown Bistro"
    assert req.version == 1
    assert req.retry_count == 0
    assert req.expires_at.replace(tzinfo=timezone.utc) == expires
    assert req.requester.email == "operator_req@test.com"

    # 3. Add clarification thread
    clarification = ApprovalClarification(
        approval_request_id=req.id,
        author_user_id=approver.id,
        clarification_type="question",
        message="Please specify the initial seating capacity.",
    )
    db_session.add(clarification)
    db_session.commit()
    db_session.refresh(req)

    assert len(req.clarifications) == 1
    assert req.clarifications[0].message == "Please specify the initial seating capacity."
    assert req.clarifications[0].author.email == "admin_app@test.com"

    # 4. Lifecycle transition: Needs Information -> Approved -> Execution Succeeded
    req.status = ApprovalStatus.NEEDS_INFORMATION
    db_session.commit()

    # Requester responds
    resp_clarification = ApprovalClarification(
        approval_request_id=req.id,
        author_user_id=requester.id,
        clarification_type="response",
        message="Initial capacity is 60 seats.",
    )
    db_session.add(resp_clarification)
    req.status = ApprovalStatus.APPROVED
    req.approver_user_id = approver.id
    req.decided_at = utc_now()
    req.decision_reason = "Approved after capacity clarification"
    req.execution_status = ExecutionStatus.SUCCEEDED
    req.execution_completed_at = utc_now()
    db_session.commit()

    db_session.refresh(req)
    assert req.status == ApprovalStatus.APPROVED
    assert req.execution_status == ExecutionStatus.SUCCEEDED
    assert len(req.clarifications) == 2
    assert req.approver.email == "admin_app@test.com"
    # Automatic version increment by SQLAlchemy ORM versioning
    assert req.version == 3


def test_approved_request_with_execution_failure_state(db_session: Session):
    """
    Verifies that an execution failure preserves status = approved and sets execution_status = failed.
    """
    user = User(
        email="operator_fail@test.com",
        password_hash="dummyhash",
        display_name="Fail Test",
        status="active",
    )
    db_session.add(user)
    db_session.commit()

    req = ApprovalRequest(
        request_type="outlet_creation",
        target_entity_type="outlet",
        requester_user_id=user.id,
        status=ApprovalStatus.APPROVED,
        execution_status=ExecutionStatus.FAILED,
        execution_error="Database connection timed out during outlet creation.",
        payload_snapshot={"name": "Faulty Outlet"},
    )
    db_session.add(req)
    db_session.commit()
    db_session.refresh(req)

    assert req.status == ApprovalStatus.APPROVED
    assert req.execution_status == ExecutionStatus.FAILED
    assert req.execution_error == "Database connection timed out during outlet creation."


def test_optimistic_locking_stale_data_error(db_session: Session):
    """
    Verifies that SQLAlchemy ORM raises StaleDataError when updating a stale version.
    """
    user = User(
        email="concurrent@test.com",
        password_hash="dummyhash",
        display_name="Concurrent Test",
        status="active",
    )
    db_session.add(user)
    db_session.commit()

    req = ApprovalRequest(
        request_type="user_role_change",
        target_entity_type="user",
        requester_user_id=user.id,
        status=ApprovalStatus.PENDING,
        payload_snapshot={"target_user_id": str(user.id), "new_platform_role": "admin"},
    )
    db_session.add(req)
    db_session.commit()

    # Create two separate sessions to simulate concurrent workers/actors
    bind = db_session.get_bind()
    session1 = Session(bind)
    session2 = Session(bind)
    try:
        req1 = session1.query(ApprovalRequest).filter(ApprovalRequest.id == req.id).first()
        req2 = session2.query(ApprovalRequest).filter(ApprovalRequest.id == req.id).first()
        assert req1.version == 1
        assert req2.version == 1

        # Session 1 updates and commits
        req1.decision_reason = "Approved by Actor 1"
        session1.commit()
        assert req1.version == 2

        # Session 2 attempts to commit with stale version 1
        req2.decision_reason = "Rejected by Actor 2"
        with pytest.raises(StaleDataError):
            session2.commit()
    finally:
        session1.close()
        session2.close()


def test_business_deletion_preserves_approval_request(db_session: Session):
    """
    Verifies ON DELETE SET NULL on business_id preserves approval requests when business is deleted.
    """
    # SQLite does not enforce foreign keys by default unless PRAGMA foreign_keys = ON is set
    db_session.execute(sa.text("PRAGMA foreign_keys = ON"))

    user = User(
        email="biz_owner@test.com",
        password_hash="dummyhash",
        display_name="Biz Owner",
        status="active",
    )
    biz = Business(name="Deletable Business", status="active")
    db_session.add_all([user, biz])
    db_session.commit()

    req = ApprovalRequest(
        business_id=biz.id,
        request_type="outlet_creation",
        target_entity_type="outlet",
        requester_user_id=user.id,
        status=ApprovalStatus.PENDING,
        payload_snapshot={"name": "Outlet 1"},
    )
    db_session.add(req)
    db_session.commit()

    # Delete business directly via SQL or session
    db_session.delete(biz)
    db_session.commit()

    # Verify approval request still exists with business_id set to NULL
    db_session.refresh(req)
    assert req.id is not None
    assert req.business_id is None
    assert req.payload_snapshot["name"] == "Outlet 1"


def test_payload_snapshot_immutability(db_session: Session):
    """
    Verifies that payload_snapshot cannot be reassigned or mutated in place.
    """
    user = User(
        email="immutability@test.com",
        password_hash="dummyhash",
        display_name="Immutability User",
        status="active",
    )
    db_session.add(user)
    db_session.commit()

    req = ApprovalRequest(
        request_type="outlet_creation",
        target_entity_type="outlet",
        requester_user_id=user.id,
        status=ApprovalStatus.PENDING,
        payload_snapshot={"name": "Original Name", "currency": "INR"},
    )
    db_session.add(req)
    db_session.commit()

    # 1. Attempt reassignment -> Rejected by validator
    with pytest.raises(ValueError, match="payload_snapshot is immutable"):
        req.payload_snapshot = {"name": "Tampered Name"}

    # 2. Attempt in-place nested mutation -> Rejected at UOW before_update flush
    req.payload_snapshot["name"] = "Tampered In-Place"
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(req, "payload_snapshot")
    with pytest.raises(ValueError, match="strictly immutable"):
        db_session.commit()

    db_session.rollback()


def test_sanitization_rules_and_sensitive_data():
    """
    Tests sanitization utilities rejecting forbidden keys, passwords, and sanitizing error traces.
    """
    # 1. Forbidden keys detection
    assert contains_forbidden_keys({"password": "secret"}) is True
    assert contains_forbidden_keys({"nested": {"owner_password": "123"}}) is True
    assert contains_forbidden_keys({"token": "xyz"}) is True
    assert contains_forbidden_keys({"normal_field": "val"}) is False

    # 2. validate_and_sanitize_payload rejects passwords
    with pytest.raises(ValueError, match="forbidden sensitive fields"):
        validate_and_sanitize_payload("business_creation", {"name": "Biz", "owner_password": "pass"})

    # 3. validate_and_sanitize_payload enforces allowlist
    with pytest.raises(ValueError, match="unauthorized fields"):
        validate_and_sanitize_payload("business_creation", {"name": "Biz", "unauthorized_extra": "hack"})

    # 4. Valid payload passes
    clean = validate_and_sanitize_payload("business_creation", {"name": "Valid Biz", "owner_email": "o@test.com"})
    assert clean["name"] == "Valid Biz"

    # 5. Diagnostic string sanitization
    raw_error = "Failed to connect to postgresql://user:supersecretpass@db.neon.tech/main?sslmode=require"
    sanitized = sanitize_diagnostic_message(raw_error)
    assert "supersecretpass" not in sanitized
    assert "[REDACTED_SECRET]" in sanitized

    # 6. Diagnostic details JSON sanitization
    details = {
        "query": "SELECT *",
        "auth": {"authorization": "Bearer eyJhbGciOi...", "headers": "ok"},
    }
    clean_details = sanitize_diagnostic_details(details)
    assert clean_details["auth"]["authorization"] == "[REDACTED]"
    assert clean_details["auth"]["headers"] == "ok"


def test_alembic_migration_0015_structure():
    m0015 = load_migration_module("0015_approval_workflow_schema.py")
    assert m0015.revision == "0015_approval_workflow_schema"
    assert m0015.down_revision == "0014_add_missing_tenant_indexes"
    assert callable(m0015.upgrade)
    assert callable(m0015.downgrade)


def test_migration_0015_upgrade_downgrade_sqlite():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect

    m0015 = load_migration_module("0015_approval_workflow_schema.py")

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(sa.text("""
            CREATE TABLE users (
                id CHAR(36) PRIMARY KEY,
                created_at DATETIME,
                updated_at DATETIME,
                email VARCHAR(254) NOT NULL,
                status VARCHAR(20) NOT NULL
            )
        """))
        conn.execute(sa.text("""
            CREATE TABLE businesses (
                id CHAR(36) PRIMARY KEY,
                created_at DATETIME,
                updated_at DATETIME,
                name VARCHAR(200) NOT NULL,
                status VARCHAR(20) NOT NULL
            )
        """))
        conn.execute(sa.text("""
            CREATE TABLE outlets (
                id CHAR(36) PRIMARY KEY,
                created_at DATETIME,
                updated_at DATETIME,
                business_id CHAR(36),
                name VARCHAR(200) NOT NULL,
                status VARCHAR(20) NOT NULL
            )
        """))

    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        old_op = m0015.op
        m0015.op = op
        try:
            m0015.upgrade()

            insp = inspect(conn)
            tables = set(insp.get_table_names())
            assert "approval_requests" in tables
            assert "approval_clarifications" in tables

            cols = {c["name"] for c in insp.get_columns("approval_requests")}
            assert "id" in cols
            assert "status" in cols
            assert "execution_status" in cols
            assert "payload_snapshot" in cols
            assert "expires_at" in cols
            assert "version" in cols
            assert "retry_count" in cols
            assert "idempotency_key" in cols

            # Downgrade cleanly
            m0015.downgrade()

            insp = inspect(conn)
            post_tables = set(insp.get_table_names())
            assert "approval_requests" not in post_tables
            assert "approval_clarifications" not in post_tables
        finally:
            m0015.op = old_op
    engine.dispose()
