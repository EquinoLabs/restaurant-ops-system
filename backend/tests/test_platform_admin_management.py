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
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    unauth_user = db_session.query(User).filter(User.email == "unauth@test.com").first()

    assert client.get("/api/v1/platform/admins", headers=headers).status_code == 403
    assert client.post(f"/api/v1/platform/admins/{unauth_user.id}/grant", headers=headers).status_code == 403
    assert client.post(f"/api/v1/platform/admins/{unauth_user.id}/revoke", headers=headers).status_code == 403


def test_grant_and_revoke_platform_admin_flow(client: TestClient, db_session: Session):
    # Setup admin1 (acting admin)
    admin1 = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin1.is_platform_admin = True

    # Setup target user
    unauth = db_session.query(User).filter(User.email == "unauth@test.com").first()
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
    # Only staff@test.com is active platform admin
    admin = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin.is_platform_admin = True
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

