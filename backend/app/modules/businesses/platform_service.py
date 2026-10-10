import uuid
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.staff.models import User, OutletMembership
from app.modules.businesses.schemas import (
    PlatformBusinessCreate,
    PlatformOutletCreate,
    PlatformAssignOwner,
    PlatformSubscriptionUpdate,
)
from app.core.security import hash_password
from app.core.errors import NotFoundError, ValidationError, ForbiddenError
from app.modules.audit.service import log_audit
from app.modules.subscriptions.models import Plan, BusinessSubscription
from app.modules.subscriptions.service import EntitlementService

PLAN_MAP = {
    'starter': 'starter_pos',
    'growth': 'growth_pos',
    'pro': 'pro_kds',
    'enterprise': 'enterprise',
    'digital_menu': 'free_qr',
    'free': 'free_qr',
}

from sqlalchemy import text


VALID_SUBSCRIPTION_STATUSES = {"trial", "active", "past_due", "cancelled"}
VALID_ACCOUNT_STATUSES = {"active", "suspended"}
ADMIN_PRIVILEGE_LOCK_KEY = 424242111


def _acquire_admin_serialization_lock(db: Session) -> None:
    """
    Acquires a transaction-scoped advisory lock in PostgreSQL to serialize platform-admin privilege mutations.
    Safe and ignored in non-PostgreSQL (e.g. SQLite) test environments.
    """
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": ADMIN_PRIVILEGE_LOCK_KEY})


def list_platform_businesses(db: Session) -> List[Business]:
    """
    Returns all businesses across tenants with preloaded outlets sorted by created_at desc.
    """
    return (
        db.query(Business)
        .options(joinedload(Business.outlets))
        .order_by(Business.created_at.desc())
        .all()
    )


def create_platform_business(
    db: Session, data: PlatformBusinessCreate, actor_user_id: Optional[uuid.UUID] = None
) -> Business:
    """
    Provisions a new Business, its initial BusinessSubscription, and primary Outlet in a single transaction.
    Validates public_slug uniqueness.
    """
    slug = data.public_slug.strip().lower()

    existing_slug = db.query(Outlet).filter(Outlet.public_slug == slug).first()
    if existing_slug:
        raise ValidationError(f"Public slug '{slug}' is already in use by another outlet.")

    if data.subscription_status and data.subscription_status not in VALID_SUBSCRIPTION_STATUSES:
        raise ValidationError(
            f"Invalid subscription_status '{data.subscription_status}'. Allowed: {sorted(list(VALID_SUBSCRIPTION_STATUSES))}"
        )

    if data.max_outlets is not None and data.max_outlets < 1:
        raise ValidationError("max_outlets must be at least 1 or None.")

    sub_status = data.subscription_status or "trial"
    trial_ends = data.trial_ends_at
    if sub_status == "trial" and trial_ends is None:
        from datetime import timedelta
        from app.db.base import utc_now
        trial_ends = utc_now() + timedelta(days=14)

    business = Business(
        name=data.name.strip(),
        status="active",
        subscription_status=sub_status,
        plan_name=data.plan_name,
        max_outlets=data.max_outlets,
        trial_ends_at=trial_ends
    )
    db.add(business)
    db.flush()

    # Create initial BusinessSubscription
    if data.plan_name:
        raw_plan = data.plan_name.strip().lower()
        target_code = PLAN_MAP.get(raw_plan, 'starter_pos')
    else:
        target_code = 'starter_pos' if (data.max_outlets == 1) else 'growth_pos'

    plan = db.query(Plan).filter(Plan.code == target_code).first()
    if plan:
        sub = BusinessSubscription(
            business_id=business.id,
            plan_id=plan.id,
            status=business.subscription_status,
            is_current=True,
            trial_ends_at=business.trial_ends_at
        )
        db.add(sub)
        db.flush()

    primary_outlet = Outlet(
        business_id=business.id,
        name=data.primary_outlet_name.strip(),
        public_slug=slug,
        currency=data.currency,
        timezone=data.timezone,
        address=data.address.strip() if data.address else None,
        status="active"
    )
    db.add(primary_outlet)
    db.flush()

    log_audit(
        db=db,
        business_id=business.id,
        outlet_id=primary_outlet.id,
        actor_user_id=actor_user_id,
        action="platform.business.create",
        entity_type="business",
        entity_id=business.id,
        metadata_json={
            "outcome": "success",
            "name": business.name,
            "primary_outlet_name": primary_outlet.name,
            "public_slug": primary_outlet.public_slug,
            "subscription_status": business.subscription_status,
            "plan_name": business.plan_name,
            "max_outlets": business.max_outlets,
            "trial_ends_at": business.trial_ends_at.isoformat() if business.trial_ends_at else None,
        }
    )

    db.commit()
    db.refresh(business)
    return business


def update_business_subscription(
    db: Session, business_id: uuid.UUID, data: PlatformSubscriptionUpdate, actor_user_id: Optional[uuid.UUID] = None
) -> Business:
    """
    Updates subscription status, account status, plan name, max outlets, and trial end date for a business.
    Syncs authoritative BusinessSubscription record.
    """
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise NotFoundError(f"Business with ID '{business_id}' not found.")

    before_state = {
        "status": business.status,
        "subscription_status": business.subscription_status,
        "plan_name": business.plan_name,
        "max_outlets": business.max_outlets,
        "trial_ends_at": business.trial_ends_at.isoformat() if business.trial_ends_at else None,
    }

    if data.subscription_status is not None:
        if data.subscription_status not in VALID_SUBSCRIPTION_STATUSES:
            raise ValidationError(
                f"Invalid subscription_status '{data.subscription_status}'. Allowed: {sorted(list(VALID_SUBSCRIPTION_STATUSES))}"
            )
        business.subscription_status = data.subscription_status

    if data.status is not None:
        if data.status not in VALID_ACCOUNT_STATUSES:
            raise ValidationError(
                f"Invalid status '{data.status}'. Allowed: {sorted(list(VALID_ACCOUNT_STATUSES))}"
            )
        business.status = data.status

    if data.plan_name is not None:
        business.plan_name = data.plan_name.strip() if data.plan_name else None

    if data.max_outlets is not None:
        if data.max_outlets < 1:
            raise ValidationError("max_outlets must be at least 1 or None.")
        business.max_outlets = data.max_outlets

    if data.trial_ends_at is not None:
        business.trial_ends_at = data.trial_ends_at

    # Sync BusinessSubscription
    curr_sub = db.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == business_id,
        BusinessSubscription.is_current == True
    ).first()

    target_plan_code = PLAN_MAP.get(business.plan_name.lower() if business.plan_name else "", 'free_qr')
    new_plan = db.query(Plan).filter(Plan.code == target_plan_code).first()

    if new_plan:
        if curr_sub and curr_sub.plan_id != new_plan.id:
            curr_sub.is_current = False
            new_sub = BusinessSubscription(
                business_id=business_id,
                plan_id=new_plan.id,
                status=business.subscription_status,
                is_current=True,
                trial_ends_at=business.trial_ends_at
            )
            db.add(new_sub)
        elif curr_sub:
            curr_sub.status = business.subscription_status
            curr_sub.trial_ends_at = business.trial_ends_at
        else:
            new_sub = BusinessSubscription(
                business_id=business_id,
                plan_id=new_plan.id,
                status=business.subscription_status,
                is_current=True,
                trial_ends_at=business.trial_ends_at
            )
            db.add(new_sub)

    after_state = {
        "status": business.status,
        "subscription_status": business.subscription_status,
        "plan_name": business.plan_name,
        "max_outlets": business.max_outlets,
        "trial_ends_at": business.trial_ends_at.isoformat() if business.trial_ends_at else None,
    }

    if before_state["status"] != "suspended" and after_state["status"] == "suspended":
        action = "platform.business.suspend"
    elif before_state["status"] == "suspended" and after_state["status"] == "active":
        action = "platform.business.reactivate"
    else:
        action = "platform.business.update_subscription"

    log_audit(
        db=db,
        business_id=business.id,
        outlet_id=None,
        actor_user_id=actor_user_id,
        action=action,
        entity_type="business",
        entity_id=business.id,
        metadata_json={
            "outcome": "success",
            "before": before_state,
            "after": after_state,
        }
    )

    db.commit()
    db.refresh(business)
    return business


def add_outlet_to_business(
    db: Session, business_id: uuid.UUID, data: PlatformOutletCreate, actor_user_id: Optional[uuid.UUID] = None
) -> Outlet:
    """
    Adds a new Outlet to an existing Business, enforcing central EntitlementService authorization and capacity limits.
    Uses pessimistic row locking on PostgreSQL to prevent concurrent outlet creation race conditions.
    """
    if db.bind and db.bind.dialect.name == "postgresql":
        business = db.query(Business).with_for_update().filter(Business.id == business_id).first()
    else:
        business = db.query(Business).filter(Business.id == business_id).first()

    if not business:
        raise NotFoundError(f"Business with ID '{business_id}' not found.")

    # Entitlement Check 1: Feature Authorization
    entitlement = EntitlementService.check_entitlement(db, business_id=business_id, feature_code="outlets.max_count")
    if not entitlement.authorized:
        if entitlement.reason == "BUSINESS_SUSPENDED":
            raise ForbiddenError("This business account is currently suspended.")
        raise ValidationError(
            f"Business '{business.name}' is not entitled to create outlets. Reason: {entitlement.reason}"
        )

    # Entitlement Check 2: Numeric Capacity Limit
    if entitlement.limit_value is not None:
        current_count = db.query(Outlet).filter(Outlet.business_id == business_id).count()
        if current_count >= entitlement.limit_value:
            raise ValidationError(
                f"Business '{business.name}' has reached its maximum allowed limit of {entitlement.limit_value} outlet(s)."
            )

    slug = data.public_slug.strip().lower()
    existing_slug = db.query(Outlet).filter(Outlet.public_slug == slug).first()
    if existing_slug:
        raise ValidationError(f"Public slug '{slug}' is already in use by another outlet.")

    outlet = Outlet(
        business_id=business_id,
        name=data.name.strip(),
        public_slug=slug,
        currency=data.currency,
        timezone=data.timezone,
        address=data.address.strip() if data.address else None,
        status="active"
    )
    db.add(outlet)
    db.flush()

    log_audit(
        db=db,
        business_id=business_id,
        outlet_id=outlet.id,
        actor_user_id=actor_user_id,
        action="platform.outlet.create",
        entity_type="outlet",
        entity_id=outlet.id,
        metadata_json={
            "outcome": "success",
            "name": outlet.name,
            "public_slug": outlet.public_slug,
            "currency": outlet.currency,
            "timezone": outlet.timezone,
        }
    )

    db.commit()
    db.refresh(outlet)
    return outlet


def assign_owner_to_outlet(
    db: Session, business_id: uuid.UUID, data: PlatformAssignOwner, actor_user_id: Optional[uuid.UUID] = None
) -> OutletMembership:
    """
    Creates or assigns a User as an 'owner' for a specific Outlet under a Business.
    """
    outlet = db.query(Outlet).filter(
        Outlet.id == data.outlet_id,
        Outlet.business_id == business_id
    ).first()
    if not outlet:
        raise NotFoundError(f"Outlet with ID '{data.outlet_id}' not found under business '{business_id}'.")

    user: Optional[User] = None
    created_new_user = False

    if data.user_id:
        user = db.query(User).filter(User.id == data.user_id).first()
        if not user:
            raise NotFoundError(f"User with ID '{data.user_id}' not found.")
    elif data.email:
        email = data.email.strip().lower()
        user = db.query(User).filter(User.email == email).first()
        if not user:
            if not data.password or not data.display_name:
                raise ValidationError("password and display_name are required when creating a new owner user.")
            user = User(
                email=email,
                password_hash=hash_password(data.password),
                display_name=data.display_name.strip(),
                status="active",
                is_platform_admin=False
            )
            db.add(user)
            db.flush()
            created_new_user = True
    else:
        raise ValidationError("Either user_id or email must be provided to assign an owner.")

    membership = db.query(OutletMembership).filter(
        OutletMembership.user_id == user.id,
        OutletMembership.outlet_id == outlet.id
    ).first()

    if membership:
        membership.role = "owner"
    else:
        membership = OutletMembership(
            user_id=user.id,
            outlet_id=outlet.id,
            role="owner"
        )
        db.add(membership)

    db.flush()

    log_audit(
        db=db,
        business_id=business_id,
        outlet_id=outlet.id,
        actor_user_id=actor_user_id,
        action="platform.owner.assign",
        entity_type="membership",
        entity_id=membership.id,
        metadata_json={
            "outcome": "success",
            "assigned_user_id": str(user.id),
            "email": user.email,
            "role": "owner",
            "created_new_user": created_new_user,
        }
    )

    db.commit()
    db.refresh(membership)
    return membership


def list_platform_admins(db: Session) -> List[User]:
    """
    Returns all users with platform administrator privileges.
    """
    return (
        db.query(User)
        .filter(User.is_platform_admin == True)
        .order_by(User.created_at.asc())
        .all()
    )


def grant_platform_admin(
    db: Session, target_user_id: uuid.UUID, actor_user_id: Optional[uuid.UUID] = None
) -> User:
    """
    Grants platform administrator privileges to an existing user.
    """
    _acquire_admin_serialization_lock(db)

    user = db.query(User).filter(User.id == target_user_id).first()
    if not user:
        raise NotFoundError(f"User with ID '{target_user_id}' not found.")

    if user.is_platform_admin:
        return user

    user.is_platform_admin = True
    db.flush()

    log_audit(
        db=db,
        business_id=None,
        outlet_id=None,
        actor_user_id=actor_user_id,
        action="platform.admin.grant",
        entity_type="user",
        entity_id=user.id,
        metadata_json={
            "outcome": "success",
            "target_user_id": str(user.id),
            "target_email": user.email,
        }
    )

    db.commit()
    db.refresh(user)
    return user


def revoke_platform_admin(
    db: Session, target_user_id: uuid.UUID, actor_user_id: Optional[uuid.UUID] = None
) -> User:
    """
    Revokes platform administrator privileges from a user, with concurrency-safe last-admin protection.
    """
    _acquire_admin_serialization_lock(db)

    user = db.query(User).filter(User.id == target_user_id).first()
    if not user:
        raise NotFoundError(f"User with ID '{target_user_id}' not found.")

    if not user.is_platform_admin:
        return user

    if user.status == "active":
        active_admins = (
            db.query(User)
            .filter(User.is_platform_admin == True, User.status == "active")
            .order_by(User.id.asc())
            .all()
        )
        if len(active_admins) <= 1:
            raise ValidationError("Cannot revoke platform admin privileges from the last active platform administrator.")

    user.is_platform_admin = False
    db.flush()

    log_audit(
        db=db,
        business_id=None,
        outlet_id=None,
        actor_user_id=actor_user_id,
        action="platform.admin.revoke",
        entity_type="user",
        entity_id=user.id,
        metadata_json={
            "outcome": "success",
            "target_user_id": str(user.id),
            "target_email": user.email,
        }
    )

    db.commit()
    db.refresh(user)
    return user
