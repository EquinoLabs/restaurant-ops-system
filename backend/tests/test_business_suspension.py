import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.menus.models import MenuCategory, MenuItem
from app.modules.staff.models import User


def test_public_menu_suspended_business(client: TestClient, db_session: Session):
    # 1. Active business -> 200 OK
    resp = client.get("/api/v1/public/outlets/test-camp/menu")
    assert resp.status_code == 200

    qr_resp = client.get("/api/v1/public/outlets/test-camp/qr")
    assert qr_resp.status_code == 200

    # 2. Suspend business
    biz = db_session.query(Business).filter(Business.name == "Test Business").first()
    biz.status = "suspended"
    db_session.commit()

    # 3. Public menu & QR code query -> 404 NOT FOUND
    resp_suspended = client.get("/api/v1/public/outlets/test-camp/menu")
    assert resp_suspended.status_code == 404
    assert resp_suspended.json()["detail"]["error"]["code"] == "OUTLET_NOT_FOUND"

    qr_suspended = client.get("/api/v1/public/outlets/test-camp/qr")
    assert qr_suspended.status_code == 404
    assert qr_suspended.json()["detail"]["error"]["code"] == "OUTLET_NOT_FOUND"


def test_staff_protected_endpoints_suspended_business(client: TestClient, db_session: Session):
    # Login staff user
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    outlet = db_session.query(Outlet).filter(Outlet.public_slug == "test-camp").first()
    cat = db_session.query(MenuCategory).filter(MenuCategory.outlet_id == outlet.id).first()
    item = db_session.query(MenuItem).filter(MenuItem.outlet_id == outlet.id).first()

    # Verify active business works fine
    assert client.get(f"/api/v1/outlets/{outlet.id}/admin/menu", headers=headers).status_code == 200

    # Suspend business
    biz = db_session.query(Business).filter(Business.id == outlet.business_id).first()
    biz.status = "suspended"
    db_session.commit()

    # Verify operations denied with 403
    assert client.get(f"/api/v1/outlets/{outlet.id}/admin/menu", headers=headers).status_code == 403
    assert client.post(
        f"/api/v1/outlets/{outlet.id}/categories",
        headers=headers,
        json={"name": "Desserts", "description": "Sweets", "sort_order": 5}
    ).status_code == 403
    assert client.patch(
        f"/api/v1/categories/{cat.id}",
        headers=headers,
        json={"name": "Updated Category"}
    ).status_code == 403
    assert client.post(
        f"/api/v1/items/{item.id}/availability",
        headers=headers,
        json={"is_available": False}
    ).status_code == 403
    assert client.get(f"/api/v1/outlets/{outlet.id}/orders", headers=headers).status_code == 403
    assert client.post(
        f"/api/v1/outlets/{outlet.id}/orders",
        headers=headers,
        json={
            "table_number": "T1",
            "notes": "No spicy",
            "items": [{"item_id": str(item.id), "quantity": 1}]
        }
    ).status_code == 403
    assert client.get(f"/api/v1/outlets/{outlet.id}/tables", headers=headers).status_code == 403


def test_user_me_filters_suspended_business_memberships(client: TestClient, db_session: Session):
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Active business -> membership included
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert len(me_resp.json()["memberships"]) == 1

    # 2. Suspend business
    biz = db_session.query(Business).filter(Business.name == "Test Business").first()
    biz.status = "suspended"
    db_session.commit()

    # 3. Suspended business -> membership excluded from profile list
    me_resp_suspended = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp_suspended.status_code == 200
    assert len(me_resp_suspended.json()["memberships"]) == 0


def test_platform_admin_can_reactivate_suspended_business(client: TestClient, db_session: Session):
    # Promote staff user to platform admin
    staff_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff_user.is_platform_admin = True

    biz = db_session.query(Business).filter(Business.name == "Test Business").first()
    biz.status = "suspended"
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Platform admin updates subscription status back to active
    patch_resp = client.patch(
        f"/api/v1/platform/businesses/{biz.id}/subscription",
        headers=headers,
        json={"status": "active"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "active"

    # Public menu works again
    public_resp = client.get("/api/v1/public/outlets/test-camp/menu")
    assert public_resp.status_code == 200

    # Staff operations work again
    outlet = db_session.query(Outlet).filter(Outlet.public_slug == "test-camp").first()
    admin_menu_resp = client.get(f"/api/v1/outlets/{outlet.id}/admin/menu", headers=headers)
    assert admin_menu_resp.status_code == 200
