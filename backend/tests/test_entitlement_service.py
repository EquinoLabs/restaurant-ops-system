import uuid
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, utc_now
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.subscriptions.models import (
    Plan, Feature, PlanFeature, BusinessSubscription, EntitlementOverride
)
from app.modules.subscriptions.service import EntitlementService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    # Seed canonical plans and features
    p_free = Plan(id=uuid.uuid4(), code="free_qr", name="Free QR Menu", sort_order=1)
    p_starter = Plan(id=uuid.uuid4(), code="starter_pos", name="Starter POS", sort_order=2)
    p_growth = Plan(id=uuid.uuid4(), code="growth_pos", name="Growth POS", sort_order=3)
    p_pro = Plan(id=uuid.uuid4(), code="pro_kds", name="Pro KDS", sort_order=4)
    p_ent = Plan(id=uuid.uuid4(), code="enterprise", name="Enterprise", sort_order=5)

    session.add_all([p_free, p_starter, p_growth, p_pro, p_ent])

    f_menu = Feature(id=uuid.uuid4(), code="menu.digital", name="Digital Menu", category="menu")
    f_staff = Feature(id=uuid.uuid4(), code="ordering.staff", name="Staff Ordering", category="ordering")
    f_cust = Feature(id=uuid.uuid4(), code="ordering.customer", name="Customer Ordering", category="ordering")
    f_kds = Feature(id=uuid.uuid4(), code="kds.enabled", name="KDS", category="kitchen")
    f_outlets = Feature(id=uuid.uuid4(), code="outlets.max_count", name="Max Outlets", category="billing")

    session.add_all([f_menu, f_staff, f_cust, f_kds, f_outlets])
    session.commit()

    # Map features to starter_pos
    pf_starter_menu = PlanFeature(id=uuid.uuid4(), plan_id=p_starter.id, feature_id=f_menu.id, limit_value=None)
    pf_starter_staff = PlanFeature(id=uuid.uuid4(), plan_id=p_starter.id, feature_id=f_staff.id, limit_value=None)
    pf_starter_outlets = PlanFeature(id=uuid.uuid4(), plan_id=p_starter.id, feature_id=f_outlets.id, limit_value=1)

    # Map features to growth_pos
    pf_growth_menu = PlanFeature(id=uuid.uuid4(), plan_id=p_growth.id, feature_id=f_menu.id, limit_value=None)
    pf_growth_staff = PlanFeature(id=uuid.uuid4(), plan_id=p_growth.id, feature_id=f_staff.id, limit_value=None)
    pf_growth_cust = PlanFeature(id=uuid.uuid4(), plan_id=p_growth.id, feature_id=f_cust.id, limit_value=None)
    pf_growth_outlets = PlanFeature(id=uuid.uuid4(), plan_id=p_growth.id, feature_id=f_outlets.id, limit_value=3)

    session.add_all([
        pf_starter_menu, pf_starter_staff, pf_starter_outlets,
        pf_growth_menu, pf_growth_staff, pf_growth_cust, pf_growth_outlets
    ])
    session.commit()

    yield session
    session.close()


def test_zero_day_expiry_exact_boundary(db_session):
    now = utc_now()
    b = Business(id=uuid.uuid4(), name="Boundary Test Business", status="active")
    db_session.add(b)
    db_session.commit()

    plan_starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))

    # Active subscription with end time in future
    sub = BusinessSubscription(
        id=uuid.uuid4(),
        business_id=b.id,
        plan_id=plan_starter.id,
        status="active",
        is_current=True,
        current_period_start=now - timedelta(days=30),
        current_period_end=now + timedelta(seconds=10)
    )
    db_session.add(sub)
    db_session.commit()

    # Before period end -> ALLOWED
    res1 = EntitlementService.check_entitlement(db_session, b.id, "ordering.staff", now=now)
    assert res1.authorized is True
    assert res1.resolved_status == "active"

    # Exactly at period end -> EXPIRED under 0-day grace policy
    res2 = EntitlementService.check_entitlement(
        db_session, b.id, "ordering.staff", now=sub.current_period_end
    )
    assert res2.authorized is False
    assert res2.reason == "SUBSCRIPTION_EXPIRED"
    assert res2.resolved_status == "expired"


def test_scheduled_cancellation_preserves_access_until_period_end(db_session):
    now = utc_now()
    b = Business(id=uuid.uuid4(), name="Scheduled Cancel Business", status="active")
    db_session.add(b)
    db_session.commit()

    plan_starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))

    sub = BusinessSubscription(
        id=uuid.uuid4(),
        business_id=b.id,
        plan_id=plan_starter.id,
        status="active",
        is_current=True,
        current_period_start=now - timedelta(days=15),
        current_period_end=now + timedelta(days=15),
        cancel_at_period_end=True,
        cancelled_at=now - timedelta(days=1)
    )
    db_session.add(sub)
    db_session.commit()

    # Access preserved before period end
    res1 = EntitlementService.check_entitlement(db_session, b.id, "ordering.staff", now=now)
    assert res1.authorized is True

    # Access revoked at period end
    res2 = EntitlementService.check_entitlement(
        db_session, b.id, "ordering.staff", now=now + timedelta(days=16)
    )
    assert res2.authorized is False
    assert res2.reason == "SUBSCRIPTION_EXPIRED"


def test_immediate_cancellation_revokes_access_immediately(db_session):
    now = utc_now()
    b = Business(id=uuid.uuid4(), name="Immediate Cancel Business", status="active")
    db_session.add(b)
    db_session.commit()

    plan_starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))

    sub = BusinessSubscription(
        id=uuid.uuid4(),
        business_id=b.id,
        plan_id=plan_starter.id,
        status="cancelled",
        is_current=True,
        cancel_at_period_end=False,
        cancelled_at=now - timedelta(hours=1)
    )
    db_session.add(sub)
    db_session.commit()

    res = EntitlementService.check_entitlement(db_session, b.id, "ordering.staff", now=now)
    assert res.authorized is False
    assert res.reason == "SUBSCRIPTION_CANCELLED"

    # menu.digital exception for active business
    res_menu = EntitlementService.check_entitlement(db_session, b.id, "menu.digital", now=now)
    assert res_menu.authorized is True
    assert res_menu.reason == "READ_ONLY_MENU_ALLOWED"


def test_suspended_business_blocks_all_features(db_session):
    now = utc_now()
    b = Business(id=uuid.uuid4(), name="Suspended Business", status="suspended")
    db_session.add(b)
    db_session.commit()

    plan_starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))

    sub = BusinessSubscription(
        id=uuid.uuid4(),
        business_id=b.id,
        plan_id=plan_starter.id,
        status="active",
        is_current=True,
        current_period_end=now + timedelta(days=30)
    )
    db_session.add(sub)
    db_session.commit()

    # Suspended business blocks menu.digital as well
    res_menu = EntitlementService.check_entitlement(db_session, b.id, "menu.digital", now=now)
    assert res_menu.authorized is False
    assert res_menu.reason == "BUSINESS_SUSPENDED"


def test_authoritative_plan_cap_overrides_stale_legacy_scalar(db_session):
    now = utc_now()
    # Business has stale legacy max_outlets = 3, but starter_pos plan cap = 1
    b = Business(id=uuid.uuid4(), name="Legacy Scalar Business", status="active", max_outlets=3)
    db_session.add(b)
    db_session.commit()

    plan_starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))

    sub = BusinessSubscription(
        id=uuid.uuid4(),
        business_id=b.id,
        plan_id=plan_starter.id,
        status="active",
        is_current=True,
        current_period_end=now + timedelta(days=30)
    )
    db_session.add(sub)
    db_session.commit()

    # Legacy max_outlets=3 cannot inflate plan cap of 1 -> resolves to cap = 1
    res = EntitlementService.check_entitlement(db_session, b.id, "outlets.max_count", now=now)
    assert res.authorized is True
    assert res.limit_value == 1


def test_explicit_numeric_grant_override_exceeds_plan_cap(db_session):
    now = utc_now()
    b = Business(id=uuid.uuid4(), name="Grant Override Business", status="active")
    db_session.add(b)
    db_session.commit()

    plan_starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))

    sub = BusinessSubscription(
        id=uuid.uuid4(),
        business_id=b.id,
        plan_id=plan_starter.id,
        status="active",
        is_current=True,
        current_period_end=now + timedelta(days=30)
    )
    db_session.add(sub)
    db_session.commit()

    # Administrative grant override for limit_value = 5 on starter_pos (plan cap = 1)
    override = EntitlementOverride(
        id=uuid.uuid4(),
        business_id=b.id,
        feature_code="outlets.max_count",
        override_type="grant",
        limit_value=5,
        reason="Approved VIP exception"
    )
    db_session.add(override)
    db_session.commit()

    # Grant override intentionally exceeds plan cap
    res = EntitlementService.check_entitlement(db_session, b.id, "outlets.max_count", now=now)
    assert res.authorized is True
    assert res.limit_value == 5


def test_decision_001_option_a_scope_precedence(db_session):
    now = utc_now()
    b = Business(id=uuid.uuid4(), name="Scope Precedence Business", status="active")
    o1 = Outlet(id=uuid.uuid4(), business_id=b.id, name="Outlet 1", public_slug="outlet-1")
    db_session.add_all([b, o1])
    db_session.commit()

    plan_starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))

    sub = BusinessSubscription(
        id=uuid.uuid4(),
        business_id=b.id,
        plan_id=plan_starter.id,
        status="active",
        is_current=True,
        current_period_end=now + timedelta(days=30)
    )
    db_session.add(sub)
    db_session.commit()

    # Business-wide grant for limit_value = 10
    g_biz = EntitlementOverride(
        id=uuid.uuid4(),
        business_id=b.id,
        outlet_id=None,
        feature_code="outlets.max_count",
        override_type="grant",
        limit_value=10,
        reason="Business grant"
    )
    # Outlet-scoped grant for limit_value = 4
    g_outlet = EntitlementOverride(
        id=uuid.uuid4(),
        business_id=b.id,
        outlet_id=o1.id,
        feature_code="outlets.max_count",
        override_type="grant",
        limit_value=4,
        reason="Outlet grant"
    )
    db_session.add_all([g_biz, g_outlet])
    db_session.commit()

    # Decision 001 Option A: When evaluating for outlet o1, outlet-scoped grant replaces business-scoped grant -> limit = 4
    res_outlet = EntitlementService.check_entitlement(
        db_session, b.id, "outlets.max_count", outlet_id=o1.id, now=now
    )
    assert res_outlet.authorized is True
    assert res_outlet.limit_value == 4

    # When evaluating without target outlet, business-scoped grant applies -> limit = 10
    res_biz = EntitlementService.check_entitlement(
        db_session, b.id, "outlets.max_count", outlet_id=None, now=now
    )
    assert res_biz.authorized is True
    assert res_biz.limit_value == 10


def test_restriction_override_defeats_grant_override(db_session):
    now = utc_now()
    b = Business(id=uuid.uuid4(), name="Restriction Test Business", status="active")
    db_session.add(b)
    db_session.commit()

    plan_growth = db_session.scalar(select(Plan).where(Plan.code == "growth_pos"))

    sub = BusinessSubscription(
        id=uuid.uuid4(),
        business_id=b.id,
        plan_id=plan_growth.id,
        status="active",
        is_current=True,
        current_period_end=now + timedelta(days=30)
    )
    db_session.add(sub)
    db_session.commit()

    # Grant override
    g = EntitlementOverride(
        id=uuid.uuid4(),
        business_id=b.id,
        feature_code="ordering.customer",
        override_type="grant",
        limit_value=None,
        reason="Grant customer ordering"
    )
    # Active Restriction override
    r = EntitlementOverride(
        id=uuid.uuid4(),
        business_id=b.id,
        feature_code="ordering.customer",
        override_type="restrict",
        limit_value=None,
        reason="Admin restriction"
    )
    db_session.add_all([g, r])
    db_session.commit()

    # Restriction override takes precedence and denies feature
    res = EntitlementService.check_entitlement(db_session, b.id, "ordering.customer", now=now)
    assert res.authorized is False
    assert res.reason == "RESTRICTION_OVERRIDE_ACTIVE"


def test_inactive_plan_fails_closed(db_session):
    now = utc_now()
    b = Business(id=uuid.uuid4(), name="Inactive Plan Business", status="active")
    db_session.add(b)
    db_session.commit()

    # Create an inactive plan in catalog
    p_inactive = Plan(id=uuid.uuid4(), code="legacy_deactivated", name="Legacy Deactivated", is_active=False, sort_order=99)
    db_session.add(p_inactive)
    db_session.commit()

    f_staff = db_session.scalar(select(Feature).where(Feature.code == "ordering.staff"))
    pf_inactive_staff = PlanFeature(id=uuid.uuid4(), plan_id=p_inactive.id, feature_id=f_staff.id, limit_value=None)
    db_session.add(pf_inactive_staff)
    db_session.commit()

    sub = BusinessSubscription(
        id=uuid.uuid4(),
        business_id=b.id,
        plan_id=p_inactive.id,
        status="active",
        is_current=True,
        current_period_end=now + timedelta(days=30)
    )
    db_session.add(sub)
    db_session.commit()

    # Inactive plan does NOT authorize operational feature
    res = EntitlementService.check_entitlement(db_session, b.id, "ordering.staff", now=now)
    assert res.authorized is False
    assert res.reason == "FEATURE_NOT_INCLUDED_IN_PLAN"


def test_unknown_feature_code_fails_closed(db_session):
    now = utc_now()
    b = Business(id=uuid.uuid4(), name="Unknown Feature Business", status="active")
    db_session.add(b)
    db_session.commit()

    plan_starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))
    sub = BusinessSubscription(
        id=uuid.uuid4(),
        business_id=b.id,
        plan_id=plan_starter.id,
        status="active",
        is_current=True,
        current_period_end=now + timedelta(days=30)
    )
    db_session.add(sub)
    db_session.commit()

    # Unknown feature code returns authorized = False without raising exception
    res = EntitlementService.check_entitlement(db_session, b.id, "invalid.unknown_feature_xyz", now=now)
    assert res.authorized is False
    assert res.reason == "FEATURE_NOT_INCLUDED_IN_PLAN"

