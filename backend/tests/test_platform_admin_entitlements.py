import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.modules.staff.models import User
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.subscriptions.models import (
    Plan, Feature, PlanFeature, BusinessSubscription, EntitlementOverride
)
from app.modules.audit.models import AuditLog


def test_platform_admin_entitlements_auth_protection(client: TestClient, db_session: Session):
    biz = Business(id=uuid.uuid4(), name="Auth Test Biz", status="active", plan_name="growth")
    db_session.add(biz)
    db_session.commit()

    # 1. Unauthenticated -> 401
    res = client.get(f"/api/v1/platform/businesses/{biz.id}/entitlements")
    assert res.status_code == 401

    res_ov = client.get(f"/api/v1/platform/businesses/{biz.id}/overrides")
    assert res_ov.status_code == 401

    # 2. Non-platform admin user -> 403
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res_forbidden = client.get(f"/api/v1/platform/businesses/{biz.id}/entitlements", headers=headers)
    assert res_forbidden.status_code == 403

    res_ov_forbidden = client.get(f"/api/v1/platform/businesses/{biz.id}/overrides", headers=headers)
    assert res_ov_forbidden.status_code == 403


def test_platform_admin_inspect_entitlements_active_subscription(client: TestClient, db_session: Session):
    # Setup platform admin auth
    staff_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff_user.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create business, plan, subscription
    p_growth = db_session.query(Plan).filter(Plan.code == "growth_pos").first()
    if not p_growth:
        p_growth = Plan(id=uuid.uuid4(), code="growth_pos", name="Growth POS", sort_order=3)
        db_session.add(p_growth)
        db_session.commit()

    f_menu = db_session.query(Feature).filter(Feature.code == "menu.digital").first()
    if not f_menu:
        f_menu = Feature(id=uuid.uuid4(), code="menu.digital", name="Digital Menu", category="menu")
        db_session.add(f_menu)
        db_session.commit()

    f_kds = db_session.query(Feature).filter(Feature.code == "kds.enabled").first()
    if not f_kds:
        f_kds = Feature(id=uuid.uuid4(), code="kds.enabled", name="KDS", category="kitchen")
        db_session.add(f_kds)
        db_session.commit()

    # Ensure PlanFeature mapping
    pf_menu = db_session.query(PlanFeature).filter(PlanFeature.plan_id == p_growth.id, PlanFeature.feature_id == f_menu.id).first()
    if not pf_menu:
        db_session.add(PlanFeature(id=uuid.uuid4(), plan_id=p_growth.id, feature_id=f_menu.id, limit_value=None))

    pf_kds = db_session.query(PlanFeature).filter(PlanFeature.plan_id == p_growth.id, PlanFeature.feature_id == f_kds.id).first()
    if not pf_kds:
        db_session.add(PlanFeature(id=uuid.uuid4(), plan_id=p_growth.id, feature_id=f_kds.id, limit_value=None))

    db_session.commit()

    biz = Business(id=uuid.uuid4(), name="Inspect Active Biz", status="active", plan_name="growth")
    db_session.add(biz)
    db_session.commit()

    sub = BusinessSubscription(
        id=uuid.uuid4(),
        business_id=biz.id,
        plan_id=p_growth.id,
        status="active",
        current_period_start=utc_now() - timedelta(days=10),
        current_period_end=utc_now() + timedelta(days=20),
        is_current=True
    )
    db_session.add(sub)
    db_session.commit()

    res = client.get(f"/api/v1/platform/businesses/{biz.id}/entitlements", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["business_id"] == str(biz.id)
    assert data["business_name"] == "Inspect Active Biz"
    assert data["subscription"]["status"] == "active"
    assert data["subscription"]["resolved_status"] == "active"
    assert data["subscription"]["plan_code"] == "growth_pos"

    features = {f["feature_code"]: f for f in data["features"]}
    assert "menu.digital" in features
    assert features["menu.digital"]["authorized"] is True
    assert features["menu.digital"]["source"] == "plan"
    assert features["menu.digital"]["scope"] == "business"

    assert "kds.enabled" in features
    assert features["kds.enabled"]["authorized"] is True


def test_platform_admin_inspect_entitlements_suspended_business(client: TestClient, db_session: Session):
    staff_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff_user.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    biz = Business(id=uuid.uuid4(), name="Suspended Biz", status="suspended", plan_name="growth")
    db_session.add(biz)
    db_session.commit()

    res = client.get(f"/api/v1/platform/businesses/{biz.id}/entitlements", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["business_status"] == "suspended"

    for feat in data["features"]:
        assert feat["authorized"] is False
        assert feat["reason"] == "BUSINESS_SUSPENDED"
        assert feat["source"] == "business_suspended"


def test_platform_admin_inspect_entitlements_expired_subscription_menu_exception(client: TestClient, db_session: Session):
    staff_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff_user.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    p_growth = db_session.query(Plan).filter(Plan.code == "growth_pos").first()

    biz = Business(id=uuid.uuid4(), name="Expired Sub Biz", status="active", plan_name="growth")
    db_session.add(biz)
    db_session.commit()

    sub = BusinessSubscription(
        id=uuid.uuid4(),
        business_id=biz.id,
        plan_id=p_growth.id,
        status="active",
        current_period_start=utc_now() - timedelta(days=40),
        current_period_end=utc_now() - timedelta(days=10), # expired
        is_current=True
    )
    db_session.add(sub)
    db_session.commit()

    res = client.get(f"/api/v1/platform/businesses/{biz.id}/entitlements", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["subscription"]["resolved_status"] == "expired"

    features = {f["feature_code"]: f for f in data["features"]}
    if "menu.digital" in features:
        assert features["menu.digital"]["authorized"] is True
        assert features["menu.digital"]["reason"] == "READ_ONLY_MENU_ALLOWED"
        assert features["menu.digital"]["source"] == "read_only_fallback"

    if "kds.enabled" in features:
        assert features["kds.enabled"]["authorized"] is False
        assert "SUBSCRIPTION_EXPIRED" in features["kds.enabled"]["reason"]




def test_platform_admin_cross_business_outlet_rejection(client: TestClient, db_session: Session):
    staff_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff_user.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    biz1 = Business(id=uuid.uuid4(), name="Biz 1", status="active")
    biz2 = Business(id=uuid.uuid4(), name="Biz 2", status="active")
    db_session.add_all([biz1, biz2])
    db_session.commit()

    outlet2 = Outlet(id=uuid.uuid4(), business_id=biz2.id, name="Biz 2 Outlet", public_slug="b2-out")
    db_session.add(outlet2)
    db_session.commit()

    # Request biz1 entitlements with biz2's outlet_id -> 422 or 400 validation error
    res = client.get(f"/api/v1/platform/businesses/{biz1.id}/entitlements?outlet_id={outlet2.id}", headers=headers)
    assert res.status_code in (400, 422)


def test_platform_admin_overrides_and_revocation_history(client: TestClient, db_session: Session):
    staff_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff_user.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    biz = Business(id=uuid.uuid4(), name="Override History Biz", status="active")
    db_session.add(biz)
    db_session.commit()

    # Active override
    ov_active = EntitlementOverride(
        id=uuid.uuid4(),
        business_id=biz.id,
        feature_code="kds.enabled",
        override_type="grant",
        limit_value=None,
        reason="VIP customer perk",
        created_by_user_id=staff_user.id,
        created_at=utc_now() - timedelta(days=2)
    )
    # Expired override
    ov_expired = EntitlementOverride(
        id=uuid.uuid4(),
        business_id=biz.id,
        feature_code="ordering.customer",
        override_type="grant",
        limit_value=5,
        reason="Temporary trial feature",
        expires_at=utc_now() - timedelta(days=1),
        created_by_user_id=staff_user.id,
        created_at=utc_now() - timedelta(days=5)
    )
    db_session.add_all([ov_active, ov_expired])
    db_session.commit()

    # Add audit log for a revoked override
    revoked_ov_id = uuid.uuid4()
    audit_entry = AuditLog(
        id=uuid.uuid4(),
        business_id=biz.id,
        actor_user_id=staff_user.id,
        action="platform.entitlement.override_revoke",
        entity_type="EntitlementOverride",
        entity_id=revoked_ov_id,
        metadata_json={
            "revoked_override_id": str(revoked_ov_id),
            "feature_code": "inventory.tracking",
            "override_type": "grant",
            "reason_for_revocation": "Requested by account owner"
        },
        created_at=utc_now() - timedelta(hours=3)
    )
    db_session.add(audit_entry)
    db_session.commit()

    # Call endpoint
    res = client.get(f"/api/v1/platform/businesses/{biz.id}/overrides", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["business_id"] == str(biz.id)
    assert len(data["overrides"]) == 2

    active_items = [o for o in data["overrides"] if o["is_active"]]
    assert len(active_items) == 1
    assert active_items[0]["feature_code"] == "kds.enabled"

    expired_items = [o for o in data["overrides"] if not o["is_active"]]
    assert len(expired_items) == 1
    assert expired_items[0]["feature_code"] == "ordering.customer"

    assert len(data["revocation_history"]) == 1
    rev = data["revocation_history"][0]
    assert rev["revoked_override_id"] == str(revoked_ov_id)
    assert rev["feature_code"] == "inventory.tracking"
    assert rev["actor_email"] == staff_user.email
    assert rev["reason"] == "Requested by account owner"
