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

    session.add_all([p_free, p_starter, p_growth, p_pro])

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

    session.add_all([
        pf_free_menu, pf_free_outlets,
        pf_starter_menu, pf_starter_outlets,
        pf_growth_menu, pf_growth_outlets
    ])
    session.commit()

    yield session
    session.close()


def test_entitled_business_creates_outlet_within_limit(db_session):
    # Business on growth_pos (limit = 3) created with 1 primary outlet
    data = platform_service.PlatformBusinessCreate(
        name="Growth Biz",
        public_slug="growth-outlet-1",
        primary_outlet_name="Outlet 1",
        plan_name="growth"
    )
    biz = platform_service.create_platform_business(db_session, data=data)

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
        public_slug="starter-outlet-1",
        primary_outlet_name="Outlet 1",
        plan_name="starter"
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
        public_slug="free-qr-outlet-1",
        primary_outlet_name="Primary Outlet",
        plan_name="free"
    )
    biz = platform_service.create_platform_business(db_session, data=data)

    # Primary outlet exists
    primary = db_session.query(Outlet).filter(Outlet.business_id == biz.id).first()
    assert primary is not None

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
        public_slug="override-outlet-1",
        primary_outlet_name="Outlet 1",
        plan_name="starter"
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
        public_slug="suspended-outlet-1",
        primary_outlet_name="Outlet 1",
        plan_name="growth"
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
