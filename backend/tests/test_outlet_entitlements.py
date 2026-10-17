import uuid
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, utc_now
from app.core.errors import ValidationError, ForbiddenError
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.businesses.schemas import PlatformOutletCreate
from app.modules.businesses import platform_service
from app.modules.subscriptions.models import (
    Plan, Feature, PlanFeature, BusinessSubscription, EntitlementOverride
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    # Seed core plans and features
    p_free = Plan(id=uuid.uuid4(), code="free_qr", name="Free QR Menu", sort_order=1)
    p_starter = Plan(id=uuid.uuid4(), code="starter_pos", name="Starter POS", sort_order=2)
    p_growth = Plan(id=uuid.uuid4(), code="growth_pos", name="Growth POS", sort_order=3)
    p_pro = Plan(id=uuid.uuid4(), code="pro_kds", name="Pro KDS", sort_order=4)
    p_ent = Plan(id=uuid.uuid4(), code="enterprise", name="Enterprise", sort_order=5)

    session.add_all([p_free, p_starter, p_growth, p_pro, p_ent])

    f_menu = Feature(id=uuid.uuid4(), code="menu.digital", name="Digital Menu", category="menu")
    f_outlets = Feature(id=uuid.uuid4(), code="outlets.max_count", name="Max Outlets", category="billing")
    session.add_all([f_menu, f_outlets])
    session.commit()

    # free_qr: menu.digital (null), outlets.max_count (1)
    pf_free_menu = PlanFeature(id=uuid.uuid4(), plan_id=p_free.id, feature_id=f_menu.id, limit_value=None)
    pf_free_outlets = PlanFeature(id=uuid.uuid4(), plan_id=p_free.id, feature_id=f_outlets.id, limit_value=1)

    # starter_pos: menu.digital (null), outlets.max_count (1)
    pf_starter_menu = PlanFeature(id=uuid.uuid4(), plan_id=p_starter.id, feature_id=f_menu.id, limit_value=None)
    pf_starter_outlets = PlanFeature(id=uuid.uuid4(), plan_id=p_starter.id, feature_id=f_outlets.id, limit_value=1)

    # growth_pos: menu.digital (null), outlets.max_count (3)
    pf_growth_menu = PlanFeature(id=uuid.uuid4(), plan_id=p_growth.id, feature_id=f_menu.id, limit_value=None)
    pf_growth_outlets = PlanFeature(id=uuid.uuid4(), plan_id=p_growth.id, feature_id=f_outlets.id, limit_value=3)

    # enterprise: menu.digital (null), outlets.max_count (None = unlimited)
    pf_ent_menu = PlanFeature(id=uuid.uuid4(), plan_id=p_ent.id, feature_id=f_menu.id, limit_value=None)
    pf_ent_outlets = PlanFeature(id=uuid.uuid4(), plan_id=p_ent.id, feature_id=f_outlets.id, limit_value=None)

    session.add_all([
        pf_free_menu, pf_free_outlets,
        pf_starter_menu, pf_starter_outlets,
        pf_growth_menu, pf_growth_outlets,
        pf_ent_menu, pf_ent_outlets,
    ])
    session.commit()

    yield session
    session.close()


def test_entitled_business_creates_outlet_within_limit(db_session):
    # Business on growth_pos (limit = 3) created with 1 primary outlet
    data = platform_service.PlatformBusinessCreate(
        name="Growth Biz",
        owner_email="owner@growth.com",
        owner_password="Password123!",
        owner_display_name="Growth Owner"
    )
    biz = platform_service.create_platform_business(db_session, data=data)

    # Add primary outlet (since it wasn't auto-created)
    primary_data = PlatformOutletCreate(name="Outlet 1", public_slug="growth-outlet-1", plan_code="growth_pos")
    platform_service.add_outlet_to_business(db_session, business_id=biz.id, data=primary_data)

    # Add 2nd outlet
    out2_data = PlatformOutletCreate(name="Outlet 2", public_slug="growth-outlet-2")
    out2 = platform_service.add_outlet_to_business(db_session, business_id=biz.id, data=out2_data)
    assert out2.name == "Outlet 2"

    # Add 3rd outlet
    out3_data = PlatformOutletCreate(name="Outlet 3", public_slug="growth-outlet-3")
    out3 = platform_service.add_outlet_to_business(db_session, business_id=biz.id, data=out3_data)
    assert out3.name == "Outlet 3"


def test_business_at_outlet_limit_blocked_from_creating_outlet(db_session):
    """
    Phase 1: max_outlets cap removed from add_outlet_to_business.
    A starter_pos business (plan limit = 1) can now create additional outlets freely —
    subscription enforcement is outlet-scoped, not a creation-time hard cap.
    """
    data = platform_service.PlatformBusinessCreate(
        name="Starter Biz",
        owner_email="owner@starter.com",
        owner_password="Password123!",
        owner_display_name="Starter Owner",
    )
    biz = platform_service.create_platform_business(db_session, data=data)

    # Phase 1: No cap — 2nd outlet creation must succeed
    out2_data = PlatformOutletCreate(name="Outlet 2", public_slug="starter-outlet-2")
    out2 = platform_service.add_outlet_to_business(db_session, business_id=biz.id, data=out2_data)
    assert out2.name == "Outlet 2", "Outlet creation must succeed regardless of plan outlet limit (cap removed)"

    # And a 3rd outlet
    out3_data = PlatformOutletCreate(name="Outlet 3", public_slug="starter-outlet-3")
    out3 = platform_service.add_outlet_to_business(db_session, business_id=biz.id, data=out3_data)
    assert out3.name == "Outlet 3", "Uncapped: any number of outlets can be created"


def test_free_qr_operates_primary_outlet_but_cannot_create_second(db_session):
    """
    Phase 1: max_outlets cap removed. Even free_qr businesses can create additional outlets.
    Entitlement for each outlet is governed by its own OutletSubscription, not a creation gate.
    """
    data = platform_service.PlatformBusinessCreate(
        name="Free QR Biz",
        owner_email="owner@free-qr.com",
        owner_password="Password123!",
        owner_display_name="Free QR Owner"
    )
    biz = platform_service.create_platform_business(db_session, data=data)

    # Phase 1: 2nd outlet creation now succeeds (no cap)
    out2_data = PlatformOutletCreate(name="Second Outlet", public_slug="free-qr-outlet-2")
    out2 = platform_service.add_outlet_to_business(db_session, business_id=biz.id, data=out2_data)
    assert out2.name == "Second Outlet", "Uncapped: free_qr business can create a second outlet"


def test_grant_and_restriction_overrides_modify_outlet_creation(db_session):
    """
    Phase 1: Outlet creation is uncapped. Entitlement overrides (grant/restrict) now affect
    entitlement resolution via EntitlementService, not outlet creation in platform_service.
    This test verifies: (a) outlet creation is uncapped, (b) restriction override is still
    enforced by EntitlementService for the outlets.max_count feature check.
    """
    from app.modules.subscriptions.service import EntitlementService

    data = platform_service.PlatformBusinessCreate(
        name="Override Biz",
        owner_email="owner@override.com",
        owner_password="Password123!",
        owner_display_name="Override Owner"
    )
    biz = platform_service.create_platform_business(db_session, data=data)

    # Phase 1: 2nd outlet creation succeeds without any grant override (no cap)
    out2_data = PlatformOutletCreate(name="Outlet 2", public_slug="override-outlet-2")
    out2 = platform_service.add_outlet_to_business(db_session, business_id=biz.id, data=out2_data)
    assert out2.name == "Outlet 2", "Uncapped: 2nd outlet creation must succeed without any grant"

    # Grant override still reflected in EntitlementService
    grant = EntitlementOverride(
        id=uuid.uuid4(),
        business_id=biz.id,
        feature_code="outlets.max_count",
        override_type="grant",
        limit_value=5,
        reason="Admin VIP Grant"
    )
    db_session.add(grant)
    db_session.commit()

    grant_result = EntitlementService.check_entitlement(
        db_session, biz.id, "outlets.max_count"
    )
    assert grant_result.authorized, "Grant override must be authorized via EntitlementService"
    assert grant_result.limit_value == 5, "Grant override must set limit_value=5"

    # Restriction override blocks entitlement for outlets.max_count (but does NOT block creation)
    restrict = EntitlementOverride(
        id=uuid.uuid4(),
        business_id=biz.id,
        feature_code="outlets.max_count",
        override_type="restrict",
        limit_value=0,
        reason="Admin Restriction"
    )
    db_session.add(restrict)
    db_session.commit()

    restrict_result = EntitlementService.check_entitlement(
        db_session, biz.id, "outlets.max_count"
    )
    assert not restrict_result.authorized, "Restriction override must deny outlets.max_count entitlement"
    assert "RESTRICTION_OVERRIDE_ACTIVE" in restrict_result.reason

    # Outlet creation is still uncapped even with restriction override
    out3_data = PlatformOutletCreate(name="Outlet 3", public_slug="override-outlet-3")
    out3 = platform_service.add_outlet_to_business(db_session, business_id=biz.id, data=out3_data)
    assert out3.name == "Outlet 3", "Phase 1: outlet creation is never blocked by entitlement checks"




def test_suspended_business_blocked_from_outlet_creation(db_session):
    data = platform_service.PlatformBusinessCreate(
        name="Suspended Biz",
        owner_email="owner@suspended.com",
        owner_password="Password123!",
        owner_display_name="Suspended Owner"
    )
    biz = platform_service.create_platform_business(db_session, data=data)

    # Suspend business
    platform_service.update_business_subscription(
        db_session, business_id=biz.id, data=platform_service.PlatformSubscriptionUpdate(status="suspended")
    )

    # Outlet creation blocked with ForbiddenError
    out2_data = PlatformOutletCreate(name="Outlet 2", public_slug="suspended-outlet-2")
    with pytest.raises(ForbiddenError) as exc_info:
        platform_service.add_outlet_to_business(db_session, business_id=biz.id, data=out2_data)

    assert "suspended" in str(exc_info.value).lower()


def test_outlet_creation_uses_requested_plan_code(db_session):
    """Outlet creation must use the plan_code from the request, not a hardcoded default."""
    data = platform_service.PlatformBusinessCreate(
        name="Plan Selection Biz",
        owner_email="owner@plan-sel.com",
        owner_password="Password123!",
        owner_display_name="Plan Selection Owner"
    )
    biz = platform_service.create_platform_business(db_session, data=data)

    from app.modules.subscriptions.models import OutletSubscription
    # No primary outlet auto-created — create one manually
    primary_out = platform_service.add_outlet_to_business(
        db_session,
        business_id=biz.id,
        data=PlatformOutletCreate(name="Primary", public_slug="plan-sel-outlet-1", plan_code="starter_pos")
    )
    sub = db_session.scalar(
        select(OutletSubscription)
        .where(OutletSubscription.outlet_id == primary_out.id)
    )
    assert sub is not None
    plan = db_session.scalar(select(Plan).where(Plan.id == sub.plan_id))
    assert plan.code == "starter_pos", "Primary outlet should get starter_pos plan"

    # Create secondary outlet with free_qr plan
    out2_data = PlatformOutletCreate(name="Free QR Outlet", public_slug="plan-sel-free-qr", plan_code="free_qr")
    out2 = platform_service.add_outlet_to_business(db_session, business_id=biz.id, data=out2_data)

    sub2 = db_session.scalar(
        select(OutletSubscription).where(OutletSubscription.outlet_id == out2.id)
    )
    assert sub2 is not None
    plan2 = db_session.scalar(select(Plan).where(Plan.id == sub2.plan_id))
    assert plan2.code == "free_qr", "Secondary outlet must use requested free_qr plan"


def test_outlet_creation_rejects_unknown_plan_code(db_session):
    """Backend must reject unknown plan codes with a clear validation error."""
    data = platform_service.PlatformBusinessCreate(
        name="Unknown Plan Biz",
        owner_email="owner@unknown-plan.com",
        owner_password="Password123!",
        owner_display_name="Unknown Plan Owner"
    )
    biz = platform_service.create_platform_business(db_session, data=data)

    out2_data = PlatformOutletCreate(name="Bad Plan Outlet", public_slug="unknown-plan-outlet-2", plan_code="bogus_plan_xyz")
    with pytest.raises(ValidationError) as exc_info:
        platform_service.add_outlet_to_business(db_session, business_id=biz.id, data=out2_data)
    assert "Unknown or inactive plan code" in str(exc_info.value)


def test_default_plan_code_uses_trial_semantics(db_session):
    """When plan_code is omitted, the outlet must be created as a Trial on starter_pos."""
    data = platform_service.PlatformBusinessCreate(
        name="Default Trial Biz",
        owner_email="owner@default-trial.com",
        owner_password="Password123!",
        owner_display_name="Default Trial Owner"
    )
    biz = platform_service.create_platform_business(db_session, data=data)

    out_data = PlatformOutletCreate(name="Default Trial Outlet", public_slug="default-trial-outlet-2")
    out = platform_service.add_outlet_to_business(db_session, business_id=biz.id, data=out_data)

    from app.modules.subscriptions.models import OutletSubscription
    sub = db_session.scalar(select(OutletSubscription).where(OutletSubscription.outlet_id == out.id))
    assert sub is not None
    plan = db_session.scalar(select(Plan).where(Plan.id == sub.plan_id))
    assert plan.code == "starter_pos", "Trial default must resolve to starter_pos plan"
    assert sub.status == "trial", "Trial sentinel must create a trial-status subscription"
    assert sub.trial_ends_at is not None, "Trial must have a trial_ends_at"
    from datetime import timedelta
    diff = sub.trial_ends_at - sub.created_at
    assert abs(diff.total_seconds() - (30 * 86400)) < 5, "Trial must be exactly 30 days"
    assert sub.current_period_end is None, "Trial must not have current_period_end"


def test_explicit_plan_codes_create_active_subscriptions(db_session):
    """Explicit canonical plan codes must create active subscriptions with period dates."""
    data = platform_service.PlatformBusinessCreate(
        name="Active Plan Biz",
        owner_email="owner@active-plan.com",
        owner_password="Password123!",
        owner_display_name="Active Plan Owner"
    )
    biz = platform_service.create_platform_business(db_session, data=data)

    from app.modules.subscriptions.models import OutletSubscription
    for plan_code in ("growth_pos", "pro_kds", "enterprise", "free_qr"):
        slug = f"active-plan-{plan_code}"
        out_data = PlatformOutletCreate(name=f"Outlet {plan_code}", public_slug=slug, plan_code=plan_code)
        out = platform_service.add_outlet_to_business(db_session, business_id=biz.id, data=out_data)

        sub = db_session.scalar(select(OutletSubscription).where(OutletSubscription.outlet_id == out.id))
        assert sub is not None, f"Outlet with plan_code={plan_code} must have a subscription"
        plan = db_session.scalar(select(Plan).where(Plan.id == sub.plan_id))
        assert plan.code == plan_code, f"Subscribed plan must match requested plan_code={plan_code}"
        assert sub.status == "active", f"Explicit plan {plan_code} must create active subscription"
        assert sub.trial_ends_at is None, f"Active plan {plan_code} must not set trial_ends_at"


def test_outlet_subscriptions_are_isolated(db_session):
    """Each outlet must have its own independent subscription; changing one must not affect siblings."""
    data = platform_service.PlatformBusinessCreate(
        name="Isolation Biz",
        owner_email="owner@isolation.com",
        owner_password="Password123!",
        owner_display_name="Isolation Owner"
    )
    biz = platform_service.create_platform_business(db_session, data=data)

    # First outlet with trial
    out1_data = PlatformOutletCreate(name="Outlet 1", public_slug="isolation-outlet-1")
    out1 = platform_service.add_outlet_to_business(db_session, business_id=biz.id, data=out1_data)

    # Second outlet with explicit growth_pos
    out2_data = PlatformOutletCreate(name="Outlet 2", public_slug="isolation-outlet-2", plan_code="growth_pos")
    out2 = platform_service.add_outlet_to_business(db_session, business_id=biz.id, data=out2_data)

    from app.modules.subscriptions.models import OutletSubscription
    sub1 = db_session.scalar(select(OutletSubscription).where(OutletSubscription.outlet_id == out1.id))
    sub2 = db_session.scalar(select(OutletSubscription).where(OutletSubscription.outlet_id == out2.id))

    assert sub1.plan_id != sub2.plan_id, "Different outlets must have different subscriptions"
    assert sub1.status == "trial"
    assert sub2.status == "active"
    assert sub1.plan_id is not None and sub2.plan_id is not None
