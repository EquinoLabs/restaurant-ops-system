import uuid
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from app.modules.staff.models import User, OutletMembership, BusinessMembership
from app.modules.outlets.models import Outlet
from app.modules.staff.schemas import UserMeOut, OutletMembershipOut, BusinessMembershipOut
from app.core.security import verify_password, hash_password
from app.core.errors import AuthenticationError, NotFoundError


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.strip().lower()).first()


def get_user_by_id(db: Session, user_id: uuid.UUID) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if not user:
        raise AuthenticationError("Invalid email or password")
    if not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid email or password")
    if user.status != "active":
        raise AuthenticationError("User account is inactive")
    return user


def get_user_me_profile(db: Session, user_id: uuid.UUID) -> UserMeOut:
    user = (
        db.query(User)
        .options(
            joinedload(User.memberships)
            .joinedload(OutletMembership.outlet)
            .joinedload(Outlet.business),
            joinedload(User.business_memberships)
            .joinedload(BusinessMembership.business)
        )
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise NotFoundError(f"User with ID '{user_id}' not found")

    memberships_out = []
    for mem in user.memberships:
        if mem.outlet and mem.outlet.status == "active" and mem.outlet.business and mem.outlet.business.status == "active":
            memberships_out.append(
                OutletMembershipOut(
                    outlet_id=mem.outlet.id,
                    outlet_name=mem.outlet.name,
                    public_slug=mem.outlet.public_slug,
                    business_id=mem.outlet.business_id,
                    business_name=mem.outlet.business.name if mem.outlet.business else "",
                    role=mem.role
                )
            )

    # Deterministic API contract: business memberships ordered by business creation
    # time (unknown timestamps first), tie-broken by business id. Outlet memberships
    # remain in relationship (insertion) order.
    ordered_business_memberships = sorted(
        user.business_memberships,
        key=lambda m: (
            m.business.created_at.isoformat() if (m.business and m.business.created_at) else "",
            str(m.business_id),
        ),
    )

    business_memberships_out = []
    for bmem in ordered_business_memberships:
        if bmem.business and bmem.business.status == "active":
            business_memberships_out.append(
                BusinessMembershipOut(
                    business_id=bmem.business_id,
                    business_name=bmem.business.name,
                    role=bmem.role
                )
            )

    return UserMeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        is_platform_admin=user.is_platform_admin,
        platform_role=user.platform_role,
        memberships=memberships_out,
        business_memberships=business_memberships_out
    )

