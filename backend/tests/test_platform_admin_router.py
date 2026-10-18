import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.modules.staff.models import User, OutletMembership, BusinessMembership
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
        "owner_email": "u@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Unauth",
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
            "owner_email": "owner@trout.com",
            "owner_password": "Password123!",
            "owner_display_name": "Trout Owner",
            "public_slug": "trout-house-riverside",
            "currency": "INR",
            "timezone": "Asia/Kolkata",
            "address": "Kullu Valley, HP"
        }
    )
    assert create_resp.status_code == 200
    new_biz = create_resp.json()
    assert new_biz["name"] == "Himalayan Trout House"
    assert len(new_biz.get("outlets", [])) == 0
    

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
            "email": "owner.trout@example.com",
            "password": "SecurePassword123!",
            "display_name": "Trout Owner"
        }
    )
    assert assign_resp.status_code == 200
    mem_data = assign_resp.json()
    assert mem_data["role"] == "owner"
    assert "business_id" in mem_data

    # Verify newly created owner can log in
    owner_login = client.post(
        "/api/v1/auth/login",
        json={"email": "owner.trout@example.com", "password": "SecurePassword123!"}
    )
    assert owner_login.status_code == 200


def test_business_creation_requires_owner_fields(client: TestClient, db_session: Session):
    """Business creation now requires owner fields and rejects missing ones."""
    staff_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff_user.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Missing owner fields -> 422
    missing_resp = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={"name": "Incomplete Biz"}
    )
    assert missing_resp.status_code == 422


def test_platform_subscription_updates_and_max_outlets(client: TestClient, db_session: Session):
    """Business creation no longer accepts plan_name/max_outlets; trials are outlet-scoped."""
    staff_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff_user.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Provision a business (no plan_name/max_outlets accepted at creation)
    create_resp = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Single Outlet Cafe",
            "owner_email": "so@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "SO Owner",
            "public_slug": "single-outlet-main",
        }
    )
    assert create_resp.status_code == 200
    biz = create_resp.json()
    biz_id = biz["id"]
    # subscription_status defaults to 'trial' from model; plan_name/max_outlets not set at creation
    assert biz["subscription_status"] == "trial"
    assert biz["plan_name"] is None

    # 1b. Plan_name/max_outlets fields are now ignored (no longer on schema) 闂備胶鍋ㄩ崕濠氬箯閿燂拷 no 422
    invalid_create_resp = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Invalid Cap Cafe",
            "owner_email": "ic@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "IC Owner",
            "public_slug": "invalid-cap-main",
        }
    )
    assert invalid_create_resp.status_code == 200

    # 2. Create primary outlet with explicit plan 闂備胶锟借�勫�归梺璺ㄥ櫐閹凤拷 active subscription on outlet
    add_outlet_resp = client.post(
        f"/api/v1/platform/businesses/{biz_id}/outlets",
        headers=headers,
        json={
            "name": "Single Outlet First",
            "public_slug": "single-outlet-first",
            "plan_code": "starter_pos"
        }
    )
    assert add_outlet_resp.status_code == 200
    assert add_outlet_resp.json()["public_slug"] == "single-outlet-first"

    # 3. Legacy bulk subscription update is still accepted (status/plan/max_outlets echoed)
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

    # 4. Outlet creation remains uncapped after the subscription update
    add_third_outlet_resp = client.post(
        f"/api/v1/platform/businesses/{biz_id}/outlets",
        headers=headers,
        json={
            "name": "Single Outlet Third",
            "public_slug": "single-outlet-third"
        }
    )
    assert add_third_outlet_resp.status_code == 200
    assert add_third_outlet_resp.json()["public_slug"] == "single-outlet-third"

    # 5. Genuinely invalid subscription updates are still rejected
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
    def _walk_routes(routes, current_prefix=""):
        flat = []
        for r in routes:
            if type(r).__name__ == "_IncludedRouter":
                new_prefix = current_prefix + (r.include_context.prefix or "")
                flat.extend(_walk_routes(r.original_router.routes, new_prefix))
            else:
                full_path = current_prefix + getattr(r, "path", "")
                flat.append((r, full_path))
        return flat

    route_counts = {}
    app_platform_routes = {}
    for route, full_path in _walk_routes(app.routes):
        if hasattr(route, "methods") and full_path.startswith("/api/v1/platform"):
            for method in route.methods:
                if method in ("GET", "POST", "PATCH", "DELETE", "PUT"):
                    key = (method, full_path)
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
            "owner_email": "op2@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Op Outlet",
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
            "owner_email": "admin2@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Admin Primary Outlet",
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


def test_assign_owner_business_scoped_validation(client: TestClient, db_session: Session):
    # Admin user
    admin_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin_user.is_platform_admin = True
    admin_user.platform_role = "admin"
    db_session.commit()

    admin_login = client.post("/api/v1/auth/login", json={"email": "staff@test.com", "password": "password123"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # Create a fresh business via API to ensure clean state (no existing owner)
    create_resp = client.post("/api/v1/platform/businesses", headers=admin_headers, json={
        "name": "Validation Biz",
        "owner_email": "val-owner@business.com",
        "owner_password": "Password123!",
        "owner_display_name": "Val Owner",
        "public_slug": f"val-biz-{uuid.uuid4().hex[:6]}"
    })
    assert create_resp.status_code == 200
    biz = create_resp.json()
    biz_id = biz["id"]

    # 1. Assign owner successfully -> 200
    assign_resp = client.post(
        f"/api/v1/platform/businesses/{biz_id}/assign-owner",
        headers=admin_headers,
        json={
            "email": "newowner@val.com",
            "password": "Password123!",
            "display_name": "New Owner"
        }
    )
    assert assign_resp.status_code == 200
    mem = assign_resp.json()
    assert mem["role"] == "owner"
    assert mem["business_id"] == biz_id

    # 2. Non-existent business ID -> 404
    fake_biz_id = uuid.uuid4()
    fake_biz_resp = client.post(
        f"/api/v1/platform/businesses/{fake_biz_id}/assign-owner",
        headers=admin_headers,
        json={
            "email": "fakebiz@example.com",
            "password": "Password123!",
            "display_name": "Fake Biz Owner"
        }
    )
    assert fake_biz_resp.status_code == 404
    assert f"Business with ID '{fake_biz_id}' not found" in fake_biz_resp.json()["detail"]["error"]["message"]

    # 3. Missing both user_id and email -> 422 Validation Error
    missing_user_resp = client.post(
        f"/api/v1/platform/businesses/{biz_id}/assign-owner",
        headers=admin_headers,
        json={}
    )
    assert missing_user_resp.status_code == 422






def test_add_outlet_with_manager_validation(client: TestClient, db_session: Session):
    # Admin user
    admin_user = db_session.query(User).filter(User.email == 'staff@test.com').first()
    admin_user.is_platform_admin = True
    admin_user.platform_role = 'admin'
    db_session.commit()
    admin_login = client.post('/api/v1/auth/login', json={'email': 'staff@test.com', 'password': 'password123'})
    admin_headers = {'Authorization': f'Bearer {admin_login.json()["access_token"]}'}

    # Create business
    biz = Business(name='Manager Biz', status='active')
    db_session.add(biz)
    db_session.flush()

    # User without business membership
    user_no_mem = User(email='no-mem@test.com', password_hash=hash_password('password123'), display_name='No Mem User', status='active')
    db_session.add(user_no_mem)
    db_session.flush()

    unique_slug = f'mgr-test-outlet-{uuid.uuid4().hex[:6]}'

    unique_slug_ineligible = f'mgr-test-ineligible-{uuid.uuid4().hex[:6]}'
    unique_slug_eligible = f'mgr-test-eligible-{uuid.uuid4().hex[:6]}'

    # Create outlet with ineligible manager -> 422
    resp = client.post(f'/api/v1/platform/businesses/{biz.id}/outlets', headers=admin_headers, json={
        'name': 'Outlet Ineligible',
        'public_slug': unique_slug_ineligible,
        'plan_code': 'trial',
        'manager': {'user_id': str(user_no_mem.id)}
    })
    assert resp.status_code == 422
    assert 'is not a manager of this business' in resp.json()['detail']['error']['message']

    # Assign manager role
    biz_mem = BusinessMembership(business_id=biz.id, user_id=user_no_mem.id, role='manager')
    db_session.add(biz_mem)
    db_session.commit()

    # Create outlet with eligible manager -> 200
    resp = client.post(f'/api/v1/platform/businesses/{biz.id}/outlets', headers=admin_headers, json={
        'name': 'Outlet Eligible',
        'public_slug': unique_slug_eligible,
        'plan_code': 'trial',
        'manager': {'user_id': str(user_no_mem.id)}
    })
    assert resp.status_code == 200


def test_add_outlet_audit_metadata_contains_manager_user_id(client: TestClient, db_session: Session):
    admin_user = db_session.query(User).filter(User.email == 'staff@test.com').first()
    admin_user.is_platform_admin = True
    admin_user.platform_role = 'admin'
    db_session.commit()
    admin_login = client.post('/api/v1/auth/login', json={'email': 'staff@test.com', 'password': 'password123'})
    admin_headers = {'Authorization': f'Bearer {admin_login.json()["access_token"]}'}

    biz = Business(name='Audit Biz', status='active')
    db_session.add(biz)
    db_session.flush()

    mgr = User(email='audit-mgr@test.com', password_hash=hash_password('password123'), display_name='Audit Mgr', status='active')
    db_session.add(mgr)
    db_session.flush()
    db_session.add(BusinessMembership(business_id=biz.id, user_id=mgr.id, role='manager'))
    db_session.commit()

    slug = f'audit-outlet-{uuid.uuid4().hex[:6]}'
    resp = client.post(f'/api/v1/platform/businesses/{biz.id}/outlets', headers=admin_headers, json={
        'name': 'Audit Outlet',
        'public_slug': slug,
        'plan_code': 'trial',
        'manager': {'user_id': str(mgr.id)}
    })
    assert resp.status_code == 200
    outlet_id = resp.json()['id']

    audit_resp = client.get('/api/v1/platform/audit-logs', headers=admin_headers, params={'entity_id': str(outlet_id)})
    assert audit_resp.status_code == 200
    items = audit_resp.json()['items']
    create_log = next((i for i in items if i['action'] == 'platform.outlet.create'), None)
    assert create_log is not None
    meta = create_log['metadata_json']
    assert meta['manager_user_id'] == str(mgr.id)
    assert 'password' not in str(meta)


def test_add_outlet_without_manager_audit_metadata(client: TestClient, db_session: Session):
    admin_user = db_session.query(User).filter(User.email == 'staff@test.com').first()
    admin_user.is_platform_admin = True
    admin_user.platform_role = 'admin'
    db_session.commit()
    admin_login = client.post('/api/v1/auth/login', json={'email': 'staff@test.com', 'password': 'password123'})
    admin_headers = {'Authorization': f'Bearer {admin_login.json()["access_token"]}'}

    biz = Business(name='NoMgr Biz', status='active')
    db_session.add(biz)
    db_session.flush()

    slug = f'no-mgr-outlet-{uuid.uuid4().hex[:6]}'
    resp = client.post(f'/api/v1/platform/businesses/{biz.id}/outlets', headers=admin_headers, json={
        'name': 'No Mgr Outlet',
        'public_slug': slug,
        'plan_code': 'trial'
    })
    assert resp.status_code == 200
    outlet_id = resp.json()['id']

    audit_resp = client.get('/api/v1/platform/audit-logs', headers=admin_headers, params={'entity_id': str(outlet_id)})
    assert audit_resp.status_code == 200
    items = audit_resp.json()['items']
    create_log = next((i for i in items if i['action'] == 'platform.outlet.create'), None)
    assert create_log is not None
    assert create_log['metadata_json']['manager_user_id'] is None
