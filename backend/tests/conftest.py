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


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
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
