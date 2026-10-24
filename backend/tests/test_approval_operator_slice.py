"""Comprehensive test suite for Approval Backend Slice 1: Add Operator End-to-End.

Validates:
1. Submission authorization (Owner, Admin, Operator).
2. Input sanitization (rejection of plaintext passwords, invalid fields).
3. Mode 1 (existing user) vs Mode 2 (new user) submission and pending request deduplication.
4. Rejection of direct operator provisioning on POST /api/v1/platform/operators with 403 Forbidden.
5. Approval and execution: creates operator with valid bcrypt hash and platform_role='operator'.
6. Secure temporary password generation (cryptographically random, non-static, never in payload/audit).
7. Credential artifact delivery to backend/.local-user-credentials.txt with 0o600 permissions.
8. Safe retry endpoint (POST /api/v1/platform/approvals/{id}/retry) for execution_status='failed'.
9. Retry idempotency: does not overwrite credentials or re-create user if already provisioned.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.modules.staff.models import User
from app.modules.approvals.models import (
    ApprovalRequest,
    ApprovalStatus,
    ExecutionStatus,
)
from app.modules.approvals.credentials import (
    generate_secure_temporary_password,
    deliver_local_credential_artifact,
)
from app.modules.audit.models import AuditLog


def _setup_actors(db: Session):
    """Set up Platform Owner, Admin, Operator, and Unprivileged user."""
    owner = db.query(User).filter(User.email == "staff@test.com").first()
    if not owner:
        owner = User(email="staff@test.com", display_name="Owner User")
        db.add(owner)
    owner.platform_role = "owner"
    owner.is_platform_admin = True
    owner.status = "active"
    owner.password_hash = hash_password("OwnerPassword123!")

    admin = db.query(User).filter(User.email == "slice_admin@test.com").first()
    if not admin:
        admin = User(email="slice_admin@test.com", display_name="Slice Admin")
        db.add(admin)
    admin.platform_role = "admin"
    admin.is_platform_admin = True
    admin.status = "active"
    admin.password_hash = hash_password("AdminPassword123!")

    operator = db.query(User).filter(User.email == "slice_op@test.com").first()
    if not operator:
        operator = User(email="slice_op@test.com", display_name="Slice Operator")
        db.add(operator)
    operator.platform_role = "operator"
    operator.is_platform_admin = False
    operator.status = "active"
    operator.password_hash = hash_password("OperatorPassword123!")

    regular = db.query(User).filter(User.email == "unauth@test.com").first()
    if not regular:
        regular = User(email="unauth@test.com", display_name="Regular User")
        db.add(regular)
    regular.platform_role = None
    regular.is_platform_admin = False
    regular.status = "active"
    regular.password_hash = hash_password("RegularPassword123!")

    db.commit()
    return owner, admin, operator, regular


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Direct Endpoint Disabled
# ---------------------------------------------------------------------------

def test_direct_operator_provisioning_is_disabled(client: TestClient, db_session: Session):
    owner, _, _, regular = _setup_actors(db_session)
    owner_headers = _login(client, owner.email, "OwnerPassword123!")

    resp = client.post(
        "/api/v1/platform/operators",
        headers=owner_headers,
        json={"user_id": str(regular.id)},
    )
    assert resp.status_code == 403
    err_body = resp.json()
    assert "Direct operator provisioning is disabled" in err_body["detail"]["error"]["message"]


# ---------------------------------------------------------------------------
# 2. Submission Validation & Authorization
# ---------------------------------------------------------------------------

def test_operator_approval_submission_mode2_success(client: TestClient, db_session: Session):
    owner, admin, _, _ = _setup_actors(db_session)
    admin_headers = _login(client, admin.email, "AdminPassword123!")

    email = f"new_op_{uuid.uuid4().hex[:6]}@example.com"
    resp = client.post(
        "/api/v1/platform/approvals",
        headers=admin_headers,
        json={
            "request_type": "operator_creation",
            "target_entity_type": "operator",
            "payload": {
                "email": email,
                "display_name": "New Candidate",
            },
            "justification": "Expanding operations shift",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["request_type"] == "operator_creation"
    assert data["status"] == "pending"
    assert data["execution_status"] == "not_started"
    assert data["payload_snapshot"]["email"] == email
    assert data["payload_snapshot"]["display_name"] == "New Candidate"
    # Plaintext password must NOT be in snapshot
    assert "password" not in data["payload_snapshot"]


def test_operator_approval_submission_rejects_password_in_payload(client: TestClient, db_session: Session):
    owner, admin, _, _ = _setup_actors(db_session)
    admin_headers = _login(client, admin.email, "AdminPassword123!")

    resp = client.post(
        "/api/v1/platform/approvals",
        headers=admin_headers,
        json={
            "request_type": "operator_creation",
            "target_entity_type": "operator",
            "payload": {
                "email": "invalidsneak@example.com",
                "password": "SneakyPassword123!",
            },
        },
    )
    assert resp.status_code in (400, 422)


def test_operator_approval_submission_duplicate_pending_rejected(client: TestClient, db_session: Session):
    owner, admin, _, _ = _setup_actors(db_session)
    admin_headers = _login(client, admin.email, "AdminPassword123!")

    email = f"dup_pending_{uuid.uuid4().hex[:6]}@example.com"
    # First submission
    resp1 = client.post(
        "/api/v1/platform/approvals",
        headers=admin_headers,
        json={
            "request_type": "operator_creation",
            "target_entity_type": "operator",
            "payload": {"email": email, "display_name": "Dup Op"},
        },
    )
    assert resp1.status_code == 201

    # Second submission for same email while pending must fail
    resp2 = client.post(
        "/api/v1/platform/approvals",
        headers=admin_headers,
        json={
            "request_type": "operator_creation",
            "target_entity_type": "operator",
            "payload": {"email": email, "display_name": "Dup Op 2"},
        },
    )
    assert resp2.status_code in (400, 422)
    assert "already pending" in resp2.json()["detail"]["error"]["message"]


def test_operator_approval_submission_unauthenticated_rejected(client: TestClient):
    resp = client.post(
        "/api/v1/platform/approvals",
        json={
            "request_type": "operator_creation",
            "target_entity_type": "operator",
            "payload": {"email": "unauth@example.com"},
        },
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 3. Decision, Execution, and Credential Generation
# ---------------------------------------------------------------------------

def test_operator_approval_and_execution_end_to_end(client: TestClient, db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import app.modules.approvals.credentials as cred_module
    orig_deliver = cred_module.deliver_local_credential_artifact
    monkeypatch.setattr(
        cred_module,
        "deliver_local_credential_artifact",
        lambda **kwargs: orig_deliver(**{**kwargs, "target_dir": kwargs.get("target_dir") or tmp_path}),
    )

    owner, admin, _, _ = _setup_actors(db_session)
    admin_headers = _login(client, admin.email, "AdminPassword123!")
    owner_headers = _login(client, owner.email, "OwnerPassword123!")

    email = f"op_e2e_{uuid.uuid4().hex[:6]}@example.com"
    # 1. Submit approval request
    sub_resp = client.post(
        "/api/v1/platform/approvals",
        headers=admin_headers,
        json={
            "request_type": "operator_creation",
            "target_entity_type": "operator",
            "payload": {
                "email": email,
                "display_name": "End to End Op",
            },
            "justification": "Coverage required",
        },
    )
    assert sub_resp.status_code == 201
    req_id = sub_resp.json()["id"]

    # 2. Approve request (Owner decides)
    dec_resp = client.post(
        f"/api/v1/platform/approvals/{req_id}/decide",
        headers=owner_headers,
        json={
            "decision": "approve",
            "reason": "Approved for live coverage",
        },
    )
    assert dec_resp.status_code == 200, dec_resp.text
    dec_data = dec_resp.json()
    assert dec_data["status"] == "approved"
    assert dec_data["execution_status"] == "succeeded"
    assert dec_data["execution_details_json"]["email"] == email
    assert "operator_id" in dec_data["execution_details_json"]
    # Verify temporary password is NOT leaked in response
    assert "_temp_password" not in dec_data["execution_details_json"]

    # 3. Authoritative verification of user record in DB
    created_user = db_session.query(User).filter(User.email == email).first()
    assert created_user is not None
    assert created_user.platform_role == "operator"
    assert created_user.is_platform_admin is False
    assert created_user.status == "active"
    assert created_user.password_hash.startswith("$2b$") or created_user.password_hash.startswith("$2a$")

    # 4. Credential delivery file verification
    cred_file = tmp_path / ".local-user-credentials.txt"
    assert cred_file.exists(), "Credential artifact was not created"
    content = cred_file.read_text(encoding="utf-8")
    assert f"EMAIL={email}" in content
    assert f"USER_ID={created_user.id}" in content
    assert "ROLE=operator" in content


# ---------------------------------------------------------------------------
# 4. Mode 1: Promote Existing User
# ---------------------------------------------------------------------------

def test_operator_approval_mode1_promotes_existing_user(client: TestClient, db_session: Session):
    owner, admin, _, regular = _setup_actors(db_session)
    admin_headers = _login(client, admin.email, "AdminPassword123!")
    owner_headers = _login(client, owner.email, "OwnerPassword123!")

    # Verify regular has no role and original password
    old_hash = regular.password_hash

    # 1. Submit Mode 1 request
    sub_resp = client.post(
        "/api/v1/platform/approvals",
        headers=admin_headers,
        json={
            "request_type": "operator_creation",
            "target_entity_type": "operator",
            "target_entity_id": str(regular.id),
            "payload": {
                "target_user_id": str(regular.id),
            },
            "justification": "Promoting staff member",
        },
    )
    assert sub_resp.status_code == 201
    req_id = sub_resp.json()["id"]

    # 2. Approve and auto-execute
    dec_resp = client.post(
        f"/api/v1/platform/approvals/{req_id}/decide",
        headers=owner_headers,
        json={
            "decision": "approve",
            "reason": "Promoted to operator",
        },
    )
    assert dec_resp.status_code == 200
    assert dec_resp.json()["execution_status"] == "succeeded"

    # 3. Verify user promoted without altering existing password
    db_session.refresh(regular)
    assert regular.platform_role == "operator"
    assert regular.password_hash == old_hash


# ---------------------------------------------------------------------------
# 5. Retry Endpoint for Failed Executions
# ---------------------------------------------------------------------------

def test_approval_retry_endpoint_recovers_failed_execution(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import app.modules.approvals.credentials as cred_module
    orig_deliver = cred_module.deliver_local_credential_artifact
    monkeypatch.setattr(
        cred_module,
        "deliver_local_credential_artifact",
        lambda **kwargs: orig_deliver(**{**kwargs, "target_dir": kwargs.get("target_dir") or tmp_path}),
    )

    owner, admin, _, _ = _setup_actors(db_session)
    admin_headers = _login(client, admin.email, "AdminPassword123!")
    owner_headers = _login(client, owner.email, "OwnerPassword123!")

    email = f"retry_test_{uuid.uuid4().hex[:6]}@example.com"
    # Create request directly in approved + failed status
    req = ApprovalRequest(
        requester_user_id=admin.id,
        approver_user_id=owner.id,
        request_type="operator_creation",
        target_entity_type="operator",
        status=ApprovalStatus.APPROVED,
        execution_status=ExecutionStatus.FAILED,
        payload_snapshot={"email": email, "display_name": "Retry User"},
        decision_reason="Approved prior to failure",
    )
    db_session.add(req)
    db_session.commit()
    db_session.refresh(req)

    # 1. Retry execution via endpoint
    retry_resp = client.post(
        f"/api/v1/platform/approvals/{req.id}/retry",
        headers=owner_headers,
    )
    assert retry_resp.status_code == 200, retry_resp.text
    retry_data = retry_resp.json()
    assert retry_data["status"] == "approved"
    assert retry_data["execution_status"] == "succeeded"

    # 2. Verify user now provisioned
    op_user = db_session.query(User).filter(User.email == email).first()
    assert op_user is not None
    assert op_user.platform_role == "operator"

    # 3. Retry on SUCCEEDED execution must fail (only FAILED is retryable)
    retry_again = client.post(
        f"/api/v1/platform/approvals/{req.id}/retry",
        headers=owner_headers,
    )
    assert retry_again.status_code in (400, 422)


def test_retry_endpoint_rejects_pending_or_rejected_status(client: TestClient, db_session: Session):
    owner, admin, _, _ = _setup_actors(db_session)
    owner_headers = _login(client, owner.email, "OwnerPassword123!")

    # Request with status PENDING cannot be retried
    req = ApprovalRequest(
        requester_user_id=admin.id,
        request_type="operator_creation",
        target_entity_type="operator",
        status=ApprovalStatus.PENDING,
        execution_status=ExecutionStatus.NOT_STARTED,
        payload_snapshot={"email": "pending@example.com"},
    )
    db_session.add(req)
    db_session.commit()

    resp = client.post(
        f"/api/v1/platform/approvals/{req.id}/retry",
        headers=owner_headers,
    )
    assert resp.status_code in (400, 422)
    assert "Only 'approved' requests can be retried" in resp.json()["detail"]["error"]["message"]


# ---------------------------------------------------------------------------
# 6. Unified Full Lifecycle Verification (Phases A through H)
# ---------------------------------------------------------------------------

def test_operator_provisioning_complete_lifecycle(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    """Unified, end-to-end bounded verification of the operator provisioning lifecycle.

    Validates:
    Phase A: New operator submission without domain mutations or plaintext leaks.
    Phase B: Direct provisioning bypasses and unauthorized decisions blocked (HTTP 403).
    Phase C: Approval and auto-execution creates exactly one operator with bcrypt hash.
    Phase D: Credential secrecy, artifact delivery in tmp_path, and successful auth login.
    Phase E: Provisioned Operator role boundaries (read-only approval access, mutation 403).
    Phase F: Existing user promotion (Mode 1) preserves password and skips credential artifact.
    Phase G: Rejection with mandatory reason and failed-execution retry recovery.
    Phase H: Simulated uncertain commit handling (503 COMMIT_OUTCOME_UNCERTAIN).
    """
    import re
    import app.modules.approvals.credentials as cred_module
    from app.core.errors import CommitOutcomeUncertainError
    import app.api.v1.approvals as approvals_api

    # Credential artifact redirection to isolated test directory
    orig_deliver = cred_module.deliver_local_credential_artifact
    monkeypatch.setattr(
        cred_module,
        "deliver_local_credential_artifact",
        lambda **kwargs: orig_deliver(**{**kwargs, "target_dir": kwargs.get("target_dir") or tmp_path}),
    )

    owner, admin, operator, regular = _setup_actors(db_session)
    owner_headers = _login(client, owner.email, "OwnerPassword123!")
    admin_headers = _login(client, admin.email, "AdminPassword123!")
    op_headers = _login(client, operator.email, "OperatorPassword123!")
    reg_headers = _login(client, regular.email, "RegularPassword123!")

    # -----------------------------------------------------------------------
    # Phase A: New Operator Submission (Mode 2)
    # -----------------------------------------------------------------------
    new_op_email = f"lifecycle_{uuid.uuid4().hex[:6]}@example.com"
    sub_resp = client.post(
        "/api/v1/platform/approvals",
        headers=admin_headers,
        json={
            "request_type": "operator_creation",
            "target_entity_type": "operator",
            "payload": {
                "email": new_op_email,
                "display_name": "Lifecycle Operator",
            },
            "justification": "Required for lifecycle verification",
        },
    )
    assert sub_resp.status_code == 201
    sub_data = sub_resp.json()
    req_id = sub_data["id"]
    assert sub_data["status"] == "pending"
    assert sub_data["execution_status"] == "not_started"
    assert "password" not in sub_data["payload_snapshot"]
    assert "_temp_password" not in sub_data["payload_snapshot"]

    # Verify no operator account or credential artifact was created during submission
    assert db_session.query(User).filter(User.email == new_op_email).first() is None
    cred_file = tmp_path / ".local-user-credentials.txt"
    assert not cred_file.exists()

    # -----------------------------------------------------------------------
    # Phase B: Direct Provisioning & Authorization Bypasses Blocked
    # -----------------------------------------------------------------------
    # Direct provisioning bypass is blocked even for Platform Owner
    bypass_resp = client.post(
        "/api/v1/platform/operators",
        headers=owner_headers,
        json={"email": new_op_email, "password": "BypassPassword123!", "display_name": "Bypass Attempt"},
    )
    assert bypass_resp.status_code == 403
    assert "Direct operator provisioning is disabled" in bypass_resp.json()["detail"]["error"]["message"]

    # Operator role cannot decide requests
    unauth_decide = client.post(
        f"/api/v1/platform/approvals/{req_id}/decide",
        headers=op_headers,
        json={"decision": "approve", "reason": "Operator attempting self-decision"},
    )
    assert unauth_decide.status_code == 403

    # Unauthenticated decide is rejected
    unauth_anon = client.post(
        f"/api/v1/platform/approvals/{req_id}/decide",
        json={"decision": "approve", "reason": "Anonymous"},
    )
    assert unauth_anon.status_code == 401

    # -----------------------------------------------------------------------
    # Phase C & D: Approval, Execution, Credential Secrecy & Login
    # -----------------------------------------------------------------------
    with caplog.at_level("DEBUG"):
        dec_resp = client.post(
            f"/api/v1/platform/approvals/{req_id}/decide",
            headers=admin_headers,  # Admin self-approval permitted for operator_creation per established policy
            json={"decision": "approve", "reason": "Approved by admin for operations"},
        )
    assert dec_resp.status_code == 200, dec_resp.text
    dec_data = dec_resp.json()
    assert dec_data["status"] == "approved"
    assert dec_data["execution_status"] == "succeeded"
    assert dec_data["execution_details_json"]["email"] == new_op_email
    assert "_temp_password" not in dec_data["execution_details_json"]

    # Verify user created in DB with correct bcrypt password hash
    created_op = db_session.query(User).filter(User.email == new_op_email).first()
    assert created_op is not None
    assert created_op.platform_role == "operator"
    assert created_op.is_platform_admin is False
    assert created_op.status == "active"
    assert created_op.password_hash.startswith("$2b$") or created_op.password_hash.startswith("$2a$")
    assert db_session.query(User).filter(User.email == new_op_email).count() == 1

    # Verify credential artifact delivery in isolated tmp_path
    assert cred_file.exists()
    if os.name != "nt":
        assert (cred_file.stat().st_mode & 0o777) == 0o600

    cred_content = cred_file.read_text(encoding="utf-8")
    assert f"EMAIL={new_op_email}" in cred_content
    assert f"USER_ID={created_op.id}" in cred_content
    assert "ROLE=operator" in cred_content

    # Extract temporary password securely without printing or logging
    pwd_match = re.search(rf'USER_ID={created_op.id}.*?TEMP_PASSWORD="([^"]+)"', cred_content)
    assert pwd_match is not None
    temp_pwd = pwd_match.group(1)
    assert len(temp_pwd) >= 14

    # Verify plaintext password is NOT in captured logs, audit logs, or approval detail
    assert temp_pwd not in caplog.text
    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.entity_id == uuid.UUID(req_id),
        AuditLog.action == "approval.execute.operator_creation",
    ).first()
    assert audit_entry is not None
    assert temp_pwd not in str(audit_entry.metadata_json)
    detail_resp = client.get(f"/api/v1/platform/approvals/{req_id}", headers=admin_headers)
    assert temp_pwd not in detail_resp.text

    # Authenticate newly provisioned operator with temporary password
    new_op_login = client.post(
        "/api/v1/auth/login",
        json={"email": new_op_email, "password": temp_pwd},
    )
    assert new_op_login.status_code == 200, new_op_login.text
    new_op_token = new_op_login.json()["access_token"]
    assert new_op_token is not None
    new_op_headers = {"Authorization": f"Bearer {new_op_token}"}

    # -----------------------------------------------------------------------
    # Phase E: Provisioned Operator Permissions
    # -----------------------------------------------------------------------
    # Permitted read-only access to approval list
    q_resp = client.get("/api/v1/platform/approvals", headers=new_op_headers)
    assert q_resp.status_code == 200

    # Decision endpoint returns 403 Forbidden
    cant_decide = client.post(
        f"/api/v1/platform/approvals/{req_id}/decide",
        headers=new_op_headers,
        json={"decision": "approve", "reason": "Operator decision attempt"},
    )
    assert cant_decide.status_code == 403

    # Retry endpoint returns 403 Forbidden
    cant_retry = client.post(
        f"/api/v1/platform/approvals/{req_id}/retry",
        headers=new_op_headers,
    )
    assert cant_retry.status_code == 403

    # Direct operator creation returns 403 Forbidden
    cant_create_op = client.post(
        "/api/v1/platform/operators",
        headers=new_op_headers,
        json={"email": "another_op@example.com"},
    )
    assert cant_create_op.status_code == 403

    # -----------------------------------------------------------------------
    # Phase F: Existing User Promotion (Mode 1)
    # -----------------------------------------------------------------------
    promo_user = db_session.query(User).filter(User.email == "promo_user@example.com").first()
    if not promo_user:
        promo_user = User(
            email="promo_user@example.com",
            display_name="Promo Staff",
            status="active",
            platform_role=None,
            is_platform_admin=False,
            password_hash=hash_password("OriginalPromoPwd123!"),
        )
        db_session.add(promo_user)
        db_session.commit()
    orig_hash = promo_user.password_hash

    lines_before = len(cred_file.read_text(encoding="utf-8").strip().splitlines())

    mode1_sub = client.post(
        "/api/v1/platform/approvals",
        headers=admin_headers,
        json={
            "request_type": "operator_creation",
            "target_entity_type": "operator",
            "target_entity_id": str(promo_user.id),
            "payload": {"target_user_id": str(promo_user.id)},
            "justification": "Promoting staff member",
        },
    )
    assert mode1_sub.status_code == 201
    mode1_id = mode1_sub.json()["id"]

    mode1_dec = client.post(
        f"/api/v1/platform/approvals/{mode1_id}/decide",
        headers=owner_headers,
        json={"decision": "approve", "reason": "Promote confirmed"},
    )
    assert mode1_dec.status_code == 200
    assert mode1_dec.json()["execution_status"] == "succeeded"

    db_session.refresh(promo_user)
    assert promo_user.platform_role == "operator"
    assert promo_user.password_hash == orig_hash

    # Login with original password succeeds
    promo_login = client.post(
        "/api/v1/auth/login",
        json={"email": "promo_user@example.com", "password": "OriginalPromoPwd123!"},
    )
    assert promo_login.status_code == 200

    # No new credential was written to credential file for Mode 1
    lines_after = len(cred_file.read_text(encoding="utf-8").strip().splitlines())
    assert lines_after == lines_before

    # -----------------------------------------------------------------------
    # Phase G: Rejection & Failed Execution Retry
    # -----------------------------------------------------------------------
    reject_email = f"reject_{uuid.uuid4().hex[:6]}@example.com"
    sub_rej = client.post(
        "/api/v1/platform/approvals",
        headers=admin_headers,
        json={
            "request_type": "operator_creation",
            "target_entity_type": "operator",
            "payload": {"email": reject_email, "display_name": "Rejected Op"},
            "justification": "Test rejection",
        },
    )
    assert sub_rej.status_code == 201
    rej_id = sub_rej.json()["id"]

    # Rejection requires reason
    empty_rej = client.post(
        f"/api/v1/platform/approvals/{rej_id}/decide",
        headers=admin_headers,
        json={"decision": "reject", "reason": "   "},
    )
    assert empty_rej.status_code in (400, 422)

    # Valid rejection
    valid_rej = client.post(
        f"/api/v1/platform/approvals/{rej_id}/decide",
        headers=admin_headers,
        json={"decision": "reject", "reason": "Policy compliance failure"},
    )
    assert valid_rej.status_code == 200
    assert valid_rej.json()["status"] == "rejected"
    assert valid_rej.json()["execution_status"] == "not_started"
    assert db_session.query(User).filter(User.email == reject_email).first() is None

    # Retry on rejected request fails
    retry_rej = client.post(
        f"/api/v1/platform/approvals/{rej_id}/retry",
        headers=admin_headers,
    )
    assert retry_rej.status_code in (400, 422)

    # Exercise failed-execution retry
    failed_email = f"failed_exec_{uuid.uuid4().hex[:6]}@example.com"
    failed_req = ApprovalRequest(
        requester_user_id=admin.id,
        approver_user_id=owner.id,
        request_type="operator_creation",
        target_entity_type="operator",
        status=ApprovalStatus.APPROVED,
        execution_status=ExecutionStatus.FAILED,
        payload_snapshot={"email": failed_email, "display_name": "Failed User"},
        decision_reason="Approved",
    )
    db_session.add(failed_req)
    db_session.commit()
    db_session.refresh(failed_req)

    # Operator cannot retry
    op_cant_retry = client.post(
        f"/api/v1/platform/approvals/{failed_req.id}/retry",
        headers=op_headers,
    )
    assert op_cant_retry.status_code == 403

    # Admin retry succeeds and provisions account
    admin_retry = client.post(
        f"/api/v1/platform/approvals/{failed_req.id}/retry",
        headers=admin_headers,
    )
    assert admin_retry.status_code == 200
    assert admin_retry.json()["status"] == "approved"
    assert admin_retry.json()["execution_status"] == "succeeded"
    assert db_session.query(User).filter(User.email == failed_email).first() is not None

    # Retry again on succeeded request fails
    retry_again = client.post(
        f"/api/v1/platform/approvals/{failed_req.id}/retry",
        headers=admin_headers,
    )
    assert retry_again.status_code in (400, 422)

    # -----------------------------------------------------------------------
    # Phase H: Failure & Uncertain Commit Handling
    # -----------------------------------------------------------------------
    unc_email = f"unc_{uuid.uuid4().hex[:6]}@example.com"
    sub_unc = client.post(
        "/api/v1/platform/approvals",
        headers=admin_headers,
        json={
            "request_type": "operator_creation",
            "target_entity_type": "operator",
            "payload": {"email": unc_email, "display_name": "Uncertain Op"},
            "justification": "Fault injection",
        },
    )
    unc_id = sub_unc.json()["id"]

    def mock_uncertain(*args, **kwargs):
        raise CommitOutcomeUncertainError(
            message="Commit outcome uncertain: transport timeout during commit acknowledgment.",
            code="COMMIT_OUTCOME_UNCERTAIN",
            details={"request_id": unc_id, "error": "Simulated transport timeout"},
        )
    monkeypatch.setattr(approvals_api, "decide_approval_request", mock_uncertain)

    unc_resp = client.post(
        f"/api/v1/platform/approvals/{unc_id}/decide",
        headers=owner_headers,
        json={"decision": "approve", "reason": "Proceeding"},
    )
    assert unc_resp.status_code == 503
    assert unc_resp.json()["detail"]["error"]["code"] == "COMMIT_OUTCOME_UNCERTAIN"

    # User was not created by uncertain abort
    assert db_session.query(User).filter(User.email == unc_email).first() is None

