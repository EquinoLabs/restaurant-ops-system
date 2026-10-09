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
)
from app.core.security import hash_password
from app.core.errors import NotFoundError, ValidationError


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


def create_platform_business(db: Session, data: PlatformBusinessCreate) -> Business:
    """
    Provisions a new Business and its primary Outlet in a single transaction.
    Validates public_slug uniqueness.
    """
    slug = data.public_slug.strip().lower()

    existing_slug = db.query(Outlet).filter(Outlet.public_slug == slug).first()
    if existing_slug:
        raise ValidationError(f"Public slug '{slug}' is already in use by another outlet.")

    business = Business(
        name=data.name.strip(),
        status="active"
    )
    db.add(business)
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
    db.commit()
    db.refresh(business)
    return business


def add_outlet_to_business(db: Session, business_id: uuid.UUID, data: PlatformOutletCreate) -> Outlet:
    """
    Adds a new Outlet to an existing Business.
    """
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise NotFoundError(f"Business with ID '{business_id}' not found.")

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
    db.commit()
    db.refresh(outlet)
    return outlet


def assign_owner_to_outlet(
    db: Session, business_id: uuid.UUID, data: PlatformAssignOwner
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

    db.commit()
    db.refresh(membership)
    return membership
