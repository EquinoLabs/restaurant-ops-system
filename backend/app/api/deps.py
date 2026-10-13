import uuid
from typing import Optional, List
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import decode_access_token
from app.core.errors import AuthenticationError, ForbiddenError, ServiceUnavailableError
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


class RequirePlatformRole:
    """
    Enforces three-tier platform role access control ('owner', 'admin', 'operator').
    Includes legacy authorization bridge: users without platform_role (platform_role is None)
    are treated as 'admin' if and only if is_platform_admin is True.
    Operators and Owner are never inferred from is_platform_admin.
    A non-null platform_role (even unsupported or empty) never falls back to is_platform_admin.
    A conflicting legacy boolean cannot elevate a caller whose non-null role is more restrictive.
    """
    VALID_ROLES = {"owner", "admin", "operator"}

    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = [r.lower() for r in allowed_roles]

    def __call__(
        self,
        current_user: User = Depends(get_current_user),
    ) -> User:
        role = current_user.platform_role
        if role is not None:
            if role not in self.VALID_ROLES:
                # Non-null but unsupported or malformed platform_role (including whitespace, casing, empty string)
                # is rejected; MUST NOT fall back to legacy boolean
                raise ForbiddenError("Platform administrator privileges are required")

            # Validate role-field consistency (fail closed on contradictory pairs)
            if role in ("owner", "admin") and not current_user.is_platform_admin:
                raise ForbiddenError("Platform administrator privileges are required")
            if role == "operator" and current_user.is_platform_admin:
                raise ForbiddenError("Platform administrator privileges are required")

            effective_role = role
        elif current_user.is_platform_admin:
            # Legacy authorization bridge: callers with platform_role IS NULL are treated
            # as 'admin' if and only if is_platform_admin is True.
            # Operators and Owner are never inferred from is_platform_admin.
            effective_role = "admin"
        else:
            effective_role = None

        if not effective_role or effective_role not in self.allowed_roles:
            raise ForbiddenError("Platform administrator privileges are required")

        return current_user



def _assert_platform_owner_initialized(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Guards ordinary role-governance operations. Fails closed with HTTP 503
    when no active Platform Owner exists in the system.
    """
    active_owner_count = (
        db.query(User)
        .filter(User.platform_role == "owner", User.status == "active")
        .count()
    )
    if active_owner_count == 0:
        raise ServiceUnavailableError(
            message="Platform Owner has not been initialized. Governance operations are unavailable.",
            code="PLATFORM_OWNER_NOT_INITIALIZED"
        )


def get_current_platform_admin(
    current_user: User = Depends(RequirePlatformRole(["owner", "admin"]))
) -> User:
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


