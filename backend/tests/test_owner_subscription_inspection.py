import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.core.security import hash_password, create_access_token
from app.modules.staff.models import User, OutletMembership
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.subscriptions.models import (
    Plan, Feature, PlanFeature, BusinessSubscription, EntitlementOverride
)


def create_test_user(db_session: Session, email: str, role: str, outlet: Outlet, status: str = "active") -> tuple[User, str]:
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        display_name=f"User {role}",
        status=status
    )
    db_session.add(user)
    db_session.commit()

    membership = OutletMembership(
        user_id=user.id,
        outlet_id=outlet.id,
        role=role
    )
    db_session.add(membership)
    db_session.commit()

    token = create_access_token(subject=str(user.id))
    return user, token


def test_authorized_owner_receives_subscription_summary(client: TestClient, db_session: Session):
    # Retrieve default test business and outlet seeded in conftest
    biz = db_session.query(Business).filter(Business.name == "Test Business").first()
    outlet = db_session.query(Outlet).filter(Outlet.business_id == biz.id).first()
    owner_user = db_session.query(User).filter(User.email == "staff@test.com").first()

    # Seed an active subscription on growth_pos
    plan_growth = db_session.query(Plan).filter(Plan.code == "growth_pos").first()
    now = utc_now()
    sub = BusinessSubscription(
        business_id=biz.id,
        plan_id=plan_growth.id,
        status="active",
        is_current=True,
        current_period_start=now - timedelta(days=30),
        current_period_end=now + timedelta(days=335),
        cancel_at_period_end=False
    )
    db_session.add(sub)
    db_session.commit()

    token = create_access_token(subject=str(owner_user.id))
    response = client.get(
        "/api/v1/business/subscription",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["business_id"] == str(biz.id)
    assert data["business_name"] == biz.name
    assert data["business_status"] == "active"
    assert data["plan"]["code"] == "growth_pos"
    assert data["plan"]["name"] == "Growth POS"
    assert data["subscription"]["status"] == "active"
    assert data["subscription"]["is_current"] is True
    assert data["outlets"]["current_count"] == 1
    assert data["outlets"]["max_allowed"] == 3
    assert data["outlets"]["is_limit_reached"] is False
    assert data["support_cta"]["requires_action"] is False
    assert data["support_cta"]["support_email"] == "support@roms.com"

    # Verify features list contains core platform features
    feature_codes = [f["code"] for f in data["features"]]
    assert "menu.digital" in feature_codes
    assert "outlets.max_count" in feature_codes


def test_manager_role_denied_access(client: TestClient, db_session: Session):
    biz = db_session.query(Business).filter(Business.name == "Test Business").first()
    outlet = db_session.query(Outlet).filter(Outlet.business_id == biz.id).first()

    _, manager_token = create_test_user(db_session, "manager_test@example.com", "manager", outlet)

    response = client.get(
        "/api/v1/business/subscription",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert response.status_code == 403
    assert "You are not authorized as an owner of this business" in response.text


def test_waiter_and_kitchen_roles_denied_access(client: TestClient, db_session: Session):
    biz = db_session.query(Business).filter(Business.name == "Test Business").first()
    outlet = db_session.query(Outlet).filter(Outlet.business_id == biz.id).first()

    _, waiter_token = create_test_user(db_session, "waiter_test@example.com", "waiter", outlet)
    _, kitchen_token = create_test_user(db_session, "kitchen_test@example.com", "kitchen", outlet)

    res_waiter = client.get(
        "/api/v1/business/subscription",
        headers={"Authorization": f"Bearer {waiter_token}"}
    )
    assert res_waiter.status_code == 403

    res_kitchen = client.get(
        "/api/v1/business/subscription",
        headers={"Authorization": f"Bearer {kitchen_token}"}
    )
    assert res_kitchen.status_code == 403


def test_unauthenticated_request_rejected(client: TestClient):
    response = client.get("/api/v1/business/subscription")
    assert response.status_code == 401


def test_suspended_account_cannot_use_endpoint(client: TestClient, db_session: Session):
    biz = db_session.query(Business).filter(Business.name == "Test Business").first()
    outlet = db_session.query(Outlet).filter(Outlet.business_id == biz.id).first()

    # Case A: User account itself is inactive
    _, inactive_token = create_test_user(
        db_session, "inactive_owner@example.com", "owner", outlet, status="inactive"
    )
    res_inactive_user = client.get(
        "/api/v1/business/subscription",
        headers={"Authorization": f"Bearer {inactive_token}"}
    )
    assert res_inactive_user.status_code == 401
    assert "User account is inactive" in res_inactive_user.text

    # Case B: Business is suspended
    biz_suspended = Business(
        name="Suspended Restaurant",
        status="suspended"
    )
    db_session.add(biz_suspended)
    db_session.commit()

    outlet_suspended = Outlet(
        business_id=biz_suspended.id,
        name="Suspended Outlet",
        public_slug="suspended-outlet"
    )
    db_session.add(outlet_suspended)
    db_session.commit()

    _, suspended_owner_token = create_test_user(
        db_session, "suspended_owner@example.com", "owner", outlet_suspended, status="active"
    )
    res_suspended_biz = client.get(
        "/api/v1/business/subscription",
        headers={"Authorization": f"Bearer {suspended_owner_token}"}
    )
    assert res_suspended_biz.status_code == 403
    assert "This business account is currently suspended" in res_suspended_biz.text


def test_owner_cannot_inspect_another_business_subscription(client: TestClient, db_session: Session):
    biz_a = db_session.query(Business).filter(Business.name == "Test Business").first()
    outlet_a = db_session.query(Outlet).filter(Outlet.business_id == biz_a.id).first()
    _, owner_a_token = create_test_user(db_session, "owner_a@example.com", "owner", outlet_a)

    biz_b = Business(name="Competitor Business", status="active")
    db_session.add(biz_b)
    db_session.commit()

    # Owner A attempts to query business_b by supplying foreign business_id parameter
    response = client.get(
        f"/api/v1/business/subscription?business_id={biz_b.id}",
        headers={"Authorization": f"Bearer {owner_a_token}"}
    )
    assert response.status_code == 403
    assert "You are not authorized as an owner of the requested business" in response.text


def test_missing_subscription_data_safe_fallback(client: TestClient, db_session: Session):
    biz = Business(
        name="Fallback Diner",
        status="active",
        plan_name="starter",
        subscription_status="active",
        max_outlets=1
    )
    db_session.add(biz)
    db_session.commit()

    outlet = Outlet(
        business_id=biz.id,
        name="Fallback Diner Outlet",
        public_slug="fallback-diner"
    )
    db_session.add(outlet)
    db_session.commit()

    _, owner_token = create_test_user(db_session, "fallback_owner@example.com", "owner", outlet)

    response = client.get(
        "/api/v1/business/subscription",
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["business_id"] == str(biz.id)
    assert data["plan"]["code"] == "starter_pos"
    assert data["subscription"]["status"] == "active"
    assert data["outlets"]["current_count"] == 1
    assert data["outlets"]["max_allowed"] == 1
    assert data["support_cta"]["requires_action"] is True  # 1 outlet of 1 allowed -> limit reached
    assert data["support_cta"]["reason"] == "OUTLET_LIMIT_REACHED"


def test_trial_expiration_represented_correctly(client: TestClient, db_session: Session):
    biz = Business(name="Trial Expired Cafe", status="active")
    db_session.add(biz)
    db_session.commit()

    outlet = Outlet(business_id=biz.id, name="Cafe Outlet", public_slug="cafe-outlet")
    db_session.add(outlet)
    db_session.commit()

    plan_starter = db_session.query(Plan).filter(Plan.code == "starter_pos").first()
    sub_expired = BusinessSubscription(
        business_id=biz.id,
        plan_id=plan_starter.id,
        status="trial",
        is_current=True,
        trial_ends_at=utc_now() - timedelta(days=2)  # Expired 2 days ago
    )
    db_session.add(sub_expired)
    db_session.commit()

    _, owner_token = create_test_user(db_session, "trial_expired_owner@example.com", "owner", outlet)

    response = client.get(
        "/api/v1/business/subscription",
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["subscription"]["status"] == "expired"
    assert data["support_cta"]["requires_action"] is True
    assert "TRIAL_EXPIRED" in data["support_cta"]["reason"]
    assert "support@roms.com" in data["support_cta"]["message"]


def test_outlet_limit_reached_represented_correctly(client: TestClient, db_session: Session):
    biz = Business(name="Single Outlet Restaurant", status="active")
    db_session.add(biz)
    db_session.commit()

    out1 = Outlet(business_id=biz.id, name="Outlet One", public_slug="single-outlet-one")
    db_session.add(out1)
    db_session.commit()

    plan_starter = db_session.query(Plan).filter(Plan.code == "starter_pos").first()  # limit = 1
    sub_active = BusinessSubscription(
        business_id=biz.id,
        plan_id=plan_starter.id,
        status="active",
        is_current=True,
        current_period_start=utc_now() - timedelta(days=10),
        current_period_end=utc_now() + timedelta(days=355)
    )
    db_session.add(sub_active)
    db_session.commit()

    _, owner_token = create_test_user(db_session, "single_owner@example.com", "owner", out1)

    response = client.get(
        "/api/v1/business/subscription",
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["outlets"]["current_count"] == 1
    assert data["outlets"]["max_allowed"] == 1
    assert data["outlets"]["is_limit_reached"] is True
    assert data["support_cta"]["requires_action"] is True
    assert data["support_cta"]["reason"] == "OUTLET_LIMIT_REACHED"
    assert "reached your limit of 1 outlet(s)" in data["support_cta"]["message"]
    assert "support@roms.com" in data["support_cta"]["message"]


def test_platform_admin_endpoints_retain_behavior_and_reject_owner(client: TestClient, db_session: Session):
    biz = db_session.query(Business).filter(Business.name == "Test Business").first()
    outlet = db_session.query(Outlet).filter(Outlet.business_id == biz.id).first()

    # Create restaurant owner
    _, owner_token = create_test_user(db_session, "restaurant_owner_guard@example.com", "owner", outlet)

    # 1. Owner attempts to call Platform Admin subscription mutation -> rejected with 403
    res_mutation = client.patch(
        f"/api/v1/platform/businesses/{biz.id}/subscription",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"plan_name": "enterprise"}
    )
    assert res_mutation.status_code == 403
    assert "Platform administrator privileges are required" in res_mutation.text

    # 2. Owner attempts to call Platform Admin override creation -> rejected with 403
    res_override = client.post(
        f"/api/v1/platform/businesses/{biz.id}/overrides",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"feature_code": "outlets.max_count", "override_type": "grant", "limit_value": 10, "reason": "Self-grant"}
    )
    assert res_override.status_code == 403
    assert "Platform administrator privileges are required" in res_override.text

    # 3. Platform Admin succeeds
    admin_user = User(
        email="platform_admin_guard@example.com",
        password_hash=hash_password("adminpass"),
        display_name="Platform Admin",
        status="active",
        is_platform_admin=True,
        platform_role="admin"
    )
    db_session.add(admin_user)
    db_session.commit()

    admin_token = create_access_token(subject=str(admin_user.id))
    res_admin_view = client.get(
        f"/api/v1/platform/businesses/{biz.id}/subscriptions",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin_view.status_code == 200
