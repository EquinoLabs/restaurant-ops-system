import pytest
from decimal import Decimal
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.tables.models import DiningTable
from app.modules.menus.models import MenuItem, MenuCategory
from app.modules.orders.models import Order, OrderItem, OrderIdempotencyKey


def test_public_order_success_with_server_calculated_totals(client, db_session):
    outlet = db_session.query(Outlet).filter(Outlet.public_slug == "test-camp").first()
    item = db_session.query(MenuItem).filter(MenuItem.outlet_id == outlet.id, MenuItem.is_available == True, MenuItem.is_active == True).first()

    # Create a table for this outlet
    table = DiningTable(outlet_id=outlet.id, table_number="T-01", capacity=4, status="available")
    db_session.add(table)
    db_session.commit()

    payload = {
        "table_number": "T-01",
        "items": [
            {"menu_item_id": str(item.id), "quantity": 2, "special_instructions": "Extra sauce"}
        ],
        "notes": "Customer Note"
    }

    resp = client.post(f"/api/v1/public/outlets/{outlet.public_slug}/orders", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert data["status"] == "pending"
    assert data["order_type"] == "dine_in"
    assert data["table_number"] == "T-01"
    assert data["waiter_user_id"] is None
    assert data["waiter_name"] is None
    assert float(data["total_amount"]) == 500.00  # 250.00 * 2
    assert len(data["items"]) == 1
    assert data["items"][0]["item_name"] == "Fried Fish"
    assert float(data["items"][0]["unit_price"]) == 250.00
    assert float(data["items"][0]["subtotal"]) == 500.00
    assert data["items"][0]["special_instructions"] == "Extra sauce"

    # Verify table status updated to occupied
    db_session.refresh(table)
    assert table.status == "occupied"


def test_public_order_takeaway_without_table(client, db_session):
    outlet = db_session.query(Outlet).filter(Outlet.public_slug == "test-camp").first()
    item = db_session.query(MenuItem).filter(MenuItem.outlet_id == outlet.id, MenuItem.is_available == True, MenuItem.is_active == True).first()

    payload = {
        "items": [
            {"menu_item_id": str(item.id), "quantity": 1}
        ]
    }

    resp = client.post(f"/api/v1/public/outlets/{outlet.public_slug}/orders", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert data["status"] == "pending"
    assert data["order_type"] == "takeaway"
    assert data["table_id"] is None
    assert data["table_number"] is None


def test_public_order_inactive_outlet_or_business(client, db_session):
    # Test non-existent slug
    resp = client.post("/api/v1/public/outlets/non-existent-slug/orders", json={
        "items": [{"menu_item_id": "00000000-0000-0000-0000-000000000000", "quantity": 1}]
    })
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "OUTLET_NOT_FOUND"

    # Test inactive outlet
    outlet = db_session.query(Outlet).first()
    outlet.status = "inactive"
    db_session.commit()

    item = db_session.query(MenuItem).first()
    resp = client.post(f"/api/v1/public/outlets/{outlet.public_slug}/orders", json={
        "items": [{"menu_item_id": str(item.id), "quantity": 1}]
    })
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "OUTLET_NOT_FOUND"

    # Restore outlet status and test suspended business
    outlet.status = "active"
    biz = outlet.business
    biz.status = "suspended"
    db_session.commit()

    resp = client.post(f"/api/v1/public/outlets/{outlet.public_slug}/orders", json={
        "items": [{"menu_item_id": str(item.id), "quantity": 1}]
    })
    assert resp.status_code == 404

    # Restore business
    biz.status = "active"
    db_session.commit()


def test_public_order_invalid_table_or_cross_outlet_table(client, db_session):
    outlet1 = db_session.query(Outlet).first()

    # Create second business and outlet
    biz2 = Business(name="Second Business", status="active")
    db_session.add(biz2)
    db_session.commit()

    outlet2 = Outlet(business_id=biz2.id, name="Outlet Two", public_slug="outlet-two", status="active")
    db_session.add(outlet2)
    db_session.commit()

    table2 = DiningTable(outlet_id=outlet2.id, table_number="T-99", capacity=4)
    db_session.add(table2)
    db_session.commit()

    item1 = db_session.query(MenuItem).filter(MenuItem.outlet_id == outlet1.id, MenuItem.is_available == True).first()

    # Requesting outlet1 with table2's number (which does not exist in outlet1)
    resp = client.post(f"/api/v1/public/outlets/{outlet1.public_slug}/orders", json={
        "table_number": "T-99",
        "items": [{"menu_item_id": str(item1.id), "quantity": 1}]
    })
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "INVALID_TABLE"


def test_public_order_invalid_or_unavailable_menu_items(client, db_session):
    outlet = db_session.query(Outlet).first()

    # Unavail item
    unavail_item = db_session.query(MenuItem).filter(MenuItem.is_available == False).first()

    resp = client.post(f"/api/v1/public/outlets/{outlet.public_slug}/orders", json={
        "items": [{"menu_item_id": str(unavail_item.id), "quantity": 1}]
    })
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "ITEM_UNAVAILABLE"

    # Inactive / deleted item
    inactive_item = db_session.query(MenuItem).filter(MenuItem.is_active == False).first()

    resp = client.post(f"/api/v1/public/outlets/{outlet.public_slug}/orders", json={
        "items": [{"menu_item_id": str(inactive_item.id), "quantity": 1}]
    })
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "ITEM_UNAVAILABLE"


def test_public_order_invalid_quantities_and_payloads(client, db_session):
    outlet = db_session.query(Outlet).first()
    item = db_session.query(MenuItem).filter(MenuItem.is_available == True, MenuItem.is_active == True).first()

    # Quantity 0
    resp = client.post(f"/api/v1/public/outlets/{outlet.public_slug}/orders", json={
        "items": [{"menu_item_id": str(item.id), "quantity": 0}]
    })
    assert resp.status_code == 422

    # Quantity > 99
    resp = client.post(f"/api/v1/public/outlets/{outlet.public_slug}/orders", json={
        "items": [{"menu_item_id": str(item.id), "quantity": 100}]
    })
    assert resp.status_code == 422

    # Empty items list
    resp = client.post(f"/api/v1/public/outlets/{outlet.public_slug}/orders", json={
        "items": []
    })
    assert resp.status_code == 422


def test_public_order_idempotency_retry_and_conflict(client, db_session):
    outlet = db_session.query(Outlet).first()
    item = db_session.query(MenuItem).filter(MenuItem.is_available == True, MenuItem.is_active == True).first()

    idemp_key = "test-key-uuid-1234"
    payload = {
        "items": [{"menu_item_id": str(item.id), "quantity": 2}],
        "notes": "Test Idempotency"
    }

    # Initial request with header
    headers = {"X-Idempotency-Key": idemp_key}
    resp1 = client.post(f"/api/v1/public/outlets/{outlet.public_slug}/orders", headers=headers, json=payload)
    assert resp1.status_code == 201
    order1 = resp1.json()

    # Retry identical request with same idempotency key
    resp2 = client.post(f"/api/v1/public/outlets/{outlet.public_slug}/orders", headers=headers, json=payload)
    assert resp2.status_code == 201
    order2 = resp2.json()

    assert order1["id"] == order2["id"]
    assert order1["order_number"] == order2["order_number"]

    # Verify only 1 order created in database
    orders_in_db = db_session.query(Order).filter(Order.outlet_id == outlet.id).all()
    assert len(orders_in_db) == 1

    # Attempt reuse of same idempotency key with a DIFFERENT payload
    different_payload = {
        "items": [{"menu_item_id": str(item.id), "quantity": 5}],
        "notes": "Modified Payload"
    }
    resp_conflict = client.post(f"/api/v1/public/outlets/{outlet.public_slug}/orders", headers=headers, json=different_payload)
    assert resp_conflict.status_code == 409
    assert resp_conflict.json()["detail"]["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_staff_endpoint_authorization_unaffected(client, db_session):
    outlet = db_session.query(Outlet).first()

    # Attempting staff order creation without token fails with 401
    resp_unauth = client.post(f"/api/v1/outlets/{outlet.id}/orders", json={
        "items": [{"menu_item_id": "00000000-0000-0000-0000-000000000000", "quantity": 1}]
    })
    assert resp_unauth.status_code == 401


def test_idempotency_key_mismatch_header_and_body(client, db_session):
    outlet = db_session.query(Outlet).first()
    item = db_session.query(MenuItem).filter(MenuItem.is_available == True, MenuItem.is_active == True).first()

    # Header = Key-A, Body = Key-B -> Should return 400 Bad Request
    headers = {"X-Idempotency-Key": "Key-Header-A"}
    payload = {
        "idempotency_key": "Key-Body-B",
        "items": [{"menu_item_id": str(item.id), "quantity": 1}]
    }
    resp = client.post(f"/api/v1/public/outlets/{outlet.public_slug}/orders", headers=headers, json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "IDEMPOTENCY_KEY_MISMATCH"


def test_idempotency_key_body_only(client, db_session):
    outlet = db_session.query(Outlet).first()
    item = db_session.query(MenuItem).filter(MenuItem.is_available == True, MenuItem.is_active == True).first()

    payload = {
        "idempotency_key": "Body-Only-Key-999",
        "items": [{"menu_item_id": str(item.id), "quantity": 1}]
    }
    resp1 = client.post(f"/api/v1/public/outlets/{outlet.public_slug}/orders", json=payload)
    assert resp1.status_code == 201
    order1 = resp1.json()

    # Retry with body-only key
    resp2 = client.post(f"/api/v1/public/outlets/{outlet.public_slug}/orders", json=payload)
    assert resp2.status_code == 201
    assert resp2.json()["id"] == order1["id"]


def test_order_idempotency_key_model_and_schema_parity(client, db_session):
    outlet = db_session.query(Outlet).first()
    item = db_session.query(MenuItem).filter(MenuItem.is_available == True, MenuItem.is_active == True).first()

    payload = {
        "idempotency_key": "Schema-Parity-Key-001",
        "items": [{"menu_item_id": str(item.id), "quantity": 1}]
    }
    resp = client.post(f"/api/v1/public/outlets/{outlet.public_slug}/orders", json=payload)
    assert resp.status_code == 201

    # Verify OrderIdempotencyKey record in database has both created_at and updated_at
    idemp_rec = db_session.query(OrderIdempotencyKey).filter(
        OrderIdempotencyKey.outlet_id == outlet.id,
        OrderIdempotencyKey.idempotency_key == "Schema-Parity-Key-001"
    ).first()
    assert idemp_rec is not None
    assert idemp_rec.created_at is not None
    assert idemp_rec.updated_at is not None

