import uuid
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from app.modules.staff.models import User, OutletMembership
from app.modules.staff.schemas import UserMeOut, OutletMembershipOut
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
        )
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise NotFoundError(f"User with ID '{user_id}' not found")

    memberships_out = []
    for mem in user.memberships:
        if mem.outlet and mem.outlet.status == "active":
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

    return UserMeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        is_platform_admin=user.is_platform_admin,
        memberships=memberships_out
    )

