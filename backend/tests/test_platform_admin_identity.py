import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.api.deps import get_current_platform_admin
from app.modules.staff.models import User
from scripts.create_platform_admin import promote_user_to_platform_admin

from app.core.security import hash_password
from app.core.errors import AuthenticationError, ForbiddenError
from app.modules.staff.service import authenticate_user


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

    # 6. Contradictory role/boolean pairs fail closed on all guards
    # ('operator', True) is rejected
    user.platform_role = "operator"
    user.is_platform_admin = True
    with pytest.raises(ForbiddenError):
        operator_guard(current_user=user)
    with pytest.raises(ForbiddenError):
        admin_guard(current_user=user)
    with pytest.raises(ForbiddenError):
        owner_guard(current_user=user)

    # ('admin', False) is rejected
    user.platform_role = "admin"
    user.is_platform_admin = False
    with pytest.raises(ForbiddenError):
        admin_guard(current_user=user)
    with pytest.raises(ForbiddenError):
        owner_guard(current_user=user)
    with pytest.raises(ForbiddenError):
        operator_guard(current_user=user)

    # ('owner', False) is rejected
    user.platform_role = "owner"
    user.is_platform_admin = False
    with pytest.raises(ForbiddenError):
        owner_guard(current_user=user)
    with pytest.raises(ForbiddenError):
        admin_guard(current_user=user)
    with pytest.raises(ForbiddenError):
        operator_guard(current_user=user)

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


def test_cli_promote_first_owner_success(db_session: Session):
    # Ensure no active owners exist initially
    users = db_session.query(User).all()
    for u in users:
        u.is_platform_admin = False
        u.platform_role = None
    db_session.commit()

    success = promote_user_to_platform_admin("unauth@test.com", role="owner", db=db_session)
    assert success is True

    unauth = db_session.query(User).filter(User.email == "unauth@test.com").first()
    assert unauth.is_platform_admin is True
    assert unauth.platform_role == "owner"


def test_cli_promote_second_owner_refused(db_session: Session):
    # Setup existing active Owner
    owner = db_session.query(User).filter(User.email == "staff@test.com").first()
    owner.is_platform_admin = True
    owner.platform_role = "owner"
    owner.status = "active"

    candidate = db_session.query(User).filter(User.email == "unauth@test.com").first()
    candidate.is_platform_admin = False
    candidate.platform_role = None
    db_session.commit()

    # Attempting to bootstrap a second owner must be refused
    success = promote_user_to_platform_admin("unauth@test.com", role="owner", db=db_session)
    assert success is False

    db_session.refresh(candidate)
    assert candidate.is_platform_admin is False
    assert candidate.platform_role is None


def test_cli_promote_owner_idempotent(db_session: Session):
    # Setup existing active Owner
    owner = db_session.query(User).filter(User.email == "staff@test.com").first()
    owner.is_platform_admin = True
    owner.platform_role = "owner"
    owner.status = "active"
    db_session.commit()

    # Repeated invocation on same Owner returns True
    success = promote_user_to_platform_admin("staff@test.com", role="owner", db=db_session)
    assert success is True

    db_session.refresh(owner)
    assert owner.is_platform_admin is True
    assert owner.platform_role == "owner"


def test_cli_promote_suspended_user_as_owner_refused(db_session: Session):
    # Ensure no active owners exist initially
    users = db_session.query(User).all()
    for u in users:
        u.is_platform_admin = False
        u.platform_role = None
    target = db_session.query(User).filter(User.email == "unauth@test.com").first()
    target.status = "suspended"
    db_session.commit()

    # Designating a suspended user as Owner must be refused
    success = promote_user_to_platform_admin("unauth@test.com", role="owner", db=db_session)
    assert success is False

    db_session.refresh(target)
    assert target.is_platform_admin is False
    assert target.platform_role is None
    assert target.status == "suspended"

    # Reset
    target.status = "active"
    db_session.commit()


def test_cli_promote_suspended_user_as_admin_refused(db_session: Session):
    target = db_session.query(User).filter(User.email == "unauth@test.com").first()
    target.status = "suspended"
    target.is_platform_admin = False
    target.platform_role = None
    db_session.commit()

    # Promoting a suspended user as Admin must be refused
    success = promote_user_to_platform_admin("unauth@test.com", role="admin", db=db_session)
    assert success is False

    db_session.refresh(target)
    assert target.is_platform_admin is False
    assert target.platform_role is None
    assert target.status == "suspended"

    # Reset
    target.status = "active"
    db_session.commit()


def test_cli_promote_inactive_nonactive_status_refused(db_session: Session):
    target = db_session.query(User).filter(User.email == "unauth@test.com").first()
    target.status = "pending"
    target.is_platform_admin = False
    target.platform_role = None
    db_session.commit()

    # Promoting a user with non-active status ('pending') must be refused
    success = promote_user_to_platform_admin("unauth@test.com", role="admin", db=db_session)
    assert success is False

    db_session.refresh(target)
    assert target.is_platform_admin is False
    assert target.platform_role is None
    assert target.status == "pending"

    # Reset
    target.status = "active"
    db_session.commit()


def test_cli_promote_contradictory_owner_repaired(db_session: Session):
    # Setup active user with platform_role="owner" but is_platform_admin=False
    owner = db_session.query(User).filter(User.email == "staff@test.com").first()
    owner.status = "active"
    owner.platform_role = "owner"
    owner.is_platform_admin = False
    db_session.commit()

    # Re-invoking owner role repairs contradictory boolean
    success = promote_user_to_platform_admin("staff@test.com", role="owner", db=db_session)
    assert success is True

    db_session.refresh(owner)
    assert owner.status == "active"
    assert owner.platform_role == "owner"
    assert owner.is_platform_admin is True


def test_cli_promote_external_session_caller_work_preserved(db_session: Session):
    staff = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff.display_name = "Dirty Uncommitted Modification"

    # 1. Failure (user not found) preserves caller uncommitted work without rolling back
    success_missing = promote_user_to_platform_admin("nonexistent@test.com", db=db_session)
    assert success_missing is False
    assert staff.display_name == "Dirty Uncommitted Modification"

    # 2. Failure (suspended user) preserves caller uncommitted work without rolling back
    target = db_session.query(User).filter(User.email == "unauth@test.com").first()
    target.status = "suspended"
    success_suspended = promote_user_to_platform_admin("unauth@test.com", db=db_session)
    assert success_suspended is False
    assert staff.display_name == "Dirty Uncommitted Modification"

    # 3. Success flushes but does not commit caller's transaction
    target.status = "active"
    success_promote = promote_user_to_platform_admin("unauth@test.com", role="admin", db=db_session)
    assert success_promote is True
    assert staff.display_name == "Dirty Uncommitted Modification"

    # Cleanup
    db_session.rollback()


def test_cli_promote_external_session_early_return_safe(db_session: Session):
    # Missing user triggers early return
    success = promote_user_to_platform_admin("nonexistent@test.com", db=db_session)
    assert success is False

    # Session is cleanly usable immediately following early return
    staff = db_session.query(User).filter(User.email == "staff@test.com").first()
    assert staff is not None


def test_cli_promote_invalid_role_refused(db_session: Session):
    assert promote_user_to_platform_admin("unauth@test.com", role="operator", db=db_session) is False
    assert promote_user_to_platform_admin("unauth@test.com", role="superadmin", db=db_session) is False
    assert promote_user_to_platform_admin("unauth@test.com", role="", db=db_session) is False


def test_cli_promote_explicit_target_selection(db_session: Session):
    staff = db_session.query(User).filter(User.email == "staff@test.com").first()
    unauth = db_session.query(User).filter(User.email == "unauth@test.com").first()
    staff.is_platform_admin = False
    staff.platform_role = None
    unauth.is_platform_admin = False
    unauth.platform_role = None
    db_session.commit()

    success = promote_user_to_platform_admin("unauth@test.com", role="admin", db=db_session)
    assert success is True

    db_session.refresh(unauth)
    db_session.refresh(staff)
    assert unauth.is_platform_admin is True
    assert unauth.platform_role == "admin"
    assert staff.is_platform_admin is False
    assert staff.platform_role is None


def test_cli_promote_script_owned_mode_commits_and_rolls_back():
    from unittest.mock import patch, MagicMock

    # 1. Success commits and closes script-owned session
    mock_session = MagicMock()
    mock_user = MagicMock()
    mock_user.status = "active"
    mock_user.platform_role = None
    mock_user.is_platform_admin = False
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user

    with patch("scripts.create_platform_admin.SessionLocal", return_value=mock_session):
        success = promote_user_to_platform_admin("test@example.com", role="admin", db=None)
        assert success is True
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    # 2. Refusal/failure rolls back and closes script-owned session
    mock_session_fail = MagicMock()
    mock_session_fail.query.return_value.filter.return_value.first.return_value = None

    with patch("scripts.create_platform_admin.SessionLocal", return_value=mock_session_fail):
        success = promote_user_to_platform_admin("nonexistent@example.com", role="admin", db=None)
        assert success is False
        mock_session_fail.rollback.assert_called_once()
        mock_session_fail.close.assert_called_once()

    # 3. Unhandled error rolls back, re-raises, and closes script-owned session
    mock_session_err = MagicMock()
    mock_session_err.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session_err.commit.side_effect = RuntimeError("Simulated commit error")

    with patch("scripts.create_platform_admin.SessionLocal", return_value=mock_session_err):
        with pytest.raises(RuntimeError, match="Simulated commit error"):
            promote_user_to_platform_admin("test@example.com", role="admin", db=None)
        mock_session_err.rollback.assert_called_once()
        mock_session_err.close.assert_called_once()


def test_suspended_user_cannot_authenticate(db_session: Session):
    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    user.status = "suspended"
    db_session.commit()

    with pytest.raises(AuthenticationError) as exc_info:
        authenticate_user(db_session, email="staff@test.com", password="password123")
    assert "inactive" in str(exc_info.value).lower()

    # Reset
    user.status = "active"
    db_session.commit()


def test_suspended_user_login_endpoint_denied(client: TestClient, db_session: Session):
    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    user.status = "suspended"
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    assert resp.status_code == 401
    assert "inactive" in resp.json()["detail"]["error"]["message"].lower()

    # Reset
    user.status = "active"
    db_session.commit()


def test_suspended_user_token_invalidated_after_suspension(client: TestClient, db_session: Session):
    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    user.status = "active"
    db_session.commit()

    # 1. Login successfully while active
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Token works initially
    me_resp = client.get("/api/v1/me", headers=headers)
    assert me_resp.status_code == 200

    # 3. User account is suspended
    user.status = "suspended"
    db_session.commit()

    # 4. Previously issued bearer token is rejected on subsequent authenticated request
    me_resp_after = client.get("/api/v1/me", headers=headers)
    assert me_resp_after.status_code == 401
    assert "inactive" in me_resp_after.json()["detail"]["error"]["message"].lower()

    # Reset
    user.status = "active"
    db_session.commit()


def test_suspended_user_denied_platform_routes(client: TestClient, db_session: Session):
    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    user.status = "active"
    user.is_platform_admin = True
    user.platform_role = "admin"
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify access while active
    assert client.get("/api/v1/dummy-platform/ping", headers=headers).status_code == 200

    # Suspend user
    user.status = "suspended"
    db_session.commit()

    # Access denied on subsequent request with previously valid token
    resp = client.get("/api/v1/dummy-platform/ping", headers=headers)
    assert resp.status_code == 401
    assert "inactive" in resp.json()["detail"]["error"]["message"].lower()

    # Reset
    user.status = "active"
    user.is_platform_admin = False
    user.platform_role = None
    db_session.commit()


def test_active_user_authenticates_normally(client: TestClient, db_session: Session):
    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    user.status = "active"
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_resp = client.get("/api/v1/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "staff@test.com"


def test_require_platform_role_exact_matching_and_rejection_of_malformed_roles(db_session: Session):
    from app.api.deps import RequirePlatformRole
    from app.core.errors import ForbiddenError

    owner_guard = RequirePlatformRole(["owner"])
    admin_guard = RequirePlatformRole(["owner", "admin"])
    operator_guard = RequirePlatformRole(["operator"])
    any_platform_guard = RequirePlatformRole(["owner", "admin", "operator"])

    user = db_session.query(User).filter(User.email == "staff@test.com").first()

    malformed_roles = [
        # Case variants
        "Owner", "OWNER", "Admin", "ADMIN", "Operator", "OPERATOR", "Admin ",
        # Leading / trailing whitespace
        " admin", "admin ", " owner ", "\tadmin", "operator\n", "  operator  ",
        # Empty string and whitespace-only
        "", "   ", "\t", "\n",
        # Unsupported strings
        "superuser", "guest", "root", "unknown",
    ]

    for role_val in malformed_roles:
        # Test with is_platform_admin=True: MUST fail closed with ForbiddenError, NOT fall back to admin
        user.platform_role = role_val
        user.is_platform_admin = True
        for guard in [owner_guard, admin_guard, operator_guard, any_platform_guard]:
            with pytest.raises(ForbiddenError):
                guard(current_user=user)

        # Test with is_platform_admin=False: MUST fail closed with ForbiddenError
        user.is_platform_admin = False
        for guard in [owner_guard, admin_guard, operator_guard, any_platform_guard]:
            with pytest.raises(ForbiddenError):
                guard(current_user=user)

    # Legacy fallback: platform_role=None with is_platform_admin=True maps strictly to admin
    user.platform_role = None
    user.is_platform_admin = True
    assert admin_guard(current_user=user).id == user.id
    assert any_platform_guard(current_user=user).id == user.id
    with pytest.raises(ForbiddenError):
        owner_guard(current_user=user)
    with pytest.raises(ForbiddenError):
        operator_guard(current_user=user)

    # Valid exact roles with consistent booleans succeed on their respective guards
    user.platform_role = "owner"
    user.is_platform_admin = True
    assert owner_guard(current_user=user).id == user.id
    assert admin_guard(current_user=user).id == user.id
    assert any_platform_guard(current_user=user).id == user.id
    with pytest.raises(ForbiddenError):
        operator_guard(current_user=user)

    user.platform_role = "admin"
    user.is_platform_admin = True
    assert admin_guard(current_user=user).id == user.id
    assert any_platform_guard(current_user=user).id == user.id
    with pytest.raises(ForbiddenError):
        owner_guard(current_user=user)
    with pytest.raises(ForbiddenError):
        operator_guard(current_user=user)

    user.platform_role = "operator"
    user.is_platform_admin = False
    assert operator_guard(current_user=user).id == user.id
    assert any_platform_guard(current_user=user).id == user.id
    with pytest.raises(ForbiddenError):
        owner_guard(current_user=user)
    with pytest.raises(ForbiddenError):
        admin_guard(current_user=user)

    # Cleanup
    user.platform_role = None
    user.is_platform_admin = False
    db_session.commit()

