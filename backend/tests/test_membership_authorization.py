import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password, create_access_token
from app.modules.staff.models import User, OutletMembership, BusinessMembership
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet


def _create_user(db: Session, email: str, **user_kwargs) -> User:
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        display_name=email.split("@")[0],
        status="active",
        **user_kwargs,
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


def _create_outlet(db: Session, biz: Business, name: str, slug: str) -> Outlet:
    outlet = Outlet(business_id=biz.id, name=name, public_slug=slug, status="active")
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


# ---------------------------------------------------------------------------
# RequireBusinessOwner: canonical BusinessMembership + gated legacy fallback
# ---------------------------------------------------------------------------

def test_canonical_membership_resolves_owner_without_outlet_membership(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Canonical Biz")
    _create_outlet(db_session, biz, "Canonical Outlet", "canonical-outlet")
    user = _create_user(db_session, "canonical_owner@example.com")
    _grant_business_owner(db_session, user, biz)

    resp = client.get("/api/v1/business/subscription", headers=_auth(user))
    assert resp.status_code == 200
    assert resp.json()["business_id"] == str(biz.id)


def test_legacy_outlet_owner_fallback_engages_without_canonical_rows(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Legacy Biz")
    outlet = _create_outlet(db_session, biz, "Legacy Outlet", "legacy-outlet")
    user = _create_user(db_session, "legacy_owner@example.com")
    _grant_outlet_role(db_session, user, outlet, "owner")

    resp = client.get("/api/v1/business/subscription", headers=_auth(user))
    assert resp.status_code == 200
    assert resp.json()["business_id"] == str(biz.id)


def test_canonical_membership_gates_legacy_outlet_owner_from_foreign_business(
    client: TestClient, db_session: Session
):
    biz_a = _create_business(db_session, "Canonical Home Biz")
    _create_outlet(db_session, biz_a, "Home Outlet", "canonical-home-outlet")
    biz_b = _create_business(db_session, "Drift Foreign Biz")
    outlet_b = _create_outlet(db_session, biz_b, "Drift Outlet", "canonical-drift-outlet")

    user = _create_user(db_session, "drift_owner@example.com")
    _grant_business_owner(db_session, user, biz_a)
    _grant_outlet_role(db_session, user, outlet_b, "owner")

    resp_ok = client.get(
        f"/api/v1/business/subscription?business_id={biz_a.id}", headers=_auth(user)
    )
    assert resp_ok.status_code == 200

    resp_foreign = client.get(
        f"/api/v1/business/subscription?business_id={biz_b.id}", headers=_auth(user)
    )
    assert resp_foreign.status_code == 403
    assert "You are not authorized as an owner of the requested business" in resp_foreign.text


def test_no_membership_forbidden_on_owner_endpoint(client: TestClient, db_session: Session):
    _create_business(db_session, "No Membership Biz")
    user = _create_user(db_session, "no_membership@example.com")

    resp = client.get("/api/v1/business/subscription", headers=_auth(user))
    assert resp.status_code == 403
    assert "You are not authorized as an owner of this business" in resp.text


def test_platform_admin_without_tenant_membership_denied_owner_endpoint(
    client: TestClient, db_session: Session
):
    _create_business(db_session, "Platform Isolation Biz")
    admin_user = _create_user(
        db_session,
        "platform_admin_isolation@example.com",
        is_platform_admin=True,
        platform_role="admin",
    )

    resp = client.get("/api/v1/business/subscription", headers=_auth(admin_user))
    assert resp.status_code == 403
    assert "You are not authorized as an owner of this business" in resp.text


# ---------------------------------------------------------------------------
# RequireOutletRole: anti-probing (uniform 403), suspension, role isolation
# ---------------------------------------------------------------------------

def test_outlet_existence_not_probeable_by_tenant_user(client: TestClient, db_session: Session):
    home_biz = _create_business(db_session, "Probe Home Biz")
    home_outlet = _create_outlet(db_session, home_biz, "Probe Home Outlet", "probe-home-outlet")

    foreign_biz = _create_business(db_session, "Probe Foreign Biz")
    foreign_outlet = _create_outlet(db_session, foreign_biz, "Probe Foreign Outlet", "probe-foreign-outlet")

    suspended_biz = _create_business(db_session, "Probe Suspended Biz", status="suspended")
    suspended_outlet = _create_outlet(
        db_session, suspended_biz, "Probe Suspended Outlet", "probe-suspended-outlet"
    )

    user = _create_user(db_session, "probe_user@example.com")
    _grant_outlet_role(db_session, user, home_outlet, "manager")

    nonexistent_id = uuid.uuid4()
    r_nonexistent = client.get(
        f"/api/v1/outlets/{nonexistent_id}/admin/menu", headers=_auth(user)
    )
    r_foreign = client.get(
        f"/api/v1/outlets/{foreign_outlet.id}/admin/menu", headers=_auth(user)
    )
    r_suspended_foreign = client.get(
        f"/api/v1/outlets/{suspended_outlet.id}/admin/menu", headers=_auth(user)
    )
    r_own = client.get(
        f"/api/v1/outlets/{home_outlet.id}/admin/menu", headers=_auth(user)
    )

    assert r_nonexistent.status_code == 403
    assert r_foreign.status_code == 403
    assert r_suspended_foreign.status_code == 403
    assert r_own.status_code == 200

    uniform_message = "You do not have administrative access to this outlet"
    assert uniform_message in r_nonexistent.text
    assert uniform_message in r_foreign.text
    assert uniform_message in r_suspended_foreign.text
    assert "suspended" not in r_suspended_foreign.text
    assert r_nonexistent.text == r_foreign.text


def test_business_owner_accesses_outlet_without_outlet_membership(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Blanket Owner Biz")
    outlet = _create_outlet(db_session, biz, "Blanket Owner Outlet", "blanket-owner-outlet")
    user = _create_user(db_session, "blanket_owner@example.com")
    _grant_business_owner(db_session, user, biz)

    resp = client.get(f"/api/v1/outlets/{outlet.id}/tables", headers=_auth(user))
    assert resp.status_code == 200


def test_staff_role_denied_on_owner_manager_route(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Staff Isolation Biz")
    outlet = _create_outlet(db_session, biz, "Staff Isolation Outlet", "staff-isolation-outlet")
    waiter = _create_user(db_session, "waiter_isolation@example.com")
    _grant_outlet_role(db_session, waiter, outlet, "waiter")

    resp = client.post(
        f"/api/v1/outlets/{outlet.id}/tables",
        headers=_auth(waiter),
        json={"table_number": "T-ISO-1"},
    )
    assert resp.status_code == 403
    assert "Role 'waiter' is not authorized" in resp.text


def test_non_member_denied_on_outlet_route(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Non Member Biz")
    outlet = _create_outlet(db_session, biz, "Non Member Outlet", "non-member-outlet")
    outsider = _create_user(db_session, "outsider@example.com")

    resp = client.get(f"/api/v1/outlets/{outlet.id}/tables", headers=_auth(outsider))
    assert resp.status_code == 403
    assert "You do not have administrative access to this outlet" in resp.text


# ---------------------------------------------------------------------------
# Owner revocation invariant: BusinessMembership persists while user still
# legitimately owns another outlet of the business
# ---------------------------------------------------------------------------

def test_outlet_owner_revocation_preserves_business_membership(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Revocation Biz")
    out1 = _create_outlet(db_session, biz, "Revocation Outlet One", "revocation-outlet-one")
    out2 = _create_outlet(db_session, biz, "Revocation Outlet Two", "revocation-outlet-two")

    user = _create_user(db_session, "revocation_owner@example.com")
    _grant_outlet_role(db_session, user, out1, "owner")
    _grant_outlet_role(db_session, user, out2, "owner")
    _grant_business_owner(db_session, user, biz)

    outlet_one_membership = (
        db_session.query(OutletMembership)
        .filter(OutletMembership.user_id == user.id, OutletMembership.outlet_id == out1.id)
        .first()
    )
    db_session.delete(outlet_one_membership)
    db_session.commit()

    remaining_biz_memberships = (
        db_session.query(BusinessMembership)
        .filter(
            BusinessMembership.user_id == user.id,
            BusinessMembership.business_id == biz.id,
        )
        .all()
    )
    assert len(remaining_biz_memberships) == 1
    assert remaining_biz_memberships[0].role == "owner"

    resp_summary = client.get("/api/v1/business/subscription", headers=_auth(user))
    assert resp_summary.status_code == 200
    assert resp_summary.json()["business_id"] == str(biz.id)

    resp_out2 = client.get(f"/api/v1/outlets/{out2.id}/tables", headers=_auth(user))
    assert resp_out2.status_code == 200

    resp_out1 = client.get(f"/api/v1/outlets/{out1.id}/tables", headers=_auth(user))
    assert resp_out1.status_code == 200


# ---------------------------------------------------------------------------
# /me: business memberships exposed alongside outlet memberships
# ---------------------------------------------------------------------------

def test_me_exposes_business_memberships(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Me Biz")
    outlet = _create_outlet(db_session, biz, "Me Outlet", "me-outlet")
    user = _create_user(db_session, "me_membership_user@example.com")
    _grant_outlet_role(db_session, user, outlet, "manager")
    _grant_business_owner(db_session, user, biz)

    resp = client.get("/api/v1/me", headers=_auth(user))
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["memberships"]) == 1
    assert data["memberships"][0]["role"] == "manager"
    assert data["memberships"][0]["business_id"] == str(biz.id)

    assert len(data["business_memberships"]) == 1
    assert data["business_memberships"][0]["business_id"] == str(biz.id)
    assert data["business_memberships"][0]["business_name"] == "Me Biz"
    assert data["business_memberships"][0]["role"] == "owner"


def test_me_returns_empty_business_memberships_for_users_without_canonical_rows(
    client: TestClient, db_session: Session
):
    user = _create_user(db_session, "me_no_canonical@example.com")

    resp = client.get("/api/v1/me", headers=_auth(user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["memberships"] == []
    assert data["business_memberships"] == []


def test_me_filters_suspended_business_memberships(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Me Suspended Biz", status="suspended")
    outlet = _create_outlet(db_session, biz, "Me Suspended Outlet", "me-suspended-outlet")
    user = _create_user(db_session, "me_suspended_user@example.com")
    _grant_outlet_role(db_session, user, outlet, "owner")
    _grant_business_owner(db_session, user, biz)

    resp = client.get("/api/v1/me", headers=_auth(user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["memberships"] == []
    assert data["business_memberships"] == []


# ---------------------------------------------------------------------------
# P5: ownership & /me regression coverage
# ---------------------------------------------------------------------------

def test_me_business_memberships_deterministic_creation_order(client: TestClient, db_session: Session):
    from datetime import timedelta
    from app.db.base import utc_now

    biz_early = _create_business(db_session, "Ordering Biz Early")
    biz_later = _create_business(db_session, "Ordering Biz Later")
    # Guarantee distinct, ordered creation timestamps (avoid same-microsecond ties)
    biz_early.created_at = utc_now() - timedelta(hours=2)
    biz_later.created_at = utc_now() - timedelta(hours=1)
    db_session.commit()
    _create_outlet(db_session, biz_early, "Ordering Outlet Early", "ordering-early")
    _create_outlet(db_session, biz_later, "Ordering Outlet Later", "ordering-later")
    user = _create_user(db_session, "ordering_me_user@example.com")
    _grant_business_owner(db_session, user, biz_early)
    _grant_business_owner(db_session, user, biz_later)

    resp_1 = client.get("/api/v1/me", headers=_auth(user))
    resp_2 = client.get("/api/v1/me", headers=_auth(user))
    assert resp_1.status_code == 200 and resp_2.status_code == 200

    ids_1 = [m["business_id"] for m in resp_1.json()["business_memberships"]]
    ids_2 = [m["business_id"] for m in resp_2.json()["business_memberships"]]
    assert ids_1 == ids_2, "repeated /me calls must return identical ordering"
    assert ids_1 == [str(biz_early.id), str(biz_later.id)], "order follows business creation time"

    # Filtering keeps the deterministic order of the surviving entries
    biz_later.status = "suspended"
    db_session.commit()
    resp_3 = client.get("/api/v1/me", headers=_auth(user))
    ids_3 = [m["business_id"] for m in resp_3.json()["business_memberships"]]
    assert ids_3 == [str(biz_early.id)]


def test_me_legacy_outlet_owner_has_outlet_memberships_but_no_business_memberships(
    client: TestClient, db_session: Session
):
    biz = _create_business(db_session, "Legacy Me Biz")
    outlet = _create_outlet(db_session, biz, "Legacy Me Outlet", "legacy-me-outlet")
    user = _create_user(db_session, "legacy_me_user@example.com")
    _grant_outlet_role(db_session, user, outlet, "owner")

    resp = client.get("/api/v1/me", headers=_auth(user))
    assert resp.status_code == 200
    data = resp.json()
    assert [m["role"] for m in data["memberships"]] == ["owner"]
    assert data["business_memberships"] == []

    # Legacy fallback still grants business-level access while no canonical rows exist
    resp_owner = client.get("/api/v1/business/subscription", headers=_auth(user))
    assert resp_owner.status_code == 200


def test_canonical_owner_access_spans_all_owned_outlets(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Span Biz")
    outlet_a = _create_outlet(db_session, biz, "Span Outlet A", "span-a")
    outlet_b = _create_outlet(db_session, biz, "Span Outlet B", "span-b")
    from app.modules.tables.models import DiningTable
    table_b = DiningTable(outlet_id=outlet_b.id, table_number="T-SPAN", capacity=2)
    db_session.add(table_b)
    db_session.commit()

    owner = _create_user(db_session, "span_owner@example.com")
    _grant_business_owner(db_session, owner, biz)

    for outlet in (outlet_a, outlet_b):
        resp_menu = client.get(f"/api/v1/outlets/{outlet.id}/admin/menu", headers=_auth(owner))
        assert resp_menu.status_code == 200

    resp_table = client.patch(
        f"/api/v1/tables/{table_b.id}", headers=_auth(owner), json={"capacity": 4}
    )
    assert resp_table.status_code == 200


def test_revoking_outlet_membership_preserves_canonical_owner_grants(client: TestClient, db_session: Session):
    biz = _create_business(db_session, "Revocation Safety Biz")
    outlet_a = _create_outlet(db_session, biz, "Revocation Outlet A", "revocation-a")
    outlet_b = _create_outlet(db_session, biz, "Revocation Outlet B", "revocation-b")
    user = _create_user(db_session, "revocation_safety_user@example.com")
    _grant_business_owner(db_session, user, biz)
    mem_a = _grant_outlet_role(db_session, user, outlet_a, "owner")
    _grant_outlet_role(db_session, user, outlet_b, "owner")

    # Simulate revocation of outlet A's membership row
    db_session.delete(mem_a)
    db_session.commit()

    # Canonical grant is not cascaded away
    from app.modules.staff.models import BusinessMembership
    canonical = (
        db_session.query(BusinessMembership)
        .filter(BusinessMembership.user_id == user.id, BusinessMembership.business_id == biz.id)
        .first()
    )
    assert canonical is not None, "revoking an outlet membership must not revoke BusinessMembership"

    # /me still reports business ownership; business endpoint still authorized
    resp_me = client.get("/api/v1/me", headers=_auth(user))
    assert [m["business_id"] for m in resp_me.json()["business_memberships"]] == [str(biz.id)]
    resp_owner = client.get("/api/v1/business/subscription", headers=_auth(user))
    assert resp_owner.status_code == 200

    # Remaining outlet and canonical cross-outlet access intact
    resp_b = client.get(f"/api/v1/outlets/{outlet_b.id}/admin/menu", headers=_auth(user))
    assert resp_b.status_code == 200
    resp_a = client.get(f"/api/v1/outlets/{outlet_a.id}/admin/menu", headers=_auth(user))
    assert resp_a.status_code == 200, "canonical owner retains blanket outlet access after row revocation"
