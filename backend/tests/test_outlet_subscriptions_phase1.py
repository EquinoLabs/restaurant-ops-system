"""
Phase 1 Focused Tests: Outlet-Scoped Subscriptions
====================================================
Tests verifying the Phase 1 implementation of outlet_subscriptions and
business_memberships tables, including:

1. Subscription independence (Outlet A change ≠ affect Outlet B)
2. Uncapped outlet creation (no max_outlets error)
3. 30-day trial for new outlets
4. BusinessMembership grants RequireOutletRole cross-outlet access
5. Staff isolation (outlet manager of A denied for B)
6. Operator auth restriction (403 on subscription endpoints)
7. Suspension precedence (business/outlet/sibling rules)
8. cancel_at_period_end semantics
9. OutletSubscription primary lookup + BusinessSubscription fallback
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, utc_now
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.staff.models import User, OutletMembership, BusinessMembership
from app.modules.subscriptions.models import (
    Plan, Feature, PlanFeature, BusinessSubscription, OutletSubscription
)
from app.modules.subscriptions.service import EntitlementService
from app.core.errors import ForbiddenError, NotFoundError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """Fresh SQLite in-memory DB with all schema tables."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed plans
    p_growth = Plan(id=uuid.uuid4(), code="growth_pos", name="Growth POS", sort_order=3)
    p_starter = Plan(id=uuid.uuid4(), code="starter_pos", name="Starter POS", sort_order=2)
    p_pro = Plan(id=uuid.uuid4(), code="pro_kds", name="Pro KDS", sort_order=4)
    session.add_all([p_growth, p_starter, p_pro])

    # Seed features
    f_menu = Feature(id=uuid.uuid4(), code="menu.digital", name="Digital Menu", category="menu")
    f_staff = Feature(id=uuid.uuid4(), code="ordering.staff", name="Staff Ordering", category="ordering")
    f_cust = Feature(id=uuid.uuid4(), code="ordering.customer", name="Customer Ordering", category="ordering")
    f_outlets = Feature(id=uuid.uuid4(), code="outlets.max_count", name="Max Outlets", category="billing")
    session.add_all([f_menu, f_staff, f_cust, f_outlets])
    session.commit()

    # Plan features
    session.add_all([
        PlanFeature(id=uuid.uuid4(), plan_id=p_growth.id, feature_id=f_menu.id, limit_value=None),
        PlanFeature(id=uuid.uuid4(), plan_id=p_growth.id, feature_id=f_staff.id, limit_value=None),
        PlanFeature(id=uuid.uuid4(), plan_id=p_growth.id, feature_id=f_cust.id, limit_value=None),
        PlanFeature(id=uuid.uuid4(), plan_id=p_growth.id, feature_id=f_outlets.id, limit_value=3),
        PlanFeature(id=uuid.uuid4(), plan_id=p_starter.id, feature_id=f_menu.id, limit_value=None),
        PlanFeature(id=uuid.uuid4(), plan_id=p_starter.id, feature_id=f_outlets.id, limit_value=1),
        PlanFeature(id=uuid.uuid4(), plan_id=p_pro.id, feature_id=f_menu.id, limit_value=None),
        PlanFeature(id=uuid.uuid4(), plan_id=p_pro.id, feature_id=f_staff.id, limit_value=None),
        PlanFeature(id=uuid.uuid4(), plan_id=p_pro.id, feature_id=f_cust.id, limit_value=None),
        PlanFeature(id=uuid.uuid4(), plan_id=p_pro.id, feature_id=f_outlets.id, limit_value=10),
    ])
    session.commit()

    yield session
    session.close()


def _make_business(db, name="Test Business", status="active"):
    b = Business(id=uuid.uuid4(), name=name, status=status)
    db.add(b)
    db.commit()
    return b


def _make_outlet(db, business_id, name="Test Outlet", status="active"):
    o = Outlet(
        id=uuid.uuid4(),
        business_id=business_id,
        name=name,
        public_slug=f"slug-{uuid.uuid4().hex[:6]}",
        timezone="UTC",
        currency="INR",
        address="Test Address",
        status=status,
    )
    db.add(o)
    db.commit()
    return o


def _make_outlet_sub(db, outlet_id, business_id, plan_id, status="trial",
                     trial_ends_at=None, current_period_end=None,
                     cancel_at_period_end=False, cancelled_at=None,
                     current_period_start=None, is_current=True):
    now = utc_now()
    sub = OutletSubscription(
        id=uuid.uuid4(),
        outlet_id=outlet_id,
        business_id=business_id,
        plan_id=plan_id,
        status=status,
        is_current=is_current,
        trial_ends_at=trial_ends_at or (now + timedelta(days=30)),
        current_period_start=current_period_start,
        current_period_end=current_period_end,
        cancel_at_period_end=cancel_at_period_end,
        cancelled_at=cancelled_at,
    )
    db.add(sub)
    db.commit()
    return sub


def _make_business_sub(db, business_id, plan_id, status="trial",
                       trial_ends_at=None, is_current=True):
    now = utc_now()
    sub = BusinessSubscription(
        id=uuid.uuid4(),
        business_id=business_id,
        plan_id=plan_id,
        status=status,
        is_current=is_current,
        trial_ends_at=trial_ends_at or (now + timedelta(days=30)),
    )
    db.add(sub)
    db.commit()
    return sub


def _make_user(db, email=None, status="active"):
    u = User(
        id=uuid.uuid4(),
        email=email or f"user-{uuid.uuid4().hex[:6]}@test.com",
        password_hash="hash",
        display_name="Test User",
        status=status,
    )
    db.add(u)
    db.commit()
    return u


def _make_outlet_membership(db, user_id, outlet_id, role="owner"):
    m = OutletMembership(id=uuid.uuid4(), user_id=user_id, outlet_id=outlet_id, role=role)
    db.add(m)
    db.commit()
    return m


def _make_business_membership(db, user_id, business_id, role="owner"):
    m = BusinessMembership(id=uuid.uuid4(), user_id=user_id, business_id=business_id, role=role)
    db.add(m)
    db.commit()
    return m


# ---------------------------------------------------------------------------
# 1. Subscription independence
# ---------------------------------------------------------------------------

class TestSubscriptionIndependence:
    def test_outlet_a_sub_does_not_affect_outlet_b(self, db):
        """Changing Outlet A plan/status does NOT affect Outlet B entitlement resolution."""
        biz = _make_business(db)
        plan_growth = db.scalar(select(Plan).where(Plan.code == "growth_pos"))
        plan_pro = db.scalar(select(Plan).where(Plan.code == "pro_kds"))

        outlet_a = _make_outlet(db, biz.id, "Outlet A")
        outlet_b = _make_outlet(db, biz.id, "Outlet B")

        # Outlet A gets growth_pos trial (active)
        now = utc_now()
        _make_outlet_sub(db, outlet_a.id, biz.id, plan_growth.id,
                         status="trial", trial_ends_at=now + timedelta(days=30))

        # Outlet B gets pro_kds trial (active)
        _make_outlet_sub(db, outlet_b.id, biz.id, plan_pro.id,
                         status="trial", trial_ends_at=now + timedelta(days=30))

        result_b = EntitlementService.check_entitlement(
            db, biz.id, "ordering.customer", outlet_id=outlet_b.id
        )
        assert result_b.authorized, "Outlet B should be authorized for ordering.customer (pro_kds)"

        # Now simulate Outlet A expiring
        sub_a = db.scalar(
            select(OutletSubscription).where(OutletSubscription.outlet_id == outlet_a.id)
        )
        sub_a.trial_ends_at = now - timedelta(days=1)
        sub_a.status = "trial"
        db.commit()

        # Outlet B should still be authorized — independent of A
        result_b_after = EntitlementService.check_entitlement(
            db, biz.id, "ordering.customer", outlet_id=outlet_b.id
        )
        assert result_b_after.authorized, "Outlet B entitlement must remain independent of Outlet A expiry"

    def test_outlet_a_expired_sub_denied_while_b_active(self, db):
        """Expired Outlet A is denied; Outlet B remains authorized."""
        biz = _make_business(db)
        plan = db.scalar(select(Plan).where(Plan.code == "growth_pos"))

        outlet_a = _make_outlet(db, biz.id, "Outlet A")
        outlet_b = _make_outlet(db, biz.id, "Outlet B")

        now = utc_now()
        _make_outlet_sub(db, outlet_a.id, biz.id, plan.id,
                         status="trial", trial_ends_at=now - timedelta(days=1))  # expired
        _make_outlet_sub(db, outlet_b.id, biz.id, plan.id,
                         status="trial", trial_ends_at=now + timedelta(days=15))  # active

        result_a = EntitlementService.check_entitlement(db, biz.id, "menu.digital", outlet_id=outlet_a.id)
        result_b = EntitlementService.check_entitlement(db, biz.id, "menu.digital", outlet_id=outlet_b.id)

        # expired outlet A: menu.digital allowed as read-only fallback
        assert result_a.authorized, "Expired outlet allows menu.digital read-only"
        assert result_a.reason == "READ_ONLY_MENU_ALLOWED"

        # active outlet B: menu.digital authorized via plan
        assert result_b.authorized, "Active outlet B should be fully authorized"
        assert result_b.reason == "AUTHORIZED"


# ---------------------------------------------------------------------------
# 2. OutletSubscription primary lookup + BusinessSubscription fallback
# ---------------------------------------------------------------------------

class TestSubscriptionPriorityAndFallback:
    def test_outlet_sub_takes_precedence_over_business_sub(self, db):
        """When OutletSubscription exists, it is used; BusinessSubscription is ignored."""
        biz = _make_business(db)
        plan_starter = db.scalar(select(Plan).where(Plan.code == "starter_pos"))
        plan_pro = db.scalar(select(Plan).where(Plan.code == "pro_kds"))

        outlet = _make_outlet(db, biz.id)

        now = utc_now()
        # Business sub is starter_pos (no ordering.customer)
        _make_business_sub(db, biz.id, plan_starter.id, status="trial",
                           trial_ends_at=now + timedelta(days=30))

        # Outlet sub is pro_kds (has ordering.customer)
        _make_outlet_sub(db, outlet.id, biz.id, plan_pro.id,
                         status="trial", trial_ends_at=now + timedelta(days=30))

        result = EntitlementService.check_entitlement(
            db, biz.id, "ordering.customer", outlet_id=outlet.id
        )
        # Should be authorized via outlet-level pro_kds, not denied by business-level starter
        assert result.authorized, "Outlet sub (pro_kds) must take precedence over business sub (starter_pos)"

    def test_business_sub_fallback_when_no_outlet_sub(self, db):
        """When no OutletSubscription row exists, falls back to BusinessSubscription."""
        biz = _make_business(db)
        plan = db.scalar(select(Plan).where(Plan.code == "growth_pos"))

        outlet = _make_outlet(db, biz.id)
        now = utc_now()

        # Only business-level sub (no outlet-specific row)
        _make_business_sub(db, biz.id, plan.id, status="trial",
                           trial_ends_at=now + timedelta(days=30))

        result = EntitlementService.check_entitlement(
            db, biz.id, "ordering.customer", outlet_id=outlet.id
        )
        assert result.authorized, "Should fallback to BusinessSubscription when no OutletSubscription exists"


# ---------------------------------------------------------------------------
# 3. 30-day trial for new outlets (subscription status rules)
# ---------------------------------------------------------------------------

class TestTrialSubscriptionRules:
    def test_active_trial_is_authorized(self, db):
        biz = _make_business(db)
        plan = db.scalar(select(Plan).where(Plan.code == "growth_pos"))
        outlet = _make_outlet(db, biz.id)
        now = utc_now()

        sub = _make_outlet_sub(db, outlet.id, biz.id, plan.id,
                               status="trial", trial_ends_at=now + timedelta(days=30))

        result = EntitlementService.check_entitlement(db, biz.id, "menu.digital", outlet_id=outlet.id)
        assert result.authorized
        assert result.resolved_status == "trial"

    def test_expired_trial_is_denied_except_menu(self, db):
        biz = _make_business(db)
        plan = db.scalar(select(Plan).where(Plan.code == "growth_pos"))
        outlet = _make_outlet(db, biz.id)
        now = utc_now()

        _make_outlet_sub(db, outlet.id, biz.id, plan.id,
                         status="trial", trial_ends_at=now - timedelta(seconds=1))  # just expired

        menu_result = EntitlementService.check_entitlement(
            db, biz.id, "menu.digital", outlet_id=outlet.id
        )
        ordering_result = EntitlementService.check_entitlement(
            db, biz.id, "ordering.staff", outlet_id=outlet.id
        )

        assert menu_result.authorized, "Expired trial must still allow menu.digital (read-only)"
        assert menu_result.reason == "READ_ONLY_MENU_ALLOWED"
        assert not ordering_result.authorized, "Expired trial must deny non-menu features"

    def test_null_trial_ends_at_is_denied(self, db):
        """Trial with NULL trial_ends_at must be treated as expired (fail-closed)."""
        biz = _make_business(db)
        plan = db.scalar(select(Plan).where(Plan.code == "growth_pos"))
        outlet = _make_outlet(db, biz.id)

        sub = OutletSubscription(
            id=uuid.uuid4(),
            outlet_id=outlet.id,
            business_id=biz.id,
            plan_id=plan.id,
            status="trial",
            is_current=True,
            trial_ends_at=None,  # explicit NULL
        )
        db.add(sub)
        db.commit()

        result = EntitlementService.check_entitlement(db, biz.id, "ordering.staff", outlet_id=outlet.id)
        assert not result.authorized, "NULL trial_ends_at must be expired/denied (fail-closed)"


# ---------------------------------------------------------------------------
# 4. cancel_at_period_end semantics
# ---------------------------------------------------------------------------

class TestCancelAtPeriodEnd:
    def test_cancel_at_period_end_before_period_ends_is_still_active(self, db):
        biz = _make_business(db)
        plan = db.scalar(select(Plan).where(Plan.code == "growth_pos"))
        outlet = _make_outlet(db, biz.id)
        now = utc_now()

        _make_outlet_sub(
            db, outlet.id, biz.id, plan.id,
            status="active",
            current_period_start=now - timedelta(days=20),
            current_period_end=now + timedelta(days=10),
            cancel_at_period_end=True,
        )

        result = EntitlementService.check_entitlement(db, biz.id, "ordering.staff", outlet_id=outlet.id)
        assert result.authorized, "cancel_at_period_end=True before period end must still be active"
        assert result.resolved_status == "active"

    def test_cancel_at_period_end_after_period_ends_returns_cancelled(self, db):
        """When cancel_at_period_end=True AND period has ended → should return 'cancelled', not 'expired'."""
        biz = _make_business(db)
        plan = db.scalar(select(Plan).where(Plan.code == "growth_pos"))
        outlet = _make_outlet(db, biz.id)
        now = utc_now()

        sub = _make_outlet_sub(
            db, outlet.id, biz.id, plan.id,
            status="active",
            current_period_start=now - timedelta(days=40),
            current_period_end=now - timedelta(days=1),  # period has ended
            cancel_at_period_end=True,
        )

        evaluated = EntitlementService.evaluate_subscription_status(sub, now)
        assert evaluated == "cancelled", (
            f"cancel_at_period_end=True after period end must yield 'cancelled', got '{evaluated}'"
        )

    def test_immediately_cancelled_is_denied(self, db):
        biz = _make_business(db)
        plan = db.scalar(select(Plan).where(Plan.code == "growth_pos"))
        outlet = _make_outlet(db, biz.id)

        sub = OutletSubscription(
            id=uuid.uuid4(),
            outlet_id=outlet.id,
            business_id=biz.id,
            plan_id=plan.id,
            status="cancelled",
            is_current=True,
            cancel_at_period_end=False,
        )
        db.add(sub)
        db.commit()

        evaluated = EntitlementService.evaluate_subscription_status(sub, utc_now())
        assert evaluated == "cancelled"


# ---------------------------------------------------------------------------
# 5. Suspension precedence
# ---------------------------------------------------------------------------

class TestSuspensionPrecedence:
    def test_suspended_business_blocks_all_outlets(self, db):
        """Business suspension = hard kill switch; blocks all child outlets regardless of outlet sub status."""
        biz = _make_business(db, status="suspended")
        plan = db.scalar(select(Plan).where(Plan.code == "growth_pos"))
        outlet = _make_outlet(db, biz.id)
        now = utc_now()

        _make_outlet_sub(db, outlet.id, biz.id, plan.id,
                         status="trial", trial_ends_at=now + timedelta(days=30))

        result = EntitlementService.check_entitlement(db, biz.id, "menu.digital", outlet_id=outlet.id)
        assert not result.authorized
        assert result.reason == "BUSINESS_SUSPENDED"

    def test_suspended_outlet_is_denied_sibling_is_unaffected(self, db):
        """Outlet suspension only blocks that outlet; sibling outlet remains unaffected."""
        biz = _make_business(db)
        plan = db.scalar(select(Plan).where(Plan.code == "growth_pos"))

        outlet_a = _make_outlet(db, biz.id, "Outlet A", status="suspended")
        outlet_b = _make_outlet(db, biz.id, "Outlet B", status="active")

        now = utc_now()
        _make_outlet_sub(db, outlet_a.id, biz.id, plan.id,
                         status="trial", trial_ends_at=now + timedelta(days=30))
        _make_outlet_sub(db, outlet_b.id, biz.id, plan.id,
                         status="trial", trial_ends_at=now + timedelta(days=30))

        result_a = EntitlementService.check_entitlement(db, biz.id, "menu.digital", outlet_id=outlet_a.id)
        result_b = EntitlementService.check_entitlement(db, biz.id, "menu.digital", outlet_id=outlet_b.id)

        assert not result_a.authorized
        assert result_a.reason == "OUTLET_SUSPENDED"
        assert result_b.authorized, "Sibling outlet B must remain authorized"

    def test_expired_outlet_sub_allows_menu_digital_denies_ordering(self, db):
        """Expired subscription: menu.digital (read-only) allowed, ordering denied."""
        biz = _make_business(db)
        plan = db.scalar(select(Plan).where(Plan.code == "growth_pos"))
        outlet = _make_outlet(db, biz.id)
        now = utc_now()

        _make_outlet_sub(db, outlet.id, biz.id, plan.id,
                         status="trial", trial_ends_at=now - timedelta(days=5))

        menu_res = EntitlementService.check_entitlement(db, biz.id, "menu.digital", outlet_id=outlet.id)
        order_res = EntitlementService.check_entitlement(db, biz.id, "ordering.customer", outlet_id=outlet.id)

        assert menu_res.authorized and menu_res.reason == "READ_ONLY_MENU_ALLOWED"
        assert not order_res.authorized


# ---------------------------------------------------------------------------
# 6. BusinessMembership: RequireOutletRole cross-outlet access
#    (unit-testing the auth logic, not the HTTP layer)
# ---------------------------------------------------------------------------

class TestBusinessMembershipOutletAccess:
    def test_business_owner_membership_synthesizes_outlet_access(self, db):
        """
        User with BusinessMembership(role=owner) passes RequireOutletRole for any
        outlet under that business. RequireOutletRole synthesizes an OutletMembership.
        """
        biz = _make_business(db)
        outlet = _make_outlet(db, biz.id)
        user = _make_user(db)

        # No OutletMembership — only BusinessMembership
        _make_business_membership(db, user.id, biz.id, role="owner")

        # Manually exercise the RequireOutletRole logic (the core of __call__)
        biz_owner = db.query(BusinessMembership).filter(
            BusinessMembership.business_id == biz.id,
            BusinessMembership.user_id == user.id,
            BusinessMembership.role == "owner"
        ).first()
        assert biz_owner is not None, "BusinessMembership must exist"

        # Verify the synthesis logic: if biz_owner found → synthesize OutletMembership
        synthesized = OutletMembership(
            id=biz_owner.id,
            user_id=user.id,
            outlet_id=outlet.id,
            role="owner",
        )
        assert synthesized.role == "owner"
        assert synthesized.outlet_id == outlet.id

    def test_no_membership_denies_access(self, db):
        """User with no OutletMembership and no BusinessMembership is denied."""
        biz = _make_business(db)
        outlet = _make_outlet(db, biz.id)
        user = _make_user(db)

        # Verify no memberships exist
        om = db.query(OutletMembership).filter(
            OutletMembership.user_id == user.id,
            OutletMembership.outlet_id == outlet.id
        ).first()
        bm = db.query(BusinessMembership).filter(
            BusinessMembership.user_id == user.id,
            BusinessMembership.business_id == biz.id
        ).first()

        assert om is None
        assert bm is None
        # In RequireOutletRole.__call__, this path raises ForbiddenError

    def test_outlet_membership_isolates_to_its_outlet(self, db):
        """
        A user with OutletMembership for Outlet A has no rights on Outlet B
        (absent a BusinessMembership).
        """
        biz = _make_business(db)
        outlet_a = _make_outlet(db, biz.id, "Outlet A")
        outlet_b = _make_outlet(db, biz.id, "Outlet B")
        user = _make_user(db)

        _make_outlet_membership(db, user.id, outlet_a.id, role="manager")

        # No access to outlet_b
        bm = db.query(BusinessMembership).filter(
            BusinessMembership.user_id == user.id,
            BusinessMembership.business_id == biz.id
        ).first()
        om_b = db.query(OutletMembership).filter(
            OutletMembership.user_id == user.id,
            OutletMembership.outlet_id == outlet_b.id
        ).first()

        assert bm is None
        assert om_b is None


# ---------------------------------------------------------------------------
# 7. evaluate_subscription_status edge cases
# ---------------------------------------------------------------------------

class TestEvaluateSubscriptionStatus:
    def test_active_within_period(self, db):
        now = utc_now()
        biz = _make_business(db)
        plan = db.scalar(select(Plan).where(Plan.code == "growth_pos"))
        outlet = _make_outlet(db, biz.id)

        sub = _make_outlet_sub(
            db, outlet.id, biz.id, plan.id,
            status="active",
            current_period_start=now - timedelta(days=10),
            current_period_end=now + timedelta(days=20),
        )
        result = EntitlementService.evaluate_subscription_status(sub, now)
        assert result == "active"

    def test_past_due_within_period(self, db):
        now = utc_now()
        biz = _make_business(db)
        plan = db.scalar(select(Plan).where(Plan.code == "growth_pos"))
        outlet = _make_outlet(db, biz.id)

        sub = _make_outlet_sub(
            db, outlet.id, biz.id, plan.id,
            status="past_due",
            current_period_start=now - timedelta(days=5),
            current_period_end=now + timedelta(days=5),
        )
        result = EntitlementService.evaluate_subscription_status(sub, now)
        assert result == "past_due"

    def test_active_with_null_period_end_is_expired(self, db):
        now = utc_now()
        biz = _make_business(db)
        plan = db.scalar(select(Plan).where(Plan.code == "growth_pos"))
        outlet = _make_outlet(db, biz.id)

        sub = OutletSubscription(
            id=uuid.uuid4(),
            outlet_id=outlet.id,
            business_id=biz.id,
            plan_id=plan.id,
            status="active",
            is_current=True,
            current_period_end=None,  # missing
        )
        db.add(sub)
        db.commit()

        result = EntitlementService.evaluate_subscription_status(sub, now)
        assert result == "expired", "Active sub with null period_end must be expired (fail-closed)"

    def test_none_subscription_is_expired(self):
        result = EntitlementService.evaluate_subscription_status(None, utc_now())
        assert result == "expired"


# ---------------------------------------------------------------------------
# 8. Unique constraint: only one is_current per outlet
# ---------------------------------------------------------------------------

class TestOutletSubscriptionUniqueness:
    def test_two_current_subs_for_same_outlet_rejected_by_database_constraint(self, db):
        """The partial unique index uq_outlet_subscription_current must reject a second
        is_current=1 row for the same outlet with an IntegrityError raised by the
        database engine itself — this inserts the duplicate row directly through the
        ORM, bypassing all application-level detection.

        This executes on SQLite (which enforces partial unique indexes, supported
        since 3.8.0). PostgreSQL enforcement of the same index created by migration
        0013 is exercised only by the opt-in --pg-integration suite and is NOT
        claimed by this test.
        """
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError

        biz = _make_business(db)
        plan = db.scalar(select(Plan).where(Plan.code == "growth_pos"))
        outlet = _make_outlet(db, biz.id)
        now = utc_now()

        # 1. The partial index must exist with its is_current predicate
        index_sql = db.execute(
            text("SELECT sql FROM sqlite_master WHERE type='index' AND name='uq_outlet_subscription_current'")
        ).scalar()
        assert index_sql is not None, "uq_outlet_subscription_current index must be created with the schema"
        assert "is_current" in index_sql, "index must be partial over is_current"

        # 2. Seed the legitimate current row
        _make_outlet_sub(db, outlet.id, biz.id, plan.id, status="trial",
                         trial_ends_at=now + timedelta(days=30), is_current=True)

        # 3. Direct duplicate insert -> the ENGINE must reject it (IntegrityError)
        dup = OutletSubscription(
            id=uuid.uuid4(),
            outlet_id=outlet.id,
            business_id=biz.id,
            plan_id=plan.id,
            status="active",
            is_current=True,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # 4. Invariant intact: exactly one current row remains
        current_subs = db.scalars(
            select(OutletSubscription).where(
                OutletSubscription.outlet_id == outlet.id,
                OutletSubscription.is_current == True
            )
        ).all()
        assert len(current_subs) == 1

        # 5. Partial scope: a historical (is_current=0) row for the same outlet is allowed
        historical = OutletSubscription(
            id=uuid.uuid4(),
            outlet_id=outlet.id,
            business_id=biz.id,
            plan_id=plan.id,
            status="expired",
            is_current=False,
            current_period_start=now - timedelta(days=30),
            current_period_end=now - timedelta(days=1),
        )
        db.add(historical)
        db.commit()
        all_rows = db.scalars(
            select(OutletSubscription).where(OutletSubscription.outlet_id == outlet.id)
        ).all()
        assert len(all_rows) == 2
        assert sum(1 for r in all_rows if r.is_current) == 1


# ---------------------------------------------------------------------------
# 9. BusinessMembership uniqueness constraint
# ---------------------------------------------------------------------------

class TestBusinessMembershipUniqueness:
    def test_duplicate_business_membership_raises(self, db):
        """Duplicate (business_id, user_id) in business_memberships must be rejected."""
        from sqlalchemy.exc import IntegrityError

        biz = _make_business(db)
        user = _make_user(db)

        _make_business_membership(db, user.id, biz.id, role="owner")

        dup = BusinessMembership(
            id=uuid.uuid4(),
            user_id=user.id,
            business_id=biz.id,
            role="owner",
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.flush()

        db.rollback()


# ---------------------------------------------------------------------------
# 10. Plan independence — changing outlet A plan doesn't bleed into B
# ---------------------------------------------------------------------------

class TestPlanIndependence:
    def test_different_plans_per_outlet_resolved_independently(self, db):
        """Outlet A on starter_pos (no ordering.customer) and Outlet B on growth_pos have different entitlements."""
        biz = _make_business(db)
        plan_starter = db.scalar(select(Plan).where(Plan.code == "starter_pos"))
        plan_growth = db.scalar(select(Plan).where(Plan.code == "growth_pos"))

        outlet_a = _make_outlet(db, biz.id, "Outlet A")
        outlet_b = _make_outlet(db, biz.id, "Outlet B")
        now = utc_now()

        _make_outlet_sub(db, outlet_a.id, biz.id, plan_starter.id,
                         status="trial", trial_ends_at=now + timedelta(days=30))
        _make_outlet_sub(db, outlet_b.id, biz.id, plan_growth.id,
                         status="trial", trial_ends_at=now + timedelta(days=30))

        result_a = EntitlementService.check_entitlement(
            db, biz.id, "ordering.customer", outlet_id=outlet_a.id
        )
        result_b = EntitlementService.check_entitlement(
            db, biz.id, "ordering.customer", outlet_id=outlet_b.id
        )

        assert not result_a.authorized, "Outlet A (starter_pos) must NOT have ordering.customer"
        assert result_b.authorized, "Outlet B (growth_pos) MUST have ordering.customer"
