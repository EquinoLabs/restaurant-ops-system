import uuid
from typing import Optional, List
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import decode_access_token
from app.core.errors import AuthenticationError, ForbiddenError
from app.modules.staff.models import User, OutletMembership

security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> User:
    if not credentials or not credentials.credentials:
        raise AuthenticationError("Authentication token is required")

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise AuthenticationError("Invalid or expired authentication token")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, TypeError):
        raise AuthenticationError("Invalid user payload in token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AuthenticationError("User not found")
    if user.status != "active":
        raise AuthenticationError("User account is inactive")

    return user


def get_current_platform_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_platform_admin:
        raise ForbiddenError("Platform administrator privileges are required")
    return current_user



class RequireOutletRole:
    def __init__(self, allowed_roles: Optional[List[str]] = None):
        self.allowed_roles = allowed_roles or ["owner", "manager"]

    def __call__(
        self,
        outlet_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> OutletMembership:
        membership = (
            db.query(OutletMembership)
            .filter(
                OutletMembership.user_id == current_user.id,
                OutletMembership.outlet_id == outlet_id
            )
            .first()
        )
        if not membership:
            raise ForbiddenError("You do not have administrative access to this outlet")

        if membership.outlet and membership.outlet.business and membership.outlet.business.status != "active":
            raise ForbiddenError("This business account is currently suspended. Please contact platform support.")

        if self.allowed_roles and membership.role not in self.allowed_roles:
            raise ForbiddenError(f"Role '{membership.role}' is not authorized to perform this operation")

        return membership


class RequireEntitlement:
    def __init__(self, feature_code: str):
        self.feature_code = feature_code

    def __call__(
        self,
        business_id: uuid.UUID,
        outlet_id: Optional[uuid.UUID] = None,
        db: Session = Depends(get_db)
    ):
        from app.modules.subscriptions.service import EntitlementService
        result = EntitlementService.check_entitlement(
            db=db,
            business_id=business_id,
            feature_code=self.feature_code,
            outlet_id=outlet_id
        )
        if not result.authorized:
            if result.reason == "BUSINESS_SUSPENDED":
                raise ForbiddenError("This business account is currently suspended.")
            raise ForbiddenError(f"Entitlement '{self.feature_code}' is not authorized. Reason: {result.reason}")
        return result


