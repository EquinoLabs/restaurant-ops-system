import uuid
from typing import Optional, List
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import decode_access_token
from app.core.errors import AuthenticationError, ForbiddenError, ServiceUnavailableError
from app.modules.staff.models import User, OutletMembership, BusinessMembership
from app.modules.outlets.models import Outlet

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
    """
    Enforces outlet-scoped tenant authorization.

    Contract:
    - Callers with no relationship to the target outlet (no OutletMembership row and no
      canonical BusinessMembership owner row for its business) receive a uniform
      HTTP 403 whether or not the outlet exists, so ordinary tenant users cannot probe
      outlet existence (no 404/403 oracle, no suspension-state oracle).
    - Established members/business-owners are then subject to the business/outlet
      suspension guards (403) and role validation (403).
    - Platform routes keep their own 404 detail semantics (platform/business-owner
      detail endpoints are outside this dependency).
    """

    def __init__(self, allowed_roles: Optional[List[str]] = None):
        self.allowed_roles = allowed_roles or ["owner", "manager"]

    def __call__(
        self,
        outlet_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> OutletMembership:
        outlet = db.query(Outlet).filter(Outlet.id == outlet_id).first()

        membership = None
        biz_owner = None
        if outlet is not None:
            membership = (
                db.query(OutletMembership)
                .filter(
                    OutletMembership.user_id == current_user.id,
                    OutletMembership.outlet_id == outlet_id
                )
                .first()
            )
            if membership is None:
                biz_owner = (
                    db.query(BusinessMembership)
                    .filter(
                        BusinessMembership.business_id == outlet.business_id,
                        BusinessMembership.user_id == current_user.id,
                        BusinessMembership.role == "owner"
                    )
                    .first()
                )

        if outlet is None:
            raise ForbiddenError("You do not have administrative access to this outlet")
        if membership is None and biz_owner is None:
            raise ForbiddenError("You do not have administrative access to this outlet")

        # Business suspension check (hard platform kill switch)
        if outlet.business and outlet.business.status != "active":
            raise ForbiddenError("This business account is currently suspended. Please contact platform support.")

        # Outlet operational suspension check
        if outlet.status != "active":
            raise ForbiddenError("This outlet is currently suspended. Please contact platform support.")

        if membership is not None:
            if self.allowed_roles and membership.role not in self.allowed_roles:
                raise ForbiddenError(f"Role '{membership.role}' is not authorized to perform this operation")
            return membership

        if self.allowed_roles and "owner" not in self.allowed_roles:
            raise ForbiddenError("Role 'owner' is not authorized to perform this operation")
        # Synthesize an OutletMembership for downstream caller compatibility
        return OutletMembership(
            id=biz_owner.id,
            user_id=current_user.id,
            outlet_id=outlet_id,
            role="owner",
            outlet=outlet
        )


def has_outlet_relationship(db: Session, outlet_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """
    True when the user has any relationship to the outlet: an OutletMembership row or a
    canonical BusinessMembership owner row for the outlet's business. Mirrors the
    relationship resolution performed by RequireOutletRole (P3 anti-probing contract).
    """
    has_membership = (
        db.query(OutletMembership)
        .filter(
            OutletMembership.user_id == user_id,
            OutletMembership.outlet_id == outlet_id
        )
        .first()
        is not None
    )
    if has_membership:
        return True

    outlet = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    if outlet is None:
        return False

    return (
        db.query(BusinessMembership)
        .filter(
            BusinessMembership.business_id == outlet.business_id,
            BusinessMembership.user_id == user_id,
            BusinessMembership.role == "owner"
        )
        .first()
        is not None
    )


def enforce_outlet_entitlement(
    db: Session,
    membership: OutletMembership,
    feature_code: str,
    write: bool = False
):
    """
    Feature entitlement gate for an outlet the caller already passed membership,
    suspension, and role checks for. Delegates all policy to EntitlementService
    (single source of truth: business/outlet operational status, subscription
    lifecycle, plan features, restrictions, and grant overrides).

    write=True additionally denies expired/cancelled subscriptions even when the
    feature carries the read-only digital-menu exception (menu.digital): writing
    requires a live subscription status.
    """
    from app.modules.subscriptions.service import EntitlementService

    outlet = membership.outlet
    result = EntitlementService.check_entitlement(
        db=db,
        business_id=outlet.business_id,
        feature_code=feature_code,
        outlet_id=outlet.id
    )
    if not result.authorized:
        if result.reason == "BUSINESS_SUSPENDED":
            raise ForbiddenError("This business account is currently suspended.")
        raise ForbiddenError(f"Entitlement '{feature_code}' is not authorized. Reason: {result.reason}")
    if write and result.resolved_status in ("expired", "cancelled"):
        raise ForbiddenError(
            f"Entitlement '{feature_code}' is not authorized. Reason: SUBSCRIPTION_{result.resolved_status.upper()}"
        )
    return result


def verify_subresource_outlet_access(
    db: Session,
    outlet_id: uuid.UUID,
    user: User,
    allowed_roles: Optional[List[str]],
    feature_code: str,
    write: bool = False
) -> OutletMembership:
    """
    Shared operational access check for sub-resource routes (menu item, category,
    order, table). Callers must have already resolved the sub-resource and applied
    the anti-probing not-found policy (has_outlet_relationship); this function
    applies the full RequireOutletRole policy (suspension guards, role validation,
    canonical business-owner access) followed by feature entitlement.
    """
    membership = RequireOutletRole(allowed_roles)(outlet_id, user, db)
    enforce_outlet_entitlement(db, membership, feature_code, write=write)
    return membership


class RequireOutletEntitlement:
    """
    Outlet-scoped operational-write gate: RequireOutletRole (relationship,
    business/outlet suspension, role validation, canonical business-owner access)
    followed by feature entitlement via EntitlementService.
    """

    def __init__(self, allowed_roles: List[str], feature_code: str, write: bool = False):
        self._role_check = RequireOutletRole(allowed_roles)
        self.feature_code = feature_code
        self.write = write

    def __call__(
        self,
        outlet_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> OutletMembership:
        membership = self._role_check(outlet_id, current_user, db)
        enforce_outlet_entitlement(db, membership, self.feature_code, write=self.write)
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


class RequireBusinessOwner:
    """
    Dependency that enforces owner-level access for business-scoped endpoints (OP-05).
    - Requires an authenticated, active User.
    - Resolves business ownership canonically from BusinessMembership rows where role == 'owner'.
    - Gated legacy fallback: only while the caller has NO BusinessMembership rows at all,
      ownership is derived from OutletMembership rows where role == 'owner' (transition
      period for pre-0013 data). When canonical rows exist, they are authoritative.
    - If optional business_id query parameter is provided, verifies caller is an owner of that specific business.
    - Fails closed if caller has no owner memberships (403 Forbidden).
    - Fails closed if the business is suspended (403 Forbidden).
    - Returns the resolved Business entity.
    """
    def __call__(
        self,
        business_id: Optional[uuid.UUID] = None,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        from app.modules.businesses.models import Business
        from app.modules.outlets.models import Outlet

        canonical_memberships = (
            db.query(BusinessMembership)
            .join(Business, BusinessMembership.business_id == Business.id)
            .filter(
                BusinessMembership.user_id == current_user.id,
                BusinessMembership.role == "owner"
            )
            .all()
        )

        if canonical_memberships:
            source_memberships = [("canonical", m) for m in canonical_memberships]
        else:
            legacy_memberships = (
                db.query(OutletMembership)
                .join(Outlet, OutletMembership.outlet_id == Outlet.id)
                .join(Business, Outlet.business_id == Business.id)
                .filter(
                    OutletMembership.user_id == current_user.id,
                    OutletMembership.role == "owner"
                )
                .all()
            )
            source_memberships = [("legacy_outlet", m) for m in legacy_memberships]

        if not source_memberships:
            raise ForbiddenError("You are not authorized as an owner of this business")

        owned_businesses = {}
        for source, m in source_memberships:
            if source == "canonical":
                owned_businesses[m.business.id] = m.business
            elif m.outlet and m.outlet.business:
                owned_businesses[m.outlet.business.id] = m.outlet.business

        if not owned_businesses:
            raise ForbiddenError("No associated business found for your owner account")

        if business_id is not None:
            if business_id not in owned_businesses:
                raise ForbiddenError("You are not authorized as an owner of the requested business")
            target_business = owned_businesses[business_id]
        else:
            target_business = next(iter(owned_businesses.values()))

        if target_business.status != "active":
            raise ForbiddenError("This business account is currently suspended. Please contact platform support.")

        return target_business


