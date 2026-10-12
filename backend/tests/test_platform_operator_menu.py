import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.menus.models import MenuCategory, MenuItem
from app.modules.staff.models import User, OutletMembership
from app.modules.audit.models import AuditLog
from app.core.security import hash_password


@pytest.fixture
def test_setup(db_session: Session):
    """
    Sets up two businesses and outlets, plus test users with different platform/tenant roles.
    """
    biz_a = db_session.query(Business).first()
    outlet_a = db_session.query(Outlet).filter(Outlet.business_id == biz_a.id).first()

    # Second business & outlet for cross-outlet validation
    biz_b = Business(name="Second Business", status="active")
    db_session.add(biz_b)
    db_session.commit()

    outlet_b = Outlet(
        business_id=biz_b.id,
        name="Second Outlet",
        public_slug="second-outlet",
        timezone="Asia/Kolkata",
        currency="INR",
        address="Second Valley",
        status="active",
    )
    db_session.add(outlet_b)
    db_session.commit()

    # Menu resources in Outlet A
    cat_a = db_session.query(MenuCategory).filter(MenuCategory.outlet_id == outlet_a.id).first()
    item_a = db_session.query(MenuItem).filter(MenuItem.outlet_id == outlet_a.id).first()

    # Menu resources in Outlet B
    cat_b = MenuCategory(
        outlet_id=outlet_b.id,
        name="Outlet B Starters",
        description="Category in B",
        sort_order=1,
        is_active=True,
    )
    db_session.add(cat_b)
    db_session.commit()

    item_b = MenuItem(
        outlet_id=outlet_b.id,
        category_id=cat_b.id,
        name="Outlet B Special",
        description="Item in B",
        price=Decimal("350.00"),
        is_available=True,
        is_active=True,
        sort_order=1,
    )
    db_session.add(item_b)
    db_session.commit()

    # Platform Operator (platform_role="operator", is_platform_admin=False)
    operator_user = User(
        email="operator_menu@test.com",
        password_hash=hash_password("password123"),
        display_name="Menu Operator",
        status="active",
        is_platform_admin=False,
        platform_role="operator",
    )
    # Platform Admin (platform_role="admin", is_platform_admin=True)
    admin_user = User(
        email="admin_menu@test.com",
        password_hash=hash_password("password123"),
        display_name="Menu Admin",
        status="active",
        is_platform_admin=True,
        platform_role="admin",
    )
    # Platform Owner (platform_role="owner", is_platform_admin=True)
    owner_user = User(
        email="owner_menu@test.com",
        password_hash=hash_password("password123"),
        display_name="Menu Owner",
        status="active",
        is_platform_admin=True,
        platform_role="owner",
    )
    # Legacy Admin (platform_role=None, is_platform_admin=True)
    legacy_admin = User(
        email="legacy_admin_menu@test.com",
        password_hash=hash_password("password123"),
        display_name="Legacy Admin",
        status="active",
        is_platform_admin=True,
        platform_role=None,
    )
    # Tenant-Only User (Manager at Outlet A, zero platform role)
    tenant_user = User(
        email="tenant_manager@test.com",
        password_hash=hash_password("password123"),
        display_name="Tenant Manager",
        status="active",
        is_platform_admin=False,
        platform_role=None,
    )
    db_session.add_all([operator_user, admin_user, owner_user, legacy_admin, tenant_user])
    db_session.commit()

    # Assign tenant membership to tenant_user
    mem = OutletMembership(
        user_id=tenant_user.id,
        outlet_id=outlet_a.id,
        role="manager",
    )
    db_session.add(mem)
    db_session.commit()

    return {
        "biz_a": biz_a,
        "outlet_a": outlet_a,
        "cat_a": cat_a,
        "item_a": item_a,
        "biz_b": biz_b,
        "outlet_b": outlet_b,
        "cat_b": cat_b,
        "item_b": item_b,
        "operator": operator_user,
        "admin": admin_user,
        "owner": owner_user,
        "legacy_admin": legacy_admin,
        "tenant_user": tenant_user,
    }


def _get_auth_headers(client: TestClient, email: str, password: str = "password123") -> dict:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. Authorization: Operator, Admin, Owner & Legacy Admin on Platform Menu Endpoints
# ==============================================================================

def test_operator_platform_menu_full_lifecycle(client: TestClient, test_setup: dict, db_session: Session):
    headers = _get_auth_headers(client, "operator_menu@test.com")
    outlet_id = str(test_setup["outlet_a"].id)

    # 1. GET /outlets/{id}/menu
    get_resp = client.get(f"/api/v1/platform/outlets/{outlet_id}/menu", headers=headers)
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["outlet_id"] == outlet_id
    assert len(data["categories"]) >= 1

    # 2. POST /outlets/{id}/menu/categories
    cat_resp = client.post(
        f"/api/v1/platform/outlets/{outlet_id}/menu/categories",
        headers=headers,
        json={"name": "Desserts", "description": "Sweet treats", "sort_order": 5, "is_active": True},
    )
    assert cat_resp.status_code == 200
    cat_data = cat_resp.json()
    assert cat_data["name"] == "Desserts"
    new_cat_id = cat_data["id"]

    # 3. PATCH /outlets/{id}/menu/categories/{cat_id}
    patch_cat_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/menu/categories/{new_cat_id}",
        headers=headers,
        json={"name": "Artisan Desserts", "sort_order": 6},
    )
    assert patch_cat_resp.status_code == 200
    assert patch_cat_resp.json()["name"] == "Artisan Desserts"

    # 4. POST /outlets/{id}/menu/items
    item_resp = client.post(
        f"/api/v1/platform/outlets/{outlet_id}/menu/items",
        headers=headers,
        json={
            "category_id": new_cat_id,
            "name": "Chocolate Lava Cake",
            "description": "Warm molten cake",
            "price": "180.00",
            "is_available": True,
            "is_active": True,
            "sort_order": 1,
        },
    )
    assert item_resp.status_code == 200
    item_data = item_resp.json()
    assert item_data["name"] == "Chocolate Lava Cake"
    assert Decimal(str(item_data["price"])) == Decimal("180.00")
    new_item_id = item_data["id"]

    # 5. PATCH /outlets/{id}/menu/items/{item_id}
    patch_item_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/menu/items/{new_item_id}",
        headers=headers,
        json={"price": "195.00", "description": "Warm molten cake with vanilla gelato"},
    )
    assert patch_item_resp.status_code == 200
    assert Decimal(str(patch_item_resp.json()["price"])) == Decimal("195.00")

    # 6. PATCH /outlets/{id}/menu/items/{item_id}/availability
    avail_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/menu/items/{new_item_id}/availability",
        headers=headers,
        json={"is_available": False},
    )
    assert avail_resp.status_code == 200
    assert avail_resp.json()["is_available"] is False

    # 7. POST /outlets/{id}/menu/items/{item_id}/image
    fake_png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    with patch("app.core.r2_storage.upload_item_image", return_value="outlets/test/lava_cake.png") as mock_upload, \
         patch("app.core.r2_storage.delete_object") as mock_del:
        img_resp = client.post(
            f"/api/v1/platform/outlets/{outlet_id}/menu/items/{new_item_id}/image",
            headers=headers,
            files={"file": ("lava_cake.png", fake_png_bytes, "image/png")},
        )
        assert img_resp.status_code == 200
        mock_upload.assert_called_once()
        assert "lava_cake.png" in img_resp.json()["image_url"]

    # 8. DELETE /outlets/{id}/menu/items/{item_id}/image
    with patch("app.core.r2_storage.delete_object") as mock_del:
        del_img_resp = client.delete(
            f"/api/v1/platform/outlets/{outlet_id}/menu/items/{new_item_id}/image",
            headers=headers,
        )
        assert del_img_resp.status_code == 200
        assert del_img_resp.json()["image_url"] is None
        mock_del.assert_called_once_with("outlets/test/lava_cake.png")


def test_admin_and_owner_and_legacy_admin_access(client: TestClient, test_setup: dict):
    outlet_id = str(test_setup["outlet_a"].id)

    # Platform Admin can access
    admin_headers = _get_auth_headers(client, "admin_menu@test.com")
    resp_admin = client.get(f"/api/v1/platform/outlets/{outlet_id}/menu", headers=admin_headers)
    assert resp_admin.status_code == 200

    # Platform Owner can access
    owner_headers = _get_auth_headers(client, "owner_menu@test.com")
    resp_owner = client.get(f"/api/v1/platform/outlets/{outlet_id}/menu", headers=owner_headers)
    assert resp_owner.status_code == 200

    # Legacy Admin (platform_role=None, is_platform_admin=True) can access
    legacy_headers = _get_auth_headers(client, "legacy_admin_menu@test.com")
    resp_legacy = client.get(f"/api/v1/platform/outlets/{outlet_id}/menu", headers=legacy_headers)
    assert resp_legacy.status_code == 200


# ==============================================================================
# 2. Rejection of Unauthenticated and Tenant-Only Callers
# ==============================================================================

def test_unauthenticated_and_tenant_only_callers_rejected(client: TestClient, test_setup: dict):
    outlet_id = str(test_setup["outlet_a"].id)

    # 1. Unauthenticated -> 401 Unauthorized
    resp_unauth = client.get(f"/api/v1/platform/outlets/{outlet_id}/menu")
    assert resp_unauth.status_code == 401

    resp_post_unauth = client.post(
        f"/api/v1/platform/outlets/{outlet_id}/menu/categories",
        json={"name": "Drinks"},
    )
    assert resp_post_unauth.status_code == 401

    # 2. Tenant Manager (without platform role) -> 403 Forbidden
    tenant_headers = _get_auth_headers(client, "tenant_manager@test.com")
    resp_tenant = client.get(f"/api/v1/platform/outlets/{outlet_id}/menu", headers=tenant_headers)
    assert resp_tenant.status_code == 403

    resp_tenant_post = client.post(
        f"/api/v1/platform/outlets/{outlet_id}/menu/categories",
        headers=tenant_headers,
        json={"name": "Drinks"},
    )
    assert resp_tenant_post.status_code == 403


# ==============================================================================
# 3. Cross-Outlet Resource Isolation & Validation Failures
# ==============================================================================

def test_cross_outlet_isolation_and_reassignment_validation(client: TestClient, test_setup: dict):
    headers = _get_auth_headers(client, "operator_menu@test.com")
    outlet_a_id = str(test_setup["outlet_a"].id)
    outlet_b_id = str(test_setup["outlet_b"].id)
    cat_b_id = str(test_setup["cat_b"].id)
    item_b_id = str(test_setup["item_b"].id)
    cat_a_id = str(test_setup["cat_a"].id)
    item_a_id = str(test_setup["item_a"].id)

    # 1. Update Outlet B category using Outlet A URL -> 404 Not Found
    resp_mismatched_cat = client.patch(
        f"/api/v1/platform/outlets/{outlet_a_id}/menu/categories/{cat_b_id}",
        headers=headers,
        json={"name": "Tampered Name"},
    )
    assert resp_mismatched_cat.status_code == 404

    # 2. Update Outlet B item using Outlet A URL -> 404 Not Found
    resp_mismatched_item = client.patch(
        f"/api/v1/platform/outlets/{outlet_a_id}/menu/items/{item_b_id}",
        headers=headers,
        json={"name": "Tampered Item"},
    )
    assert resp_mismatched_item.status_code == 404

    # 3. Toggle availability of Outlet B item using Outlet A URL -> 404 Not Found
    resp_mismatched_avail = client.patch(
        f"/api/v1/platform/outlets/{outlet_a_id}/menu/items/{item_b_id}/availability",
        headers=headers,
        json={"is_available": False},
    )
    assert resp_mismatched_avail.status_code == 404

    # 4. Image upload on Outlet B item using Outlet A URL -> 404 Not Found
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    resp_mismatched_upload = client.post(
        f"/api/v1/platform/outlets/{outlet_a_id}/menu/items/{item_b_id}/image",
        headers=headers,
        files={"file": ("test.png", fake_png, "image/png")},
    )
    assert resp_mismatched_upload.status_code == 404

    # 5. Image delete on Outlet B item using Outlet A URL -> 404 Not Found
    resp_mismatched_del = client.delete(
        f"/api/v1/platform/outlets/{outlet_a_id}/menu/items/{item_b_id}/image",
        headers=headers,
    )
    assert resp_mismatched_del.status_code == 404

    # 6. Category reassignment: reassign Item A to Cat B (cross-outlet) -> 422 Validation Error
    resp_cross_reassign = client.patch(
        f"/api/v1/platform/outlets/{outlet_a_id}/menu/items/{item_a_id}",
        headers=headers,
        json={"category_id": cat_b_id},
    )
    assert resp_cross_reassign.status_code == 422
    assert "does not belong to outlet" in resp_cross_reassign.text

    # 7. Create item with cross-outlet category -> 422 Validation Error
    resp_cross_create = client.post(
        f"/api/v1/platform/outlets/{outlet_a_id}/menu/items",
        headers=headers,
        json={
            "category_id": cat_b_id,
            "name": "Cross Outlet Item",
            "price": "100.00",
        },
    )
    assert resp_cross_create.status_code == 422
    assert "does not belong to outlet" in resp_cross_create.text

    # 8. Nonexistent outlet ID -> 404 Not Found
    fake_outlet_id = str(uuid.uuid4())
    resp_nonexistent_outlet = client.get(
        f"/api/v1/platform/outlets/{fake_outlet_id}/menu",
        headers=headers,
    )
    assert resp_nonexistent_outlet.status_code == 404


# ==============================================================================
# 4. Operator Negative Boundary Enforcement (Commercial, Governance, Tenant Routes)
# ==============================================================================

def test_operator_denied_on_commercial_governance_and_tenant_routes(client: TestClient, test_setup: dict):
    headers = _get_auth_headers(client, "operator_menu@test.com")
    biz_id = str(test_setup["biz_a"].id)
    outlet_id = str(test_setup["outlet_a"].id)
    admin_user_id = str(test_setup["admin"].id)

    # 1. Commercial Endpoints -> 403 Forbidden
    assert client.get("/api/v1/platform/businesses", headers=headers).status_code == 403
    assert client.get("/api/v1/platform/plans", headers=headers).status_code == 403
    assert client.get("/api/v1/platform/admins", headers=headers).status_code == 403
    assert client.get("/api/v1/platform/audit-logs", headers=headers).status_code == 403
    assert client.get(f"/api/v1/platform/businesses/{biz_id}/subscriptions", headers=headers).status_code == 403
    assert client.get(f"/api/v1/platform/businesses/{biz_id}/entitlements", headers=headers).status_code == 403
    assert client.get(f"/api/v1/platform/businesses/{biz_id}/overrides", headers=headers).status_code == 403
    assert client.patch(f"/api/v1/platform/businesses/{biz_id}/subscription", headers=headers, json={"plan_name": "growth"}).status_code == 403
    assert client.post(f"/api/v1/platform/businesses/{biz_id}/assign-owner", headers=headers, json={"email": "x@x.com"}).status_code == 403

    # 2. Governance Endpoints -> 403 Forbidden
    assert client.post(f"/api/v1/platform/admins/{admin_user_id}/grant", headers=headers).status_code == 403
    assert client.post(f"/api/v1/platform/admins/{admin_user_id}/revoke", headers=headers).status_code == 403

    # 3. Provisioning Endpoints -> 403 Forbidden
    assert client.post("/api/v1/platform/businesses", headers=headers, json={"name": "Biz", "primary_outlet_name": "Out", "public_slug": "slug"}).status_code == 403
    assert client.post(f"/api/v1/platform/businesses/{biz_id}/outlets", headers=headers, json={"name": "Out", "public_slug": "out-slug"}).status_code == 403

    # 4. Tenant Routes (without OutletMembership) -> 403 Forbidden
    assert client.get(f"/api/v1/outlets/{outlet_id}/admin/menu", headers=headers).status_code == 403
    assert client.post(f"/api/v1/outlets/{outlet_id}/categories", headers=headers, json={"name": "Cat"}).status_code == 403


# ==============================================================================
# 5. Platform Audit Log Persistence & Failure Atomicity
# ==============================================================================

def test_platform_audit_log_persistence_and_failure_atomicity(client: TestClient, test_setup: dict, db_session: Session):
    headers = _get_auth_headers(client, "operator_menu@test.com")
    outlet_id = str(test_setup["outlet_a"].id)
    cat_id = str(test_setup["cat_a"].id)
    item_id = str(test_setup["item_a"].id)

    # 1. Create item and verify audit row
    create_resp = client.post(
        f"/api/v1/platform/outlets/{outlet_id}/menu/items",
        headers=headers,
        json={
            "category_id": cat_id,
            "name": "Audit Test Dish",
            "price": "220.00",
        },
    )
    assert create_resp.status_code == 200
    created_id = uuid.UUID(create_resp.json()["id"])

    audit_entry = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_type == "menu_item",
            AuditLog.entity_id == created_id,
            AuditLog.action == "platform.outlet.menu_item.create",
        )
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.outlet_id == test_setup["outlet_a"].id
    assert audit_entry.business_id == test_setup["biz_a"].id
    assert audit_entry.actor_user_id == test_setup["operator"].id
    assert audit_entry.metadata_json["source"] == "platform_operator"

    # 2. Failed mutation creates no audit log entry
    audit_count_before = db_session.query(AuditLog).count()
    failed_resp = client.post(
        f"/api/v1/platform/outlets/{outlet_id}/menu/items",
        headers=headers,
        json={
            "category_id": str(test_setup["cat_b"].id),  # cross-outlet category error
            "name": "Should Fail",
            "price": "100.00",
        },
    )
    assert failed_resp.status_code == 422
    audit_count_after = db_session.query(AuditLog).count()
    assert audit_count_after == audit_count_before


# ==============================================================================
# 6. R2 Storage Upload Rollback & Deletion Failure Handling
# ==============================================================================

def test_r2_upload_rollback_on_database_failure(client: TestClient, test_setup: dict):
    headers = _get_auth_headers(client, "operator_menu@test.com")
    outlet_id = str(test_setup["outlet_a"].id)
    item_id = str(test_setup["item_a"].id)
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"

    # Simulate DB error during upload commit
    with patch("app.core.r2_storage.upload_item_image", return_value="outlets/test/rollback.png") as mock_upload, \
         patch("app.core.r2_storage.delete_object") as mock_delete, \
         patch("app.modules.menus.platform_service.log_audit", side_effect=RuntimeError("Simulated DB audit crash")):
        with pytest.raises(RuntimeError, match="Simulated DB audit crash"):
            client.post(
                f"/api/v1/platform/outlets/{outlet_id}/menu/items/{item_id}/image",
                headers=headers,
                files={"file": ("rollback.png", fake_png, "image/png")},
            )
        # Verify uploaded object was cleaned up
        mock_delete.assert_called_once_with("outlets/test/rollback.png")


def test_r2_deletion_post_commit_failure_handled_gracefully(client: TestClient, test_setup: dict, db_session: Session, caplog: pytest.LogCaptureFixture):
    import logging
    headers = _get_auth_headers(client, "operator_menu@test.com")
    outlet_id = str(test_setup["outlet_a"].id)
    item = test_setup["item_a"]
    item.image_url = "outlets/test/existing.png"
    db_session.commit()

    # Simulate R2 delete_object raising generic unexpected exception post-commit
    with caplog.at_level(logging.WARNING):
        with patch("app.core.r2_storage.delete_object", side_effect=Exception("Unexpected R2 network timeout")):
            resp = client.delete(
                f"/api/v1/platform/outlets/{outlet_id}/menu/items/{item.id}/image",
                headers=headers,
            )

    # 1. Verify API reports the committed operation as successful (HTTP 200)
    assert resp.status_code == 200
    assert resp.json()["image_url"] is None

    # 2. Verify database image reference remains cleared
    refreshed_item = db_session.query(MenuItem).filter(MenuItem.id == item.id).first()
    assert refreshed_item.image_url is None

    # 3. Verify audit record remains persisted
    audit_entry = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_type == "menu_item",
            AuditLog.entity_id == item.id,
            AuditLog.action == "platform.outlet.menu_item.image_delete",
        )
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.metadata_json["old_key"] == "outlets/test/existing.png"

    # 4. Verify cleanup failure is observable through logging
    assert "Failed to delete R2 object" in caplog.text
    assert "Unexpected R2 network timeout" in caplog.text


def test_inactive_outlet_policy_read_write_asymmetry(client: TestClient, test_setup: dict, db_session: Session):
    """
    Documents and verifies the known limitation (L-01):
    - Platform mutations (create/update category/item) validate outlet/business existence
      without filtering on `Outlet.status == 'active'`, allowing operators to configure menus
      for draft/inactive outlets during onboarding.
    - Conversely, `get_platform_outlet_menu` delegates to `admin_service.get_admin_menu`,
      which strictly enforces `Outlet.status == 'active'` and returns 404 for inactive outlets.
    Aligning this policy across read and write operations requires a dedicated product decision.
    """
    headers = _get_auth_headers(client, "operator_menu@test.com")
    biz = test_setup["biz_a"]

    # Create an inactive outlet under an active business
    inactive_outlet = Outlet(
        business_id=biz.id,
        name="Inactive Draft Outlet",
        public_slug="inactive-draft-outlet",
        timezone="Asia/Kolkata",
        currency="INR",
        address="Draft Road",
        status="inactive",
    )
    db_session.add(inactive_outlet)
    db_session.commit()

    # 1. Platform menu read returns 404 for inactive outlet (admin_service.py active-status filter)
    read_resp = client.get(
        f"/api/v1/platform/outlets/{inactive_outlet.id}/menu",
        headers=headers,
    )
    assert read_resp.status_code == 404
    assert f"Outlet with ID '{inactive_outlet.id}' not found" in read_resp.text

    # 2. Platform menu mutation succeeds on inactive outlet (_get_verified_outlet existence check)
    cat_resp = client.post(
        f"/api/v1/platform/outlets/{inactive_outlet.id}/menu/categories",
        headers=headers,
        json={"name": "Draft Onboarding Category", "sort_order": 1, "is_active": True},
    )
    assert cat_resp.status_code == 200
    assert cat_resp.json()["name"] == "Draft Onboarding Category"
