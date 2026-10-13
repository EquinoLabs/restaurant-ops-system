import pytest
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.modules.staff.models import User, OutletMembership
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.audit.models import AuditLog
from app.core.security import hash_password, verify_password
from app.core.errors import (
    NotFoundError,
    ValidationError,
    ForbiddenError,
)
from app.modules.businesses.schemas import PlatformOperatorCreateRequest
from app.modules.businesses.platform_service import (
    create_platform_operator,
    revoke_platform_operator,
    list_platform_operators,
)


def _setup_owner_and_users(
    db_session: Session,
):
    """Helper to set up standard test users in the database."""
    # Active Platform Owner
    owner = db_session.query(User).filter(User.email == "staff@test.com").first()
    owner.platform_role = "owner"
    owner.is_platform_admin = True
    owner.status = "active"
    owner.password_hash = hash_password("OwnerPassword123!")

    # Active regular user (unauth@test.com)
    target = db_session.query(User).filter(User.email == "unauth@test.com").first()
    target.platform_role = None
    target.is_platform_admin = False
    target.status = "active"
    target.password_hash = hash_password("TargetPassword123!")

    # Create additional users if needed
    admin = db_session.query(User).filter(User.email == "admin_test@test.com").first()
    if not admin:
        admin = User(
            email="admin_test@test.com",
            display_name="Test Admin",
            password_hash=hash_password("AdminPassword123!"),
            status="active",
            is_platform_admin=True,
            platform_role="admin",
        )
        db_session.add(admin)

    db_session.commit()
    db_session.refresh(owner)
    db_session.refresh(target)
    db_session.refresh(admin)
    return owner, target, admin


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed for {email}: {resp.json()}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. Mode 1: Existing-User Assignment (POST /api/v1/platform/operators)
# ==============================================================================

def test_create_operator_mode1_success(client: TestClient, db_session: Session):
    owner, target, _ = _setup_owner_and_users(db_session)
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        "/api/v1/platform/operators",
        headers=headers,
        json={"user_id": str(target.id)},
    )
    assert resp.status_code == 200, resp.json()
    data = resp.json()

    assert data["id"] == str(target.id)
    assert data["email"] == target.email
    assert data["platform_role"] == "operator"
    assert data["is_platform_admin"] is False
    assert data["status"] == "active"

    # DB verification
    db_session.refresh(target)
    assert target.platform_role == "operator"
    assert target.is_platform_admin is False

    # Audit log verification
    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.operator.create",
        AuditLog.entity_id == target.id,
    ).first()
    assert audit is not None
    assert audit.actor_user_id == owner.id
    assert audit.metadata_json["outcome"] == "success"
    assert audit.metadata_json["mode"] == "existing_user"
    assert audit.metadata_json["previous_role"] is None
    assert audit.metadata_json["new_role"] == "operator"


def test_create_operator_mode1_demotes_admin(client: TestClient, db_session: Session):
    owner, _, admin = _setup_owner_and_users(db_session)
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        "/api/v1/platform/operators",
        headers=headers,
        json={"user_id": str(admin.id)},
    )
    assert resp.status_code == 200, resp.json()
    data = resp.json()

    assert data["id"] == str(admin.id)
    assert data["platform_role"] == "operator"
    assert data["is_platform_admin"] is False

    # DB verification: admin is demoted
    db_session.refresh(admin)
    assert admin.platform_role == "operator"
    assert admin.is_platform_admin is False

    # Audit log records previous_role="admin"
    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.operator.create",
        AuditLog.entity_id == admin.id,
    ).first()
    assert audit is not None
    assert audit.metadata_json["previous_role"] == "admin"
    assert audit.metadata_json["new_role"] == "operator"


def test_create_operator_mode1_idempotent(client: TestClient, db_session: Session):
    owner, target, _ = _setup_owner_and_users(db_session)
    target.platform_role = "operator"
    target.is_platform_admin = False
    db_session.commit()

    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    initial_audit_count = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.operator.create"
    ).count()

    resp = client.post(
        "/api/v1/platform/operators",
        headers=headers,
        json={"user_id": str(target.id)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["platform_role"] == "operator"
    assert data["is_platform_admin"] is False

    # No duplicate audit log
    after_audit_count = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.operator.create"
    ).count()
    assert after_audit_count == initial_audit_count


def test_create_operator_mode1_nonexistent_user(client: TestClient, db_session: Session):
    _setup_owner_and_users(db_session)
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    fake_id = uuid.uuid4()
    resp = client.post(
        "/api/v1/platform/operators",
        headers=headers,
        json={"user_id": str(fake_id)},
    )
    assert resp.status_code == 404
    assert f"Target user with ID '{fake_id}' not found" in resp.json()["detail"]["error"]["message"]


def test_create_operator_mode1_suspended_user(client: TestClient, db_session: Session):
    _, target, _ = _setup_owner_and_users(db_session)
    target.status = "suspended"
    db_session.commit()

    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        "/api/v1/platform/operators",
        headers=headers,
        json={"user_id": str(target.id)},
    )
    assert resp.status_code == 422
    assert "Cannot assign Operator role to user with status 'suspended'" in resp.json()["detail"]["error"]["message"]


def test_create_operator_mode1_owner_target_rejected(client: TestClient, db_session: Session):
    owner, _, _ = _setup_owner_and_users(db_session)
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        "/api/v1/platform/operators",
        headers=headers,
        json={"user_id": str(owner.id)},
    )
    assert resp.status_code == 422
    assert "Platform Owner cannot be demoted to Operator" in resp.json()["detail"]["error"]["message"]


# ==============================================================================
# 2. Mode 2: New-User Creation (POST /api/v1/platform/operators)
# ==============================================================================

def test_create_operator_mode2_success(client: TestClient, db_session: Session):
    owner, _, _ = _setup_owner_and_users(db_session)
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    new_email = f"new_operator_{uuid.uuid4().hex[:6]}@test.com"
    resp = client.post(
        "/api/v1/platform/operators",
        headers=headers,
        json={
            "email": new_email,
            "password": "SecurePassword123!",
            "display_name": "New Operator",
        },
    )
    assert resp.status_code == 200, resp.json()
    data = resp.json()

    assert data["email"] == new_email
    assert data["display_name"] == "New Operator"
    assert data["status"] == "active"
    assert data["platform_role"] == "operator"
    assert data["is_platform_admin"] is False

    # DB verification
    created_user = db_session.query(User).filter(User.email == new_email).first()
    assert created_user is not None
    assert created_user.platform_role == "operator"
    assert created_user.is_platform_admin is False
    assert created_user.status == "active"

    # Audit log verification
    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.operator.create",
        AuditLog.entity_id == created_user.id,
    ).first()
    assert audit is not None
    assert audit.metadata_json["outcome"] == "success"
    assert audit.metadata_json["mode"] == "new_user"


def test_create_operator_mode2_password_hashing(client: TestClient, db_session: Session):
    _setup_owner_and_users(db_session)
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    new_email = f"hashed_op_{uuid.uuid4().hex[:6]}@test.com"
    raw_password = "SecretPassword123!"
    resp = client.post(
        "/api/v1/platform/operators",
        headers=headers,
        json={
            "email": new_email,
            "password": raw_password,
            "display_name": "Hashed Operator",
        },
    )
    assert resp.status_code == 200
    created_user = db_session.query(User).filter(User.email == new_email).first()
    assert created_user.password_hash != raw_password
    assert verify_password(raw_password, created_user.password_hash) is True


def test_create_operator_mode2_duplicate_email_rejected(client: TestClient, db_session: Session):
    _, target, _ = _setup_owner_and_users(db_session)
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    # Attempt to use Mode 2 with target's existing email
    resp = client.post(
        "/api/v1/platform/operators",
        headers=headers,
        json={
            "email": target.email,
            "password": "Password1234!",
            "display_name": "Duplicate Target",
        },
    )
    assert resp.status_code == 422
    msg = resp.json()["detail"]["error"]["message"]
    assert f"user with email '{target.email}' already exists" in msg
    assert f"user_id '{target.id}'" in msg


def test_create_operator_mode2_concurrent_integrity_error(db_session: Session):
    owner, _, _ = _setup_owner_and_users(db_session)

    req = PlatformOperatorCreateRequest(
        email="race_condition@test.com",
        password="ValidPassword123!",
        display_name="Race Condition",
    )

    with patch.object(db_session, "flush", side_effect=IntegrityError("stmt", "params", Exception("unique constraint violation"))):
        with pytest.raises(ValidationError, match="already exists"):
            create_platform_operator(db_session, data=req, actor_user_id=owner.id)

    db_session.rollback()


def test_create_operator_mode2_missing_fields(client: TestClient, db_session: Session):
    _setup_owner_and_users(db_session)
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    # Missing display_name
    resp = client.post(
        "/api/v1/platform/operators",
        headers=headers,
        json={
            "email": "missing_name@test.com",
            "password": "Password123!",
        },
    )
    assert resp.status_code == 422

    # Missing password
    resp = client.post(
        "/api/v1/platform/operators",
        headers=headers,
        json={
            "email": "missing_pass@test.com",
            "display_name": "No Password",
        },
    )
    assert resp.status_code == 422


def test_create_operator_mode2_password_too_short(client: TestClient, db_session: Session):
    _setup_owner_and_users(db_session)
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        "/api/v1/platform/operators",
        headers=headers,
        json={
            "email": "short_pass@test.com",
            "password": "short",
            "display_name": "Short Password",
        },
    )
    assert resp.status_code == 422


# ==============================================================================
# 3. Schema Mutual Exclusivity
# ==============================================================================

def test_create_operator_ambiguous_payload_rejected(client: TestClient, db_session: Session):
    _, target, _ = _setup_owner_and_users(db_session)
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    # Ambiguous: user_id + email + password
    resp = client.post(
        "/api/v1/platform/operators",
        headers=headers,
        json={
            "user_id": str(target.id),
            "email": "ambiguous@test.com",
            "password": "Password123!",
            "display_name": "Ambiguous",
        },
    )
    assert resp.status_code == 422
    assert "Ambiguous request" in str(resp.json())


def test_create_operator_empty_payload_rejected(client: TestClient, db_session: Session):
    _setup_owner_and_users(db_session)
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        "/api/v1/platform/operators",
        headers=headers,
        json={},
    )
    assert resp.status_code == 422
    assert "Incomplete request" in str(resp.json())


# ==============================================================================
# 4. Operator Revocation (POST /api/v1/platform/operators/{user_id}/revoke)
# ==============================================================================

def test_revoke_operator_success(client: TestClient, db_session: Session):
    owner, target, _ = _setup_owner_and_users(db_session)
    target.platform_role = "operator"
    target.is_platform_admin = False
    db_session.commit()

    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        f"/api/v1/platform/operators/{target.id}/revoke",
        headers=headers,
    )
    assert resp.status_code == 200, resp.json()
    data = resp.json()

    assert data["id"] == str(target.id)
    assert data["platform_role"] is None
    assert data["is_platform_admin"] is False

    # DB verification
    db_session.refresh(target)
    assert target.platform_role is None
    assert target.is_platform_admin is False

    # Audit log
    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.operator.revoke",
        AuditLog.entity_id == target.id,
    ).first()
    assert audit is not None
    assert audit.actor_user_id == owner.id
    assert audit.metadata_json["outcome"] == "success"


def test_revoke_operator_preserves_account_status(client: TestClient, db_session: Session):
    _, target, _ = _setup_owner_and_users(db_session)
    target.platform_role = "operator"
    target.is_platform_admin = False
    target.status = "suspended"
    db_session.commit()

    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        f"/api/v1/platform/operators/{target.id}/revoke",
        headers=headers,
    )
    assert resp.status_code == 200
    db_session.refresh(target)
    assert target.status == "suspended"
    assert target.platform_role is None


def test_revoke_operator_preserves_tenant_memberships(client: TestClient, db_session: Session):
    _, target, _ = _setup_owner_and_users(db_session)
    target.platform_role = "operator"
    target.is_platform_admin = False

    # Attach tenant membership to target
    outlet = db_session.query(Outlet).first()
    membership = OutletMembership(
        user_id=target.id,
        outlet_id=outlet.id,
        role="cashier",
    )
    db_session.add(membership)
    db_session.commit()

    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        f"/api/v1/platform/operators/{target.id}/revoke",
        headers=headers,
    )
    assert resp.status_code == 200

    # Verify membership is preserved
    mems = db_session.query(OutletMembership).filter(OutletMembership.user_id == target.id).all()
    assert len(mems) == 1
    assert mems[0].role == "cashier"
    assert mems[0].outlet_id == outlet.id


def test_revoke_operator_idempotent(client: TestClient, db_session: Session):
    owner, target, _ = _setup_owner_and_users(db_session)
    target.platform_role = None
    target.is_platform_admin = False
    db_session.commit()

    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    initial_audit_count = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.operator.revoke"
    ).count()

    resp = client.post(
        f"/api/v1/platform/operators/{target.id}/revoke",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["platform_role"] is None

    # No duplicate audit log
    after_audit_count = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.operator.revoke"
    ).count()
    assert after_audit_count == initial_audit_count


def test_revoke_operator_nonexistent_user(client: TestClient, db_session: Session):
    _setup_owner_and_users(db_session)
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    fake_id = uuid.uuid4()
    resp = client.post(
        f"/api/v1/platform/operators/{fake_id}/revoke",
        headers=headers,
    )
    assert resp.status_code == 404


def test_revoke_operator_owner_target_rejected(client: TestClient, db_session: Session):
    owner, _, _ = _setup_owner_and_users(db_session)
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        f"/api/v1/platform/operators/{owner.id}/revoke",
        headers=headers,
    )
    assert resp.status_code == 422
    assert "Platform Owner privileges cannot be revoked" in resp.json()["detail"]["error"]["message"]


# ==============================================================================
# 5. Operator Listing (GET /api/v1/platform/operators)
# ==============================================================================

def test_list_operators_returns_only_valid_operators(client: TestClient, db_session: Session):
    owner, target, admin = _setup_owner_and_users(db_session)

    # Make target an operator
    target.platform_role = "operator"
    target.is_platform_admin = False

    # Create another operator
    op2 = User(
        email="operator2@test.com",
        display_name="Operator Two",
        password_hash=hash_password("Pass123!"),
        status="active",
        is_platform_admin=False,
        platform_role="operator",
    )
    db_session.add(op2)
    db_session.commit()

    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.get("/api/v1/platform/operators", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    op_emails = [item["email"] for item in data]
    assert target.email in op_emails
    assert "operator2@test.com" in op_emails
    assert owner.email not in op_emails
    assert admin.email not in op_emails


def test_list_operators_excludes_contradictory_pairs(db_session: Session):
    _setup_owner_and_users(db_session)

    # Create contradictory user: platform_role="operator" but is_platform_admin=True
    bad_user = User(
        email="contradictory@test.com",
        display_name="Contradictory",
        password_hash=hash_password("Pass123!"),
        status="active",
        is_platform_admin=True,
        platform_role="operator",
    )
    # Create valid operator
    valid_op = User(
        email="valid_op@test.com",
        display_name="Valid Operator",
        password_hash=hash_password("Pass123!"),
        status="active",
        is_platform_admin=False,
        platform_role="operator",
    )
    db_session.add_all([bad_user, valid_op])
    db_session.commit()

    ops = list_platform_operators(db_session)
    op_emails = [u.email for u in ops]
    assert "valid_op@test.com" in op_emails
    assert "contradictory@test.com" not in op_emails


# ==============================================================================
# 6. RBAC and Three-Tier Boundaries
# ==============================================================================

def test_rbac_unauthenticated_requests_denied(client: TestClient):
    fake_id = uuid.uuid4()
    assert client.post("/api/v1/platform/operators", json={"user_id": str(fake_id)}).status_code == 401
    assert client.post(f"/api/v1/platform/operators/{fake_id}/revoke").status_code == 401
    assert client.get("/api/v1/platform/operators").status_code == 401


def test_rbac_non_platform_staff_denied(client: TestClient, db_session: Session):
    _, target, _ = _setup_owner_and_users(db_session)
    # target is a non-platform user (platform_role=None, is_platform_admin=False)
    headers = _login(client, "unauth@test.com", "TargetPassword123!")

    fake_id = uuid.uuid4()
    assert client.post("/api/v1/platform/operators", headers=headers, json={"user_id": str(fake_id)}).status_code == 403
    assert client.post(f"/api/v1/platform/operators/{fake_id}/revoke", headers=headers).status_code == 403
    assert client.get("/api/v1/platform/operators", headers=headers).status_code == 403


def test_rbac_operator_role_boundaries(client: TestClient, db_session: Session):
    owner, target, _ = _setup_owner_and_users(db_session)
    target.platform_role = "operator"
    target.is_platform_admin = False
    db_session.commit()

    headers = _login(client, "unauth@test.com", "TargetPassword123!")

    # 1. Operator denied governance endpoints
    fake_id = uuid.uuid4()
    assert client.post("/api/v1/platform/operators", headers=headers, json={"user_id": str(fake_id)}).status_code == 403
    assert client.post(f"/api/v1/platform/operators/{fake_id}/revoke", headers=headers).status_code == 403

    # 2. Operator denied listing operators (commercial router requires owner/admin)
    assert client.get("/api/v1/platform/operators", headers=headers).status_code == 403

    # 3. Operator denied commercial/operations routes
    assert client.post("/api/v1/platform/businesses", headers=headers, json={"name": "Op Biz"}).status_code == 403
    biz = db_session.query(Business).first()
    assert client.post(f"/api/v1/platform/businesses/{biz.id}/assign-owner", headers=headers, json={"outlet_id": str(uuid.uuid4())}).status_code == 403

    # 4. Operator allowed on profile routes (GET business, GET outlet, PATCH outlet)
    outlet = db_session.query(Outlet).first()
    assert client.get(f"/api/v1/platform/businesses/{biz.id}", headers=headers).status_code == 200
    assert client.get(f"/api/v1/platform/outlets/{outlet.id}", headers=headers).status_code == 200
    patch_resp = client.patch(f"/api/v1/platform/outlets/{outlet.id}", headers=headers, json={"name": "Op Updated Outlet"})
    assert patch_resp.status_code == 200

    # 5. Operator allowed on platform menu routes
    menu_resp = client.get(f"/api/v1/platform/outlets/{outlet.id}/menu", headers=headers)
    assert menu_resp.status_code == 200


def test_rbac_admin_role_boundaries(client: TestClient, db_session: Session):
    _, target, admin = _setup_owner_and_users(db_session)
    headers = _login(client, "admin_test@test.com", "AdminPassword123!")

    # 1. Admin denied governance endpoints (Owner only)
    assert client.post("/api/v1/platform/operators", headers=headers, json={"user_id": str(target.id)}).status_code == 403
    assert client.post(f"/api/v1/platform/operators/{target.id}/revoke", headers=headers).status_code == 403

    # 2. Admin allowed on commercial listing
    assert client.get("/api/v1/platform/operators", headers=headers).status_code == 200


# ==============================================================================
# 7. Fail-Closed Zero-Owner Governance
# ==============================================================================

def test_fail_closed_zero_owner_governance(client: TestClient, db_session: Session):
    owner, target, admin = _setup_owner_and_users(db_session)

    # Demote owner to admin to create zero-owner state
    owner.platform_role = "admin"
    db_session.commit()

    active_owners = db_session.query(User).filter(User.platform_role == "owner", User.status == "active").count()
    assert active_owners == 0

    admin_headers = _login(client, "staff@test.com", "OwnerPassword123!")

    # 1. Governance routes fail closed with 503
    gov1 = client.post("/api/v1/platform/operators", headers=admin_headers, json={"user_id": str(target.id)})
    assert gov1.status_code == 503
    assert gov1.json()["detail"]["error"]["code"] == "PLATFORM_OWNER_NOT_INITIALIZED"

    gov2 = client.post(f"/api/v1/platform/operators/{target.id}/revoke", headers=admin_headers)
    assert gov2.status_code == 503
    assert gov2.json()["detail"]["error"]["code"] == "PLATFORM_OWNER_NOT_INITIALIZED"

    # 2. Commercial listing succeeds for admin under zero-owner condition
    comm = client.get("/api/v1/platform/operators", headers=admin_headers)
    assert comm.status_code == 200


# ==============================================================================
# 8. Transaction Safety, Advisory Lock & Audit Security
# ==============================================================================

def test_operator_transactions_service_preserves_caller_uncommitted_work(db_session: Session):
    owner, target, _ = _setup_owner_and_users(db_session)

    biz = db_session.query(Business).first()
    biz.name = "Dirty Uncommitted Business Name"

    # 1. Service failure does not roll back caller uncommitted changes
    fake_id = uuid.uuid4()
    req_fail = PlatformOperatorCreateRequest(user_id=fake_id)
    with pytest.raises(NotFoundError):
        create_platform_operator(db_session, data=req_fail, actor_user_id=owner.id)

    assert biz.name == "Dirty Uncommitted Business Name"

    # 2. Service success flushes but does not commit caller uncommitted changes
    req_success = PlatformOperatorCreateRequest(user_id=target.id)
    op = create_platform_operator(db_session, data=req_success, actor_user_id=owner.id)
    assert op.platform_role == "operator"
    assert biz.name == "Dirty Uncommitted Business Name"

    # 3. Caller rollback cleanly undoes everything, proving service never committed
    db_session.rollback()
    db_session.refresh(biz)
    db_session.refresh(target)
    assert biz.name == "Test Business"
    assert target.platform_role is None


def test_operator_advisory_lock_invoked_on_create_and_revoke(db_session: Session):
    owner, target, _ = _setup_owner_and_users(db_session)

    # Verify lock during create
    with patch(
        "app.modules.businesses.platform_service._acquire_admin_serialization_lock"
    ) as mock_lock:
        req = PlatformOperatorCreateRequest(user_id=target.id)
        create_platform_operator(db_session, data=req, actor_user_id=owner.id)
        mock_lock.assert_called_once_with(db_session)

    db_session.rollback()

    # Make target operator for revoke test
    target.platform_role = "operator"
    target.is_platform_admin = False
    db_session.commit()

    # Verify lock during revoke
    with patch(
        "app.modules.businesses.platform_service._acquire_admin_serialization_lock"
    ) as mock_lock:
        revoke_platform_operator(db_session, target_user_id=target.id, actor_user_id=owner.id)
        mock_lock.assert_called_once_with(db_session)

    db_session.rollback()


def test_operator_audit_log_secrets_exclusion_and_rollback(client: TestClient, db_session: Session):
    owner, _, _ = _setup_owner_and_users(db_session)
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    # 1. Secrets exclusion: verify password or hash is never in audit log metadata
    new_email = f"secrets_test_{uuid.uuid4().hex[:6]}@test.com"
    raw_pass = "UltraSecretPassword123!"
    resp = client.post(
        "/api/v1/platform/operators",
        headers=headers,
        json={
            "email": new_email,
            "password": raw_pass,
            "display_name": "Secrets Check",
        },
    )
    assert resp.status_code == 200
    created_id = resp.json()["id"]

    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.operator.create",
        AuditLog.entity_id == uuid.UUID(created_id),
    ).first()
    assert audit is not None
    meta_str = str(audit.metadata_json)
    assert raw_pass not in meta_str
    assert "password" not in audit.metadata_json
    assert "password_hash" not in audit.metadata_json

    # 2. Route rollback on audit logging failure
    with patch("app.modules.businesses.platform_service.log_audit", side_effect=RuntimeError("Audit failure")):
        fail_email = f"fail_audit_{uuid.uuid4().hex[:6]}@test.com"
        with pytest.raises(RuntimeError, match="Audit failure"):
            client.post(
                "/api/v1/platform/operators",
                headers=headers,
                json={
                    "email": fail_email,
                    "password": "Password12345!",
                    "display_name": "Audit Fail User",
                },
            )

        # Verify failed user was rolled back
        assert db_session.query(User).filter(User.email == fail_email).first() is None

    # 3. Route rollback on commit failure
    with patch.object(Session, "commit", side_effect=RuntimeError("Database commit error")):
        fail_email2 = f"fail_commit_{uuid.uuid4().hex[:6]}@test.com"
        with pytest.raises(RuntimeError, match="Database commit error"):
            client.post(
                "/api/v1/platform/operators",
                headers=headers,
                json={
                    "email": fail_email2,
                    "password": "Password12345!",
                    "display_name": "Commit Fail User",
                },
            )

        # Verify user was rolled back
        assert db_session.query(User).filter(User.email == fail_email2).first() is None
