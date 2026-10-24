import pytest
from app.modules.outlets.models import Outlet
from app.modules.tables.models import DiningTable
from app.modules.menus.models import MenuItem


def test_table_crud(client, db_session):
    # Staff login
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "staff@test.com",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    outlet = db_session.query(Outlet).first()

    # Create table
    create_resp = client.post(
        f"/api/v1/outlets/{outlet.id}/tables",
        headers=headers,
        json={"table_number": "T-10", "capacity": 4}
    )
    assert create_resp.status_code == 200
    table_data = create_resp.json()
    assert table_data["table_number"] == "T-10"
    assert table_data["status"] == "available"
    table_id = table_data["id"]

    # List tables
    list_resp = client.get(f"/api/v1/outlets/{outlet.id}/tables", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Patch table
    patch_resp = client.patch(
        f"/api/v1/tables/{table_id}",
        headers=headers,
        json={"capacity": 6}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["capacity"] == 6


def test_create_order_with_price_snapshot_and_occupancy(client, db_session):
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "staff@test.com",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    outlet = db_session.query(Outlet).first()

    # Create table
    table_resp = client.post(
        f"/api/v1/outlets/{outlet.id}/tables",
        headers=headers,
        json={"table_number": "T-01", "capacity": 4}
    )
    table_id = table_resp.json()["id"]

    # Get available menu item (Fried Fish - price 250.00)
    item = db_session.query(MenuItem).filter(
        MenuItem.outlet_id == outlet.id,
        MenuItem.is_available == True,
        MenuItem.is_active == True
    ).first()

    # Create Order
    order_resp = client.post(
        f"/api/v1/outlets/{outlet.id}/orders",
        headers=headers,
        json={
            "table_id": table_id,
            "order_type": "dine_in",
            "items": [
                {"menu_item_id": str(item.id), "quantity": 2, "special_instructions": "Extra crispy"}
            ],
            "notes": "VIP Guest"
        }
    )
    assert order_resp.status_code == 200
    order_data = order_resp.json()
    assert order_data["status"] == "pending"
    assert float(order_data["total_amount"]) == 500.00  # 250.00 * 2
    assert len(order_data["items"]) == 1
    assert order_data["items"][0]["item_name"] == item.name
    assert float(order_data["items"][0]["unit_price"]) == 250.00

    # Verify table status updated to occupied
    table_get = client.get(f"/api/v1/outlets/{outlet.id}/tables", headers=headers)
    assert table_get.json()[0]["status"] == "occupied"


def test_order_status_transitions_and_table_release(client, db_session):
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "staff@test.com",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    outlet = db_session.query(Outlet).first()

    # Create table & order
    table_resp = client.post(
        f"/api/v1/outlets/{outlet.id}/tables",
        headers=headers,
        json={"table_number": "T-02", "capacity": 2}
    )
    table_id = table_resp.json()["id"]

    item = db_session.query(MenuItem).filter(
        MenuItem.outlet_id == outlet.id,
        MenuItem.is_available == True
    ).first()

    order_resp = client.post(
        f"/api/v1/outlets/{outlet.id}/orders",
        headers=headers,
        json={
            "table_id": table_id,
            "order_type": "dine_in",
            "items": [{"menu_item_id": str(item.id), "quantity": 1}]
        }
    )
    order_id = order_resp.json()["id"]

    # Advance status: pending -> confirmed -> in_kitchen -> served
    for next_status in ["confirmed", "in_kitchen", "served"]:
        status_resp = client.patch(
            f"/api/v1/orders/{order_id}/status",
            headers=headers,
            json={"status": next_status}
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == next_status

    # Verify attempting to complete an unpaid order is blocked
    unpaid_complete = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers=headers,
        json={"status": "completed"}
    )
    assert unpaid_complete.status_code == 422
    assert "unpaid" in unpaid_complete.json()["detail"]["error"]["message"].lower()

    # Settle bill explicitly
    settle_resp = client.post(
        f"/api/v1/orders/{order_id}/settle",
        headers=headers,
        json={"payment_method": "cash", "confirm": True}
    )
    assert settle_resp.status_code == 200
    assert settle_resp.json()["payment_status"] == "paid"
    assert settle_resp.json()["payment_method"] == "cash"

    # Now complete order successfully
    comp_resp = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers=headers,
        json={"status": "completed"}
    )
    assert comp_resp.status_code == 200
    assert comp_resp.json()["status"] == "completed"

    # Verify table is automatically released back to available
    table_get = client.get(f"/api/v1/outlets/{outlet.id}/tables", headers=headers)
    assert table_get.json()[0]["status"] == "available"
