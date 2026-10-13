import pytest
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.staff.models import User
from app.modules.audit.models import AuditLog
from app.core.security import hash_password
from app.core.errors import (
    AuthenticationError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.modules.businesses.platform_service import (
    transfer_platform_owner,
    _acquire_admin_serialization_lock,
)


def _setup_owner_and_target(
    db_session: Session,
    target_role: str = None,
    target_is_admin: bool = False,
    target_status: str = "active",
):
    """Helper to set up staff@test.com as Owner and unauth@test.com as target."""
    owner = db_session.query(User).filter(User.email == "staff@test.com").first()
    owner.platform_role = "owner"
    owner.is_platform_admin = True
    owner.status = "active"
    owner.password_hash = hash_password("OwnerPassword123!")

    target = db_session.query(User).filter(User.email == "unauth@test.com").first()
    target.platform_role = target_role
    target.is_platform_admin = target_is_admin
    target.status = target_status
    target.password_hash = hash_password("TargetPassword123!")

    db_session.commit()
    db_session.refresh(owner)
    db_session.refresh(target)
    return owner, target


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed for {email}: {resp.json()}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. Happy Path Transfers
# ==============================================================================

def test_owner_transfer_to_admin_success(client: TestClient, db_session: Session):
    owner, target = _setup_owner_and_target(
        db_session, target_role="admin", target_is_admin=True, target_status="active"
    )
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        "/api/v1/platform/owner/transfer",
        headers=headers,
        json={
            "target_user_id": str(target.id),
            "current_password": "OwnerPassword123!",
        },
    )
    assert resp.status_code == 200, resp.json()
    data = resp.json()

    # Successor returned as PlatformAdminUserOut
    assert data["id"] == str(target.id)
    assert data["email"] == target.email
    assert data["platform_role"] == "owner"
    assert data["is_platform_admin"] is True

    # Database verification
    db_session.refresh(owner)
    db_session.refresh(target)
    assert owner.platform_role == "admin"
    assert owner.is_platform_admin is True
    assert owner.status == "active"

    assert target.platform_role == "owner"
    assert target.is_platform_admin is True
    assert target.status == "active"

    # Audit log verification
    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.owner.transfer"
    ).first()
    assert audit is not None
    assert audit.actor_user_id == owner.id
    assert audit.entity_id == target.id
    assert audit.entity_type == "user"
    assert audit.metadata_json["outcome"] == "success"
    assert audit.metadata_json["predecessor_user_id"] == str(owner.id)
    assert audit.metadata_json["successor_user_id"] == str(target.id)
    assert audit.metadata_json["predecessor_new_role"] == "admin"
    assert audit.metadata_json["successor_new_role"] == "owner"
    assert audit.metadata_json["predecessor_email"] == "staff@test.com"
    assert audit.metadata_json["successor_email"] == "unauth@test.com"


def test_owner_transfer_to_ordinary_user_success(client: TestClient, db_session: Session):
    owner, target = _setup_owner_and_target(
        db_session, target_role=None, target_is_admin=False, target_status="active"
    )
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        "/api/v1/platform/owner/transfer",
        headers=headers,
        json={
            "target_user_id": str(target.id),
            "current_password": "OwnerPassword123!",
        },
    )
    assert resp.status_code == 200
    db_session.refresh(owner)
    db_session.refresh(target)

    assert owner.platform_role == "admin"
    assert owner.is_platform_admin is True
    assert target.platform_role == "owner"
    assert target.is_platform_admin is True


def test_owner_transfer_to_operator_success(client: TestClient, db_session: Session):
    owner, target = _setup_owner_and_target(
        db_session, target_role="operator", target_is_admin=False, target_status="active"
    )
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        "/api/v1/platform/owner/transfer",
        headers=headers,
        json={
            "target_user_id": str(target.id),
            "current_password": "OwnerPassword123!",
        },
    )
    assert resp.status_code == 200
    db_session.refresh(owner)
    db_session.refresh(target)

    assert owner.platform_role == "admin"
    assert owner.is_platform_admin is True
    assert target.platform_role == "owner"
    assert target.is_platform_admin is True


# ==============================================================================
# 2. Rejection / Negative Test Cases
# ==============================================================================

def test_owner_transfer_invalid_password_rejected(client: TestClient, db_session: Session):
    owner, target = _setup_owner_and_target(
        db_session, target_role="admin", target_is_admin=True, target_status="active"
    )
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        "/api/v1/platform/owner/transfer",
        headers=headers,
        json={
            "target_user_id": str(target.id),
            "current_password": "IncorrectPassword999!",
        },
    )
    assert resp.status_code == 401
    assert "Invalid current password" in resp.json()["detail"]["error"]["message"]

    # State completely unchanged
    db_session.refresh(owner)
    db_session.refresh(target)
    assert owner.platform_role == "owner"
    assert target.platform_role == "admin"

    # No audit log created
    assert db_session.query(AuditLog).filter(AuditLog.action == "platform.owner.transfer").count() == 0


def test_owner_transfer_self_transfer_rejected(client: TestClient, db_session: Session):
    owner, _ = _setup_owner_and_target(db_session)
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        "/api/v1/platform/owner/transfer",
        headers=headers,
        json={
            "target_user_id": str(owner.id),
            "current_password": "OwnerPassword123!",
        },
    )
    assert resp.status_code == 422
    assert "Cannot transfer platform ownership to yourself" in resp.json()["detail"]["error"]["message"]

    db_session.refresh(owner)
    assert owner.platform_role == "owner"
    assert db_session.query(AuditLog).filter(AuditLog.action == "platform.owner.transfer").count() == 0


def test_owner_transfer_nonexistent_target_rejected(client: TestClient, db_session: Session):
    owner, _ = _setup_owner_and_target(db_session)
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    fake_target_id = uuid.uuid4()
    resp = client.post(
        "/api/v1/platform/owner/transfer",
        headers=headers,
        json={
            "target_user_id": str(fake_target_id),
            "current_password": "OwnerPassword123!",
        },
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]["error"]["message"].lower()

    db_session.refresh(owner)
    assert owner.platform_role == "owner"
    assert db_session.query(AuditLog).filter(AuditLog.action == "platform.owner.transfer").count() == 0


def test_owner_transfer_suspended_target_rejected(client: TestClient, db_session: Session):
    owner, target = _setup_owner_and_target(
        db_session, target_role="admin", target_is_admin=True, target_status="suspended"
    )
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        "/api/v1/platform/owner/transfer",
        headers=headers,
        json={
            "target_user_id": str(target.id),
            "current_password": "OwnerPassword123!",
        },
    )
    assert resp.status_code == 422
    err_msg = resp.json()["detail"]["error"]["message"]
    assert "Target account must be active" in err_msg
    assert "suspended" in err_msg

    db_session.refresh(owner)
    db_session.refresh(target)
    assert owner.platform_role == "owner"
    assert target.platform_role == "admin"
    assert target.status == "suspended"
    assert db_session.query(AuditLog).filter(AuditLog.action == "platform.owner.transfer").count() == 0


def test_owner_transfer_inactive_target_rejected(client: TestClient, db_session: Session):
    owner, target = _setup_owner_and_target(
        db_session, target_role=None, target_is_admin=False, target_status="inactive"
    )
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    resp = client.post(
        "/api/v1/platform/owner/transfer",
        headers=headers,
        json={
            "target_user_id": str(target.id),
            "current_password": "OwnerPassword123!",
        },
    )
    assert resp.status_code == 422
    assert "Target account must be active" in resp.json()["detail"]["error"]["message"]

    db_session.refresh(owner)
    db_session.refresh(target)
    assert owner.platform_role == "owner"
    assert db_session.query(AuditLog).filter(AuditLog.action == "platform.owner.transfer").count() == 0


def test_owner_transfer_non_owner_callers_forbidden(client: TestClient, db_session: Session):
    owner, target = _setup_owner_and_target(
        db_session, target_role="admin", target_is_admin=True, target_status="active"
    )

    # 1. Standard Admin attempts transfer -> 403 Forbidden
    target_headers = _login(client, "unauth@test.com", "TargetPassword123!")
    resp_admin = client.post(
        "/api/v1/platform/owner/transfer",
        headers=target_headers,
        json={
            "target_user_id": str(owner.id),
            "current_password": "TargetPassword123!",
        },
    )
    assert resp_admin.status_code == 403

    # 2. Operator attempts transfer -> 403 Forbidden
    target.platform_role = "operator"
    target.is_platform_admin = False
    db_session.commit()

    resp_op = client.post(
        "/api/v1/platform/owner/transfer",
        headers=target_headers,
        json={
            "target_user_id": str(owner.id),
            "current_password": "TargetPassword123!",
        },
    )
    assert resp_op.status_code == 403

    # 3. Ordinary user attempts transfer -> 403 Forbidden
    target.platform_role = None
    target.is_platform_admin = False
    db_session.commit()

    resp_reg = client.post(
        "/api/v1/platform/owner/transfer",
        headers=target_headers,
        json={
            "target_user_id": str(owner.id),
            "current_password": "TargetPassword123!",
        },
    )
    assert resp_reg.status_code == 403

    # 4. Unauthenticated caller -> 401 Unauthorized
    resp_unauth = client.post(
        "/api/v1/platform/owner/transfer",
        json={
            "target_user_id": str(owner.id),
            "current_password": "TargetPassword123!",
        },
    )
    assert resp_unauth.status_code == 401


# ==============================================================================
# 3. Governance Access Transition
# ==============================================================================

def test_owner_transfer_governance_access_transition(client: TestClient, db_session: Session):
    owner, target = _setup_owner_and_target(
        db_session, target_role="admin", target_is_admin=True, target_status="active"
    )
    owner_headers = _login(client, "staff@test.com", "OwnerPassword123!")
    target_headers = _login(client, "unauth@test.com", "TargetPassword123!")

    # Initial: Owner can access governance; Target cannot access governance
    candidate_id = uuid.uuid4()
    assert client.post(f"/api/v1/platform/admins/{candidate_id}/grant", headers=owner_headers).status_code == 404
    assert client.post(f"/api/v1/platform/admins/{candidate_id}/grant", headers=target_headers).status_code == 403

    # Execute transfer
    transfer_resp = client.post(
        "/api/v1/platform/owner/transfer",
        headers=owner_headers,
        json={
            "target_user_id": str(target.id),
            "current_password": "OwnerPassword123!",
        },
    )
    assert transfer_resp.status_code == 200

    # Post-transfer:
    # 1. Predecessor immediately loses Owner-only governance access (403 Forbidden)
    assert client.post(f"/api/v1/platform/admins/{candidate_id}/grant", headers=owner_headers).status_code == 403
    assert client.post(
        "/api/v1/platform/owner/transfer",
        headers=owner_headers,
        json={"target_user_id": str(target.id), "current_password": "OwnerPassword123!"},
    ).status_code == 403

    # 2. Successor immediately gains Owner-only governance access (reaches service, returns 404 for unknown user)
    assert client.post(f"/api/v1/platform/admins/{candidate_id}/grant", headers=target_headers).status_code == 404

    # 3. Both retain commercial access (200 OK)
    assert client.get("/api/v1/platform/businesses", headers=owner_headers).status_code == 200
    assert client.get("/api/v1/platform/businesses", headers=target_headers).status_code == 200


def test_owner_transfer_zero_owner_guard_fails_closed(client: TestClient, db_session: Session):
    # Set all users to admin (active owner count == 0)
    for u in db_session.query(User).all():
        u.platform_role = "admin"
        u.is_platform_admin = True
    db_session.commit()

    admin = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin.password_hash = hash_password("password123")
    db_session.commit()

    headers = _login(client, "staff@test.com", "password123")

    resp = client.post(
        "/api/v1/platform/owner/transfer",
        headers=headers,
        json={
            "target_user_id": str(uuid.uuid4()),
            "current_password": "password123",
        },
    )
    assert resp.status_code == 503
    assert resp.json()["detail"]["error"]["code"] == "PLATFORM_OWNER_NOT_INITIALIZED"


# ==============================================================================
# 4. Transaction Atomicity & Rollback Guarantees
# ==============================================================================

def test_owner_transfer_service_rollback_after_predecessor_flush(db_session: Session):
    owner, target = _setup_owner_and_target(
        db_session, target_role="admin", target_is_admin=True, target_status="active"
    )

    original_flush = db_session.flush
    flush_call_count = 0

    def fail_on_second_flush(*args, **kwargs):
        nonlocal flush_call_count
        flush_call_count += 1
        if flush_call_count == 2:
            raise RuntimeError("Simulated failure on successor flush")
        return original_flush(*args, **kwargs)

    with patch.object(db_session, "flush", side_effect=fail_on_second_flush):
        with pytest.raises(RuntimeError, match="Simulated failure on successor flush"):
            transfer_platform_owner(
                db_session,
                actor_user_id=owner.id,
                target_user_id=target.id,
                current_password="OwnerPassword123!",
            )

    # Caller rolls back
    db_session.rollback()

    # Predecessor MUST still be owner; successor MUST still be admin
    db_session.refresh(owner)
    db_session.refresh(target)
    assert owner.platform_role == "owner"
    assert owner.is_platform_admin is True
    assert target.platform_role == "admin"
    assert target.is_platform_admin is True
    assert db_session.query(AuditLog).filter(AuditLog.action == "platform.owner.transfer").count() == 0


def test_owner_transfer_service_rollback_on_audit_failure(db_session: Session):
    owner, target = _setup_owner_and_target(
        db_session, target_role="admin", target_is_admin=True, target_status="active"
    )

    with patch(
        "app.modules.businesses.platform_service.log_audit",
        side_effect=RuntimeError("Simulated audit log write failure"),
    ):
        with pytest.raises(RuntimeError, match="Simulated audit log write failure"):
            transfer_platform_owner(
                db_session,
                actor_user_id=owner.id,
                target_user_id=target.id,
                current_password="OwnerPassword123!",
            )

    # Caller rolls back
    db_session.rollback()

    db_session.refresh(owner)
    db_session.refresh(target)
    assert owner.platform_role == "owner"
    assert target.platform_role == "admin"
    assert db_session.query(AuditLog).filter(AuditLog.action == "platform.owner.transfer").count() == 0


def test_owner_transfer_route_rollback_on_commit_failure(client: TestClient, db_session: Session):
    owner, target = _setup_owner_and_target(
        db_session, target_role="admin", target_is_admin=True, target_status="active"
    )
    headers = _login(client, "staff@test.com", "OwnerPassword123!")

    # Patch commit on Session to simulate database commit failure at route level
    with patch.object(Session, "commit", side_effect=RuntimeError("Simulated DB commit error")):
        with pytest.raises(RuntimeError, match="Simulated DB commit error"):
            client.post(
                "/api/v1/platform/owner/transfer",
                headers=headers,
                json={
                    "target_user_id": str(target.id),
                    "current_password": "OwnerPassword123!",
                },
            )

    # Verify route executed db.rollback(): DB state remains predecessor=owner, successor=admin
    db_session.refresh(owner)
    db_session.refresh(target)
    assert owner.platform_role == "owner"
    assert target.platform_role == "admin"
    assert db_session.query(AuditLog).filter(AuditLog.action == "platform.owner.transfer").count() == 0


# ==============================================================================
# 5. Concurrency, Advisory Lock & populate_existing() Audit
# ==============================================================================

def test_owner_transfer_advisory_lock_invoked(db_session: Session):
    owner, target = _setup_owner_and_target(
        db_session, target_role="admin", target_is_admin=True, target_status="active"
    )

    with patch(
        "app.modules.businesses.platform_service._acquire_admin_serialization_lock"
    ) as mock_lock:
        transfer_platform_owner(
            db_session,
            actor_user_id=owner.id,
            target_user_id=target.id,
            current_password="OwnerPassword123!",
        )
        mock_lock.assert_called_once_with(db_session)
    db_session.rollback()


def test_owner_transfer_detects_out_of_band_actor_demotion(db_session: Session):
    owner, target = _setup_owner_and_target(
        db_session, target_role="admin", target_is_admin=True, target_status="active"
    )

    # Simulate: Actor demoted by concurrent transaction while waiting for lock
    def demote_actor_during_lock(db):
        # Directly modify actor row in underlying storage to simulate committed concurrent update
        owner.platform_role = "admin"
        db.flush()

    with patch(
        "app.modules.businesses.platform_service._acquire_admin_serialization_lock",
        side_effect=demote_actor_during_lock,
    ):
        with pytest.raises(ForbiddenError, match="Platform Owner privileges"):
            transfer_platform_owner(
                db_session,
                actor_user_id=owner.id,
                target_user_id=target.id,
                current_password="OwnerPassword123!",
            )

    db_session.rollback()


def test_owner_transfer_detects_out_of_band_password_change(db_session: Session):
    owner, target = _setup_owner_and_target(
        db_session, target_role="admin", target_is_admin=True, target_status="active"
    )

    # 1. Concurrent change to a NEW password; old password fails reverification
    def change_password_during_lock_1(db):
        owner.password_hash = hash_password("NewDifferentPassword123!")
        db.flush()

    with patch(
        "app.modules.businesses.platform_service._acquire_admin_serialization_lock",
        side_effect=change_password_during_lock_1,
    ):
        with pytest.raises(AuthenticationError, match="Invalid current password"):
            transfer_platform_owner(
                db_session,
                actor_user_id=owner.id,
                target_user_id=target.id,
                current_password="OwnerPassword123!",
            )

    db_session.rollback()

    # 2. Concurrent change to an identical password; reverification succeeds
    owner, target = _setup_owner_and_target(
        db_session, target_role="admin", target_is_admin=True, target_status="active"
    )

    def change_password_during_lock_2(db):
        # New hash for same password
        owner.password_hash = hash_password("OwnerPassword123!")
        db.flush()

    with patch(
        "app.modules.businesses.platform_service._acquire_admin_serialization_lock",
        side_effect=change_password_during_lock_2,
    ):
        successor = transfer_platform_owner(
            db_session,
            actor_user_id=owner.id,
            target_user_id=target.id,
            current_password="OwnerPassword123!",
        )
        assert successor.platform_role == "owner"

    db_session.rollback()


def test_owner_transfer_service_preserves_caller_uncommitted_work(db_session: Session):
    owner, target = _setup_owner_and_target(
        db_session, target_role="admin", target_is_admin=True, target_status="active"
    )

    from app.modules.businesses.models import Business
    biz = db_session.query(Business).first()
    biz.name = "Dirty Business Modification"

    # 1. Failure does not rollback caller work
    with pytest.raises(AuthenticationError):
        transfer_platform_owner(
            db_session,
            actor_user_id=owner.id,
            target_user_id=target.id,
            current_password="WrongPassword!",
        )

    assert biz.name == "Dirty Business Modification"

    # 2. Success flushes but does not commit caller work
    successor = transfer_platform_owner(
        db_session,
        actor_user_id=owner.id,
        target_user_id=target.id,
        current_password="OwnerPassword123!",
    )
    assert successor.platform_role == "owner"
    assert biz.name == "Dirty Business Modification"

    # 3. Caller rollback cleanly undoes everything, confirming service did not commit
    db_session.rollback()
    db_session.refresh(biz)
    db_session.refresh(owner)
    db_session.refresh(target)
    assert biz.name == "Test Business"
    assert owner.platform_role == "owner"
    assert target.platform_role == "admin"
