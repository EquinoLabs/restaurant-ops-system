import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.api.deps import get_current_platform_admin
from app.modules.staff.models import User
from scripts.create_platform_admin import promote_user_to_platform_admin

from app.core.security import hash_password


# Dummy router to exercise get_current_platform_admin dependency safely in tests
dummy_platform_router = APIRouter()

@dummy_platform_router.get("/api/v1/dummy-platform/ping")
def dummy_platform_ping_endpoint(admin_user: User = Depends(get_current_platform_admin)):
    return {"status": "ok", "admin_email": admin_user.email}

app.include_router(dummy_platform_router)



def test_default_user_is_not_platform_admin(db_session: Session):
    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    assert user is not None
    assert user.is_platform_admin is False


def test_cli_promote_existing_user(db_session: Session):
    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    assert user.is_platform_admin is False
    assert user.platform_role is None

    success = promote_user_to_platform_admin("staff@test.com", db=db_session)
    assert success is True

    db_session.refresh(user)
    assert user.is_platform_admin is True
    assert user.platform_role == "admin"


def test_cli_promote_owner_is_safe_noop(db_session: Session):
    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    user.is_platform_admin = True
    user.platform_role = "owner"
    db_session.commit()

    success = promote_user_to_platform_admin("staff@test.com", db=db_session)
    assert success is True

    db_session.refresh(user)
    assert user.is_platform_admin is True
    assert user.platform_role == "owner"


def test_cli_promote_unknown_user_fails(db_session: Session):
    success = promote_user_to_platform_admin("nonexistent@test.com", db=db_session)
    assert success is False


def test_platform_admin_dependency_authorization(client: TestClient, db_session: Session):
    # 1. Unauthenticated request -> 401 Unauthorized
    unauth_resp = client.get("/api/v1/dummy-platform/ping")
    assert unauth_resp.status_code == 401

    # 2. Authenticated non-admin user -> 403 Forbidden
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    forbidden_resp = client.get("/api/v1/dummy-platform/ping", headers=headers)
    assert forbidden_resp.status_code == 403
    assert "Platform administrator privileges are required" in forbidden_resp.json()["detail"]["error"]["message"]

    # 3. Promote user to platform admin
    staff_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff_user.is_platform_admin = True
    db_session.commit()

    # 4. Authenticated platform admin user -> 200 OK
    allowed_resp = client.get("/api/v1/dummy-platform/ping", headers=headers)
    assert allowed_resp.status_code == 200
    assert allowed_resp.json()["admin_email"] == "staff@test.com"



def test_user_me_profile_includes_is_platform_admin(client: TestClient, db_session: Session):
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_resp = client.get("/api/v1/me", headers=headers)
    assert me_resp.status_code == 200
    assert "is_platform_admin" in me_resp.json()
    assert me_resp.json()["is_platform_admin"] is False


def test_user_model_platform_role_nullable(db_session: Session):
    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    assert user is not None
    # 1. Existing users have platform_role is None
    assert user.platform_role is None

    # 2. Can be set to a valid role string and persisted
    user.platform_role = "admin"
    db_session.commit()
    db_session.refresh(user)
    assert user.platform_role == "admin"

    # 3. Can be set back to None and persisted
    user.platform_role = None
    db_session.commit()
    db_session.refresh(user)
    assert user.platform_role is None


def test_user_me_profile_includes_nullable_platform_role(client: TestClient, db_session: Session):
    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    assert user is not None
    user.platform_role = None
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Default response includes platform_role: None
    me_resp = client.get("/api/v1/me", headers=headers)
    assert me_resp.status_code == 200
    assert "platform_role" in me_resp.json()
    assert me_resp.json()["platform_role"] is None

    # 2. When set, returns the assigned role string
    user.platform_role = "operator"
    db_session.commit()

    me_resp2 = client.get("/api/v1/me", headers=headers)
    assert me_resp2.status_code == 200
    assert me_resp2.json()["platform_role"] == "operator"

    # Reset
    user.platform_role = None
    db_session.commit()


def test_platform_admin_user_out_schema_platform_role_compatibility(db_session: Session):
    from app.modules.businesses.schemas import PlatformAdminUserOut

    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    assert user is not None

    # 1. Serializing from User model with platform_role = None
    user.platform_role = None
    user.is_platform_admin = True
    db_session.commit()
    db_session.refresh(user)

    schema_out = PlatformAdminUserOut.model_validate(user)
    assert schema_out.platform_role is None
    assert schema_out.is_platform_admin is True

    # 2. Serializing from User model with platform_role = "admin"
    user.platform_role = "admin"
    db_session.commit()
    db_session.refresh(user)

    schema_out2 = PlatformAdminUserOut.model_validate(user)
    assert schema_out2.platform_role == "admin"
    assert schema_out2.is_platform_admin is True

    # Reset
    user.platform_role = None
    user.is_platform_admin = False
    db_session.commit()


def test_require_platform_role_audit_cases(client: TestClient, db_session: Session):
    from app.api.deps import RequirePlatformRole, get_current_platform_admin
    from app.core.errors import ForbiddenError

    owner_guard = RequirePlatformRole(["owner"])
    admin_guard = RequirePlatformRole(["owner", "admin"])
    operator_guard = RequirePlatformRole(["operator"])

    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    assert user is not None

    # 1. platform_role="owner" grants Owner access only where permitted
    user.platform_role = "owner"
    user.is_platform_admin = True
    assert owner_guard(current_user=user).id == user.id
    assert admin_guard(current_user=user).id == user.id
    with pytest.raises(ForbiddenError):
        operator_guard(current_user=user)

    # 2. platform_role="admin" grants Admin access where permitted (rejected on owner-only)
    user.platform_role = "admin"
    user.is_platform_admin = True
    assert admin_guard(current_user=user).id == user.id
    with pytest.raises(ForbiddenError):
        owner_guard(current_user=user)
    with pytest.raises(ForbiddenError):
        operator_guard(current_user=user)

    # 3. platform_role="operator" grants only explicitly permitted Operator access
    user.platform_role = "operator"
    user.is_platform_admin = False
    assert operator_guard(current_user=user).id == user.id
    with pytest.raises(ForbiddenError):
        admin_guard(current_user=user)
    with pytest.raises(ForbiddenError):
        owner_guard(current_user=user)

    # 4. platform_role=None with is_platform_admin=True maps to Admin, NEVER Owner
    user.platform_role = None
    user.is_platform_admin = True
    assert admin_guard(current_user=user).id == user.id
    with pytest.raises(ForbiddenError):
        owner_guard(current_user=user)
    with pytest.raises(ForbiddenError):
        operator_guard(current_user=user)

    # 5. Non-null but unsupported platform_role is rejected; MUST NOT fall back to legacy boolean
    for unsupported_role in ["superuser", "guest", "unknown", "", "   "]:
        user.platform_role = unsupported_role
        user.is_platform_admin = True
        with pytest.raises(ForbiddenError):
            admin_guard(current_user=user)
        with pytest.raises(ForbiddenError):
            owner_guard(current_user=user)

    # 6. A conflicting legacy boolean cannot elevate a caller whose non-null role is more restrictive
    user.platform_role = "operator"
    user.is_platform_admin = True  # Conflicting True boolean
    assert operator_guard(current_user=user).id == user.id
    with pytest.raises(ForbiddenError):
        admin_guard(current_user=user)
    with pytest.raises(ForbiddenError):
        owner_guard(current_user=user)

    # 7. A user with is_platform_admin=False and no platform role cannot access protected routes
    user.platform_role = None
    user.is_platform_admin = False
    with pytest.raises(ForbiddenError):
        admin_guard(current_user=user)
    with pytest.raises(ForbiddenError):
        owner_guard(current_user=user)
    with pytest.raises(ForbiddenError):
        operator_guard(current_user=user)

    # 8. get_current_platform_admin backward compatibility: allows admin and owner, never elevates to owner
    user.platform_role = None
    user.is_platform_admin = True
    assert get_current_platform_admin(current_user=admin_guard(current_user=user)).id == user.id

    # Reset
    user.platform_role = None
    user.is_platform_admin = False
    db_session.commit()

