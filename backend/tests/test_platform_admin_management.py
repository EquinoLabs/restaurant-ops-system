import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.staff.models import User
from app.modules.audit.models import AuditLog
from app.core.errors import ValidationError
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


def test_last_active_platform_admin_protection(db_session: Session):
    from app.modules.businesses.platform_service import revoke_platform_admin
    # Only staff@test.com is active platform admin (not owner)
    admin = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin.is_platform_admin = True
    admin.platform_role = "admin"
    db_session.commit()

    actor_id = uuid.uuid4()
    with pytest.raises(ValidationError) as exc_info:
        revoke_platform_admin(db_session, target_user_id=admin.id, actor_user_id=actor_id)
    assert "last active platform administrator" in str(exc_info.value)

    # Verify NO revoke audit log was created
    revoke_log = db_session.query(AuditLog).filter(AuditLog.action == "platform.admin.revoke").first()
    assert revoke_log is None

    # Verify user remains platform admin
    db_session.refresh(admin)
    assert admin.is_platform_admin is True


def test_revoke_sole_active_owner_rejected(client: TestClient, db_session: Session):
    # Sole active platform user is an Owner
    owner = db_session.query(User).filter(User.email == "staff@test.com").first()
    owner.is_platform_admin = True
    owner.platform_role = "owner"
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt revoke on the Owner: Owner protection fires before last-active-admin check
    revoke_resp = client.post(f"/api/v1/platform/admins/{owner.id}/revoke", headers=headers)
    assert revoke_resp.status_code == 422
    assert "Platform Owner privileges cannot be revoked" in revoke_resp.json()["detail"]["error"]["message"]

    # Verify NO revoke audit log was created
    revoke_log = db_session.query(AuditLog).filter(AuditLog.action == "platform.admin.revoke").first()
    assert revoke_log is None

    # Verify user remains platform owner
    db_session.refresh(owner)
    assert owner.is_platform_admin is True
    assert owner.platform_role == "owner"


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
    assert unauth.platform_role == "admin"

    # Promoting again returns True (notice/no-op)
    assert promote_user_to_platform_admin("unauth@test.com", db=db_session) is True


def test_serialization_lock_helper_executes_without_error(db_session: Session):
    from app.modules.businesses.platform_service import _acquire_admin_serialization_lock
    # Verifies helper executes cleanly on test DB session
    _acquire_admin_serialization_lock(db_session)


def test_self_revocation_rejected_when_multiple_admins_exist(db_session: Session):
    from app.modules.businesses.platform_service import revoke_platform_admin
    # Setup two active platform admins: admin1 as owner, admin2 as admin
    admin1 = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin1.is_platform_admin = True
    admin1.platform_role = "owner"
    admin2 = db_session.query(User).filter(User.email == "unauth@test.com").first()
    admin2.is_platform_admin = True
    admin2.platform_role = "admin"
    db_session.commit()

    # admin2 attempts to self-revoke at service level
    with pytest.raises(ValidationError) as exc_info:
        revoke_platform_admin(db_session, target_user_id=admin2.id, actor_user_id=admin2.id)
    assert "cannot revoke their own privileges" in str(exc_info.value).lower()

    # Verify user remains platform admin
    db_session.refresh(admin2)
    assert admin2.is_platform_admin is True

    # Verify NO audit log was generated for rejected self-revocation
    revoke_log = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.admin.revoke",
        AuditLog.actor_user_id == admin2.id,
        AuditLog.entity_id == admin2.id
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


def test_revoke_modern_admin_clears_role_and_denies_commercial_access(client: TestClient, db_session: Session):
    from app.modules.businesses.models import Business

    # 1. Setup active Owner and modern Admin
    owner = db_session.query(User).filter(User.email == "staff@test.com").first()
    owner.is_platform_admin = True
    owner.platform_role = "owner"

    admin = db_session.query(User).filter(User.email == "unauth@test.com").first()
    admin.is_platform_admin = True
    admin.platform_role = "admin"
    db_session.commit()

    # 2. Verify modern Admin initially has commercial and operations access
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "unauth@test.com", "password": "password123"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    assert client.get("/api/v1/platform/businesses", headers=admin_headers).status_code == 200
    assert client.get("/api/v1/platform/plans", headers=admin_headers).status_code == 200
    assert client.get("/api/v1/platform/audit-logs", headers=admin_headers).status_code == 200

    # 3. Owner revokes the modern Admin via API
    owner_login = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    owner_token = owner_login.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    revoke_resp = client.post(f"/api/v1/platform/admins/{admin.id}/revoke", headers=owner_headers)
    assert revoke_resp.status_code == 200
    revoked_payload = revoke_resp.json()
    assert revoked_payload["is_platform_admin"] is False
    assert revoked_payload["platform_role"] is None

    # 4. Assert database fields are both cleared atomically
    db_session.refresh(admin)
    assert admin.is_platform_admin is False
    assert admin.platform_role is None

    # 5. Assert audit log was recorded with actor=owner and target=admin
    revoke_log = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.admin.revoke",
        AuditLog.actor_user_id == owner.id,
        AuditLog.entity_id == admin.id
    ).first()
    assert revoke_log is not None
    assert revoke_log.metadata_json["target_email"] == "unauth@test.com"
    assert revoke_log.metadata_json["outcome"] == "success"

    # 6. Verify effective role via /api/v1/me
    me_resp = client.get("/api/v1/me", headers=admin_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["is_platform_admin"] is False
    assert me_resp.json()["platform_role"] is None

    # 7. CRITICAL VERIFICATION: Revoked user receives HTTP 403 on all commercial and operations endpoints
    assert client.get("/api/v1/platform/businesses", headers=admin_headers).status_code == 403
    assert client.get("/api/v1/platform/plans", headers=admin_headers).status_code == 403
    assert client.get("/api/v1/platform/audit-logs", headers=admin_headers).status_code == 403
    assert client.get("/api/v1/platform/admins", headers=admin_headers).status_code == 403
    assert client.post("/api/v1/platform/businesses", headers=admin_headers, json={
        "name": "Revoked Biz Attempt",
        "owner_email": "mgmt@example.com",
        "owner_password": "Password123!",
        "owner_display_name": "Mgmt Owner",
        "public_slug": "revoked-biz-attempt"
    }).status_code == 403

    biz = db_session.query(Business).first()
    if biz:
        assert client.patch(f"/api/v1/platform/businesses/{biz.id}", headers=admin_headers, json={
            "name": "Unauthorized Update"
        }).status_code == 403


def test_grant_admin_restores_admin_role_and_commercial_access(client: TestClient, db_session: Session):
    # Setup owner and target ordinary user
    owner = db_session.query(User).filter(User.email == "staff@test.com").first()
    owner.is_platform_admin = True
    owner.platform_role = "owner"

    target = db_session.query(User).filter(User.email == "unauth@test.com").first()
    target.is_platform_admin = False
    target.platform_role = None
    db_session.commit()

    owner_login = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}

    # 1. Grant admin
    grant_resp = client.post(f"/api/v1/platform/admins/{target.id}/grant", headers=owner_headers)
    assert grant_resp.status_code == 200
    assert grant_resp.json()["is_platform_admin"] is True
    assert grant_resp.json()["platform_role"] == "admin"

    # 2. Database state verified
    db_session.refresh(target)
    assert target.is_platform_admin is True
    assert target.platform_role == "admin"

    # 3. Target now has commercial access
    target_login = client.post(
        "/api/v1/auth/login",
        json={"email": "unauth@test.com", "password": "password123"},
    )
    target_headers = {"Authorization": f"Bearer {target_login.json()['access_token']}"}

    assert client.get("/api/v1/platform/businesses", headers=target_headers).status_code == 200
    assert client.get("/api/v1/platform/plans", headers=target_headers).status_code == 200

    # 4. Target is an Admin, NOT an Owner: denied on owner-only governance endpoints
    fake_user_id = uuid.uuid4()
    assert client.post(f"/api/v1/platform/admins/{fake_user_id}/grant", headers=target_headers).status_code == 403
    assert client.post(f"/api/v1/platform/admins/{fake_user_id}/revoke", headers=target_headers).status_code == 403


def test_cannot_revoke_owner_via_admin_revoke(client: TestClient, db_session: Session):
    from app.core.errors import ValidationError
    from app.modules.businesses.platform_service import revoke_platform_admin

    owner = db_session.query(User).filter(User.email == "staff@test.com").first()
    owner.is_platform_admin = True
    owner.platform_role = "owner"

    admin = db_session.query(User).filter(User.email == "unauth@test.com").first()
    admin.is_platform_admin = True
    admin.platform_role = "admin"

    # Add a third active admin so len(active_admins) > 1
    third_admin = User(
        email="third_admin@test.com",
        password_hash=owner.password_hash,
        display_name="Third Admin",
        status="active",
        is_platform_admin=True,
        platform_role="admin"
    )
    db_session.add(third_admin)
    db_session.commit()

    # Direct service call attempting to revoke Owner with a different actor ID
    with pytest.raises(ValidationError) as exc_info:
        revoke_platform_admin(db_session, target_user_id=owner.id, actor_user_id=admin.id)
    assert "Owner privileges cannot be revoked" in str(exc_info.value)

    # Verify Owner state is completely unchanged
    db_session.refresh(owner)
    assert owner.is_platform_admin is True
    assert owner.platform_role == "owner"


def test_grant_admin_on_owner_is_noop(client: TestClient, db_session: Session):
    from app.modules.businesses.platform_service import grant_platform_admin

    owner = db_session.query(User).filter(User.email == "staff@test.com").first()
    owner.is_platform_admin = True
    owner.platform_role = "owner"
    db_session.commit()

    initial_audit_count = db_session.query(AuditLog).filter(AuditLog.action == "platform.admin.grant").count()

    result = grant_platform_admin(db_session, target_user_id=owner.id, actor_user_id=owner.id)
    assert result.id == owner.id
    assert result.platform_role == "owner"
    assert result.is_platform_admin is True

    # No duplicate audit log created
    assert db_session.query(AuditLog).filter(AuditLog.action == "platform.admin.grant").count() == initial_audit_count


def test_legacy_admin_revocation_clears_access(client: TestClient, db_session: Session):
    owner = db_session.query(User).filter(User.email == "staff@test.com").first()
    owner.is_platform_admin = True
    owner.platform_role = "owner"

    # Setup legacy admin with platform_role IS NULL
    legacy_admin = db_session.query(User).filter(User.email == "unauth@test.com").first()
    legacy_admin.is_platform_admin = True
    legacy_admin.platform_role = None
    db_session.commit()

    # Legacy admin initially has access via legacy bridge
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "unauth@test.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
    assert client.get("/api/v1/platform/businesses", headers=headers).status_code == 200

    # Owner revokes legacy admin
    owner_login = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}

    revoke_resp = client.post(f"/api/v1/platform/admins/{legacy_admin.id}/revoke", headers=owner_headers)
    assert revoke_resp.status_code == 200

    db_session.refresh(legacy_admin)
    assert legacy_admin.is_platform_admin is False
    assert legacy_admin.platform_role is None

    # Revoked legacy admin is denied access
    assert client.get("/api/v1/platform/businesses", headers=headers).status_code == 403


def test_list_platform_admins_transitional_filtering(db_session: Session):
    from app.modules.businesses.platform_service import list_platform_admins

    # 1. Consistent Owner
    u_owner = User(
        email="owner_test@example.com",
        password_hash="fakehash",
        display_name="Owner User",
        status="active",
        is_platform_admin=True,
        platform_role="owner",
    )
    # 2. Consistent Admin
    u_admin = User(
        email="admin_test@example.com",
        password_hash="fakehash",
        display_name="Admin User",
        status="active",
        is_platform_admin=True,
        platform_role="admin",
    )
    # 3. Legacy Admin (True, None)
    u_legacy = User(
        email="legacy_test@example.com",
        password_hash="fakehash",
        display_name="Legacy Admin",
        status="active",
        is_platform_admin=True,
        platform_role=None,
    )
    # 4. Consistent Operator (False, 'operator')
    u_operator = User(
        email="operator_test@example.com",
        password_hash="fakehash",
        display_name="Operator User",
        status="active",
        is_platform_admin=False,
        platform_role="operator",
    )
    # 5. Regular User (False, None)
    u_regular = User(
        email="regular_test@example.com",
        password_hash="fakehash",
        display_name="Regular User",
        status="active",
        is_platform_admin=False,
        platform_role=None,
    )
    # 6. Contradictory Operator (True, 'operator')
    u_contra_op = User(
        email="contra_op@example.com",
        password_hash="fakehash",
        display_name="Contradictory Operator",
        status="active",
        is_platform_admin=True,
        platform_role="operator",
    )
    # 7. Contradictory Admin (False, 'admin')
    u_contra_admin = User(
        email="contra_admin@example.com",
        password_hash="fakehash",
        display_name="Contradictory Admin",
        status="active",
        is_platform_admin=False,
        platform_role="admin",
    )
    # 8. Contradictory Owner (False, 'owner')
    u_contra_owner = User(
        email="contra_owner@example.com",
        password_hash="fakehash",
        display_name="Contradictory Owner",
        status="active",
        is_platform_admin=False,
        platform_role="owner",
    )
    db_session.add_all([
        u_owner, u_admin, u_legacy, u_operator, u_regular,
        u_contra_op, u_contra_admin, u_contra_owner
    ])
    db_session.commit()

    admins = list_platform_admins(db_session)
    admin_emails = {u.email for u in admins}

    # Must include: consistent Owner, consistent Admin, legacy Admin
    assert "owner_test@example.com" in admin_emails
    assert "admin_test@example.com" in admin_emails
    assert "legacy_test@example.com" in admin_emails

    # Must NOT include: Operator, regular user, or contradictory pairs
    assert "operator_test@example.com" not in admin_emails
    assert "regular_test@example.com" not in admin_emails
    assert "contra_op@example.com" not in admin_emails
    assert "contra_admin@example.com" not in admin_emails
    assert "contra_owner@example.com" not in admin_emails


def test_owner_protection_precedence_over_last_active_admin(db_session: Session):
    from app.modules.businesses.platform_service import revoke_platform_admin
    # Ensure ONLY one active admin exists and it is an Owner
    users = db_session.query(User).all()
    for u in users:
        u.is_platform_admin = False
        u.platform_role = None
    db_session.commit()

    sole_owner = db_session.query(User).filter(User.email == "staff@test.com").first()
    sole_owner.is_platform_admin = True
    sole_owner.platform_role = "owner"
    sole_owner.status = "active"
    db_session.commit()

    # Active admins count is exactly 1 (<= 1)
    # If last-active-admin check ran first, it would raise "Cannot revoke ... last active platform administrator"
    # Because Owner check runs first, it must raise "Platform Owner privileges cannot be revoked."
    with pytest.raises(ValidationError) as exc_info:
        revoke_platform_admin(db_session, target_user_id=sole_owner.id, actor_user_id=uuid.uuid4())
    assert "Platform Owner privileges cannot be revoked" in str(exc_info.value)
    assert "last active" not in str(exc_info.value).lower()


def test_advisory_lock_helper_postgres_and_sqlite_behavior(db_session: Session):
    from unittest.mock import MagicMock
    from app.modules.businesses.platform_service import (
        _acquire_admin_serialization_lock,
        ADMIN_PRIVILEGE_LOCK_KEY,
    )

    # 1. SQLite dialect skips PG-specific lock SQL without error
    assert db_session.bind.dialect.name == "sqlite"
    _acquire_admin_serialization_lock(db_session)

    # 2. Mock PostgreSQL dialect executes the intended pg_advisory_xact_lock
    mock_db = MagicMock()
    mock_db.bind.dialect.name = "postgresql"
    _acquire_admin_serialization_lock(mock_db)
    mock_db.execute.assert_called_once()
    executed_sql = str(mock_db.execute.call_args[0][0])
    assert "pg_advisory_xact_lock" in executed_sql
    params = mock_db.execute.call_args[0][1]
    assert params["key"] == ADMIN_PRIVILEGE_LOCK_KEY
    assert params["key"] == 424242111


def test_grant_platform_admin_rejects_non_active_users(db_session: Session):
    from app.modules.businesses.platform_service import grant_platform_admin

    admin = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin.is_platform_admin = True
    admin.platform_role = "owner"
    admin.status = "active"

    target = db_session.query(User).filter(User.email == "unauth@test.com").first()
    target.is_platform_admin = False
    target.platform_role = None
    target.status = "suspended"
    db_session.commit()

    # 1. Suspended user is rejected with ValidationError
    with pytest.raises(ValidationError) as exc_info:
        grant_platform_admin(db_session, target_user_id=target.id, actor_user_id=admin.id)
    assert "Cannot grant platform administrator privileges to user with status 'suspended'" in str(exc_info.value)
    assert "Only active accounts can be promoted" in str(exc_info.value)

    db_session.refresh(target)
    assert target.is_platform_admin is False
    assert target.platform_role is None

    # 2. Inactive / pending user is rejected with ValidationError
    target.status = "inactive"
    db_session.commit()

    with pytest.raises(ValidationError) as exc_info:
        grant_platform_admin(db_session, target_user_id=target.id, actor_user_id=admin.id)
    assert "Cannot grant platform administrator privileges to user with status 'inactive'" in str(exc_info.value)
    assert "Only active accounts can be promoted" in str(exc_info.value)

    db_session.refresh(target)
    assert target.is_platform_admin is False
    assert target.platform_role is None

    # 3. Active user succeeds
    target.status = "active"
    db_session.commit()

    promoted = grant_platform_admin(db_session, target_user_id=target.id, actor_user_id=admin.id)
    assert promoted.is_platform_admin is True
    assert promoted.platform_role == "admin"


def test_grant_platform_admin_api_rejects_suspended_user(client: TestClient, db_session: Session):
    owner = db_session.query(User).filter(User.email == "staff@test.com").first()
    owner.is_platform_admin = True
    owner.platform_role = "owner"
    owner.status = "active"

    target = db_session.query(User).filter(User.email == "unauth@test.com").first()
    target.is_platform_admin = False
    target.platform_role = None
    target.status = "suspended"
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempting to grant admin to suspended user returns HTTP 422 (ValidationError mapping in ROMS) / 400
    grant_resp = client.post(f"/api/v1/platform/admins/{target.id}/grant", headers=headers)
    assert grant_resp.status_code in (400, 422)
    err_msg = grant_resp.json()["detail"]["error"]["message"]
    assert "Cannot grant platform administrator privileges to user with status 'suspended'" in err_msg
    assert "Only active accounts can be promoted" in err_msg

    # Verify target user was not modified in DB
    db_session.refresh(target)
    assert target.is_platform_admin is False
    assert target.platform_role is None
    assert target.status == "suspended"


def test_grant_platform_admin_rejects_suspended_preexisting_admin(db_session: Session):
    from app.modules.businesses.platform_service import grant_platform_admin

    admin = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin.is_platform_admin = True
    admin.platform_role = "owner"
    admin.status = "active"

    # Set up the target user explicitly as a suspended pre-existing Admin
    target = db_session.query(User).filter(User.email == "unauth@test.com").first()
    target.is_platform_admin = True
    target.platform_role = "admin"
    target.status = "suspended"
    db_session.commit()

    initial_audit_count = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.admin.grant",
        AuditLog.entity_id == target.id,
    ).count()

    # 1. Raises expected ValidationError; no successful idempotent return occurs
    with pytest.raises(ValidationError) as exc_info:
        grant_platform_admin(db_session, target_user_id=target.id, actor_user_id=admin.id)
    assert "Cannot grant platform administrator privileges to user with status 'suspended'" in str(exc_info.value)
    assert "Only active accounts can be promoted" in str(exc_info.value)

    # 2. Target remains status == "suspended"
    # 3. Target remains is_platform_admin is True
    # 4. Target remains platform_role == "admin"
    db_session.refresh(target)
    assert target.status == "suspended"
    assert target.is_platform_admin is True
    assert target.platform_role == "admin"

    # 5-6. No unintended mutation or audit event representing a successful grant is produced
    final_audit_count = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.admin.grant",
        AuditLog.entity_id == target.id,
    ).count()
    assert final_audit_count == initial_audit_count

