import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.staff.models import User
from app.modules.audit.models import AuditLog
from scripts.create_platform_admin import promote_user_to_platform_admin


def test_platform_admin_list_admins(client: TestClient, db_session: Session):
    admin = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/platform/admins", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any(a["email"] == "staff@test.com" for a in data)
    # Ensure secrets are excluded
    for a in data:
        assert "password_hash" not in a
        assert "password" not in a


def test_non_platform_user_denied_admin_management(client: TestClient, db_session: Session):
    # Ensure active owner exists in DB so governance endpoints pass the 503 initialization guard
    unauth_user = db_session.query(User).filter(User.email == "unauth@test.com").first()
    unauth_user.platform_role = "owner"
    unauth_user.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/v1/platform/admins", headers=headers).status_code == 403
    assert client.post(f"/api/v1/platform/admins/{unauth_user.id}/grant", headers=headers).status_code == 403
    assert client.post(f"/api/v1/platform/admins/{unauth_user.id}/revoke", headers=headers).status_code == 403


def test_grant_and_revoke_platform_admin_flow(client: TestClient, db_session: Session):
    # Setup admin1 (acting platform owner)
    admin1 = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin1.is_platform_admin = True
    admin1.platform_role = "owner"

    # Setup target user
    unauth = db_session.query(User).filter(User.email == "unauth@test.com").first()
    unauth.platform_role = None
    unauth.is_platform_admin = False
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Grant admin to unauth user
    grant_resp = client.post(f"/api/v1/platform/admins/{unauth.id}/grant", headers=headers)
    assert grant_resp.status_code == 200
    assert grant_resp.json()["is_platform_admin"] is True

    # Verify audit log for grant
    grant_log = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.admin.grant",
        AuditLog.actor_user_id == admin1.id
    ).first()
    assert grant_log is not None
    assert grant_log.entity_id == unauth.id
    assert grant_log.metadata_json["target_email"] == "unauth@test.com"

    # 2. No-op grant call
    grant_noop = client.post(f"/api/v1/platform/admins/{unauth.id}/grant", headers=headers)
    assert grant_noop.status_code == 200
    # Audit log count for grant remains 1
    assert db_session.query(AuditLog).filter(AuditLog.action == "platform.admin.grant").count() == 1

    # 3. Revoke admin from unauth user (admin1 still active)
    revoke_resp = client.post(f"/api/v1/platform/admins/{unauth.id}/revoke", headers=headers)
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["is_platform_admin"] is False

    # Verify audit log for revoke
    revoke_log = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.admin.revoke",
        AuditLog.actor_user_id == admin1.id
    ).first()
    assert revoke_log is not None
    assert revoke_log.entity_id == unauth.id

    # 4. No-op revoke call
    revoke_noop = client.post(f"/api/v1/platform/admins/{unauth.id}/revoke", headers=headers)
    assert revoke_noop.status_code == 200
    assert db_session.query(AuditLog).filter(AuditLog.action == "platform.admin.revoke").count() == 1


def test_last_active_platform_admin_protection(client: TestClient, db_session: Session):
    # Only staff@test.com is active platform owner/admin
    admin = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin.is_platform_admin = True
    admin.platform_role = "owner"
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt self-revoke when only 1 active admin remains
    revoke_resp = client.post(f"/api/v1/platform/admins/{admin.id}/revoke", headers=headers)
    assert revoke_resp.status_code == 422
    assert "last active platform administrator" in revoke_resp.json()["detail"]["error"]["message"]

    # Verify NO revoke audit log was created
    revoke_log = db_session.query(AuditLog).filter(AuditLog.action == "platform.admin.revoke").first()
    assert revoke_log is None

    # Verify user remains platform admin
    db_session.refresh(admin)
    assert admin.is_platform_admin is True


def test_nonexistent_user_grant_revoke_fails(client: TestClient, db_session: Session):
    admin = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin.is_platform_admin = True
    admin.platform_role = "owner"
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    fake_id = uuid.uuid4()
    assert client.post(f"/api/v1/platform/admins/{fake_id}/grant", headers=headers).status_code == 404
    assert client.post(f"/api/v1/platform/admins/{fake_id}/revoke", headers=headers).status_code == 404


def test_cli_bootstrap_script_compatibility(client: TestClient, db_session: Session):
    # Promote unauth user via script helper
    success = promote_user_to_platform_admin("unauth@test.com", db=db_session)
    assert success is True

    unauth = db_session.query(User).filter(User.email == "unauth@test.com").first()
    assert unauth.is_platform_admin is True

    # Promoting again returns True (notice/no-op)
    assert promote_user_to_platform_admin("unauth@test.com", db=db_session) is True


def test_serialization_lock_helper_executes_without_error(db_session: Session):
    from app.modules.businesses.platform_service import _acquire_admin_serialization_lock
    # Verifies helper executes cleanly on test DB session
    _acquire_admin_serialization_lock(db_session)


def test_self_revocation_rejected_when_multiple_admins_exist(client: TestClient, db_session: Session):
    # Setup two active platform admins: admin1 as owner, admin2 as admin
    admin1 = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin1.is_platform_admin = True
    admin1.platform_role = "owner"
    admin2 = db_session.query(User).filter(User.email == "unauth@test.com").first()
    admin2.is_platform_admin = True
    admin2.platform_role = "admin"
    db_session.commit()

    # Login as admin1
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # admin1 attempts to self-revoke
    revoke_resp = client.post(f"/api/v1/platform/admins/{admin1.id}/revoke", headers=headers)
    assert revoke_resp.status_code == 422
    assert "cannot revoke their own privileges" in revoke_resp.json()["detail"]["error"]["message"].lower()

    # Verify user remains platform admin
    db_session.refresh(admin1)
    assert admin1.is_platform_admin is True

    # Verify NO audit log was generated for rejected self-revocation
    revoke_log = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.admin.revoke",
        AuditLog.actor_user_id == admin1.id,
        AuditLog.entity_id == admin1.id
    ).first()
    assert revoke_log is None


def test_revoke_another_platform_admin_succeeds(client: TestClient, db_session: Session):
    # Setup two active platform admins: admin1 as owner, admin2 as admin
    admin1 = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin1.is_platform_admin = True
    admin1.platform_role = "owner"
    admin2 = db_session.query(User).filter(User.email == "unauth@test.com").first()
    admin2.is_platform_admin = True
    admin2.platform_role = "admin"
    db_session.commit()

    # Login as admin1
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # admin1 revokes admin2
    revoke_resp = client.post(f"/api/v1/platform/admins/{admin2.id}/revoke", headers=headers)
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["is_platform_admin"] is False

    # Verify admin2 privileges revoked
    db_session.refresh(admin2)
    assert admin2.is_platform_admin is False

    # Verify audit log created with actor=admin1 and target=admin2
    revoke_log = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.admin.revoke",
        AuditLog.actor_user_id == admin1.id,
        AuditLog.entity_id == admin2.id
    ).first()
    assert revoke_log is not None
    assert revoke_log.metadata_json["outcome"] == "success"


def test_revoke_platform_admin_requires_actor_user_id(db_session: Session):
    from app.core.errors import ValidationError
    from app.modules.businesses.platform_service import revoke_platform_admin

    admin = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin.is_platform_admin = True
    db_session.commit()

    with pytest.raises(ValidationError) as exc_info:
        revoke_platform_admin(db_session, target_user_id=admin.id, actor_user_id=None)
    assert "Actor user ID is required" in str(exc_info.value)


def test_grant_revoke_admin_requires_owner(client: TestClient, db_session: Session):
    # Setup owner and standard admin
    owner = db_session.query(User).filter(User.email == "staff@test.com").first()
    owner.is_platform_admin = True
    owner.platform_role = "owner"

    admin = db_session.query(User).filter(User.email == "unauth@test.com").first()
    admin.is_platform_admin = True
    admin.platform_role = "admin"
    db_session.commit()

    # Login as standard admin
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "unauth@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    target_id = uuid.uuid4()
    # Standard admin cannot grant admin (requires owner) -> 403 Forbidden
    grant_resp = client.post(f"/api/v1/platform/admins/{target_id}/grant", headers=headers)
    assert grant_resp.status_code == 403

    # Standard admin cannot revoke admin (requires owner) -> 403 Forbidden
    revoke_resp = client.post(f"/api/v1/platform/admins/{target_id}/revoke", headers=headers)
    assert revoke_resp.status_code == 403


def test_zero_owner_governance_fails_closed_503(client: TestClient, db_session: Session):
    # Ensure active owner count == 0
    users = db_session.query(User).all()
    for u in users:
        u.platform_role = "admin"
        u.is_platform_admin = True
    db_session.commit()

    # Login as admin
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    target_user = db_session.query(User).filter(User.email == "unauth@test.com").first()

    # Governance operations fail closed with HTTP 503
    grant_resp = client.post(f"/api/v1/platform/admins/{target_user.id}/grant", headers=headers)
    assert grant_resp.status_code == 503
    assert grant_resp.json()["detail"]["error"]["code"] == "PLATFORM_OWNER_NOT_INITIALIZED"

    revoke_resp = client.post(f"/api/v1/platform/admins/{target_user.id}/revoke", headers=headers)
    assert revoke_resp.status_code == 503
    assert revoke_resp.json()["detail"]["error"]["code"] == "PLATFORM_OWNER_NOT_INITIALIZED"



