"""Focused API tests for Platform Approval Read Endpoints:
- GET /api/v1/platform/approvals
- GET /api/v1/platform/approvals/{request_id}

Covers:
1. Unauthenticated requests (401).
2. Authenticated users without platform access (403).
3. Role visibility: Owner, Admin, Operator.
4. List filtering by status and request_type.
5. Pagination, stable ordering, and total count.
6. Detail retrieval for authorized caller.
7. Missing request and unauthorized request access (fail closed with 404).
8. Response schema validation: excludes password hashes, sensitive tokens, raw tracebacks.
9. Empty results and invalid query parameters.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.staff.models import User
from app.modules.approvals.models import ApprovalRequest, ApprovalClarification, ApprovalStatus, ExecutionStatus
from app.modules.approvals.service import create_approval_request, add_request_clarification
from app.core.security import hash_password, create_access_token


def _create_user(db: Session, email: str, role: str = None, is_admin: bool = False, status: str = "active") -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password("password123"),
        display_name=email.split("@")[0],
        status=status,
        is_platform_admin=is_admin,
        platform_role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_header(user: User) -> dict:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


def test_unauthenticated_request_rejected(client: TestClient):
    resp = client.get("/api/v1/platform/approvals")
    assert resp.status_code == 401
    assert "detail" in resp.json()


def test_non_platform_user_forbidden(client: TestClient, db_session: Session):
    plain_user = _create_user(db_session, "plain_waiter@test.com", role=None, is_admin=False)
    resp = client.get("/api/v1/platform/approvals", headers=_auth_header(plain_user))
    assert resp.status_code == 403


def test_inactive_platform_user_denied(client: TestClient, db_session: Session):
    inactive_admin = _create_user(db_session, "inactive_admin@test.com", role="admin", is_admin=True, status="suspended")
    resp = client.get("/api/v1/platform/approvals", headers=_auth_header(inactive_admin))
    assert resp.status_code == 401  # Inactive account rejected in get_current_user


def test_contradictory_platform_user_forbidden(client: TestClient, db_session: Session):
    # Operator with is_platform_admin=True is a contradictory state that fails closed
    bad_operator = _create_user(db_session, "contradictory_op@test.com", role="operator", is_admin=True)
    resp = client.get("/api/v1/platform/approvals", headers=_auth_header(bad_operator))
    assert resp.status_code == 403


def test_list_approvals_as_platform_admin(client: TestClient, db_session: Session):
    admin = _create_user(db_session, "admin_approvals_list@test.com", role="admin", is_admin=True)
    owner = _create_user(db_session, "owner_approvals_list@test.com", role="owner", is_admin=True)

    # Seed 2 approval requests
    req1 = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Cafe Sol", "email": "sol@cafe.com"},
        justification="New business onboarding",
    )
    req2 = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="operator_creation",
        target_entity_type="user",
        payload={"email": "op_test@test.com", "display_name": "Test Op"},
        justification="Provisioning support operator",
    )

    resp = client.get("/api/v1/platform/approvals", headers=_auth_header(admin))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 2
    ids = [item["id"] for item in data["items"]]
    assert str(req1.id) in ids
    assert str(req2.id) in ids


def test_list_filtering_by_status_and_request_type(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner_filter_test@test.com", role="owner", is_admin=True)

    req_pending = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="subscription_change",
        target_entity_type="subscription",
        payload={"plan_code": "pro_kds", "billing_interval": "monthly"},
    )

    resp = client.get("/api/v1/platform/approvals?status=pending", headers=_auth_header(owner))
    assert resp.status_code == 200
    pending_items = resp.json()["items"]
    assert all(i["status"] == "pending" for i in pending_items)
    assert any(i["id"] == str(req_pending.id) for i in pending_items)

    resp_type = client.get("/api/v1/platform/approvals?request_type=subscription_change", headers=_auth_header(owner))
    assert resp_type.status_code == 200
    type_items = resp_type.json()["items"]
    assert all(i["request_type"] == "subscription_change" for i in type_items)

    resp_invalid_status = client.get("/api/v1/platform/approvals?status=non_existent_status", headers=_auth_header(owner))
    assert resp_invalid_status.status_code == 422 or resp_invalid_status.status_code == 400


def test_pagination_and_ordering(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner_pagination@test.com", role="owner", is_admin=True)

    created_ids = []
    for i in range(5):
        r = create_approval_request(
            db=db_session,
            requester=owner,
            request_type="business_creation",
            target_entity_type="business",
            payload={"name": f"Page Test Biz {i}", "email": f"page_{i}@test.com"},
        )
        created_ids.append(str(r.id))

    resp_p1 = client.get("/api/v1/platform/approvals?limit=2&offset=0", headers=_auth_header(owner))
    assert resp_p1.status_code == 200
    data_p1 = resp_p1.json()
    assert len(data_p1["items"]) == 2
    assert data_p1["limit"] == 2
    assert data_p1["offset"] == 0

    resp_p2 = client.get("/api/v1/platform/approvals?limit=2&offset=2", headers=_auth_header(owner))
    assert resp_p2.status_code == 200
    data_p2 = resp_p2.json()
    assert len(data_p2["items"]) == 2
    # Ensure disjoint sets for proper offset pagination
    p1_ids = {x["id"] for x in data_p1["items"]}
    p2_ids = {x["id"] for x in data_p2["items"]}
    assert p1_ids.isdisjoint(p2_ids)


def test_operator_visibility_restrictions(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner_for_op_check@test.com", role="owner", is_admin=True)
    operator = _create_user(db_session, "operator_view@test.com", role="operator", is_admin=False)
    other_operator = _create_user(db_session, "operator_other@test.com", role="operator", is_admin=False)

    # 1. User suspension request created by owner (privileged governance)
    req_suspension = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="user_suspension",
        target_entity_type="user",
        payload={"target_user_id": str(uuid.uuid4()), "reason": "Policy breach"},
    )

    # 2. Ordinary tenant request created by operator
    req_op_biz = create_approval_request(
        db=db_session,
        requester=operator,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Operator Cafe", "email": "op_cafe@test.com"},
    )

    # Operator listing
    resp_op = client.get("/api/v1/platform/approvals", headers=_auth_header(operator))
    assert resp_op.status_code == 200
    op_items = resp_op.json()["items"]
    op_item_ids = [item["id"] for item in op_items]

    assert str(req_op_biz.id) in op_item_ids
    assert str(req_suspension.id) not in op_item_ids  # Governance suspension hidden from operator

    # Operator detail retrieval on hidden request fails closed with 404
    resp_detail_hidden = client.get(f"/api/v1/platform/approvals/{req_suspension.id}", headers=_auth_header(operator))
    assert resp_detail_hidden.status_code == 404

    # Operator detail retrieval on authorized request succeeds
    resp_detail_allowed = client.get(f"/api/v1/platform/approvals/{req_op_biz.id}", headers=_auth_header(operator))
    assert resp_detail_allowed.status_code == 200
    assert resp_detail_allowed.json()["id"] == str(req_op_biz.id)


def test_detail_endpoint_schema_and_sensitive_exclusion(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner_detail_schema@test.com", role="owner", is_admin=True)

    req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Secure Vault Cafe", "owner_email": "vault@cafe.com"},
        justification="Confidential rollout",
    )

    add_request_clarification(
        db=db_session,
        request_id=req.id,
        actor=owner,
        clarification_type="note",
        message="Verified KYC documentation in order.",
    )

    resp = client.get(f"/api/v1/platform/approvals/{req.id}", headers=_auth_header(owner))
    assert resp.status_code == 200
    data = resp.json()

    # Verify expected schema fields
    assert data["id"] == str(req.id)
    assert data["requester_user_id"] == str(owner.id)
    assert data["requester_email"] == "owner_detail_schema@test.com"
    assert data["status"] == "pending"
    assert data["execution_status"] == "not_started"
    assert data["payload_snapshot"] == {"name": "Secure Vault Cafe", "owner_email": "vault@cafe.com"}
    assert len(data["clarifications"]) == 1
    assert data["clarifications"][0]["message"] == "Verified KYC documentation in order."

    # Zero leakage of credentials or sensitive data
    raw_text = resp.text
    assert "password_hash" not in raw_text
    assert "hashed_password" not in raw_text
    assert "password123" not in raw_text


def test_detail_endpoint_not_found(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner_404_test@test.com", role="owner", is_admin=True)
    random_id = uuid.uuid4()
    resp = client.get(f"/api/v1/platform/approvals/{random_id}", headers=_auth_header(owner))
    assert resp.status_code == 404


def test_decide_endpoint_authorized_approval(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner_decide_approve@test.com", role="owner", is_admin=True)
    admin = _create_user(db_session, "admin_decide_approve@test.com", role="admin", is_admin=True)

    # Admin requests business creation
    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Himalayan Herbs Cafe", "owner_email": "herbs@cafe.com", "owner_display_name": "Herbs Owner"},
    )

    # Owner approves request via POST /platform/approvals/{id}/decide
    resp = client.post(
        f"/api/v1/platform/approvals/{req.id}/decide",
        json={"decision": "approve", "reason": "Verified business documentation"},
        headers=_auth_header(owner),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["execution_status"] == "succeeded"
    assert data["approver_email"] == "owner_decide_approve@test.com"
    assert data["decision_reason"] == "Verified business documentation"


def test_decide_endpoint_authorized_rejection_with_reason(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner_decide_reject@test.com", role="owner", is_admin=True)
    admin = _create_user(db_session, "admin_decide_reject@test.com", role="admin", is_admin=True)

    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Duplicate Cafe", "owner_email": "dup@cafe.com", "owner_display_name": "Dup Owner"},
    )

    # Owner rejects request with reason
    resp = client.post(
        f"/api/v1/platform/approvals/{req.id}/decide",
        json={"decision": "reject", "reason": "Entity with this name already registered."},
        headers=_auth_header(owner),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["execution_status"] == "not_started"
    assert data["decision_reason"] == "Entity with this name already registered."


def test_decide_endpoint_rejection_requires_non_empty_reason(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner_empty_reject@test.com", role="owner", is_admin=True)
    admin = _create_user(db_session, "admin_empty_reject@test.com", role="admin", is_admin=True)

    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "No Reason Cafe", "owner_email": "noreason@cafe.com", "owner_display_name": "No Reason"},
    )

    # Empty reason
    resp_empty = client.post(
        f"/api/v1/platform/approvals/{req.id}/decide",
        json={"decision": "reject", "reason": ""},
        headers=_auth_header(owner),
    )
    assert resp_empty.status_code == 422

    # Whitespace only reason
    resp_ws = client.post(
        f"/api/v1/platform/approvals/{req.id}/decide",
        json={"decision": "reject", "reason": "    \t \n  "},
        headers=_auth_header(owner),
    )
    assert resp_ws.status_code == 422

    # Missing reason
    resp_none = client.post(
        f"/api/v1/platform/approvals/{req.id}/decide",
        json={"decision": "reject"},
        headers=_auth_header(owner),
    )
    assert resp_none.status_code == 422


def test_decide_endpoint_invalid_decision_value_rejected(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner_invalid_dec@test.com", role="owner", is_admin=True)
    admin = _create_user(db_session, "admin_invalid_dec@test.com", role="admin", is_admin=True)

    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Invalid Dec Cafe", "owner_email": "inv@cafe.com", "owner_display_name": "Inv Owner"},
    )

    resp = client.post(
        f"/api/v1/platform/approvals/{req.id}/decide",
        json={"decision": "maybe", "reason": "Undecided"},
        headers=_auth_header(owner),
    )
    assert resp.status_code == 422


def test_decide_endpoint_operators_cannot_decide(client: TestClient, db_session: Session):
    operator = _create_user(db_session, "op_cannot_decide@test.com", role="operator", is_admin=False)
    admin = _create_user(db_session, "admin_req_for_op@test.com", role="admin", is_admin=True)

    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Op Denied Cafe", "owner_email": "opdenied@cafe.com", "owner_display_name": "Op Denied"},
    )

    resp = client.post(
        f"/api/v1/platform/approvals/{req.id}/decide",
        json={"decision": "approve"},
        headers=_auth_header(operator),
    )
    assert resp.status_code == 403


def test_decide_endpoint_prohibited_self_approval_forbidden(client: TestClient, db_session: Session):
    admin = _create_user(db_session, "admin_prohibited_self@test.com", role="admin", is_admin=True)
    target_non_op = _create_user(db_session, "target_plain_user@test.com", role=None, is_admin=False)

    # Admin requests promoting non-operator to admin (prohibited for Admin self-approval)
    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="user_role_change",
        target_entity_type="user",
        payload={"target_user_id": str(target_non_op.id), "new_platform_role": "admin"},
    )

    resp = client.post(
        f"/api/v1/platform/approvals/{req.id}/decide",
        json={"decision": "approve", "reason": "Self-promoting non-operator"},
        headers=_auth_header(admin),
    )
    assert resp.status_code == 403

    # Verify request status remains PENDING in DB
    db_session.refresh(req)
    assert req.status == ApprovalStatus.PENDING
    assert req.execution_status == ExecutionStatus.NOT_STARTED


def test_decide_endpoint_owner_only_operations_protected_from_admin(client: TestClient, db_session: Session):
    admin = _create_user(db_session, "admin_owner_only_breach@test.com", role="admin", is_admin=True)
    target_suspended = _create_user(db_session, "target_suspended@test.com", role=None, is_admin=False, status="suspended")
    owner = _create_user(db_session, "owner_for_reactivation@test.com", role="owner", is_admin=True)

    # User reactivation request
    req = create_approval_request(
        db=db_session,
        requester=owner,
        request_type="user_reactivation",
        target_entity_type="user",
        payload={"target_user_id": str(target_suspended.id), "reason": "Security review completed"},
    )

    # Admin tries to approve Owner-only reactivation request
    resp = client.post(
        f"/api/v1/platform/approvals/{req.id}/decide",
        json={"decision": "approve", "reason": "Admin approving reactivation"},
        headers=_auth_header(admin),
    )
    assert resp.status_code == 403

    db_session.refresh(req)
    assert req.status == ApprovalStatus.PENDING


def test_decide_endpoint_already_decided_or_expired_rejected(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner_stale_check@test.com", role="owner", is_admin=True)
    admin = _create_user(db_session, "admin_stale_check@test.com", role="admin", is_admin=True)

    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Stale Cafe", "owner_email": "stale@cafe.com", "owner_display_name": "Stale Owner"},
    )

    # First decision approves
    resp1 = client.post(
        f"/api/v1/platform/approvals/{req.id}/decide",
        json={"decision": "approve", "reason": "Approved initially"},
        headers=_auth_header(owner),
    )
    assert resp1.status_code == 200

    # Second decision attempts to reject already approved request
    resp2 = client.post(
        f"/api/v1/platform/approvals/{req.id}/decide",
        json={"decision": "reject", "reason": "Late rejection"},
        headers=_auth_header(owner),
    )
    assert resp2.status_code == 422


def test_decide_endpoint_not_found(client: TestClient, db_session: Session):
    owner = _create_user(db_session, "owner_decide_404@test.com", role="owner", is_admin=True)
    random_id = uuid.uuid4()
    resp = client.post(
        f"/api/v1/platform/approvals/{random_id}/decide",
        json={"decision": "approve", "reason": "Valid reason but missing id"},
        headers=_auth_header(owner),
    )
    assert resp.status_code == 404



def test_decide_endpoint_simulated_uncertain_commit(client: TestClient, db_session: Session, monkeypatch):
    from unittest.mock import MagicMock
    from app.core.errors import CommitOutcomeUncertainError
    import app.api.v1.approvals as approvals_api

    owner = _create_user(db_session, "owner_uncertain_commit@test.com", role="owner", is_admin=True)
    admin = _create_user(db_session, "admin_uncertain_commit@test.com", role="admin", is_admin=True)

    req = create_approval_request(
        db=db_session,
        requester=admin,
        request_type="business_creation",
        target_entity_type="business",
        payload={"name": "Uncertain Cafe", "owner_email": "unc@cafe.com", "owner_display_name": "Uncertain Owner"},
    )

    def mock_decide(*args, **kwargs):
        raise CommitOutcomeUncertainError(
            message="Commit outcome uncertain: transport error during commit acknowledgment. Request state preserved.",
            code="COMMIT_OUTCOME_UNCERTAIN",
            details={"request_id": str(req.id), "error": "Simulated transport timeout"},
        )

    monkeypatch.setattr(approvals_api, "decide_approval_request", mock_decide)

    resp = client.post(
        f"/api/v1/platform/approvals/{req.id}/decide",
        json={"decision": "approve", "reason": "Proceeding despite transport risk"},
        headers=_auth_header(owner),
    )
    assert resp.status_code == 503
    data = resp.json()
    assert data["detail"]["error"]["code"] == "COMMIT_OUTCOME_UNCERTAIN"

