import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.staff.models import User, OutletMembership
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet


def test_platform_router_permissions(client: TestClient, db_session: Session):
    # Unauthenticated request -> 401
    assert client.get("/api/v1/platform/businesses").status_code == 401

    # Login regular staff user (non-platform admin)
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Non-platform admin -> 403 Forbidden
    assert client.get("/api/v1/platform/businesses", headers=headers).status_code == 403
    assert client.post("/api/v1/platform/businesses", headers=headers, json={
        "name": "Unauthorized Biz",
        "primary_outlet_name": "Main",
        "public_slug": "unauth-slug"
    }).status_code == 403


def test_platform_admin_list_and_provision_business(client: TestClient, db_session: Session):
    # Promote staff user to platform admin
    staff_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff_user.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. List businesses
    list_resp = client.get("/api/v1/platform/businesses", headers=headers)
    assert list_resp.status_code == 200
    biz_data = list_resp.json()
    assert len(biz_data) >= 1
    assert biz_data[0]["name"] == "Test Business"

    # 2. Provision new business & primary outlet
    create_resp = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Himalayan Trout House",
            "primary_outlet_name": "Trout House Riverside",
            "public_slug": "trout-house-riverside",
            "currency": "INR",
            "timezone": "Asia/Kolkata",
            "address": "Kullu Valley, HP"
        }
    )
    assert create_resp.status_code == 200
    new_biz = create_resp.json()
    assert new_biz["name"] == "Himalayan Trout House"
    assert len(new_biz["outlets"]) == 1
    assert new_biz["outlets"][0]["public_slug"] == "trout-house-riverside"

    biz_id = new_biz["id"]

    # 3. Add secondary outlet to business
    add_outlet_resp = client.post(
        f"/api/v1/platform/businesses/{biz_id}/outlets",
        headers=headers,
        json={
            "name": "Trout House Express",
            "public_slug": "trout-house-express",
            "currency": "INR",
            "timezone": "Asia/Kolkata",
            "address": "Manali Mall Road"
        }
    )
    assert add_outlet_resp.status_code == 200
    express_outlet = add_outlet_resp.json()
    assert express_outlet["public_slug"] == "trout-house-express"

    # 4. Assign owner user to outlet
    assign_resp = client.post(
        f"/api/v1/platform/businesses/{biz_id}/assign-owner",
        headers=headers,
        json={
            "outlet_id": express_outlet["id"],
            "email": "owner.trout@example.com",
            "password": "SecurePassword123!",
            "display_name": "Trout Owner"
        }
    )
    assert assign_resp.status_code == 200
    mem_data = assign_resp.json()
    assert mem_data["role"] == "owner"
    assert mem_data["public_slug"] == "trout-house-express"

    # Verify newly created owner can log in
    owner_login = client.post(
        "/api/v1/auth/login",
        json={"email": "owner.trout@example.com", "password": "SecurePassword123!"}
    )
    assert owner_login.status_code == 200


def test_duplicate_slug_validation(client: TestClient, db_session: Session):
    staff_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff_user.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to create business with existing slug 'test-camp'
    dup_resp = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Duplicate Slug Resort",
            "primary_outlet_name": "Duplicate Outlet",
            "public_slug": "test-camp"
        }
    )
    assert dup_resp.status_code == 422
    assert "already in use" in dup_resp.json()["detail"]["error"]["message"]


def test_platform_subscription_updates_and_max_outlets(client: TestClient, db_session: Session):
    staff_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff_user.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Provision a business with max_outlets=1
    create_resp = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Single Outlet Cafe",
            "primary_outlet_name": "Single Outlet Main",
            "public_slug": "single-outlet-main",
            "max_outlets": 1,
            "plan_name": "starter"
        }
    )
    assert create_resp.status_code == 200
    biz = create_resp.json()
    biz_id = biz["id"]
    assert biz["subscription_status"] == "trial"
    assert biz["plan_name"] == "starter"
    assert biz["max_outlets"] == 1

    # 2. Attempt to add a 2nd outlet -> exceeds max_outlets=1 -> 422 ValidationError
    add_outlet_fail = client.post(
        f"/api/v1/platform/businesses/{biz_id}/outlets",
        headers=headers,
        json={
            "name": "Single Outlet Second",
            "public_slug": "single-outlet-second"
        }
    )
    assert add_outlet_fail.status_code == 422
    assert "maximum allowed limit" in add_outlet_fail.json()["detail"]["error"]["message"]

    # 3. Update subscription status to 'active', plan to 'growth', max_outlets to 3
    patch_resp = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={
            "subscription_status": "active",
            "plan_name": "growth",
            "max_outlets": 3,
            "status": "active"
        }
    )
    assert patch_resp.status_code == 200
    updated_biz = patch_resp.json()
    assert updated_biz["subscription_status"] == "active"
    assert updated_biz["plan_name"] == "growth"
    assert updated_biz["max_outlets"] == 3

    # 4. Now adding 2nd outlet succeeds
    add_outlet_success = client.post(
        f"/api/v1/platform/businesses/{biz_id}/outlets",
        headers=headers,
        json={
            "name": "Single Outlet Second",
            "public_slug": "single-outlet-second"
        }
    )
    assert add_outlet_success.status_code == 200

    # 5. Test invalid status updates
    invalid_sub_resp = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={"subscription_status": "invalid_status"}
    )
    assert invalid_sub_resp.status_code == 422

    invalid_max_resp = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={"max_outlets": 0}
    )
    assert invalid_max_resp.status_code == 422

