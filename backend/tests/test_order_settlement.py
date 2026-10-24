import uuid
from decimal import Decimal
from typing import Optional
import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.tables.models import DiningTable
from app.modules.menus.models import MenuItem
from app.modules.orders.models import Order
from app.modules.staff.models import User, OutletMembership
from app.modules.audit.models import AuditLog
from app.core.security import hash_password


def _setup_actors(db_session: Session):
    outlet = db_session.query(Outlet).filter(Outlet.public_slug == "test-camp").first()

    # 1. Waiter user
    waiter = User(
        email=f"waiter_{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("password123"),
        display_name="Waiter Alice",
        status="active"
    )
    db_session.add(waiter)
    db_session.commit()
    db_session.add(OutletMembership(user_id=waiter.id, outlet_id=outlet.id, role="waiter"))

    # 2. Kitchen user
    kitchen = User(
        email=f"kitchen_{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("password123"),
        display_name="Chef Bob",
        status="active"
    )
    db_session.add(kitchen)
    db_session.commit()
    db_session.add(OutletMembership(user_id=kitchen.id, outlet_id=outlet.id, role="kitchen"))

    # 3. External business & user (cross-tenant)
    other_biz = Business(name="Other Resort", status="active")
    db_session.add(other_biz)
    db_session.commit()
    other_outlet = Outlet(business_id=other_biz.id, name="Other Outlet", public_slug=f"other-{uuid.uuid4().hex[:4]}", status="active")
    db_session.add(other_outlet)
    db_session.commit()

    other_user = User(
        email=f"other_{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("password123"),
        display_name="Other Staff",
        status="active"
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.add(OutletMembership(user_id=other_user.id, outlet_id=other_outlet.id, role="owner"))

    db_session.commit()
    return outlet, waiter, kitchen, other_user, other_outlet


def _login(client: TestClient, email: str, password: str = "password123") -> dict:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_order(client: TestClient, headers: dict, outlet_id: uuid.UUID, db_session: Session, table_id: Optional[str] = None) -> dict:
    item = db_session.query(MenuItem).filter(MenuItem.outlet_id == outlet_id, MenuItem.is_available == True).first()
    if not table_id:
        table = DiningTable(outlet_id=outlet_id, table_number=f"T-{uuid.uuid4().hex[:4]}", capacity=4)
        db_session.add(table)
        db_session.commit()
        effective_table_id = str(table.id)
    else:
        effective_table_id = table_id

    order_resp = client.post(
        f"/api/v1/outlets/{outlet_id}/orders",
        headers=headers,
        json={
            "table_id": effective_table_id,
            "order_type": "dine_in",
            "items": [{"menu_item_id": str(item.id), "quantity": 2, "special_instructions": "Extra sauce"}],
            "notes": "Table order"
        }
    )
    assert order_resp.status_code == 200, order_resp.text
    return order_resp.json()


# ---------------------------------------------------------------------------
# Scenarios 1 & 6: Newly created order starts unpaid & remains visible to staff
# ---------------------------------------------------------------------------

def test_new_order_starts_unpaid_and_is_visible_to_staff(client: TestClient, db_session: Session):
    outlet, waiter, _, _, _ = _setup_actors(db_session)
    waiter_headers = _login(client, waiter.email)

    order_data = _create_order(client, waiter_headers, outlet.id, db_session)
    assert order_data["payment_status"] == "unpaid"
    assert order_data["payment_method"] is None
    assert order_data["settled_at"] is None
    assert order_data["settled_by_user_id"] is None
    assert order_data["settled_by_name"] is None

    # Check staff list orders endpoint includes payment_status
    list_resp = client.get(f"/api/v1/outlets/{outlet.id}/orders", headers=waiter_headers)
    assert list_resp.status_code == 200
    listed_orders = list_resp.json()
    matched = next((o for o in listed_orders if o["id"] == order_data["id"]), None)
    assert matched is not None
    assert matched["payment_status"] == "unpaid"
    assert matched["payment_method"] is None


# ---------------------------------------------------------------------------
# Scenario 2: Authorized staff member records Cash settlement & audit log
# ---------------------------------------------------------------------------

def test_authorized_staff_can_record_cash_settlement(client: TestClient, db_session: Session):
    outlet, waiter, _, _, _ = _setup_actors(db_session)
    waiter_headers = _login(client, waiter.email)

    order_data = _create_order(client, waiter_headers, outlet.id, db_session)
    order_id = order_data["id"]

    settle_resp = client.post(
        f"/api/v1/orders/{order_id}/settle",
        headers=waiter_headers,
        json={"payment_method": "cash", "confirm": True}
    )
    assert settle_resp.status_code == 200, settle_resp.text
    settled = settle_resp.json()
    assert settled["payment_status"] == "paid"
    assert settled["payment_method"] == "cash"
    assert settled["settled_at"] is not None
    assert settled["settled_by_user_id"] == str(waiter.id)
    assert settled["settled_by_name"] == waiter.display_name

    # Verify audit log was emitted
    audit = db_session.query(AuditLog).filter(
        AuditLog.entity_id == uuid.UUID(order_id),
        AuditLog.action == "order.settle"
    ).first()
    assert audit is not None
    assert audit.actor_user_id == waiter.id
    assert audit.metadata_json["payment_method"] == "cash"
    assert audit.metadata_json["order_number"] == order_data["order_number"]


# ---------------------------------------------------------------------------
# Scenario 3: Authorized staff member records UPI settlement
# ---------------------------------------------------------------------------

def test_authorized_staff_can_record_upi_settlement(client: TestClient, db_session: Session):
    outlet, waiter, _, _, _ = _setup_actors(db_session)
    waiter_headers = _login(client, waiter.email)

    order_data = _create_order(client, waiter_headers, outlet.id, db_session)
    order_id = order_data["id"]

    settle_resp = client.post(
        f"/api/v1/orders/{order_id}/settle",
        headers=waiter_headers,
        json={"payment_method": "upi", "confirm": True}
    )
    assert settle_resp.status_code == 200
    settled = settle_resp.json()
    assert settled["payment_status"] == "paid"
    assert settled["payment_method"] == "upi"
    assert settled["settled_by_user_id"] == str(waiter.id)


# ---------------------------------------------------------------------------
# Scenario 4: Confirmation required (confirm=False rejected)
# ---------------------------------------------------------------------------

def test_order_settlement_requires_explicit_confirmation(client: TestClient, db_session: Session):
    outlet, waiter, _, _, _ = _setup_actors(db_session)
    waiter_headers = _login(client, waiter.email)

    order_data = _create_order(client, waiter_headers, outlet.id, db_session)
    order_id = order_data["id"]

    resp = client.post(
        f"/api/v1/orders/{order_id}/settle",
        headers=waiter_headers,
        json={"payment_method": "cash", "confirm": False}
    )
    assert resp.status_code == 422
    assert "explicitly confirmed" in resp.json()["detail"]["error"]["message"].lower()

    # Verify order remains unpaid
    db_order = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    assert db_order.payment_status == "unpaid"


# ---------------------------------------------------------------------------
# Scenario 5: Unpaid served order cannot be silently closed
# ---------------------------------------------------------------------------

def test_unpaid_served_order_cannot_be_silently_closed(client: TestClient, db_session: Session):
    outlet, waiter, _, _, _ = _setup_actors(db_session)
    waiter_headers = _login(client, waiter.email)

    order_data = _create_order(client, waiter_headers, outlet.id, db_session)
    order_id = order_data["id"]

    # Transition to served
    for s in ["confirmed", "in_kitchen", "served"]:
        client.patch(f"/api/v1/orders/{order_id}/status", headers=waiter_headers, json={"status": s})

    # Attempt to complete without payment
    resp = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers=waiter_headers,
        json={"status": "completed"}
    )
    assert resp.status_code == 422
    assert "unpaid" in resp.json()["detail"]["error"]["message"].lower()

    # Verify status is still served and table is still occupied
    db_order = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    assert db_order.status == "served"
    assert db_order.table.status == "occupied"


# ---------------------------------------------------------------------------
# Scenario 7: Repeated settlement submissions (Idempotent retry vs conflict)
# ---------------------------------------------------------------------------

def test_repeated_settlement_idempotent_and_conflict(client: TestClient, db_session: Session):
    outlet, waiter, _, _, _ = _setup_actors(db_session)
    waiter_headers = _login(client, waiter.email)

    order_data = _create_order(client, waiter_headers, outlet.id, db_session)
    order_id = order_data["id"]

    # Initial cash settlement
    resp1 = client.post(
        f"/api/v1/orders/{order_id}/settle",
        headers=waiter_headers,
        json={"payment_method": "cash", "confirm": True}
    )
    assert resp1.status_code == 200
    settled_at_first = resp1.json()["settled_at"]

    # Exactly 1 audit log event emitted for the initial settlement
    audits_initial = db_session.query(AuditLog).filter(
        AuditLog.entity_id == uuid.UUID(order_id),
        AuditLog.action == "order.settle"
    ).all()
    assert len(audits_initial) == 1

    # Repeated identical settlement (cash) -> Idempotent success without mutation
    resp2 = client.post(
        f"/api/v1/orders/{order_id}/settle",
        headers=waiter_headers,
        json={"payment_method": "cash", "confirm": True}
    )
    assert resp2.status_code == 200
    assert resp2.json()["settled_at"] == settled_at_first

    # Must still have EXACTLY 1 audit event (no duplicate event emitted on identical retry)
    audits_after_retry = db_session.query(AuditLog).filter(
        AuditLog.entity_id == uuid.UUID(order_id),
        AuditLog.action == "order.settle"
    ).all()
    assert len(audits_after_retry) == 1

    # Attempt re-settlement with DIFFERENT method (upi) -> 409 Conflict
    resp3 = client.post(
        f"/api/v1/orders/{order_id}/settle",
        headers=waiter_headers,
        json={"payment_method": "upi", "confirm": True}
    )
    assert resp3.status_code == 409
    assert "already settled" in resp3.json()["detail"]["error"]["message"].lower()

    # Original settlement details remain untouched in the database
    db_order = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    assert db_order.payment_status == "paid"
    assert db_order.payment_method == "cash"
    assert db_order.settled_at.isoformat() == settled_at_first

    # Exactly 1 audit event remains (conflicting re-settlement did NOT emit an audit event)
    audits_after_conflict = db_session.query(AuditLog).filter(
        AuditLog.entity_id == uuid.UUID(order_id),
        AuditLog.action == "order.settle"
    ).all()
    assert len(audits_after_conflict) == 1
    assert audits_after_conflict[0].metadata_json["payment_method"] == "cash"


# ---------------------------------------------------------------------------
# Scenario 8: Unsupported payment methods rejected
# ---------------------------------------------------------------------------

def test_unsupported_payment_methods_rejected(client: TestClient, db_session: Session):
    outlet, waiter, _, _, _ = _setup_actors(db_session)
    waiter_headers = _login(client, waiter.email)

    order_data = _create_order(client, waiter_headers, outlet.id, db_session)
    order_id = order_data["id"]

    # Unsupported method: crypto
    resp = client.post(
        f"/api/v1/orders/{order_id}/settle",
        headers=waiter_headers,
        json={"payment_method": "crypto", "confirm": True}
    )
    assert resp.status_code == 422
    assert "invalid payment method" in resp.json()["detail"]["error"]["message"].lower()

    # Empty string method
    resp_empty = client.post(
        f"/api/v1/orders/{order_id}/settle",
        headers=waiter_headers,
        json={"payment_method": "   ", "confirm": True}
    )
    assert resp_empty.status_code == 422


# ---------------------------------------------------------------------------
# Scenario 9: Unauthorized users cannot settle orders
# ---------------------------------------------------------------------------

def test_unauthorized_users_cannot_settle(client: TestClient, db_session: Session):
    outlet, waiter, _, _, _ = _setup_actors(db_session)
    waiter_headers = _login(client, waiter.email)

    order_data = _create_order(client, waiter_headers, outlet.id, db_session)
    order_id = order_data["id"]

    # Anonymous user -> 401
    resp_anon = client.post(
        f"/api/v1/orders/{order_id}/settle",
        json={"payment_method": "cash", "confirm": True}
    )
    assert resp_anon.status_code == 401

    # Unaffiliated user (unauth@test.com from conftest) -> 404 anti-probing
    unaffil_headers = _login(client, "unauth@test.com")
    resp_unaffil = client.post(
        f"/api/v1/orders/{order_id}/settle",
        headers=unaffil_headers,
        json={"payment_method": "cash", "confirm": True}
    )
    assert resp_unaffil.status_code == 404


# ---------------------------------------------------------------------------
# Scenario 10: Cross-tenant isolation (user from another outlet/business)
# ---------------------------------------------------------------------------

def test_cross_tenant_cannot_settle_order(client: TestClient, db_session: Session):
    outlet, waiter, _, other_user, _ = _setup_actors(db_session)
    waiter_headers = _login(client, waiter.email)
    other_headers = _login(client, other_user.email)

    order_data = _create_order(client, waiter_headers, outlet.id, db_session)
    order_id = order_data["id"]

    # Other business user attempting to settle order gets anti-probing 404
    resp = client.post(
        f"/api/v1/orders/{order_id}/settle",
        headers=other_headers,
        json={"payment_method": "cash", "confirm": True}
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Scenario 11: Database failure leaves settlement state consistent
# ---------------------------------------------------------------------------

def test_database_failure_rolls_back_settlement(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch):
    outlet, waiter, _, _, _ = _setup_actors(db_session)
    waiter_headers = _login(client, waiter.email)

    order_data = _create_order(client, waiter_headers, outlet.id, db_session)
    order_id = order_data["id"]

    # Simulate DB error during commit in settle_order
    orig_commit = db_session.commit
    def fail_commit():
        raise RuntimeError("Simulated DB connection failure")
    monkeypatch.setattr(db_session, "commit", fail_commit)

    with pytest.raises(RuntimeError):
        client.post(
            f"/api/v1/orders/{order_id}/settle",
            headers=waiter_headers,
            json={"payment_method": "cash", "confirm": True}
        )

    # Restore commit and verify order state remains unpaid
    monkeypatch.setattr(db_session, "commit", orig_commit)
    db_session.rollback()
    refreshed_order = db_session.query(Order).filter(Order.id == uuid.UUID(order_id)).first()
    assert refreshed_order.payment_status == "unpaid"
    assert refreshed_order.payment_method is None


# ---------------------------------------------------------------------------
# Scenario 12: Kitchen transitions do not mark payment as received
# ---------------------------------------------------------------------------

def test_kitchen_transitions_do_not_mark_payment(client: TestClient, db_session: Session):
    outlet, waiter, kitchen, _, _ = _setup_actors(db_session)
    waiter_headers = _login(client, waiter.email)
    kitchen_headers = _login(client, kitchen.email)

    order_data = _create_order(client, waiter_headers, outlet.id, db_session)
    order_id = order_data["id"]

    # Kitchen staff advances order through cooking lifecycle
    client.patch(f"/api/v1/orders/{order_id}/status", headers=kitchen_headers, json={"status": "confirmed"})
    client.patch(f"/api/v1/orders/{order_id}/status", headers=kitchen_headers, json={"status": "in_kitchen"})
    bump_resp = client.patch(f"/api/v1/orders/{order_id}/status", headers=kitchen_headers, json={"status": "served"})
    assert bump_resp.status_code == 200

    order_after_kitchen = bump_resp.json()
    assert order_after_kitchen["status"] == "served"
    assert order_after_kitchen["payment_status"] == "unpaid"
    assert order_after_kitchen["payment_method"] is None


# ---------------------------------------------------------------------------
# Scenario 13: Cancellation and completion behaviour remains coherent
# ---------------------------------------------------------------------------

def test_cancellation_and_completion_behaviour_coherent(client: TestClient, db_session: Session):
    outlet, waiter, _, _, _ = _setup_actors(db_session)
    waiter_headers = _login(client, waiter.email)

    # 1. Order cancelled while unpaid -> frees table, remains unpaid
    order_data_1 = _create_order(client, waiter_headers, outlet.id, db_session)
    order_id_1 = order_data_1["id"]
    table_id_1 = order_data_1["table_id"]

    cancel_resp = client.patch(f"/api/v1/orders/{order_id_1}/status", headers=waiter_headers, json={"status": "cancelled"})
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["payment_status"] == "unpaid"

    # Table is released on cancellation
    table_1 = db_session.query(DiningTable).filter(DiningTable.id == uuid.UUID(table_id_1)).first()
    assert table_1.status == "available"

    # Settling a cancelled order is rejected
    settle_cancelled = client.post(
        f"/api/v1/orders/{order_id_1}/settle",
        headers=waiter_headers,
        json={"payment_method": "cash", "confirm": True}
    )
    assert settle_cancelled.status_code == 422
    assert "cancelled" in settle_cancelled.json()["detail"]["error"]["message"].lower()

    # 2. Paid order completes successfully and frees table
    order_data_2 = _create_order(client, waiter_headers, outlet.id, db_session)
    order_id_2 = order_data_2["id"]
    table_id_2 = order_data_2["table_id"]

    # Settle first
    client.post(
        f"/api/v1/orders/{order_id_2}/settle",
        headers=waiter_headers,
        json={"payment_method": "upi", "confirm": True}
    )
    # Transition to completed
    for s in ["confirmed", "in_kitchen", "served", "completed"]:
        client.patch(f"/api/v1/orders/{order_id_2}/status", headers=waiter_headers, json={"status": s})

    table_2 = db_session.query(DiningTable).filter(DiningTable.id == uuid.UUID(table_id_2)).first()
    assert table_2.status == "available"


# ---------------------------------------------------------------------------
# Scenario 14: Kitchen role cannot settle orders
# ---------------------------------------------------------------------------

def test_kitchen_role_cannot_settle_orders(client: TestClient, db_session: Session):
    outlet, waiter, kitchen, _, _ = _setup_actors(db_session)
    waiter_headers = _login(client, waiter.email)
    kitchen_headers = _login(client, kitchen.email)

    order_data = _create_order(client, waiter_headers, outlet.id, db_session)
    order_id = order_data["id"]

    # Kitchen role attempts to call settlement endpoint
    resp = client.post(
        f"/api/v1/orders/{order_id}/settle",
        headers=kitchen_headers,
        json={"payment_method": "cash", "confirm": True}
    )
    assert resp.status_code == 403
    assert "role" in resp.json()["detail"]["error"]["message"].lower() or "privilege" in resp.json()["detail"]["error"]["message"].lower()


# ---------------------------------------------------------------------------
# Scenario 15: Multi-order table lifecycle & table release gating
# ---------------------------------------------------------------------------

def test_multi_order_table_lifecycle(client: TestClient, db_session: Session):
    """Multi-order table lifecycle:
    1. Table has two active dine-in orders (Order A and Order B).
    2. Table is marked occupied.
    3. Order A is settled as paid and completed.
    4. Table must REMAIN occupied because Order B is still active.
    5. Order B is settled as paid and completed.
    6. Table transitions to available because no active orders remain on it.
    """
    outlet, waiter, _, _, _ = _setup_actors(db_session)
    waiter_headers = _login(client, waiter.email)

    # Create Order A on a new table
    order_a = _create_order(client, waiter_headers, outlet.id, db_session)
    order_a_id = order_a["id"]
    table_id = order_a["table_id"]

    # Create Order B on the SAME table
    order_b = _create_order(client, waiter_headers, outlet.id, db_session, table_id=table_id)
    order_b_id = order_b["id"]

    # Verify table is occupied
    table = db_session.query(DiningTable).filter(DiningTable.id == uuid.UUID(table_id)).first()
    assert table.status == "occupied"

    # Advance both orders to served
    for s in ["confirmed", "in_kitchen", "served"]:
        client.patch(f"/api/v1/orders/{order_a_id}/status", headers=waiter_headers, json={"status": s})
        client.patch(f"/api/v1/orders/{order_b_id}/status", headers=waiter_headers, json={"status": s})

    # Settle Order A (cash)
    settle_a = client.post(
        f"/api/v1/orders/{order_a_id}/settle",
        headers=waiter_headers,
        json={"payment_method": "cash", "confirm": True}
    )
    assert settle_a.status_code == 200

    # Complete Order A
    comp_a = client.patch(
        f"/api/v1/orders/{order_a_id}/status",
        headers=waiter_headers,
        json={"status": "completed"}
    )
    assert comp_a.status_code == 200

    # Table MUST still be occupied because Order B is still served (active)
    db_session.refresh(table)
    assert table.status == "occupied"

    # Attempting to complete Order B while unpaid is blocked (422)
    comp_b_fail = client.patch(
        f"/api/v1/orders/{order_b_id}/status",
        headers=waiter_headers,
        json={"status": "completed"}
    )
    assert comp_b_fail.status_code == 422
    db_session.refresh(table)
    assert table.status == "occupied"

    # Settle Order B (upi)
    settle_b = client.post(
        f"/api/v1/orders/{order_b_id}/settle",
        headers=waiter_headers,
        json={"payment_method": "upi", "confirm": True}
    )
    assert settle_b.status_code == 200

    # Complete Order B
    comp_b_ok = client.patch(
        f"/api/v1/orders/{order_b_id}/status",
        headers=waiter_headers,
        json={"status": "completed"}
    )
    assert comp_b_ok.status_code == 200

    # Now that both orders on the table are completed, the table must become available
    db_session.refresh(table)
    assert table.status == "available"

