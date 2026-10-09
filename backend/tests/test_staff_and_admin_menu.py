import pytest
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.modules.staff.models import User
from app.modules.outlets.models import Outlet


def test_security_utilities():
    raw_pwd = "my_secret_password"
    hashed = hash_password(raw_pwd)
    assert verify_password(raw_pwd, hashed) is True
    assert verify_password("wrong_password", hashed) is False

    token = create_access_token("user-123", extra_claims={"role": "owner"})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["role"] == "owner"


def test_staff_login_success_and_failure(client):
    # Test valid credentials
    response = client.post("/api/v1/auth/login", json={
        "email": "staff@test.com",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Test invalid password
    bad_response = client.post("/api/v1/auth/login", json={
        "email": "staff@test.com",
        "password": "wrongpassword"
    })
    assert bad_response.status_code == 401


def test_staff_get_me(client, db_session):
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "staff@test.com",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]

    me_resp = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["email"] == "staff@test.com"
    assert len(data["memberships"]) == 1
    assert data["memberships"][0]["role"] == "owner"


def test_get_admin_menu(client, db_session):
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "staff@test.com",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    outlet = db_session.query(Outlet).first()

    response = client.get(
        f"/api/v1/outlets/{outlet.id}/admin/menu",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["outlet_id"] == str(outlet.id)
    # Check that inactive category and inactive items are included in admin view
    categories = data["categories"]
    assert len(categories) == 2  # Starters and Archived Category
    
    starters_cat = next(c for c in categories if c["name"] == "Starters")
    assert len(starters_cat["items"]) == 3  # Fried Fish, Seasonal Fruit Bowl, Deleted Dish


def test_create_and_update_category(client, db_session):
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "staff@test.com",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    outlet = db_session.query(Outlet).first()

    # Create category
    create_resp = client.post(
        f"/api/v1/outlets/{outlet.id}/categories",
        headers=headers,
        json={"name": "Desserts", "description": "Sweet treats", "sort_order": 3}
    )
    assert create_resp.status_code == 200
    cat_data = create_resp.json()
    assert cat_data["name"] == "Desserts"
    cat_id = cat_data["id"]

    # Patch category
    patch_resp = client.patch(
        f"/api/v1/categories/{cat_id}",
        headers=headers,
        json={"name": "Himachali Desserts"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Himachali Desserts"


def test_create_item_and_price_change_audit(client, db_session):
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "staff@test.com",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    outlet = db_session.query(Outlet).first()

    # Get admin menu to get category id
    menu_resp = client.get(f"/api/v1/outlets/{outlet.id}/admin/menu", headers=headers)
    cat_id = menu_resp.json()["categories"][0]["id"]

    # Create Item
    create_resp = client.post(
        f"/api/v1/outlets/{outlet.id}/items",
        headers=headers,
        json={
            "category_id": cat_id,
            "name": "Local Tea",
            "price": "50.00",
            "is_available": True
        }
    )
    assert create_resp.status_code == 200
    item_id = create_resp.json()["id"]

    # Update Item price
    patch_resp = client.patch(
        f"/api/v1/items/{item_id}",
        headers=headers,
        json={"price": "65.00"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["price"] == "65.00"

    # Check Audit Logs
    audit_resp = client.get(f"/api/v1/outlets/{outlet.id}/audit-logs", headers=headers)
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    actions = [log["action"] for log in logs]
    assert "ITEM_CREATE" in actions
    assert "PRICE_CHANGE" in actions


def test_toggle_item_availability(client, db_session):
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "staff@test.com",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    outlet = db_session.query(Outlet).first()

    # Fetch item id
    menu_resp = client.get(f"/api/v1/outlets/{outlet.id}/admin/menu", headers=headers)
    item_id = menu_resp.json()["categories"][0]["items"][0]["id"]

    # Toggle availability to false
    toggle_resp = client.post(
        f"/api/v1/items/{item_id}/availability",
        headers=headers,
        json={"is_available": False}
    )
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["is_available"] is False


def test_unauthorized_admin_access(client, db_session):
    # Login as unauth_user (no membership in outlet)
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "unauth@test.com",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    outlet = db_session.query(Outlet).first()

    # Try to access admin menu -> should be 403 Forbidden
    response = client.get(f"/api/v1/outlets/{outlet.id}/admin/menu", headers=headers)
    assert response.status_code == 403
