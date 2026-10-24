import pytest
import uuid
from sqlalchemy.orm import Session

from app.modules.businesses.platform_service import (
    create_platform_business,
    add_outlet_to_business,
    assign_owner_to_business,
    grant_platform_admin,
    revoke_platform_admin,
    update_business_profile,
    update_outlet_profile,
)
from app.modules.businesses.schemas import (
    PlatformBusinessCreate,
    PlatformOutletCreate,
    PlatformAssignOwner,
    PlatformBusinessProfileUpdate,
    PlatformOutletProfileUpdate,
)
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.staff.models import User, BusinessMembership
from app.modules.audit.models import AuditLog


def test_platform_service_commit_false_rollback(db_session: Session):
    # Verify create_platform_business with commit=False can be rolled back cleanly
    data = PlatformBusinessCreate(
        name="Rollback Biz",
        owner_email="rollback_owner@test.com",
        owner_password="SecurePassword123!",
        owner_display_name="Rollback Owner",
    )
    biz = create_platform_business(db=db_session, data=data, commit=False)
    assert biz.id is not None
    assert biz.name == "Rollback Biz"

    # Roll back transaction
    db_session.rollback()

    # Verify entity does not exist in DB session
    biz_found = db_session.query(Business).filter(Business.name == "Rollback Biz").first()
    assert biz_found is None
    owner_found = db_session.query(User).filter(User.email == "rollback_owner@test.com").first()
    assert owner_found is None


def test_platform_service_commit_true_persists(db_session: Session):
    data = PlatformBusinessCreate(
        name="Persisted Biz",
        owner_email="persist_owner@test.com",
        owner_password="SecurePassword123!",
        owner_display_name="Persist Owner",
    )
    biz = create_platform_business(db=db_session, data=data, commit=True)
    assert biz.id is not None

    # Even after rollback, committed row remains
    db_session.rollback()
    biz_found = db_session.query(Business).filter(Business.name == "Persisted Biz").first()
    assert biz_found is not None
    assert biz_found.id == biz.id


def test_add_outlet_commit_false_rollback(db_session: Session):
    biz_data = PlatformBusinessCreate(
        name="Outlet Host Biz",
        owner_email="outlet_host@test.com",
        owner_password="SecurePassword123!",
        owner_display_name="Host Owner",
    )
    biz = create_platform_business(db=db_session, data=biz_data, commit=True)

    outlet_data = PlatformOutletCreate(
        name="Rollback Outlet",
        public_slug="rollback-outlet-test",
        currency="INR",
        timezone="Asia/Kolkata",
    )
    outlet = add_outlet_to_business(db=db_session, business_id=biz.id, data=outlet_data, commit=False)
    assert outlet.id is not None

    db_session.rollback()
    outlet_found = db_session.query(Outlet).filter(Outlet.name == "Rollback Outlet").first()
    assert outlet_found is None


def test_grant_and_revoke_admin_commit_false(db_session: Session):
    user = User(
        email="admin_candidate@test.com",
        password_hash="dummyhash",
        display_name="Admin Candidate",
        status="active",
        is_platform_admin=False,
    )
    db_session.add(user)
    db_session.commit()

    # Grant admin with commit=False
    grant_platform_admin(db=db_session, target_user_id=user.id, commit=False)
    assert user.is_platform_admin is True
    assert user.platform_role == "admin"

    db_session.rollback()
    db_session.refresh(user)
    assert user.is_platform_admin is False
    assert user.platform_role is None
