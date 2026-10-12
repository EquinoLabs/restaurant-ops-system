import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.staff.models import User
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.audit.models import AuditLog
from app.core.security import hash_password


def _create_user(db: Session, email: str, role: str, is_admin: bool = True) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            password_hash=hash_password("password123"),
            display_name=f"User {role}",
            status="active",
            is_platform_admin=is_admin,
            platform_role=role,
        )
        db.add(user)
    else:
        user.is_platform_admin = is_admin
        user.platform_role = role
    db.commit()
    db.refresh(user)
    return user


def _auth_headers(client: TestClient, email: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_setup(client: TestClient, db_session: Session):
    # Setup test users
    owner = _create_user(db_session, "owner_profile@test.com", "owner", is_admin=True)
    admin = _create_user(db_session, "admin_profile@test.com", "admin", is_admin=True)
    operator = _create_user(db_session, "operator_profile@test.com", "operator", is_admin=False)
    staff = _create_user(db_session, "staff_profile@test.com", "waiter", is_admin=False)

    # Setup test business and outlet
    biz = Business(
        name="Original Business Name",
        status="active",
        subscription_status="active",
        plan_name="growth_pos",
        max_outlets=5
    )
    db_session.add(biz)
    db_session.flush()

    outlet = Outlet(
        business_id=biz.id,
        name="Original Outlet Name",
        public_slug="original-outlet-slug",
        timezone="Asia/Kolkata",
        currency="INR",
        address="123 Original St, Shimla",
        status="active",
        primary_color="#4F46E5",
        accent_color="#10B981",
    )
    db_session.add(outlet)
    db_session.commit()
    db_session.refresh(biz)
    db_session.refresh(outlet)

    return {
        "owner_headers": _auth_headers(client, owner.email),
        "admin_headers": _auth_headers(client, admin.email),
        "operator_headers": _auth_headers(client, operator.email),
        "staff_headers": _auth_headers(client, staff.email),
        "business": biz,
        "outlet": outlet,
    }


def test_business_name_update_permissions(client: TestClient, db_session: Session, test_setup):
    biz = test_setup["business"]

    # 1. Unauthenticated -> 401
    assert client.patch(f"/api/v1/platform/businesses/{biz.id}", json={"name": "New Name"}).status_code == 401

    # 2. Staff user (non-platform) -> 403 Forbidden
    resp = client.patch(
        f"/api/v1/platform/businesses/{biz.id}",
        headers=test_setup["staff_headers"],
        json={"name": "Staff Attempt"}
    )
    assert resp.status_code == 403

    # 3. Platform Operator -> 403 Forbidden (Decision D-01 enforcement)
    op_resp = client.patch(
        f"/api/v1/platform/businesses/{biz.id}",
        headers=test_setup["operator_headers"],
        json={"name": "Operator Business Attempt"}
    )
    assert op_resp.status_code == 403
    assert "Platform administrator privileges are required" in op_resp.json()["detail"]["error"]["message"]

    # 4. Platform Admin -> 200 OK
    admin_resp = client.patch(
        f"/api/v1/platform/businesses/{biz.id}",
        headers=test_setup["admin_headers"],
        json={"name": "Admin Updated Business"}
    )
    assert admin_resp.status_code == 200
    assert admin_resp.json()["name"] == "Admin Updated Business"

    # 5. Platform Owner -> 200 OK
    owner_resp = client.patch(
        f"/api/v1/platform/businesses/{biz.id}",
        headers=test_setup["owner_headers"],
        json={"name": "Owner Final Business Name"}
    )
    assert owner_resp.status_code == 200
    assert owner_resp.json()["name"] == "Owner Final Business Name"

    # Verify audit log recorded
    audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.business_id == biz.id,
            AuditLog.action == "platform.business.profile_update"
        )
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.metadata_json["before"]["name"] == "Admin Updated Business"
    assert audit.metadata_json["after"]["name"] == "Owner Final Business Name"


def test_business_name_validation_and_commercial_protection(client: TestClient, db_session: Session, test_setup):
    biz = test_setup["business"]
    admin_headers = test_setup["admin_headers"]

    # Empty name -> 422
    assert client.patch(f"/api/v1/platform/businesses/{biz.id}", headers=admin_headers, json={"name": ""}).status_code == 422
    assert client.patch(f"/api/v1/platform/businesses/{biz.id}", headers=admin_headers, json={"name": "   "}).status_code == 422

    # Commercial fields are ignored and cannot be mutated via profile endpoint
    resp = client.patch(
        f"/api/v1/platform/businesses/{biz.id}",
        headers=admin_headers,
        json={
            "name": "Protected Biz",
            "subscription_status": "cancelled",
            "plan_name": "free",
            "max_outlets": 999,
            "status": "suspended"
        }
    )
    assert resp.status_code == 200
    updated_biz = resp.json()
    assert updated_biz["name"] == "Protected Biz"
    assert updated_biz["subscription_status"] == "active"
    assert updated_biz["plan_name"] == "growth_pos"
    assert updated_biz["max_outlets"] == 5
    assert updated_biz["status"] == "active"


def test_outlet_profile_update_permissions(client: TestClient, db_session: Session, test_setup):
    outlet = test_setup["outlet"]

    # 1. Unauthenticated -> 401
    assert client.patch(f"/api/v1/platform/outlets/{outlet.id}", json={"name": "New Outlet"}).status_code == 401

    # 2. Staff user (non-platform) -> 403 Forbidden
    resp = client.patch(
        f"/api/v1/platform/outlets/{outlet.id}",
        headers=test_setup["staff_headers"],
        json={"name": "Staff Attempt"}
    )
    assert resp.status_code == 403

    # 3. Platform Operator -> 200 OK (Allowed per Decision D-01)
    op_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet.id}",
        headers=test_setup["operator_headers"],
        json={
            "name": "Operator Updated Outlet",
            "address": "456 Operator Way, Manali",
            "timezone": "Asia/Kolkata",
            "currency": "INR",
            "primary_color": "#2563EB",
            "accent_color": "#F59E0B"
        }
    )
    assert op_resp.status_code == 200
    op_data = op_resp.json()
    assert op_data["name"] == "Operator Updated Outlet"
    assert op_data["address"] == "456 Operator Way, Manali"
    assert op_data["primary_color"] == "#2563EB"
    assert op_data["accent_color"] == "#F59E0B"
    assert op_data["public_slug"] == "original-outlet-slug"  # Slug remains immutable

    # 4. Platform Admin -> 200 OK
    admin_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet.id}",
        headers=test_setup["admin_headers"],
        json={"name": "Admin Updated Outlet"}
    )
    assert admin_resp.status_code == 200
    assert admin_resp.json()["name"] == "Admin Updated Outlet"

    # 5. Platform Owner -> 200 OK
    owner_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet.id}",
        headers=test_setup["owner_headers"],
        json={"name": "Owner Final Outlet"}
    )
    assert owner_resp.status_code == 200
    assert owner_resp.json()["name"] == "Owner Final Outlet"

    # Verify audit log recorded
    audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.outlet_id == outlet.id,
            AuditLog.action == "platform.outlet.profile_update"
        )
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.metadata_json["before"]["name"] == "Admin Updated Outlet"
    assert audit.metadata_json["after"]["name"] == "Owner Final Outlet"


def test_outlet_profile_validation_and_slug_immutability(client: TestClient, db_session: Session, test_setup):
    outlet = test_setup["outlet"]
    op_headers = test_setup["operator_headers"]

    # 1. Invalid timezone -> 422
    tz_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet.id}",
        headers=op_headers,
        json={"timezone": "Invalid/Fake_Zone"}
    )
    assert tz_resp.status_code == 422
    assert "Invalid timezone identifier" in tz_resp.text

    # 2. Invalid currency code -> 422
    curr_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet.id}",
        headers=op_headers,
        json={"currency": "RUPEES"}
    )
    assert curr_resp.status_code == 422
    assert "Invalid currency code" in curr_resp.text

    # 3. Invalid hex colors -> 422
    color_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet.id}",
        headers=op_headers,
        json={"primary_color": "not-a-color"}
    )
    assert color_resp.status_code == 422
    assert "Invalid hex color format" in color_resp.text

    color_resp2 = client.patch(
        f"/api/v1/platform/outlets/{outlet.id}",
        headers=op_headers,
        json={"accent_color": "#123"}  # 3-digit hex rejected
    )
    assert color_resp2.status_code == 422

    # 4. Slug immutability: passing public_slug in body does not change DB slug
    slug_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet.id}",
        headers=op_headers,
        json={"name": "Valid Outlet", "public_slug": "hacked-slug"}
    )
    assert slug_resp.status_code == 200
    assert slug_resp.json()["public_slug"] == "original-outlet-slug"

    db_outlet = db_session.query(Outlet).filter(Outlet.id == outlet.id).first()
    assert db_outlet.public_slug == "original-outlet-slug"


def test_read_business_and_outlet_details(client: TestClient, db_session: Session, test_setup):
    biz = test_setup["business"]
    outlet = test_setup["outlet"]
    op_headers = test_setup["operator_headers"]
    admin_headers = test_setup["admin_headers"]
    owner_headers = test_setup["owner_headers"]

    # 1. Operator can read business details with commercial fields strictly omitted
    biz_resp = client.get(f"/api/v1/platform/businesses/{biz.id}", headers=op_headers)
    assert biz_resp.status_code == 200
    biz_data = biz_resp.json()
    assert biz_data["id"] == str(biz.id)
    assert biz_data["name"] == biz.name
    assert biz_data["status"] == "active"
    assert len(biz_data["outlets"]) == 1
    assert biz_data["outlets"][0]["id"] == str(outlet.id)
    # Finding M-01 verification: restricted commercial fields MUST NOT be present in Operator response
    assert "subscription_status" not in biz_data
    assert "plan_name" not in biz_data
    assert "max_outlets" not in biz_data
    assert "trial_ends_at" not in biz_data

    # 2. Admin and Owner retain authorized access to commercial attributes
    admin_resp = client.get(f"/api/v1/platform/businesses/{biz.id}", headers=admin_headers)
    assert admin_resp.status_code == 200
    admin_data = admin_resp.json()
    assert admin_data["id"] == str(biz.id)
    assert admin_data["subscription_status"] == "active"
    assert admin_data["plan_name"] == "growth_pos"
    assert admin_data["max_outlets"] == 5

    owner_resp = client.get(f"/api/v1/platform/businesses/{biz.id}", headers=owner_headers)
    assert owner_resp.status_code == 200
    owner_data = owner_resp.json()
    assert owner_data["id"] == str(biz.id)
    assert owner_data["subscription_status"] == "active"
    assert owner_data["plan_name"] == "growth_pos"
    assert owner_data["max_outlets"] == 5

    # 3. Operator can read outlet details
    outlet_resp = client.get(f"/api/v1/platform/outlets/{outlet.id}", headers=op_headers)
    assert outlet_resp.status_code == 200
    outlet_data = outlet_resp.json()
    assert outlet_data["id"] == str(outlet.id)
    assert outlet_data["business_name"] == biz.name
    assert outlet_data["public_slug"] == "original-outlet-slug"

    # 4. Non-existent IDs -> 404
    fake_id = uuid.uuid4()
    assert client.get(f"/api/v1/platform/businesses/{fake_id}", headers=op_headers).status_code == 404
    assert client.get(f"/api/v1/platform/outlets/{fake_id}", headers=op_headers).status_code == 404
    assert client.patch(f"/api/v1/platform/businesses/{fake_id}", headers=admin_headers, json={"name": "X"}).status_code == 404
    assert client.patch(f"/api/v1/platform/outlets/{fake_id}", headers=op_headers, json={"name": "X"}).status_code == 404


def test_legacy_admin_business_read_receives_commercial_fields(client: TestClient, db_session: Session, test_setup):
    biz = test_setup["business"]
    # Legacy admin has is_platform_admin=True and platform_role=None
    legacy_admin = _create_user(db_session, "legacy_admin_read@test.com", None, is_admin=True)
    legacy_headers = _auth_headers(client, legacy_admin.email)

    resp = client.get(f"/api/v1/platform/businesses/{biz.id}", headers=legacy_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["subscription_status"] == "active"
    assert data["plan_name"] == "growth_pos"
    assert data["max_outlets"] == 5
