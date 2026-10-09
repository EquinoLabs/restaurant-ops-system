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

    success = promote_user_to_platform_admin("staff@test.com", db=db_session)
    assert success is True

    db_session.refresh(user)
    assert user.is_platform_admin is True


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
