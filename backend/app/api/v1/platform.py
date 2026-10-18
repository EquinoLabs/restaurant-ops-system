import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import (
    get_current_user,
    get_current_platform_admin,
    RequirePlatformRole,
    _assert_platform_owner_initialized,
)
from app.modules.staff.models import User
from app.modules.staff.schemas import OutletMembershipOut, BusinessMembershipOut
from app.modules.businesses.schemas import (
    PlatformBusinessOut,
    PlatformBusinessProfileOut,
    PlatformBusinessCreate,
    PlatformOutletOut,
    PlatformOutletCreate,
    PlatformAssignOwner,
    PlatformSubscriptionUpdate,
    PlatformOwnerTransferRequest,
    PlatformOperatorCreateRequest,
    PlatformAdminUserOut,
    PlatformBusinessProfileUpdate,
    PlatformOutletProfileUpdate,
    PlatformOutletDetailOut,
)
from app.modules.businesses import platform_service
from app.modules.subscriptions.schemas import (
    PlatformBusinessEntitlementsOut,
    PlatformBusinessOverridesResponse,
    PlatformOverrideCreate,
    PlatformOverrideRevoke,
    PlatformOverrideInspectionItem,
    PlanRead,
    BusinessSubscriptionRead,
    OutletSubscriptionRead,
    PlatformOutletSubscriptionUpdate,
)
from app.modules.subscriptions.service import EntitlementService
from app.modules.audit.schemas import PlatformAuditLogListOut, PlatformAuditLogItemOut
from app.modules.audit import service as audit_service
from app.api.v1.platform_menu import platform_menu_router


# Explicit route-policy inventory mapping for automated verification
IMPLEMENTED_PLATFORM_ROUTE_POLICIES = {
    ("GET", "/api/v1/platform/audit-logs"): {
        "router": "commercial_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("GET", "/api/v1/platform/admins"): {
        "router": "commercial_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("POST", "/api/v1/platform/admins/{user_id}/grant"): {
        "router": "governance_router",
        "allowed_roles": {"owner"},
        "service_level_auth": "_assert_platform_owner_initialized",
    },
    ("POST", "/api/v1/platform/admins/{user_id}/revoke"): {
        "router": "governance_router",
        "allowed_roles": {"owner"},
        "service_level_auth": "_assert_platform_owner_initialized, self-revocation protection, last-active-admin check",
    },
    ("POST", "/api/v1/platform/owner/transfer"): {
        "router": "governance_router",
        "allowed_roles": {"owner"},
        "service_level_auth": "_assert_platform_owner_initialized, password re-verification, active successor check",
    },
    ("POST", "/api/v1/platform/operators"): {
        "router": "governance_router",
        "allowed_roles": {"owner"},
        "service_level_auth": "_assert_platform_owner_initialized, Mode 1/Mode 2 mutually exclusive validation",
    },
    ("POST", "/api/v1/platform/operators/{user_id}/revoke"): {
        "router": "governance_router",
        "allowed_roles": {"owner"},
        "service_level_auth": "_assert_platform_owner_initialized, non-owner target check",
    },
    ("POST", "/api/v1/platform/users/{id}/suspend"): {
        "router": "governance_router",
        "allowed_roles": {"owner"},
        "service_level_auth": "_assert_platform_owner_initialized, non-owner target check, self-suspension check",
    },
    ("POST", "/api/v1/platform/users/{id}/reactivate"): {
        "router": "governance_router",
        "allowed_roles": {"owner"},
        "service_level_auth": "_assert_platform_owner_initialized, self-reactivation check",
    },
    ("GET", "/api/v1/platform/operators"): {
        "router": "commercial_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("GET", "/api/v1/platform/plans"): {
        "router": "profile_router",
        "allowed_roles": {"owner", "admin", "operator"},
        "service_level_auth": None,
    },
    ("GET", "/api/v1/platform/businesses"): {
        "router": "profile_router",
        "allowed_roles": {"owner", "admin", "operator"},
        "service_level_auth": None,
    },
    ("GET", "/api/v1/platform/businesses/{business_id}/subscriptions"): {
        "router": "commercial_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("POST", "/api/v1/platform/businesses"): {
        "router": "operations_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("PATCH", "/api/v1/platform/businesses/{business_id}/subscription"): {
        "router": "commercial_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("PATCH", "/api/v1/platform/outlets/{outlet_id}/subscription"): {
        "router": "commercial_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("POST", "/api/v1/platform/businesses/{business_id}/outlets"): {
        "router": "operations_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("POST", "/api/v1/platform/businesses/{business_id}/assign-owner"): {
        "router": "commercial_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("GET", "/api/v1/platform/businesses/{business_id}/entitlements"): {
        "router": "commercial_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("GET", "/api/v1/platform/businesses/{business_id}/overrides"): {
        "router": "commercial_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("POST", "/api/v1/platform/businesses/{business_id}/overrides"): {
        "router": "commercial_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("DELETE", "/api/v1/platform/businesses/{business_id}/overrides/{override_id}"): {
        "router": "commercial_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("GET", "/api/v1/platform/outlets/{outlet_id}/menu"): {
        "router": "platform_menu_router",
        "allowed_roles": {"owner", "admin", "operator"},
        "service_level_auth": None,
    },
    ("POST", "/api/v1/platform/outlets/{outlet_id}/menu/categories"): {
        "router": "platform_menu_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("PATCH", "/api/v1/platform/outlets/{outlet_id}/menu/categories/{category_id}"): {
        "router": "platform_menu_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("POST", "/api/v1/platform/outlets/{outlet_id}/menu/items"): {
        "router": "platform_menu_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("PATCH", "/api/v1/platform/outlets/{outlet_id}/menu/items/{item_id}"): {
        "router": "platform_menu_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("PATCH", "/api/v1/platform/outlets/{outlet_id}/menu/items/{item_id}/availability"): {
        "router": "platform_menu_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("POST", "/api/v1/platform/outlets/{outlet_id}/menu/items/{item_id}/image"): {
        "router": "platform_menu_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("DELETE", "/api/v1/platform/outlets/{outlet_id}/menu/items/{item_id}/image"): {
        "router": "platform_menu_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("GET", "/api/v1/platform/businesses/{business_id}"): {
        "router": "profile_router",
        "allowed_roles": {"owner", "admin", "operator"},
        "service_level_auth": None,
    },
    ("PATCH", "/api/v1/platform/businesses/{business_id}"): {
        "router": "operations_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
    ("GET", "/api/v1/platform/outlets/{outlet_id}"): {
        "router": "profile_router",
        "allowed_roles": {"owner", "admin", "operator"},
        "service_level_auth": None,
    },
    ("PATCH", "/api/v1/platform/outlets/{outlet_id}"): {
        "router": "operations_router",
        "allowed_roles": {"owner", "admin"},
        "service_level_auth": None,
    },
}

PLANNED_PLATFORM_ROUTE_POLICIES = {}

# Sub-routers partitioned according to the ROMS Three-Tier Access Control model
governance_router = APIRouter(
    dependencies=[
        Depends(_assert_platform_owner_initialized),
        Depends(RequirePlatformRole(["owner"])),
    ]
)

commercial_router = APIRouter(
    dependencies=[
        Depends(RequirePlatformRole(["owner", "admin"])),
    ]
)

operations_router = APIRouter(
    dependencies=[
        Depends(RequirePlatformRole(["owner", "admin"])),
    ]
)

profile_router = APIRouter(
    dependencies=[
        Depends(RequirePlatformRole(["owner", "admin", "operator"])),
    ]
)


# Top-level platform router (prefix mounted on /api/v1)
router = APIRouter(prefix="/platform", tags=["platform-admin"])


# ==============================================================================
# Commercial Router Endpoints (owner, admin)
# ==============================================================================

@commercial_router.get("/audit-logs", response_model=PlatformAuditLogListOut)
def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    action: Optional[str] = Query(default=None),
    business_id: Optional[uuid.UUID] = Query(default=None),
    db: Session = Depends(get_db)
):
    items, total = audit_service.list_platform_audit_logs(
        db, limit=limit, offset=offset, action=action, business_id=business_id
    )
    mapped_items = [
        PlatformAuditLogItemOut(
            id=log.id,
            business_id=log.business_id,
            business_name=log.business.name if log.business else None,
            outlet_id=log.outlet_id,
            outlet_name=log.outlet.name if log.outlet else None,
            actor_user_id=log.actor_user_id,
            actor_display_name=log.actor.display_name if log.actor else None,
            actor_email=log.actor.email if log.actor else None,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            metadata_json=log.metadata_json,
            created_at=log.created_at,
        )
        for log in items
    ]
    return PlatformAuditLogListOut(
        items=mapped_items,
        total=total,
        limit=limit,
        offset=offset
    )


@commercial_router.get("/admins", response_model=List[PlatformAdminUserOut])
def list_admins(db: Session = Depends(get_db)):
    users = platform_service.list_platform_admins(db)
    return [PlatformAdminUserOut.model_validate(u) for u in users]


@commercial_router.get("/operators", response_model=List[PlatformAdminUserOut])
def list_operators(db: Session = Depends(get_db)):
    users = platform_service.list_platform_operators(db)
    return [PlatformAdminUserOut.model_validate(u) for u in users]


@commercial_router.get("/businesses/{business_id}/subscriptions", response_model=List[OutletSubscriptionRead])
def list_business_subscriptions(
    business_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    subs = platform_service.list_business_subscriptions(db, business_id=business_id)
    return [OutletSubscriptionRead.model_validate(s) for s in subs]


@commercial_router.patch("/businesses/{business_id}/subscription", response_model=PlatformBusinessOut)
def update_subscription(
    business_id: uuid.UUID,
    data: PlatformSubscriptionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    biz = platform_service.update_business_subscription(
        db, business_id=business_id, data=data, actor_user_id=current_user.id
    )
    return PlatformBusinessOut.model_validate(biz)


@commercial_router.patch("/outlets/{outlet_id}/subscription", response_model=OutletSubscriptionRead)
def update_outlet_subscription(
    outlet_id: uuid.UUID,
    data: PlatformOutletSubscriptionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sub = platform_service.update_outlet_subscription(
        db, outlet_id=outlet_id, data=data, actor_user_id=current_user.id
    )
    return OutletSubscriptionRead.model_validate(sub)


@commercial_router.post("/businesses/{business_id}/assign-owner", response_model=BusinessMembershipOut)
def assign_owner(
    business_id: uuid.UUID,
    data: PlatformAssignOwner,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    mem = platform_service.assign_owner_to_business(
        db, business_id=business_id, data=data, actor_user_id=current_user.id
    )
    return BusinessMembershipOut(
        business_id=mem.business_id,
        business_name=mem.business.name if mem.business else "",
        user_id=mem.user_id,
        role=mem.role,
        created_at=mem.created_at,
        updated_at=mem.updated_at,
    )


@commercial_router.get("/businesses/{business_id}/entitlements", response_model=PlatformBusinessEntitlementsOut)
def inspect_business_entitlements(
    business_id: uuid.UUID,
    outlet_id: Optional[uuid.UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return EntitlementService.inspect_all_entitlements(
        db=db,
        business_id=business_id,
        outlet_id=outlet_id
    )


@commercial_router.get("/businesses/{business_id}/overrides", response_model=PlatformBusinessOverridesResponse)
def inspect_business_overrides(
    business_id: uuid.UUID,
    include_expired: bool = Query(default=True),
    include_revoked: bool = Query(default=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return EntitlementService.get_business_overrides_history(
        db=db,
        business_id=business_id,
        include_expired=include_expired,
        include_revoked=include_revoked
    )


@commercial_router.post("/businesses/{business_id}/overrides", response_model=PlatformOverrideInspectionItem)
def create_business_override(
    business_id: uuid.UUID,
    data: PlatformOverrideCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return EntitlementService.create_override(
        db=db,
        business_id=business_id,
        data=data,
        actor_user_id=current_user.id
    )


@commercial_router.delete("/businesses/{business_id}/overrides/{override_id}")
def revoke_business_override(
    business_id: uuid.UUID,
    override_id: uuid.UUID,
    data: PlatformOverrideRevoke,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return EntitlementService.revoke_override(
        db=db,
        business_id=business_id,
        override_id=override_id,
        reason=data.reason,
        actor_user_id=current_user.id
    )


# ==============================================================================
# Governance Router Endpoints (owner only, fails closed 503 on zero-owner)
# ==============================================================================

@governance_router.post("/admins/{user_id}/grant", response_model=PlatformAdminUserOut)
def grant_admin(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = platform_service.grant_platform_admin(
        db, target_user_id=user_id, actor_user_id=current_user.id
    )
    return PlatformAdminUserOut.model_validate(user)


@governance_router.post("/admins/{user_id}/revoke", response_model=PlatformAdminUserOut)
def revoke_admin(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = platform_service.revoke_platform_admin(
        db, target_user_id=user_id, actor_user_id=current_user.id
    )
    return PlatformAdminUserOut.model_validate(user)


@governance_router.post("/owner/transfer", response_model=PlatformAdminUserOut)
def transfer_owner(
    data: PlatformOwnerTransferRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        successor = platform_service.transfer_platform_owner(
            db,
            actor_user_id=current_user.id,
            target_user_id=data.target_user_id,
            current_password=data.current_password,
        )
        db.commit()
        db.refresh(successor)
        return PlatformAdminUserOut.model_validate(successor)
    except Exception:
        db.rollback()
        raise


@governance_router.post("/operators", response_model=PlatformAdminUserOut)
def create_operator(
    data: PlatformOperatorCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        operator = platform_service.create_platform_operator(
            db, data=data, actor_user_id=current_user.id
        )
        db.commit()
        db.refresh(operator)
        return PlatformAdminUserOut.model_validate(operator)
    except Exception:
        db.rollback()
        raise


@governance_router.post("/operators/{user_id}/revoke", response_model=PlatformAdminUserOut)
def revoke_operator(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        operator = platform_service.revoke_platform_operator(
            db, target_user_id=user_id, actor_user_id=current_user.id
        )
        db.commit()
        db.refresh(operator)
        return PlatformAdminUserOut.model_validate(operator)
    except Exception:
        db.rollback()
        raise


@governance_router.post("/users/{id}/suspend", response_model=PlatformAdminUserOut)
def suspend_user(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        user = platform_service.suspend_platform_user(
            db, target_user_id=id, actor_user_id=current_user.id
        )
        db.commit()
        db.refresh(user)
        return PlatformAdminUserOut.model_validate(user)
    except Exception:
        db.rollback()
        raise


@governance_router.post("/users/{id}/reactivate", response_model=PlatformAdminUserOut)
def reactivate_user(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        user = platform_service.reactivate_platform_user(
            db, target_user_id=id, actor_user_id=current_user.id
        )
        db.commit()
        db.refresh(user)
        return PlatformAdminUserOut.model_validate(user)
    except Exception:
        db.rollback()
        raise


# ==============================================================================
# Operations Router Endpoints (owner, admin)
# ==============================================================================

@operations_router.post("/businesses", response_model=PlatformBusinessOut)
def create_business(
    data: PlatformBusinessCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    biz = platform_service.create_platform_business(db, data=data, actor_user_id=current_user.id)
    return PlatformBusinessOut.model_validate(biz)


@operations_router.post("/businesses/{business_id}/outlets", response_model=PlatformOutletOut)
def create_outlet(
    business_id: uuid.UUID,
    data: PlatformOutletCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    outlet = platform_service.add_outlet_to_business(
        db, business_id=business_id, data=data, actor_user_id=current_user.id
    )
    return PlatformOutletOut.model_validate(outlet)


@operations_router.patch("/businesses/{business_id}", response_model=PlatformBusinessOut)
def update_business_profile(
    business_id: uuid.UUID,
    data: PlatformBusinessProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    biz = platform_service.update_business_profile(
        db, business_id=business_id, data=data, actor_user_id=current_user.id
    )
    return PlatformBusinessOut.model_validate(biz)


@operations_router.patch("/outlets/{outlet_id}", response_model=PlatformOutletDetailOut)
def update_outlet_profile(
    outlet_id: uuid.UUID,
    data: PlatformOutletProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    outlet = platform_service.update_outlet_profile(
        db, outlet_id=outlet_id, data=data, actor_user_id=current_user.id
    )
    out = PlatformOutletDetailOut.model_validate(outlet)
    out.business_name = outlet.business.name if outlet.business else None
    return out


# ==============================================================================
# Profile Router Endpoints (owner, admin, operator — read-only for operators)
# ==============================================================================

@profile_router.get("/businesses", response_model=List[PlatformBusinessOut])
def list_businesses(db: Session = Depends(get_db)):
    return platform_service.list_platform_businesses(db)


@profile_router.get("/plans", response_model=List[PlanRead])
def list_plans(db: Session = Depends(get_db)):
    plans = platform_service.list_canonical_plans(db)
    return [PlanRead.model_validate(p) for p in plans]


@profile_router.get("/businesses/{business_id}", response_model=Union[PlatformBusinessOut, PlatformBusinessProfileOut])
def get_business(
    business_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    biz = platform_service.get_platform_business(db, business_id=business_id)
    is_operator = current_user.platform_role == "operator"
    if is_operator:
        return PlatformBusinessProfileOut.model_validate(biz)
    return PlatformBusinessOut.model_validate(biz)


@profile_router.get("/outlets/{outlet_id}", response_model=PlatformOutletDetailOut)
def get_outlet(
    outlet_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    outlet = platform_service.get_platform_outlet(db, outlet_id=outlet_id)
    out = PlatformOutletDetailOut.model_validate(outlet)
    out.business_name = outlet.business.name if outlet.business else None
    return out


# Include sub-routers into the top-level platform router
router.include_router(governance_router)
router.include_router(commercial_router)
router.include_router(operations_router)
router.include_router(platform_menu_router)
router.include_router(profile_router)




