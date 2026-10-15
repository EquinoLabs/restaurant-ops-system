import uuid
from datetime import timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.core.security import hash_password, create_access_token
from app.modules.staff.models import User, OutletMembership, BusinessMembership
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.menus.models import MenuCategory, MenuItem
from app.modules.orders.models import Order
from app.modules.audit.models import AuditLog
from app.modules.subscriptions.models import (
    Plan,
    BusinessSubscription,
    OutletSubscription,
    EntitlementOverride,
)


def _create_user(db: Session, email: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        display_name=email.split("@")[0],
        status="active",
    )
    db.add(user)
    db.commit()
    return user


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}


def _create_business(db: Session, name: str, status: str = "active") -> Business:
    biz = Business(name=name, status=status)
    db.add(biz)
    db.commit()
    return biz


def _create_outlet(db: Session, biz: Business, name: str, slug: str, status: str = "active") -> Outlet:
    outlet = Outlet(business_id=biz.id, name=name, public_slug=slug, status=status)
    db.add(outlet)
    db.commit()
    return outlet


def _grant_outlet_role(db: Session, user: User, outlet: Outlet, role: str) -> OutletMembership:
    membership = OutletMembership(user_id=user.id, outlet_id=outlet.id, role=role)
    db.add(membership)
    db.commit()
    return membership


def _grant_business_owner(db: Session, user: User, biz: Business) -> BusinessMembership:
    membership = BusinessMembership(user_id=user.id, business_id=biz.id, role="owner")
    db.add(membership)
    db.commit()
    return membership


def _plan(db: Session, code: str) -> Plan:
    plan = db.query(Plan).filter(Plan.code == code).first()
    assert plan is not None, f"Plan {code} must be seeded"
    return plan


def _subscribe_business(
    db: Session,
    biz: Business,
    plan_code: str,
    *,
    status: str = "active",
    period_end_in_days: int = 30,
    trial_ends_in_days: int = None,
    cancelled_at=None,
) -> BusinessSubscription:
    now = utc_now()
    sub = BusinessSubscription(
        business_id=biz.id,
        plan_id=_plan(db, plan_code).id,
        status=status,
        is_current=True,
        trial_ends_at=(now + timedelta(days=trial_ends_in_days)) if trial_ends_in_days is not None else None,
        current_period_start=now,
        current_period_end=now + timedelta(days=period_end_in_days),
        cancelled_at=cancelled_at,
    )
    db.add(sub)
    db.commit()
    return sub


def _subscribe_outlet(
    db: Session,
    outlet: Outlet,
    biz: Business,
    plan_code: str,
    *,
    status: str = "active",
    period_end_in_days: int = 30,
) -> OutletSubscription:
    now = utc_now()
    sub = OutletSubscription(
        outlet_id=outlet.id,
        business_id=biz.id,
        plan_id=_plan(db, plan_code).id,
        status=status,
        is_current=True,
        current_period_start=now,
        current_period_end=now + timedelta(days=period_end_in_days),
    )
    db.add(sub)
    db.commit()
    return sub


def _seed_menu(db: Session, outlet: Outlet):
    cat = MenuCategory(outlet_id=outlet.id, name="Mains", sort_order=1, is_active=True)
    db.add(cat)
    db.commit()
    item = MenuItem(
        outlet_id=outlet.id,
        category_id=cat.id,
        name="Paneer Tikka",
        price=Decimal("120.00"),
        is_available=True,
        is_active=True,
        sort_order=1,
    )
    db.add(item)
    db.commit()
    return cat, item


def _seed_order(db: Session, outlet: Outlet, item: MenuItem) -> Order:
    order = Order(outlet_id=outlet.id, order_number=f"P4-{uuid.uuid4().hex[:8]}", status="pending", total_amount=Decimal("120.00"))
    db.add(order)
    db.commit()
    return order


def _staff_order_payload(item: MenuItem) -> dict:
    return {"items": [{"menu_item_id": str(item.id), "quantity": 1}]}


def _public_order_payload(item: MenuItem) -> dict:
    return {"items": [{"menu_item_id": str(item.id), "quantity": 1}]}


def _err_message(resp) -> str:
    return resp.json()["detail"]["error"]["message"]


# ---------------------------------------------------------------------------
# Expired subscription: operations denied, public menu browsing preserved
# ---------------------------------------------------------------------------

def test_expired_subscription_blocks_staff_operations(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Expired Biz")
    outlet = _create_outlet(db_session, biz, "Expired Outlet", "expired-outlet")
    cat, item = _seed_menu(db_session, outlet)
    owner = _create_user(db_session, "expired_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet, "owner")
    _subscribe_business(db_session, biz, "growth_pos", status="active", period_end_in_days=-1)

    resp_order = client.post(
        f"/api/v1/outlets/{outlet.id}/orders", headers=_auth(owner), json=_staff_order_payload(item)
    )
    assert resp_order.status_code == 403
    assert "SUBSCRIPTION_EXPIRED" in _err_message(resp_order)

    resp_table = client.post(
        f"/api/v1/outlets/{outlet.id}/tables", headers=_auth(owner), json={"table_number": "T-EXP", "capacity": 2}
    )
    assert resp_table.status_code == 403
    assert "SUBSCRIPTION_EXPIRED" in _err_message(resp_table)

    resp_item = client.patch(f"/api/v1/items/{item.id}", headers=_auth(owner), json={"price": "130.00"})
    assert resp_item.status_code == 403
    assert "SUBSCRIPTION_EXPIRED" in _err_message(resp_item)

    order = _seed_order(db_session, outlet, item)
    resp_status = client.patch(
        f"/api/v1/orders/{order.id}/status", headers=_auth(owner), json={"status": "confirmed"}
    )
    assert resp_status.status_code == 403
    assert "SUBSCRIPTION_EXPIRED" in _err_message(resp_status)

    # Read-only admin views remain available (operational reads gated only by membership/suspension)
    resp_menu = client.get(f"/api/v1/outlets/{outlet.id}/admin/menu", headers=_auth(owner))
    assert resp_menu.status_code == 200


def test_expired_subscription_public_menu_readable_but_ordering_denied(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Expired Public Biz")
    outlet = _create_outlet(db_session, biz, "Expired Public Outlet", "expired-public")
    cat, item = _seed_menu(db_session, outlet)
    _subscribe_business(db_session, biz, "growth_pos", status="active", period_end_in_days=-1)

    resp_menu = client.get(f"/api/v1/public/outlets/{outlet.public_slug}/menu")
    assert resp_menu.status_code == 200

    resp_order = client.post(
        f"/api/v1/public/outlets/{outlet.public_slug}/orders", json=_public_order_payload(item)
    )
    assert resp_order.status_code == 404
    assert resp_order.json()["detail"]["error"]["code"] == "OUTLET_NOT_FOUND"


def test_expired_trial_public_menu_readable_but_ordering_denied(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Expired Trial Biz")
    outlet = _create_outlet(db_session, biz, "Expired Trial Outlet", "expired-trial")
    cat, item = _seed_menu(db_session, outlet)
    _subscribe_business(
        db_session, biz, "growth_pos", status="trial", trial_ends_in_days=-1, period_end_in_days=-1
    )

    resp_menu = client.get(f"/api/v1/public/outlets/{outlet.public_slug}/menu")
    assert resp_menu.status_code == 200

    resp_order = client.post(
        f"/api/v1/public/outlets/{outlet.public_slug}/orders", json=_public_order_payload(item)
    )
    assert resp_order.status_code == 404


def test_cancelled_subscription_blocks_operations(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Cancelled Biz")
    outlet = _create_outlet(db_session, biz, "Cancelled Outlet", "cancelled-outlet")
    cat, item = _seed_menu(db_session, outlet)
    owner = _create_user(db_session, "cancelled_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet, "owner")
    _subscribe_business(
        db_session, biz, "growth_pos", status="cancelled", cancelled_at=utc_now() - timedelta(days=2)
    )

    resp_order = client.post(
        f"/api/v1/outlets/{outlet.id}/orders", headers=_auth(owner), json=_staff_order_payload(item)
    )
    assert resp_order.status_code == 403
    assert "SUBSCRIPTION_CANCELLED" in _err_message(resp_order)

    resp_item = client.patch(f"/api/v1/items/{item.id}", headers=_auth(owner), json={"price": "90.00"})
    assert resp_item.status_code == 403
    assert "SUBSCRIPTION_CANCELLED" in _err_message(resp_item)

    resp_public = client.post(
        f"/api/v1/public/outlets/{outlet.public_slug}/orders", json=_public_order_payload(item)
    )
    assert resp_public.status_code == 404


def test_cancel_at_period_end_within_period_remains_operational(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Cancel At End Biz")
    outlet = _create_outlet(db_session, biz, "Cancel At End Outlet", "cancel-at-end")
    cat, item = _seed_menu(db_session, outlet)
    owner = _create_user(db_session, "cancel_at_end_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet, "owner")
    sub = _subscribe_business(db_session, biz, "growth_pos", status="active", period_end_in_days=15)
    sub.cancel_at_period_end = True
    db_session.commit()

    resp_order = client.post(
        f"/api/v1/outlets/{outlet.id}/orders", headers=_auth(owner), json=_staff_order_payload(item)
    )
    assert resp_order.status_code == 200


def test_past_due_subscription_remains_operational(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Past Due Biz")
    outlet = _create_outlet(db_session, biz, "Past Due Outlet", "past-due-outlet")
    cat, item = _seed_menu(db_session, outlet)
    owner = _create_user(db_session, "past_due_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet, "owner")
    _subscribe_business(db_session, biz, "growth_pos", status="past_due", period_end_in_days=15)

    resp_order = client.post(
        f"/api/v1/outlets/{outlet.id}/orders", headers=_auth(owner), json=_staff_order_payload(item)
    )
    assert resp_order.status_code == 200

    resp_public = client.post(
        f"/api/v1/public/outlets/{outlet.public_slug}/orders", json=_public_order_payload(item)
    )
    assert resp_public.status_code == 201


def test_active_subscription_all_operations_allowed(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Active Biz")
    outlet = _create_outlet(db_session, biz, "Active Outlet", "active-outlet")
    cat, item = _seed_menu(db_session, outlet)
    owner = _create_user(db_session, "active_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet, "owner")
    _subscribe_business(db_session, biz, "growth_pos", status="active", period_end_in_days=30)

    resp_order = client.post(
        f"/api/v1/outlets/{outlet.id}/orders", headers=_auth(owner), json=_staff_order_payload(item)
    )
    assert resp_order.status_code == 200
    order_id = resp_order.json()["id"]

    resp_status = client.patch(
        f"/api/v1/orders/{order_id}/status", headers=_auth(owner), json={"status": "confirmed"}
    )
    assert resp_status.status_code == 200

    resp_table = client.post(
        f"/api/v1/outlets/{outlet.id}/tables", headers=_auth(owner), json={"table_number": "T-ACT", "capacity": 2}
    )
    assert resp_table.status_code == 200

    resp_item = client.patch(f"/api/v1/items/{item.id}", headers=_auth(owner), json={"price": "125.00"})
    assert resp_item.status_code == 200

    resp_public = client.post(
        f"/api/v1/public/outlets/{outlet.public_slug}/orders", json=_public_order_payload(item)
    )
    assert resp_public.status_code == 201


def test_outlet_subscription_governs_outlet_operations(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Multi Outlet Sub Biz")
    outlet_a = _create_outlet(db_session, biz, "Sub Outlet A", "sub-outlet-a")
    outlet_b = _create_outlet(db_session, biz, "Sub Outlet B", "sub-outlet-b")
    cat_a, item_a = _seed_menu(db_session, outlet_a)
    cat_b, item_b = _seed_menu(db_session, outlet_b)
    owner = _create_user(db_session, "multi_sub_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet_a, "owner")
    _grant_outlet_role(db_session, owner, outlet_b, "owner")
    _subscribe_outlet(db_session, outlet_a, biz, "growth_pos", status="active", period_end_in_days=30)
    _subscribe_outlet(db_session, outlet_b, biz, "growth_pos", status="active", period_end_in_days=-1)

    resp_a = client.post(
        f"/api/v1/outlets/{outlet_a.id}/orders", headers=_auth(owner), json=_staff_order_payload(item_a)
    )
    assert resp_a.status_code == 200

    resp_b = client.post(
        f"/api/v1/outlets/{outlet_b.id}/orders", headers=_auth(owner), json=_staff_order_payload(item_b)
    )
    assert resp_b.status_code == 403
    assert "SUBSCRIPTION_EXPIRED" in _err_message(resp_b)


# ---------------------------------------------------------------------------
# Lifecycle scope: business suspension blocks all outlets; outlet suspension is local
# ---------------------------------------------------------------------------

def test_suspended_business_blocks_all_outlets(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Suspend Biz")
    outlet_1 = _create_outlet(db_session, biz, "Suspend Outlet 1", "suspend-outlet-1")
    outlet_2 = _create_outlet(db_session, biz, "Suspend Outlet 2", "suspend-outlet-2")
    cat_1, item_1 = _seed_menu(db_session, outlet_1)
    cat_2, item_2 = _seed_menu(db_session, outlet_2)
    owner = _create_user(db_session, "suspend_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet_1, "owner")
    _grant_outlet_role(db_session, owner, outlet_2, "owner")
    _subscribe_business(db_session, biz, "growth_pos", status="active", period_end_in_days=30)

    biz.status = "suspended"
    db_session.commit()

    for outlet, item in ((outlet_1, item_1), (outlet_2, item_2)):
        resp = client.post(
            f"/api/v1/outlets/{outlet.id}/orders", headers=_auth(owner), json=_staff_order_payload(item)
        )
        assert resp.status_code == 403
        assert "This business account is currently suspended" in _err_message(resp)

    resp_public = client.post(
        f"/api/v1/public/outlets/{outlet_1.public_slug}/orders", json=_public_order_payload(item_1)
    )
    assert resp_public.status_code == 404


def test_suspended_outlet_affects_only_that_outlet(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Outlet Suspend Biz")
    outlet_ok = _create_outlet(db_session, biz, "Outlet OK", "outlet-ok")
    outlet_bad = _create_outlet(db_session, biz, "Outlet Suspended", "outlet-suspended")
    cat_ok, item_ok = _seed_menu(db_session, outlet_ok)
    cat_bad, item_bad = _seed_menu(db_session, outlet_bad)
    owner = _create_user(db_session, "outlet_suspend_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet_ok, "owner")
    _grant_outlet_role(db_session, owner, outlet_bad, "owner")
    _subscribe_business(db_session, biz, "growth_pos", status="active", period_end_in_days=30)

    outlet_bad.status = "inactive"
    db_session.commit()

    resp_bad = client.post(
        f"/api/v1/outlets/{outlet_bad.id}/orders", headers=_auth(owner), json=_staff_order_payload(item_bad)
    )
    assert resp_bad.status_code == 403
    assert "This outlet is currently suspended" in _err_message(resp_bad)

    resp_ok = client.post(
        f"/api/v1/outlets/{outlet_ok.id}/orders", headers=_auth(owner), json=_staff_order_payload(item_ok)
    )
    assert resp_ok.status_code == 200

    order_bad = _seed_order(db_session, outlet_bad, item_bad)
    resp_detail = client.get(f"/api/v1/orders/{order_bad.id}", headers=_auth(owner))
    assert resp_detail.status_code == 403
    assert "This outlet is currently suspended" in _err_message(resp_detail)

    resp_public_bad = client.post(
        f"/api/v1/public/outlets/{outlet_bad.public_slug}/orders", json=_public_order_payload(item_bad)
    )
    assert resp_public_bad.status_code == 404


def test_outlet_reactivation_restores_access(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Reactivation Biz")
    outlet = _create_outlet(db_session, biz, "Reactivation Outlet", "reactivation-outlet")
    cat, item = _seed_menu(db_session, outlet)
    owner = _create_user(db_session, "reactivation_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet, "owner")
    _subscribe_business(db_session, biz, "growth_pos", status="active", period_end_in_days=30)

    outlet.status = "inactive"
    db_session.commit()
    resp_suspended = client.post(
        f"/api/v1/outlets/{outlet.id}/orders", headers=_auth(owner), json=_staff_order_payload(item)
    )
    assert resp_suspended.status_code == 403

    outlet.status = "active"
    db_session.commit()
    resp_restored = client.post(
        f"/api/v1/outlets/{outlet.id}/orders", headers=_auth(owner), json=_staff_order_payload(item)
    )
    assert resp_restored.status_code == 200


def test_business_reactivation_requires_live_subscription(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Biz Reactivation Sub Biz")
    outlet = _create_outlet(db_session, biz, "Biz Reactivation Outlet", "biz-reactivation")
    cat, item = _seed_menu(db_session, outlet)
    owner = _create_user(db_session, "biz_reactivation_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet, "owner")
    _subscribe_business(db_session, biz, "growth_pos", status="active", period_end_in_days=-1)

    biz.status = "suspended"
    db_session.commit()
    resp_suspended = client.post(
        f"/api/v1/outlets/{outlet.id}/orders", headers=_auth(owner), json=_staff_order_payload(item)
    )
    assert resp_suspended.status_code == 403

    # Reactivation restores access only because the subscription is expired -> still denied
    biz.status = "active"
    db_session.commit()
    resp_after = client.post(
        f"/api/v1/outlets/{outlet.id}/orders", headers=_auth(owner), json=_staff_order_payload(item)
    )
    assert resp_after.status_code == 403
    assert "SUBSCRIPTION_EXPIRED" in _err_message(resp_after)


# ---------------------------------------------------------------------------
# Entitlement overrides flow through to operational endpoints
# ---------------------------------------------------------------------------

def test_restriction_override_denies_staff_ordering(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Restrict Biz")
    outlet = _create_outlet(db_session, biz, "Restrict Outlet", "restrict-outlet")
    cat, item = _seed_menu(db_session, outlet)
    owner = _create_user(db_session, "restrict_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet, "owner")
    _subscribe_business(db_session, biz, "growth_pos", status="active", period_end_in_days=30)
    db_session.add(
        EntitlementOverride(
            business_id=biz.id,
            feature_code="ordering.staff",
            override_type="restrict",
            reason="P4 restriction test",
        )
    )
    db_session.commit()

    resp = client.post(
        f"/api/v1/outlets/{outlet.id}/orders", headers=_auth(owner), json=_staff_order_payload(item)
    )
    assert resp.status_code == 403
    assert "RESTRICTION_OVERRIDE_ACTIVE" in _err_message(resp)

    resp_menu = client.get(f"/api/v1/outlets/{outlet.id}/admin/menu", headers=_auth(owner))
    assert resp_menu.status_code == 200


def test_grant_override_restores_customer_ordering_on_free_plan(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Grant Override Biz")
    outlet = _create_outlet(db_session, biz, "Grant Override Outlet", "grant-override")
    cat, item = _seed_menu(db_session, outlet)
    _subscribe_business(db_session, biz, "free_qr", status="active", period_end_in_days=365)

    resp_denied = client.post(
        f"/api/v1/public/outlets/{outlet.public_slug}/orders", json=_public_order_payload(item)
    )
    assert resp_denied.status_code == 404

    db_session.add(
        EntitlementOverride(
            business_id=biz.id,
            feature_code="ordering.customer",
            override_type="grant",
            reason="P4 grant test",
        )
    )
    db_session.commit()

    resp_granted = client.post(
        f"/api/v1/public/outlets/{outlet.public_slug}/orders", json=_public_order_payload(item)
    )
    assert resp_granted.status_code == 201


def test_free_plan_menu_edit_allowed_but_ordering_denied(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Free Plan Biz")
    outlet = _create_outlet(db_session, biz, "Free Plan Outlet", "free-plan")
    cat, item = _seed_menu(db_session, outlet)
    owner = _create_user(db_session, "free_plan_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet, "owner")
    _subscribe_business(db_session, biz, "free_qr", status="active", period_end_in_days=365)

    resp_menu_edit = client.patch(f"/api/v1/items/{item.id}", headers=_auth(owner), json={"price": "110.00"})
    assert resp_menu_edit.status_code == 200

    resp_order = client.post(
        f"/api/v1/outlets/{outlet.id}/orders", headers=_auth(owner), json=_staff_order_payload(item)
    )
    assert resp_order.status_code == 403
    assert "FEATURE_NOT_INCLUDED_IN_PLAN" in _err_message(resp_order)

    resp_table = client.post(
        f"/api/v1/outlets/{outlet.id}/tables", headers=_auth(owner), json={"table_number": "T-FREE", "capacity": 2}
    )
    assert resp_table.status_code == 403
    assert "FEATURE_NOT_INCLUDED_IN_PLAN" in _err_message(resp_table)

    resp_public = client.post(
        f"/api/v1/public/outlets/{outlet.public_slug}/orders", json=_public_order_payload(item)
    )
    assert resp_public.status_code == 404


# ---------------------------------------------------------------------------
# Sub-resource authorization: anti-probing, legitimate 404s, canonical owners
# ---------------------------------------------------------------------------

def test_subresource_probes_are_uniform_not_found(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Probe Biz")
    outlet = _create_outlet(db_session, biz, "Probe Outlet", "probe-outlet")
    cat, item = _seed_menu(db_session, outlet)
    owner = _create_user(db_session, "probe_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet, "owner")
    order = _seed_order(db_session, outlet, item)
    from app.modules.tables.models import DiningTable
    table = DiningTable(outlet_id=outlet.id, table_number="T-PROBE", capacity=2)
    db_session.add(table)
    db_session.commit()

    stranger = _create_user(db_session, "probe_stranger@example.com")
    stranger_auth = _auth(stranger)
    missing_id = str(uuid.uuid4())

    # Existing foreign resources and missing resources are indistinguishable
    resp_existing_order = client.get(f"/api/v1/orders/{order.id}", headers=stranger_auth)
    resp_missing_order = client.get(f"/api/v1/orders/{missing_id}", headers=stranger_auth)
    assert resp_existing_order.status_code == 404
    assert resp_missing_order.status_code == 404
    assert (
        resp_existing_order.json()["detail"]["error"]["code"]
        == resp_missing_order.json()["detail"]["error"]["code"]
        == "NOT_FOUND"
    )

    resp_existing_item = client.patch(f"/api/v1/items/{item.id}", headers=stranger_auth, json={"price": "1.00"})
    resp_missing_item = client.patch(f"/api/v1/items/{missing_id}", headers=stranger_auth, json={"price": "1.00"})
    assert resp_existing_item.status_code == 404
    assert resp_missing_item.status_code == 404
    assert (
        resp_existing_item.json()["detail"]["error"]["code"]
        == resp_missing_item.json()["detail"]["error"]["code"]
        == "NOT_FOUND"
    )

    resp_existing_cat = client.patch(f"/api/v1/categories/{cat.id}", headers=stranger_auth, json={"name": "X"})
    resp_missing_cat = client.patch(f"/api/v1/categories/{missing_id}", headers=stranger_auth, json={"name": "X"})
    assert resp_existing_cat.status_code == 404
    assert resp_missing_cat.status_code == 404

    resp_existing_table = client.patch(
        f"/api/v1/tables/{table.id}", headers=stranger_auth, json={"capacity": 8}
    )
    resp_missing_table = client.patch(f"/api/v1/tables/{missing_id}", headers=stranger_auth, json={"capacity": 8})
    assert resp_existing_table.status_code == 404
    assert resp_missing_table.status_code == 404


def test_authorized_caller_legitimate_not_found_preserved(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Legit 404 Biz")
    outlet = _create_outlet(db_session, biz, "Legit 404 Outlet", "legit-404")
    cat, item = _seed_menu(db_session, outlet)
    owner = _create_user(db_session, "legit_404_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet, "owner")

    resp = client.get(f"/api/v1/orders/{uuid.uuid4()}", headers=_auth(owner))
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "NOT_FOUND"


def test_cross_business_member_cannot_probe_resources(client: TestClient, db_session: Session):
    biz_a = _create_business(db_session, "Probe Biz A")
    outlet_a = _create_outlet(db_session, biz_a, "Probe Outlet A", "probe-outlet-a")
    cat_a, item_a = _seed_menu(db_session, outlet_a)
    order_a = _seed_order(db_session, outlet_a, item_a)

    biz_b = _create_business(db_session, "Probe Biz B")
    outlet_b = _create_outlet(db_session, biz_b, "Probe Outlet B", "probe-outlet-b")
    cat_b, item_b = _seed_menu(db_session, outlet_b)
    member_b = _create_user(db_session, "member_of_b@example.com")
    _grant_outlet_role(db_session, member_b, outlet_b, "owner")

    resp_order = client.get(f"/api/v1/orders/{order_a.id}", headers=_auth(member_b))
    assert resp_order.status_code == 404

    resp_item = client.patch(f"/api/v1/items/{item_a.id}", headers=_auth(member_b), json={"price": "1.00"})
    assert resp_item.status_code == 404

    resp_outlet_probe = client.get(f"/api/v1/outlets/{outlet_a.id}/admin/menu", headers=_auth(member_b))
    assert resp_outlet_probe.status_code == 403
    assert "administrative access" in _err_message(resp_outlet_probe)


def test_canonical_business_owner_accesses_subresources_without_outlet_row(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Canonical Subresource Biz")
    outlet = _create_outlet(db_session, biz, "Canonical Subresource Outlet", "canonical-subresource")
    cat, item = _seed_menu(db_session, outlet)
    order = _seed_order(db_session, outlet, item)
    from app.modules.tables.models import DiningTable
    table = DiningTable(outlet_id=outlet.id, table_number="T-CANON", capacity=2)
    db_session.add(table)
    db_session.commit()

    owner = _create_user(db_session, "canonical_subresource_owner@example.com")
    _grant_business_owner(db_session, owner, biz)

    resp_order = client.get(f"/api/v1/orders/{order.id}", headers=_auth(owner))
    assert resp_order.status_code == 200

    resp_table = client.patch(f"/api/v1/tables/{table.id}", headers=_auth(owner), json={"capacity": 5})
    assert resp_table.status_code == 200
    assert resp_table.json()["capacity"] == 5

    resp_item = client.patch(f"/api/v1/items/{item.id}", headers=_auth(owner), json={"price": "135.00"})
    assert resp_item.status_code == 200


def test_waiter_cannot_modify_tables_but_member_access_probes_are_consistent(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Waiter Biz")
    outlet = _create_outlet(db_session, biz, "Waiter Outlet", "waiter-outlet")
    cat, item = _seed_menu(db_session, outlet)
    from app.modules.tables.models import DiningTable
    table = DiningTable(outlet_id=outlet.id, table_number="T-WAITER", capacity=2)
    db_session.add(table)
    db_session.commit()

    waiter = _create_user(db_session, "waiter@example.com")
    _grant_outlet_role(db_session, waiter, outlet, "waiter")

    resp = client.patch(f"/api/v1/tables/{table.id}", headers=_auth(waiter), json={"capacity": 9})
    assert resp.status_code == 403
    assert "Role 'waiter' is not authorized to modify tables" in _err_message(resp)

    # Waiter can still read orders (allowed role) while subscription is live
    order = _seed_order(db_session, outlet, item)
    resp_order = client.get(f"/api/v1/orders/{order.id}", headers=_auth(waiter))
    assert resp_order.status_code == 200


def test_business_owner_without_outlet_membership_denied_on_foreign_business(client: TestClient, db_session: Session):
    biz_a = _create_business(db_session, "Foreign Owner Biz A")
    outlet_a = _create_outlet(db_session, biz_a, "Foreign Owner Outlet A", "foreign-owner-a")
    cat_a, item_a = _seed_menu(db_session, outlet_a)
    order_a = _seed_order(db_session, outlet_a, item_a)

    biz_b = _create_business(db_session, "Foreign Owner Biz B")
    owner_b = _create_user(db_session, "owner_of_b@example.com")
    _grant_business_owner(db_session, owner_b, biz_b)

    resp = client.get(f"/api/v1/orders/{order_a.id}", headers=_auth(owner_b))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# P5: write-surface verification — cross-outlet mismatches & pre-mutation failure
# ---------------------------------------------------------------------------

def test_cross_outlet_item_mismatch_rejected_without_side_effects(client: TestClient, db_session: Session):
    """A member of outlet A passing outlet A's path id with outlet B's item id on the
    item-image routes must be rejected before any service call or side effect."""
    biz = _create_business(db_session, "Mismatch Biz")
    outlet_a = _create_outlet(db_session, biz, "Mismatch Outlet A", "mismatch-a")
    outlet_b = _create_outlet(db_session, biz, "Mismatch Outlet B", "mismatch-b")
    cat_a, item_a = _seed_menu(db_session, outlet_a)
    cat_b, item_b = _seed_menu(db_session, outlet_b)
    owner_a = _create_user(db_session, "mismatch_owner_a@example.com")
    _grant_outlet_role(db_session, owner_a, outlet_a, "owner")
    _subscribe_business(db_session, biz, "growth_pos", status="active", period_end_in_days=30)

    audit_before = db_session.query(AuditLog).count()
    assert item_b.image_url is None

    resp_upload = client.post(
        f"/api/v1/outlets/{outlet_a.id}/items/{item_b.id}/image",
        headers=_auth(owner_a),
        files={"file": ("cross.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
    )
    assert resp_upload.status_code == 404
    assert "not found" in _err_message(resp_upload)

    resp_delete = client.delete(
        f"/api/v1/outlets/{outlet_a.id}/items/{item_b.id}/image",
        headers=_auth(owner_a),
    )
    assert resp_delete.status_code == 404

    # No side effects: item B untouched, no audit rows written
    db_session.refresh(item_b)
    assert item_b.image_url is None
    assert db_session.query(AuditLog).count() == audit_before

    # Legitimate pairing (outlet A + item A) passes authorization and reaches the
    # service layer (which re-scopes by outlet). In the test environment R2
    # credentials are unconfigured, so the request may fail downstream with a 500 —
    # what matters is that it is NOT an authorization rejection (403/404), proving
    # authz differentiates on the relationship, not on resource existence alone.
    resp_legit = client.post(
        f"/api/v1/outlets/{outlet_a.id}/items/{item_a.id}/image",
        headers=_auth(owner_a),
        files={"file": ("cross.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
    )
    assert resp_legit.status_code not in (403, 404), (
        f"legitimate outlet+item pairing must pass authorization, got {resp_legit.status_code}"
    )


def test_authorization_and_entitlement_failures_precede_all_mutations(client: TestClient, db_session: Session):
    """Failed authz/entitlement must produce zero rows created and zero audit entries."""
    biz = _create_business(db_session, "Side Effect Biz")
    outlet = _create_outlet(db_session, biz, "Side Effect Outlet", "side-effect")
    cat, item = _seed_menu(db_session, outlet)
    owner = _create_user(db_session, "side_effect_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet, "owner")
    stranger = _create_user(db_session, "side_effect_stranger@example.com")
    _subscribe_business(db_session, biz, "growth_pos", status="active", period_end_in_days=-1)

    counts_before = (
        db_session.query(MenuCategory).count(),
        db_session.query(MenuItem).count(),
        db_session.query(Order).count(),
        db_session.query(AuditLog).count(),
    )

    # Expired subscription: menu category create
    resp_cat = client.post(
        f"/api/v1/outlets/{outlet.id}/categories",
        headers=_auth(owner),
        json={"name": "Should Not Exist", "sort_order": 9},
    )
    assert resp_cat.status_code == 403

    # Expired subscription: staff order create
    resp_order = client.post(
        f"/api/v1/outlets/{outlet.id}/orders", headers=_auth(owner), json=_staff_order_payload(item)
    )
    assert resp_order.status_code == 403

    # Non-member stranger: item price mutation
    price_before = item.price
    resp_stranger = client.patch(
        f"/api/v1/items/{item.id}", headers=_auth(stranger), json={"price": "1.00"}
    )
    assert resp_stranger.status_code == 404

    counts_after = (
        db_session.query(MenuCategory).count(),
        db_session.query(MenuItem).count(),
        db_session.query(Order).count(),
        db_session.query(AuditLog).count(),
    )
    assert counts_after == counts_before, "denied requests must not create rows or audit logs"
    db_session.refresh(item)
    assert item.price == price_before

    # Suspended business: table create
    biz.status = "suspended"
    db_session.commit()
    resp_table = client.post(
        f"/api/v1/outlets/{outlet.id}/tables",
        headers=_auth(owner),
        json={"table_number": "T-NOPE", "capacity": 2},
    )
    assert resp_table.status_code == 403
    from app.modules.tables.models import DiningTable
    assert db_session.query(DiningTable).count() == 0


# ---------------------------------------------------------------------------
# P5: outlet branding carries role + lifecycle + entitlement like other writes
# ---------------------------------------------------------------------------

def test_expired_subscription_blocks_outlet_branding_update(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Branding Expired Biz")
    outlet = _create_outlet(db_session, biz, "Branding Expired Outlet", "branding-expired")
    owner = _create_user(db_session, "branding_expired_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet, "owner")
    _subscribe_business(db_session, biz, "growth_pos", status="active", period_end_in_days=-1)

    resp = client.patch(
        f"/api/v1/outlets/{outlet.id}/branding",
        headers=_auth(owner),
        json={"primary_color": "#111111", "logo_url": "outlets/logos/nope.png"},
    )
    assert resp.status_code == 403
    assert "SUBSCRIPTION_EXPIRED" in _err_message(resp)

    db_session.refresh(outlet)
    assert outlet.logo_url != "outlets/logos/nope.png"


def test_free_plan_and_active_plan_can_update_branding(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Branding Free Biz")
    outlet = _create_outlet(db_session, biz, "Branding Free Outlet", "branding-free")
    owner = _create_user(db_session, "branding_free_owner@example.com")
    _grant_outlet_role(db_session, owner, outlet, "owner")
    _subscribe_business(db_session, biz, "free_qr", status="active", period_end_in_days=365)

    resp = client.patch(
        f"/api/v1/outlets/{outlet.id}/branding",
        headers=_auth(owner),
        json={"primary_color": "#4f46e5", "logo_url": "outlets/logos/free-logo.png"},
    )
    assert resp.status_code == 200
    assert resp.json()["primary_color"] == "#4f46e5"
