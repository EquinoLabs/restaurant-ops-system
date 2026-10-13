import pytest
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.staff.models import User, OutletMembership
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.audit.models import AuditLog
from app.core.security import hash_password
from app.core.errors import (
    NotFoundError,
    ValidationError,
    ForbiddenError,
)
from app.modules.businesses.platform_service import (
    suspend_platform_user,
    reactivate_platform_user,
)


def _setup_test_users(db_session: Session):
    """Helper to set up standard test users across all three roles."""
    # Active Platform Owner
    owner = db_session.query(User).filter(User.email == "staff@test.com").first()
    owner.platform_role = "owner"
    owner.is_platform_admin = True
    owner.status = "active"
    owner.password_hash = hash_password("OwnerPassword123!")

    # Active Platform Admin
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
    else:
        admin.platform_role = "admin"
        admin.is_platform_admin = True
        admin.status = "active"
        admin.password_hash = hash_password("AdminPassword123!")

    # Active Platform Operator
    operator = db_session.query(User).filter(User.email == "operator_test@test.com").first()
    if not operator:
        operator = User(
            email="operator_test@test.com",
            display_name="Test Operator",
            password_hash=hash_password("OperatorPassword123!"),
            status="active",
            is_platform_admin=False,
            platform_role="operator",
        )
        db_session.add(operator)
    else:
        operator.platform_role = "operator"
        operator.is_platform_admin = False
        operator.status = "active"
        operator.password_hash = hash_password("OperatorPassword123!")

    # Active regular user (unauth@test.com)
    target = db_session.query(User).filter(User.email == "unauth@test.com").first()
    target.platform_role = None
    target.is_platform_admin = False
    target.status = "active"
    target.password_hash = hash_password("TargetPassword123!")

    db_session.commit()
    db_session.refresh(owner)
    db_session.refresh(admin)
    db_session.refresh(operator)
    db_session.refresh(target)
    return owner, admin, operator, target


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed for {email}: {resp.json()}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. Successful Suspension and Reactivation by Platform Owner
# ==============================================================================

def test_owner_can_suspend_and_reactivate_platform_admin(client: TestClient, db_session: Session):
    owner, admin, _, _ = _setup_test_users(db_session)
    owner_headers = _login(client, "staff@test.com", "OwnerPassword123!")

    # 1. Suspend Admin
    suspend_resp = client.post(
        f"/api/v1/platform/users/{admin.id}/suspend",
        headers=owner_headers,
    )
    assert suspend_resp.status_code == 200, suspend_resp.json()
    suspend_data = suspend_resp.json()
    assert suspend_data["id"] == str(admin.id)
    assert suspend_data["status"] == "suspended"
    assert suspend_data["platform_role"] == "admin"
    assert suspend_data["is_platform_admin"] is True

    # DB verification
    db_session.refresh(admin)
    assert admin.status == "suspended"
    assert admin.platform_role == "admin"
    assert admin.is_platform_admin is True

    # Audit log check for suspend
    suspend_audit = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.user.suspend",
        AuditLog.entity_id == admin.id,
    ).order_by(AuditLog.created_at.desc()).first()
    assert suspend_audit is not None
    assert suspend_audit.actor_user_id == owner.id
    assert suspend_audit.metadata_json["previous_status"] == "active"
    assert suspend_audit.metadata_json["new_status"] == "suspended"
    assert suspend_audit.metadata_json["platform_role"] == "admin"

    # 2. Reactivate Admin
    reactivate_resp = client.post(
        f"/api/v1/platform/users/{admin.id}/reactivate",
        headers=owner_headers,
    )
    assert reactivate_resp.status_code == 200, reactivate_resp.json()
    reactivate_data = reactivate_resp.json()
    assert reactivate_data["id"] == str(admin.id)
    assert reactivate_data["status"] == "active"
    assert reactivate_data["platform_role"] == "admin"
    assert reactivate_data["is_platform_admin"] is True

    # DB verification
    db_session.refresh(admin)
    assert admin.status == "active"
    assert admin.platform_role == "admin"
    assert admin.is_platform_admin is True

    # Audit log check for reactivate
    reactivate_audit = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.user.reactivate",
        AuditLog.entity_id == admin.id,
    ).order_by(AuditLog.created_at.desc()).first()
    assert reactivate_audit is not None
    assert reactivate_audit.actor_user_id == owner.id
    assert reactivate_audit.metadata_json["previous_status"] == "suspended"
    assert reactivate_audit.metadata_json["new_status"] == "active"
    assert reactivate_audit.metadata_json["platform_role"] == "admin"


def test_owner_can_suspend_and_reactivate_platform_operator(client: TestClient, db_session: Session):
    owner, _, operator, _ = _setup_test_users(db_session)
    owner_headers = _login(client, "staff@test.com", "OwnerPassword123!")

    # 1. Suspend Operator
    resp = client.post(
        f"/api/v1/platform/users/{operator.id}/suspend",
        headers=owner_headers,
    )
    assert resp.status_code == 200, resp.json()
    data = resp.json()
    assert data["status"] == "suspended"
    assert data["platform_role"] == "operator"
    assert data["is_platform_admin"] is False

    db_session.refresh(operator)
    assert operator.status == "suspended"
    assert operator.platform_role == "operator"

    # 2. Reactivate Operator
    resp2 = client.post(
        f"/api/v1/platform/users/{operator.id}/reactivate",
        headers=owner_headers,
    )
    assert resp2.status_code == 200, resp2.json()
    data2 = resp2.json()
    assert data2["status"] == "active"
    assert data2["platform_role"] == "operator"
    assert data2["is_platform_admin"] is False

    db_session.refresh(operator)
    assert operator.status == "active"


def test_owner_can_suspend_and_reactivate_regular_user(client: TestClient, db_session: Session):
    owner, _, _, target = _setup_test_users(db_session)
    owner_headers = _login(client, "staff@test.com", "OwnerPassword123!")

    # Suspend regular user
    resp = client.post(
        f"/api/v1/platform/users/{target.id}/suspend",
        headers=owner_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "suspended"
    assert resp.json()["platform_role"] is None

    # Reactivate regular user
    resp2 = client.post(
        f"/api/v1/platform/users/{target.id}/reactivate",
        headers=owner_headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "active"
    assert resp2.json()["platform_role"] is None


# ==============================================================================
# 2. Owner Protection and Self-Action Prevention
# ==============================================================================

def test_platform_owner_cannot_be_suspended(client: TestClient, db_session: Session):
    owner, _, _, _ = _setup_test_users(db_session)
    owner_headers = _login(client, "staff@test.com", "OwnerPassword123!")

    # Create a secondary user with platform_role="owner" to test pure owner protection
    # (even if another owner existed, owner cannot be suspended)
    secondary_owner = User(
        email="owner2@test.com",
        display_name="Secondary Owner",
        password_hash=hash_password("Pass123!"),
        status="active",
        is_platform_admin=True,
        platform_role="owner",
    )
    db_session.add(secondary_owner)
    db_session.commit()

    resp = client.post(
        f"/api/v1/platform/users/{secondary_owner.id}/suspend",
        headers=owner_headers,
    )
    assert resp.status_code == 422
    assert "Platform Owner cannot be suspended" in resp.json()["detail"]["error"]["message"]

    db_session.refresh(secondary_owner)
    assert secondary_owner.status == "active"


def test_user_cannot_suspend_own_account(client: TestClient, db_session: Session):
    owner, _, _, _ = _setup_test_users(db_session)
    owner_headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        f"/api/v1/platform/users/{owner.id}/suspend",
        headers=owner_headers,
    )
    assert resp.status_code == 422
    assert "You cannot suspend your own account" in resp.json()["detail"]["error"]["message"]

    db_session.refresh(owner)
    assert owner.status == "active"


def test_user_cannot_reactivate_own_account(client: TestClient, db_session: Session):
    owner, _, _, _ = _setup_test_users(db_session)
    owner_headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        f"/api/v1/platform/users/{owner.id}/reactivate",
        headers=owner_headers,
    )
    assert resp.status_code == 422
    assert "You cannot reactivate your own account" in resp.json()["detail"]["error"]["message"]


# ==============================================================================
# 3. Role Authorization Boundaries (Only Owner Authorized)
# ==============================================================================

def test_unauthenticated_requests_rejected(client: TestClient, db_session: Session):
    _, admin, _, _ = _setup_test_users(db_session)

    assert client.post(f"/api/v1/platform/users/{admin.id}/suspend").status_code == 401
    assert client.post(f"/api/v1/platform/users/{admin.id}/reactivate").status_code == 401


def test_regular_user_cannot_suspend_or_reactivate(client: TestClient, db_session: Session):
    _, admin, _, target = _setup_test_users(db_session)
    headers = _login(client, "unauth@test.com", "TargetPassword123!")

    resp = client.post(f"/api/v1/platform/users/{admin.id}/suspend", headers=headers)
    assert resp.status_code == 403

    resp2 = client.post(f"/api/v1/platform/users/{admin.id}/reactivate", headers=headers)
    assert resp2.status_code == 403


def test_operator_cannot_suspend_or_reactivate(client: TestClient, db_session: Session):
    _, admin, _, _ = _setup_test_users(db_session)
    headers = _login(client, "operator_test@test.com", "OperatorPassword123!")

    resp = client.post(f"/api/v1/platform/users/{admin.id}/suspend", headers=headers)
    assert resp.status_code == 403

    resp2 = client.post(f"/api/v1/platform/users/{admin.id}/reactivate", headers=headers)
    assert resp2.status_code == 403


def test_platform_admin_cannot_suspend_or_reactivate(client: TestClient, db_session: Session):
    _, admin, operator, _ = _setup_test_users(db_session)
    headers = _login(client, "admin_test@test.com", "AdminPassword123!")

    # Admin cannot suspend operator
    resp = client.post(f"/api/v1/platform/users/{operator.id}/suspend", headers=headers)
    assert resp.status_code == 403

    # Admin cannot reactivate operator
    resp2 = client.post(f"/api/v1/platform/users/{operator.id}/reactivate", headers=headers)
    assert resp2.status_code == 403


# ==============================================================================
# 4. Immediate Authentication Lockout and Restoration
# ==============================================================================

def test_immediate_authentication_lockout_and_restoration(client: TestClient, db_session: Session):
    owner, admin, _, _ = _setup_test_users(db_session)
    owner_headers = _login(client, "staff@test.com", "OwnerPassword123!")

    # 1. Admin logs in before suspension and verifies access
    admin_headers = _login(client, "admin_test@test.com", "AdminPassword123!")
    biz_resp = client.get("/api/v1/platform/businesses", headers=admin_headers)
    assert biz_resp.status_code == 200

    # 2. Owner suspends Admin
    suspend_resp = client.post(f"/api/v1/platform/users/{admin.id}/suspend", headers=owner_headers)
    assert suspend_resp.status_code == 200

    # 3. Previously issued JWT token is immediately rejected
    locked_resp = client.get("/api/v1/platform/businesses", headers=admin_headers)
    assert locked_resp.status_code == 401
    assert "User account is inactive" in locked_resp.json()["detail"]["error"]["message"]

    # 4. Admin login attempt is immediately denied
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin_test@test.com", "password": "AdminPassword123!"},
    )
    assert login_resp.status_code == 401
    assert "User account is inactive" in login_resp.json()["detail"]["error"]["message"]

    # 5. Owner reactivates Admin
    reactivate_resp = client.post(f"/api/v1/platform/users/{admin.id}/reactivate", headers=owner_headers)
    assert reactivate_resp.status_code == 200

    # 6. Admin can log in again and access platform resources
    new_admin_headers = _login(client, "admin_test@test.com", "AdminPassword123!")
    restored_resp = client.get("/api/v1/platform/businesses", headers=new_admin_headers)
    assert restored_resp.status_code == 200


def test_suspended_operator_menu_lockout(client: TestClient, db_session: Session):
    owner, _, operator, _ = _setup_test_users(db_session)
    owner_headers = _login(client, "staff@test.com", "OwnerPassword123!")

    # Operator gets token
    op_headers = _login(client, "operator_test@test.com", "OperatorPassword123!")

    outlet = db_session.query(Outlet).first()
    assert outlet is not None

    menu_resp = client.get(f"/api/v1/platform/outlets/{outlet.id}/menu", headers=op_headers)
    assert menu_resp.status_code == 200

    # Suspend operator
    client.post(f"/api/v1/platform/users/{operator.id}/suspend", headers=owner_headers)

    # Token immediately rejected
    menu_locked = client.get(f"/api/v1/platform/outlets/{outlet.id}/menu", headers=op_headers)
    assert menu_locked.status_code == 401


# ==============================================================================
# 5. Idempotent Behavior
# ==============================================================================

def test_idempotent_repeated_suspension(client: TestClient, db_session: Session):
    owner, admin, _, _ = _setup_test_users(db_session)
    owner_headers = _login(client, "staff@test.com", "OwnerPassword123!")

    # Initial suspend
    resp1 = client.post(f"/api/v1/platform/users/{admin.id}/suspend", headers=owner_headers)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "suspended"

    audit_count_before = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.user.suspend",
        AuditLog.entity_id == admin.id,
    ).count()
    assert audit_count_before == 1

    # Repeated suspend (idempotent no-op)
    resp2 = client.post(f"/api/v1/platform/users/{admin.id}/suspend", headers=owner_headers)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "suspended"

    audit_count_after = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.user.suspend",
        AuditLog.entity_id == admin.id,
    ).count()
    assert audit_count_after == 1  # No duplicate audit log recorded!


def test_idempotent_repeated_reactivation(client: TestClient, db_session: Session):
    owner, admin, _, _ = _setup_test_users(db_session)
    owner_headers = _login(client, "staff@test.com", "OwnerPassword123!")

    # User is currently active. Reactivating an active user is an idempotent no-op
    resp = client.post(f"/api/v1/platform/users/{admin.id}/reactivate", headers=owner_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"

    audit_count = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.user.reactivate",
        AuditLog.entity_id == admin.id,
    ).count()
    assert audit_count == 0  # No audit log recorded for no-op!


# ==============================================================================
# 6. Data Preservation (Memberships and Roles Intact)
# ==============================================================================

def test_outlet_memberships_preserved_across_suspension_and_reactivation(client: TestClient, db_session: Session):
    owner, _, _, target = _setup_test_users(db_session)
    owner_headers = _login(client, "staff@test.com", "OwnerPassword123!")

    # Assign target user multiple outlet memberships
    outlets = db_session.query(Outlet).all()
    assert len(outlets) >= 1
    outlet1 = outlets[0]

    # Create secondary outlet if needed
    if len(outlets) < 2:
        outlet2 = Outlet(
            business_id=outlet1.business_id,
            name="Secondary Test Outlet",
            public_slug="secondary-test-outlet",
            currency="INR",
            timezone="Asia/Kolkata",
            status="active",
        )
        db_session.add(outlet2)
        db_session.flush()
    else:
        outlet2 = outlets[1]

    mem1 = OutletMembership(user_id=target.id, outlet_id=outlet1.id, role="manager")
    mem2 = OutletMembership(user_id=target.id, outlet_id=outlet2.id, role="waiter")
    db_session.add_all([mem1, mem2])
    db_session.commit()

    # Suspend target user
    resp = client.post(f"/api/v1/platform/users/{target.id}/suspend", headers=owner_headers)
    assert resp.status_code == 200

    # Verify memberships are completely preserved
    db_session.refresh(target)
    assert target.status == "suspended"
    assert len(target.memberships) == 2
    roles = {m.role for m in target.memberships}
    assert roles == {"manager", "waiter"}

    # Reactivate target user
    resp2 = client.post(f"/api/v1/platform/users/{target.id}/reactivate", headers=owner_headers)
    assert resp2.status_code == 200

    # Verify memberships remain completely preserved
    db_session.refresh(target)
    assert target.status == "active"
    assert len(target.memberships) == 2
    roles2 = {m.role for m in target.memberships}
    assert roles2 == {"manager", "waiter"}


# ==============================================================================
# 7. Target Validation and 404 Handling
# ==============================================================================

def test_suspend_nonexistent_user_returns_404(client: TestClient, db_session: Session):
    _setup_test_users(db_session)
    owner_headers = _login(client, "staff@test.com", "OwnerPassword123!")

    fake_id = uuid.uuid4()
    resp = client.post(f"/api/v1/platform/users/{fake_id}/suspend", headers=owner_headers)
    assert resp.status_code == 404


def test_reactivate_nonexistent_user_returns_404(client: TestClient, db_session: Session):
    _setup_test_users(db_session)
    owner_headers = _login(client, "staff@test.com", "OwnerPassword123!")

    fake_id = uuid.uuid4()
    resp = client.post(f"/api/v1/platform/users/{fake_id}/reactivate", headers=owner_headers)
    assert resp.status_code == 404


# ==============================================================================
# 8. Zero-Owner Fail-Closed Guard
# ==============================================================================

def test_zero_active_owner_fails_closed(client: TestClient, db_session: Session):
    owner, admin, _, _ = _setup_test_users(db_session)

    # Demote owner to admin to simulate 0 active owners
    owner.platform_role = "admin"
    db_session.commit()

    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(f"/api/v1/platform/users/{admin.id}/suspend", headers=headers)
    assert resp.status_code == 503
    assert resp.json()["detail"]["error"]["code"] == "PLATFORM_OWNER_NOT_INITIALIZED"

    resp2 = client.post(f"/api/v1/platform/users/{admin.id}/reactivate", headers=headers)
    assert resp2.status_code == 503
    assert resp2.json()["detail"]["error"]["code"] == "PLATFORM_OWNER_NOT_INITIALIZED"


# ==============================================================================
# 9. Concurrency Advisory Locking and Service Semantics
# ==============================================================================

def test_advisory_lock_invoked_on_suspend_and_reactivate(db_session: Session):
    owner, admin, _, _ = _setup_test_users(db_session)

    with patch(
        "app.modules.businesses.platform_service._acquire_admin_serialization_lock"
    ) as mock_lock:
        suspend_platform_user(db_session, target_user_id=admin.id, actor_user_id=owner.id)
        mock_lock.assert_called_once_with(db_session)

    db_session.rollback()

    with patch(
        "app.modules.businesses.platform_service._acquire_admin_serialization_lock"
    ) as mock_lock2:
        # First suspend so reactivate has work
        admin.status = "suspended"
        db_session.flush()
        reactivate_platform_user(db_session, target_user_id=admin.id, actor_user_id=owner.id)
        mock_lock2.assert_called_once_with(db_session)

    db_session.rollback()


def test_service_preserves_caller_uncommitted_work(db_session: Session):
    owner, admin, _, _ = _setup_test_users(db_session)

    biz = db_session.query(Business).first()
    biz.name = "Uncommitted Caller Business Name"

    # Service flushes but does not commit
    user = suspend_platform_user(db_session, target_user_id=admin.id, actor_user_id=owner.id)
    assert user.status == "suspended"
    assert biz.name == "Uncommitted Caller Business Name"

    # Caller rollback restores everything
    db_session.rollback()
    db_session.refresh(biz)
    db_session.refresh(admin)
    assert biz.name == "Test Business"
    assert admin.status == "active"


def test_rollback_on_audit_or_commit_failure(client: TestClient, db_session: Session):
    owner, admin, _, _ = _setup_test_users(db_session)
    owner_headers = _login(client, "staff@test.com", "OwnerPassword123!")

    # 1. Rollback on audit failure
    with patch("app.modules.businesses.platform_service.log_audit", side_effect=RuntimeError("Audit error")):
        with pytest.raises(RuntimeError, match="Audit error"):
            client.post(f"/api/v1/platform/users/{admin.id}/suspend", headers=owner_headers)

        db_session.refresh(admin)
        assert admin.status == "active"

    # 2. Rollback on commit failure
    with patch.object(Session, "commit", side_effect=RuntimeError("Commit error")):
        with pytest.raises(RuntimeError, match="Commit error"):
            client.post(f"/api/v1/platform/users/{admin.id}/suspend", headers=owner_headers)

        db_session.refresh(admin)
        assert admin.status == "active"
