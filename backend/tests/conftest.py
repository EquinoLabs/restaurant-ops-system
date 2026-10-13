import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.menus.models import MenuCategory, MenuItem
from app.modules.staff.models import User, OutletMembership
from app.modules.audit.models import AuditLog
from app.modules.tables.models import DiningTable
from app.modules.orders.models import Order, OrderItem
from app.core.security import hash_password

from sqlalchemy.pool import StaticPool

# Use SQLite in-memory database with StaticPool for fast backend unit testing
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
from app import main as app_main
app_main.engine = engine

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


import uuid
from app.modules.subscriptions.models import Plan, Feature, PlanFeature


def seed_canonical_plans_and_features(session):
    p_free = Plan(id=uuid.uuid4(), code="free_qr", name="Free QR Menu", sort_order=1)
    p_starter = Plan(id=uuid.uuid4(), code="starter_pos", name="Starter POS", sort_order=2)
    p_growth = Plan(id=uuid.uuid4(), code="growth_pos", name="Growth POS", sort_order=3)
    p_pro = Plan(id=uuid.uuid4(), code="pro_kds", name="Pro KDS", sort_order=4)
    p_ent = Plan(id=uuid.uuid4(), code="enterprise", name="Enterprise", sort_order=5)

    session.add_all([p_free, p_starter, p_growth, p_pro, p_ent])

    f_menu = Feature(id=uuid.uuid4(), code="menu.digital", name="Digital Menu", category="menu")
    f_cust = Feature(id=uuid.uuid4(), code="ordering.customer", name="Customer Ordering", category="ordering")
    f_staff = Feature(id=uuid.uuid4(), code="ordering.staff", name="Staff Ordering", category="ordering")
    f_kds = Feature(id=uuid.uuid4(), code="kds.enabled", name="KDS", category="kitchen")
    f_outlets = Feature(id=uuid.uuid4(), code="outlets.max_count", name="Max Outlets", category="billing")
    f_pay = Feature(id=uuid.uuid4(), code="payments.online", name="Online Payments", category="billing")
    f_wa = Feature(id=uuid.uuid4(), code="notifications.whatsapp", name="WhatsApp", category="marketing")

    session.add_all([f_menu, f_cust, f_staff, f_kds, f_outlets, f_pay, f_wa])
    session.commit()

    plan_features_data = [
        (p_free, f_menu, None),
        (p_free, f_outlets, 1),
        (p_starter, f_menu, None),
        (p_starter, f_staff, None),
        (p_starter, f_outlets, 1),
        (p_growth, f_menu, None),
        (p_growth, f_staff, None),
        (p_growth, f_cust, None),
        (p_growth, f_outlets, 3),
        (p_pro, f_menu, None),
        (p_pro, f_staff, None),
        (p_pro, f_cust, None),
        (p_pro, f_kds, None),
        (p_pro, f_outlets, 10),
        (p_ent, f_menu, None),
        (p_ent, f_staff, None),
        (p_ent, f_cust, None),
        (p_ent, f_kds, None),
        (p_ent, f_pay, None),
        (p_ent, f_wa, None),
        (p_ent, f_outlets, None),
    ]

    for p, f, limit_val in plan_features_data:
        session.add(PlanFeature(id=uuid.uuid4(), plan_id=p.id, feature_id=f.id, limit_value=limit_val))
    session.commit()


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        seed_canonical_plans_and_features(session)

        # Seed test business & outlet
        biz = Business(name="Test Business", status="active")
        session.add(biz)
        session.commit()

        outlet = Outlet(
            business_id=biz.id,
            name="Test Camp Outlet",
            public_slug="test-camp",
            timezone="Asia/Kolkata",
            currency="INR",
            address="Test Valley",
            status="active"
        )
        session.add(outlet)
        session.commit()

        # Seed categories
        cat1 = MenuCategory(
            outlet_id=outlet.id,
            name="Starters",
            description="Appetizers",
            sort_order=1,
            is_active=True
        )
        cat_inactive = MenuCategory(
            outlet_id=outlet.id,
            name="Archived Category",
            description="Hidden category",
            sort_order=2,
            is_active=False
        )
        session.add_all([cat1, cat_inactive])
        session.commit()

        # Seed items
        item1 = MenuItem(
            outlet_id=outlet.id,
            category_id=cat1.id,
            name="Fried Fish",
            description="Crispy fish",
            price=Decimal("250.00"),
            is_available=True,
            is_active=True,
            sort_order=1
        )
        item_unavail = MenuItem(
            outlet_id=outlet.id,
            category_id=cat1.id,
            name="Seasonal Fruit Bowl",
            description="Fresh fruits",
            price=Decimal("150.00"),
            is_available=False,
            is_active=True,
            sort_order=2
        )
        item_hidden = MenuItem(
            outlet_id=outlet.id,
            category_id=cat1.id,
            name="Deleted Dish",
            description="Deleted",
            price=Decimal("999.00"),
            is_available=True,
            is_active=False,
            sort_order=3
        )
        session.add_all([item1, item_unavail, item_hidden])
        session.commit()

        # Seed test staff user with owner access to test outlet
        test_user = User(
            email="staff@test.com",
            password_hash=hash_password("password123"),
            display_name="Test Staff",
            status="active"
        )
        session.add(test_user)
        session.commit()

        membership = OutletMembership(
            user_id=test_user.id,
            outlet_id=outlet.id,
            role="owner"
        )
        session.add(membership)

        # Seed unauthorized staff user (no membership)
        unauth_user = User(
            email="unauth@test.com",
            password_hash=hash_password("password123"),
            display_name="Unauth Staff",
            status="active"
        )
        session.add(unauth_user)
        session.commit()

        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ==============================================================================
# PostgreSQL Concurrency & Integration Test Fixtures (Opt-in via --pg-integration)
# ==============================================================================

def pytest_addoption(parser):
    parser.addoption(
        "--pg-integration",
        action="store_true",
        default=False,
        help="Run PostgreSQL multi-connection concurrency and constraint integration tests.",
    )


def pytest_configure(config):
    """
    Early configuration validation hook for PostgreSQL integration testing.
    If --pg-integration is provided, validates environment variable presence and format
    immediately at test session start, exiting with a single clear refusal message rather
    than producing multiple repetitive fixture setup failures.
    """
    if config.getoption("--pg-integration", default=False):
        import os
        from tests.postgres_guard import validate_postgres_test_url, ConfigurationError
        url = os.environ.get("ROMS_POSTGRES_TEST_DATABASE_URL")
        try:
            validate_postgres_test_url(url)
        except ConfigurationError as exc:
            import pytest
            pytest.exit(
                f"\n[ROMS-GUARD-REFUSAL] PostgreSQL Integration Testing Refused:\n"
                f"{exc}\n"
                f"Aborting test session immediately before any fixture execution.\n",
                returncode=1
            )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--pg-integration"):
        skip_pg = pytest.mark.skip(
            reason="Pass --pg-integration to run PostgreSQL integration tests."
        )
        for item in items:
            if "postgres_integration" in item.keywords:
                item.add_marker(skip_pg)


@pytest.fixture(scope="session")
def pg_target(request):
    """
    Session-scoped target resolver. Validates configuration only when --pg-integration is provided.
    Fails closed immediately if missing, invalid, or matching application DATABASE_URL.
    """
    if not request.config.getoption("--pg-integration"):
        pytest.skip("Pass --pg-integration to run PostgreSQL integration tests.")

    import os
    from tests.postgres_guard import validate_postgres_test_url
    url = os.environ.get("ROMS_POSTGRES_TEST_DATABASE_URL")
    return validate_postgres_test_url(url)


@pytest.fixture(scope="session")
def pg_engine(pg_target):
    """
    Session-scoped engine factory. Verifies target identity before creating pool.
    Guarantees raw driver exceptions are sanitized and raw credentials are never printed.
    Takes a snapshot of pre-existing non-test records and strictly verifies their preservation after testing.
    """
    from tests.postgres_guard import (
        verify_disposable_test_target,
        verify_migration_dag_head,
        sanitize_error_message,
        TargetVerificationRefusal,
    )
    import sqlalchemy as sa

    verify_migration_dag_head()

    engine = sa.create_engine(
        pg_target.raw_url,
        pool_size=10,
        max_overflow=5,
        pool_pre_ping=True,
    )
    initial_user_ids = set()
    try:
        with engine.connect() as conn:
            verify_disposable_test_target(conn, pg_target)
            # Record baseline non-test users to verify preservation after all tests complete
            tables_res = conn.execute(sa.text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """)).scalars().all()
            if "users" in tables_res:
                initial_user_ids = set(
                    conn.execute(sa.text("SELECT id FROM users WHERE email NOT LIKE 'test_%'")).scalars().all()
                )
    except Exception as exc:
        safe_msg = sanitize_error_message(str(exc), pg_target)
        raise TargetVerificationRefusal(
            f"Failed to establish verified connection to test database: {safe_msg}"
        ) from None

    yield engine

    # Post-session integrity verification: verify pre-existing records are 100% intact
    if initial_user_ids:
        try:
            with engine.connect() as conn:
                final_user_ids = set(
                    conn.execute(sa.text("SELECT id FROM users WHERE email NOT LIKE 'test_%'")).scalars().all()
                )
                leaked_test_users = conn.execute(
                    sa.text("SELECT COUNT(*) FROM users WHERE email LIKE 'test_%'")
                ).scalar() or 0
                active_owners = conn.execute(
                    sa.text("SELECT COUNT(*) FROM users WHERE platform_role = 'owner' AND status = 'active'")
                ).scalar() or 0

            if initial_user_ids != final_user_ids:
                raise AssertionError(
                    "Teardown Safety Violation: Pre-existing user accounts were modified or deleted during test run!"
                )
            if leaked_test_users > 0:
                raise AssertionError(
                    f"Teardown Safety Violation: {leaked_test_users} transient test user(s) were not cleaned up!"
                )
            if active_owners > 0:
                raise AssertionError(
                    f"Teardown Safety Violation: {active_owners} active platform owner(s) remain after test run!"
                )
        except Exception as exc:
            safe_msg = sanitize_error_message(str(exc), pg_target)
            raise AssertionError(f"Post-test integrity verification failed: {safe_msg}") from None

    engine.dispose()


@pytest.fixture(scope="function")
def pg_connection_pair(pg_engine):
    """
    Yields two independent physical connections to PostgreSQL with statement timeouts set to 5s,
    and guarantees automatic rollback and closure upon test completion.
    """
    import sqlalchemy as sa

    conn1 = pg_engine.connect()
    conn2 = pg_engine.connect()

    conn1.execute(sa.text("SET statement_timeout = '5000ms';"))
    conn1.commit()
    conn2.execute(sa.text("SET statement_timeout = '5000ms';"))
    conn2.commit()

    try:
        yield conn1, conn2
    finally:
        try:
            conn1.rollback()
        except Exception:
            pass
        try:
            conn2.rollback()
        except Exception:
            pass
        conn1.close()
        conn2.close()


@pytest.fixture(scope="function")
def pg_user_tracker(pg_engine):
    """
    Function-scoped entity tracker. Guarantees deterministic, scoped teardown of transient test users
    and associated audit logs created during an integration test run.
    Deletes strictly by exact primary key (WHERE id = ANY(:ids)).
    Never performs broad, un-scoped deletions.
    """
    import uuid
    import sqlalchemy as sa
    from tests.postgres_guard import sanitize_error_message
    from app.modules.staff.models import User
    from app.core.security import hash_password

    class TestUserTracker:
        def __init__(self, engine):
            self.engine = engine
            self.created_user_ids: list[uuid.UUID] = []

        def create_user(
            self,
            session,
            email_prefix: str,
            role: str = None,
            is_admin: bool = False,
            display_name: str = None,
            status: str = "active",
        ) -> User:
            user_id = uuid.uuid4()
            user = User(
                id=user_id,
                email=f"test_{email_prefix}_{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("TestPassword123!"),
                display_name=display_name or f"Test {email_prefix.title()}",
                status=status,
                platform_role=role,
                is_platform_admin=is_admin,
            )
            session.add(user)
            session.flush()
            self.created_user_ids.append(user_id)
            return user

        def cleanup(self):
            if not self.created_user_ids:
                return
            ids = list(self.created_user_ids)
            with self.engine.connect() as conn:
                with conn.begin():
                    # 1. Scoped cleanup of audit logs where actor or entity matches created user IDs
                    conn.execute(
                        sa.text("""
                            DELETE FROM audit_logs
                            WHERE actor_user_id = ANY(:ids)
                               OR entity_id = ANY(:ids)
                        """),
                        {"ids": ids}
                    )
                    # 2. Scoped cleanup of users table by exact created user IDs
                    conn.execute(
                        sa.text("DELETE FROM users WHERE id = ANY(:ids)"),
                        {"ids": ids}
                    )
            self.created_user_ids.clear()

    tracker = TestUserTracker(pg_engine)
    try:
        yield tracker
    finally:
        try:
            tracker.cleanup()
        except Exception as exc:
            safe_msg = sanitize_error_message(str(exc))
            raise AssertionError(f"Scoped test user cleanup failed: {safe_msg}") from None


