import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.modules.staff.models import User, OutletMembership
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.db.base import utc_now
from app.core.security import hash_password
from app.modules.subscriptions.service import compute_annual_period_end
from app.api.deps import RequirePlatformRole, _assert_platform_owner_initialized
from app.api.v1.platform import IMPLEMENTED_PLATFORM_ROUTE_POLICIES, PLANNED_PLATFORM_ROUTE_POLICIES



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
    start_dt = utc_now()
    end_dt = compute_annual_period_end(start_dt)
    patch_resp = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={
            "action_type": "activate",
            "subscription_status": "active",
            "plan_name": "growth",
            "max_outlets": 3,
            "status": "active",
            "current_period_start": start_dt.isoformat(),
            "current_period_end": end_dt.isoformat(),
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


def test_bidirectional_route_policy_verification():
    # 1. Collect all platform routes registered on FastAPI app and detect duplicate registrations
    route_counts = {}
    app_platform_routes = {}
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            if route.path.startswith("/api/v1/platform"):
                for method in route.methods:
                    if method in ("GET", "POST", "PATCH", "DELETE", "PUT"):
                        key = (method, route.path)
                        route_counts[key] = route_counts.get(key, 0) + 1
                        app_platform_routes[key] = route

    # Detect duplicate route registrations
    for key, count in route_counts.items():
        assert count == 1, f"Route {key[0]} {key[1]} was registered {count} times (duplicate registration detected!)"

    # 2. Check no unregistered routes exist on the app (app -> registry)
    unregistered_routes = set(app_platform_routes.keys()) - set(IMPLEMENTED_PLATFORM_ROUTE_POLICIES.keys())
    assert not unregistered_routes, f"Detected unregistered platform routes on app: {unregistered_routes}"

    # 3. Check no stale entries in IMPLEMENTED_PLATFORM_ROUTE_POLICIES (registry -> app)
    stale_policies = set(IMPLEMENTED_PLATFORM_ROUTE_POLICIES.keys()) - set(app_platform_routes.keys())
    assert not stale_policies, f"Detected stale policy entries in registry: {stale_policies}"

    # 4. Check planned routes are not yet registered
    for planned_key in PLANNED_PLATFORM_ROUTE_POLICIES:
        assert planned_key not in app_platform_routes, f"Planned route {planned_key} was prematurely registered!"

    # Recursive helper to collect all callables from FastAPI's Dependant graph
    def collect_all_dependant_callables(dependant):
        callables = []
        if getattr(dependant, "call", None) is not None:
            callables.append(dependant.call)
        for child in getattr(dependant, "dependencies", []):
            callables.extend(collect_all_dependant_callables(child))
        return callables

    # 5. Verify effective dependency tree for every registered route
    for (method, path), policy in IMPLEMENTED_PLATFORM_ROUTE_POLICIES.items():
        route = app_platform_routes[(method, path)]

        # Traverse both explicit route.dependencies and compiled route.dependant graph
        all_callables = []
        for dep in getattr(route, "dependencies", []):
            if hasattr(dep, "dependency"):
                all_callables.append(dep.dependency)
        if hasattr(route, "dependant") and route.dependant:
            all_callables.extend(collect_all_dependant_callables(route.dependant))

        # Extract all RequirePlatformRole guards from effective dependency tree
        role_guards = [d for d in all_callables if isinstance(d, RequirePlatformRole)]
        assert len(role_guards) >= 1, (
            f"Route {method} {path} missing RequirePlatformRole guard in effective dependency graph"
        )
        for guard in role_guards:
            assert set(guard.allowed_roles) == policy["allowed_roles"], (
                f"Route {method} {path} expected allowed roles {policy['allowed_roles']}, got {set(guard.allowed_roles)}"
            )

        # Check _assert_platform_owner_initialized guard
        has_owner_initialized_guard = any(c == _assert_platform_owner_initialized for c in all_callables)
        if policy["router"] == "governance_router":
            assert has_owner_initialized_guard, (
                f"Governance route {method} {path} must depend on _assert_platform_owner_initialized"
            )
        else:
            assert not has_owner_initialized_guard, (
                f"Non-governance route {method} {path} must NOT depend on _assert_platform_owner_initialized"
            )



def test_assign_owner_role_boundary(client: TestClient, db_session: Session):
    # Retrieve business and outlet
    biz = db_session.query(Business).first()
    outlet = db_session.query(Outlet).filter(Outlet.business_id == biz.id).first()

    # Create operator user (platform_role="operator", is_platform_admin=False)
    operator = User(
        email="operator@test.com",
        password_hash=hash_password("password123"),
        display_name="Test Operator",
        status="active",
        is_platform_admin=False,
        platform_role="operator"
    )
    # Create admin user (platform_role="admin", is_platform_admin=True)
    admin_user = User(
        email="admin_boundary@test.com",
        password_hash=hash_password("password123"),
        display_name="Test Admin Boundary",
        status="active",
        is_platform_admin=True,
        platform_role="admin"
    )
    # Create owner user (platform_role="owner", is_platform_admin=True)
    owner_user = User(
        email="owner_boundary@test.com",
        password_hash=hash_password("password123"),
        display_name="Test Owner Boundary",
        status="active",
        is_platform_admin=True,
        platform_role="owner"
    )
    db_session.add_all([operator, admin_user, owner_user])
    db_session.commit()

    # 1. Platform Operator attempts assign-owner -> 403 Forbidden
    op_login = client.post("/api/v1/auth/login", json={"email": "operator@test.com", "password": "password123"})
    op_headers = {"Authorization": f"Bearer {op_login.json()['access_token']}"}
    op_resp = client.post(
        f"/api/v1/platform/businesses/{biz.id}/assign-owner",
        headers=op_headers,
        json={
            "outlet_id": str(outlet.id),
            "email": "assigned1@example.com",
            "password": "SecurePassword123!",
            "display_name": "Assigned 1"
        }
    )
    assert op_resp.status_code == 403

    # 2. Platform Admin attempts assign-owner -> 200 OK
    admin_login = client.post("/api/v1/auth/login", json={"email": "admin_boundary@test.com", "password": "password123"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    admin_resp = client.post(
        f"/api/v1/platform/businesses/{biz.id}/assign-owner",
        headers=admin_headers,
        json={
            "outlet_id": str(outlet.id),
            "email": "assigned2@example.com",
            "password": "SecurePassword123!",
            "display_name": "Assigned 2"
        }
    )
    assert admin_resp.status_code == 200
    assert admin_resp.json()["role"] == "owner"

    # 3. Platform Owner attempts assign-owner -> 200 OK
    owner_login = client.post("/api/v1/auth/login", json={"email": "owner_boundary@test.com", "password": "password123"})
    owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}
    owner_resp = client.post(
        f"/api/v1/platform/businesses/{biz.id}/assign-owner",
        headers=owner_headers,
        json={
            "outlet_id": str(outlet.id),
            "email": "assigned3@example.com",
            "password": "SecurePassword123!",
            "display_name": "Assigned 3"
        }
    )
    assert owner_resp.status_code == 200
    assert owner_resp.json()["role"] == "owner"


def test_zero_owner_commercial_continuity(client: TestClient, db_session: Session):
    # Ensure zero active platform owners exist
    for u in db_session.query(User).all():
        if u.platform_role == "owner":
            u.platform_role = "admin"
    db_session.commit()

    active_owner_count = db_session.query(User).filter(User.platform_role == "owner", User.status == "active").count()
    assert active_owner_count == 0

    # Ensure staff@test.com is an active admin
    admin = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin.is_platform_admin = True
    admin.platform_role = "admin"
    db_session.commit()

    login_resp = client.post("/api/v1/auth/login", json={"email": "staff@test.com", "password": "password123"})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # 1. Commercial operations MUST succeed (200 OK, not 503)
    assert client.get("/api/v1/platform/businesses", headers=headers).status_code == 200
    assert client.get("/api/v1/platform/admins", headers=headers).status_code == 200
    assert client.get("/api/v1/platform/plans", headers=headers).status_code == 200
    assert client.get("/api/v1/platform/audit-logs", headers=headers).status_code == 200

    # 2. Ordinary role-governance operation MUST fail closed with 503
    unauth_user = db_session.query(User).filter(User.email == "unauth@test.com").first()
    gov_resp = client.post(f"/api/v1/platform/admins/{unauth_user.id}/grant", headers=headers)
    assert gov_resp.status_code == 503
    assert gov_resp.json()["detail"]["error"]["code"] == "PLATFORM_OWNER_NOT_INITIALIZED"


def test_operator_denied_business_and_outlet_creation(client: TestClient, db_session: Session):
    biz = db_session.query(Business).first()

    # Create operator user (platform_role="operator", is_platform_admin=False)
    operator = User(
        email="operator_provision@test.com",
        password_hash=hash_password("password123"),
        display_name="Provisioning Operator",
        status="active",
        is_platform_admin=False,
        platform_role="operator"
    )
    # Create admin user (platform_role="admin", is_platform_admin=True)
    admin_user = User(
        email="admin_provision@test.com",
        password_hash=hash_password("password123"),
        display_name="Provisioning Admin",
        status="active",
        is_platform_admin=True,
        platform_role="admin"
    )
    db_session.add_all([operator, admin_user])
    db_session.commit()

    # Login as Operator
    op_login = client.post("/api/v1/auth/login", json={"email": "operator_provision@test.com", "password": "password123"})
    op_headers = {"Authorization": f"Bearer {op_login.json()['access_token']}"}

    # 1. Operator attempts to create a business -> 403 Forbidden
    op_biz_resp = client.post(
        "/api/v1/platform/businesses",
        headers=op_headers,
        json={
            "name": "Operator Biz Attempt",
            "primary_outlet_name": "Op Outlet",
            "public_slug": "op-biz-attempt",
            "currency": "INR",
            "timezone": "Asia/Kolkata",
            "address": "Op Address"
        }
    )
    assert op_biz_resp.status_code == 403
    assert "Platform administrator privileges are required" in op_biz_resp.json()["detail"]["error"]["message"]

    # 2. Operator attempts to create an outlet under existing business -> 403 Forbidden
    op_outlet_resp = client.post(
        f"/api/v1/platform/businesses/{biz.id}/outlets",
        headers=op_headers,
        json={
            "name": "Operator Outlet Attempt",
            "public_slug": "op-outlet-attempt",
            "currency": "INR",
            "timezone": "Asia/Kolkata",
            "address": "Op Outlet Address"
        }
    )
    assert op_outlet_resp.status_code == 403
    assert "Platform administrator privileges are required" in op_outlet_resp.json()["detail"]["error"]["message"]

    # 3. Admin user succeeds on both endpoints
    admin_login = client.post("/api/v1/auth/login", json={"email": "admin_provision@test.com", "password": "password123"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    admin_biz_resp = client.post(
        "/api/v1/platform/businesses",
        headers=admin_headers,
        json={
            "name": "Admin Authorized Biz",
            "primary_outlet_name": "Admin Primary Outlet",
            "public_slug": "admin-authorized-biz",
            "currency": "INR",
            "timezone": "Asia/Kolkata",
            "address": "Admin Address"
        }
    )
    assert admin_biz_resp.status_code == 200
    created_biz = admin_biz_resp.json()

    admin_outlet_resp = client.post(
        f"/api/v1/platform/businesses/{created_biz['id']}/outlets",
        headers=admin_headers,
        json={
            "name": "Admin Authorized Secondary Outlet",
            "public_slug": "admin-auth-sec-outlet",
            "currency": "INR",
            "timezone": "Asia/Kolkata",
            "address": "Admin Sec Address"
        }
    )
    assert admin_outlet_resp.status_code == 200


def test_assign_owner_resource_validation(client: TestClient, db_session: Session):
    # Setup two businesses with outlets
    biz1 = db_session.query(Business).first()
    outlet1 = db_session.query(Outlet).filter(Outlet.business_id == biz1.id).first()

    # Create second business
    biz2 = Business(name="Second Business", status="active")
    db_session.add(biz2)
    db_session.flush()
    outlet2 = Outlet(
        business_id=biz2.id,
        name="Second Outlet",
        public_slug="second-outlet-val",
        currency="INR",
        timezone="Asia/Kolkata",
        status="active"
    )
    db_session.add(outlet2)


    # Admin user
    admin_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin_user.is_platform_admin = True
    admin_user.platform_role = "admin"
    db_session.commit()

    admin_login = client.post("/api/v1/auth/login", json={"email": "staff@test.com", "password": "password123"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # 1. Cross-business mismatch: supply biz1 in URL, but outlet2 (from biz2) in payload -> 404
    cross_resp = client.post(
        f"/api/v1/platform/businesses/{biz1.id}/assign-owner",
        headers=admin_headers,
        json={
            "outlet_id": str(outlet2.id),
            "email": "cross@example.com",
            "password": "Password123!",
            "display_name": "Cross Owner"
        }
    )
    assert cross_resp.status_code == 404
    assert f"not found under business '{biz1.id}'" in cross_resp.json()["detail"]["error"]["message"]

    # 2. Non-existent business ID in URL -> 404
    fake_biz_id = uuid.uuid4()
    fake_biz_resp = client.post(
        f"/api/v1/platform/businesses/{fake_biz_id}/assign-owner",
        headers=admin_headers,
        json={
            "outlet_id": str(outlet1.id),
            "email": "fakebiz@example.com",
            "password": "Password123!",
            "display_name": "Fake Biz Owner"
        }
    )
    assert fake_biz_resp.status_code == 404
    assert f"Business with ID '{fake_biz_id}' not found" in fake_biz_resp.json()["detail"]["error"]["message"]

    # 3. Non-existent outlet ID in payload -> 404
    fake_outlet_id = uuid.uuid4()
    fake_outlet_resp = client.post(
        f"/api/v1/platform/businesses/{biz1.id}/assign-owner",
        headers=admin_headers,
        json={
            "outlet_id": str(fake_outlet_id),
            "email": "fakeout@example.com",
            "password": "Password123!",
            "display_name": "Fake Outlet Owner"
        }
    )
    assert fake_outlet_resp.status_code == 404
    assert f"not found under business '{biz1.id}'" in fake_outlet_resp.json()["detail"]["error"]["message"]

    # 4. Missing both user_id and email -> 422 Validation Error
    missing_user_resp = client.post(
        f"/api/v1/platform/businesses/{biz1.id}/assign-owner",
        headers=admin_headers,
        json={
            "outlet_id": str(outlet1.id),
        }
    )
    assert missing_user_resp.status_code == 422



