import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_platform_admin
from app.modules.staff.models import User
from app.modules.staff.schemas import OutletMembershipOut
from app.modules.businesses.schemas import (
    PlatformBusinessOut,
    PlatformBusinessCreate,
    PlatformOutletOut,
    PlatformOutletCreate,
    PlatformAssignOwner,
    PlatformSubscriptionUpdate,
    PlatformAdminUserOut,
)
from app.modules.businesses import platform_service
from app.modules.subscriptions.schemas import (
    PlatformBusinessEntitlementsOut,
    PlatformBusinessOverridesResponse,
    PlatformOverrideCreate,
    PlatformOverrideRevoke,
    PlatformOverrideInspectionItem,
)
from app.modules.subscriptions.service import EntitlementService
from app.modules.audit.schemas import PlatformAuditLogListOut, PlatformAuditLogItemOut
from app.modules.audit import service as audit_service

router = APIRouter(prefix="/platform", tags=["platform-admin"], dependencies=[Depends(get_current_platform_admin)])


@router.get("/audit-logs", response_model=PlatformAuditLogListOut)
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



@router.get("/admins", response_model=List[PlatformAdminUserOut])
def list_admins(db: Session = Depends(get_db)):
    users = platform_service.list_platform_admins(db)
    return [PlatformAdminUserOut.model_validate(u) for u in users]


@router.post("/admins/{user_id}/grant", response_model=PlatformAdminUserOut)
def grant_admin(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_platform_admin),
    db: Session = Depends(get_db)
):
    user = platform_service.grant_platform_admin(
        db, target_user_id=user_id, actor_user_id=current_user.id
    )
    return PlatformAdminUserOut.model_validate(user)


@router.post("/admins/{user_id}/revoke", response_model=PlatformAdminUserOut)
def revoke_admin(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_platform_admin),
    db: Session = Depends(get_db)
):
    user = platform_service.revoke_platform_admin(
        db, target_user_id=user_id, actor_user_id=current_user.id
    )
    return PlatformAdminUserOut.model_validate(user)


@router.get("/businesses", response_model=List[PlatformBusinessOut])
def list_businesses(db: Session = Depends(get_db)):
    return platform_service.list_platform_businesses(db)


@router.post("/businesses", response_model=PlatformBusinessOut)
def create_business(
    data: PlatformBusinessCreate,
    current_user: User = Depends(get_current_platform_admin),
    db: Session = Depends(get_db)
):
    biz = platform_service.create_platform_business(db, data=data, actor_user_id=current_user.id)
    return PlatformBusinessOut.model_validate(biz)


@router.patch("/businesses/{business_id}/subscription", response_model=PlatformBusinessOut)
def update_subscription(
    business_id: uuid.UUID,
    data: PlatformSubscriptionUpdate,
    current_user: User = Depends(get_current_platform_admin),
    db: Session = Depends(get_db)
):
    biz = platform_service.update_business_subscription(
        db, business_id=business_id, data=data, actor_user_id=current_user.id
    )
    return PlatformBusinessOut.model_validate(biz)


@router.post("/businesses/{business_id}/outlets", response_model=PlatformOutletOut)
def create_outlet(
    business_id: uuid.UUID,
    data: PlatformOutletCreate,
    current_user: User = Depends(get_current_platform_admin),
    db: Session = Depends(get_db)
):
    outlet = platform_service.add_outlet_to_business(
        db, business_id=business_id, data=data, actor_user_id=current_user.id
    )
    return PlatformOutletOut.model_validate(outlet)


@router.post("/businesses/{business_id}/assign-owner", response_model=OutletMembershipOut)
def assign_owner(
    business_id: uuid.UUID,
    data: PlatformAssignOwner,
    current_user: User = Depends(get_current_platform_admin),
    db: Session = Depends(get_db)
):
    mem = platform_service.assign_owner_to_outlet(
        db, business_id=business_id, data=data, actor_user_id=current_user.id
    )
    return OutletMembershipOut(
        outlet_id=mem.outlet.id,
        outlet_name=mem.outlet.name,
        public_slug=mem.outlet.public_slug,
        business_id=mem.outlet.business_id,
        business_name=mem.outlet.business.name if mem.outlet.business else "",
        role=mem.role
    )


@router.get("/businesses/{business_id}/entitlements", response_model=PlatformBusinessEntitlementsOut)
def inspect_business_entitlements(
    business_id: uuid.UUID,
    outlet_id: Optional[uuid.UUID] = Query(default=None),
    current_user: User = Depends(get_current_platform_admin),
    db: Session = Depends(get_db)
):
    return EntitlementService.inspect_all_entitlements(
        db=db,
        business_id=business_id,
        outlet_id=outlet_id
    )


@router.get("/businesses/{business_id}/overrides", response_model=PlatformBusinessOverridesResponse)
def inspect_business_overrides(
    business_id: uuid.UUID,
    include_expired: bool = Query(default=True),
    include_revoked: bool = Query(default=True),
    current_user: User = Depends(get_current_platform_admin),
    db: Session = Depends(get_db)
):
    return EntitlementService.get_business_overrides_history(
        db=db,
        business_id=business_id,
        include_expired=include_expired,
        include_revoked=include_revoked
    )


@router.post("/businesses/{business_id}/overrides", response_model=PlatformOverrideInspectionItem)
def create_business_override(
    business_id: uuid.UUID,
    data: PlatformOverrideCreate,
    current_user: User = Depends(get_current_platform_admin),
    db: Session = Depends(get_db)
):
    return EntitlementService.create_override(
        db=db,
        business_id=business_id,
        data=data,
        actor_user_id=current_user.id
    )


@router.delete("/businesses/{business_id}/overrides/{override_id}")
def revoke_business_override(
    business_id: uuid.UUID,
    override_id: uuid.UUID,
    data: PlatformOverrideRevoke,
    current_user: User = Depends(get_current_platform_admin),
    db: Session = Depends(get_db)
):
    return EntitlementService.revoke_override(
        db=db,
        business_id=business_id,
        override_id=override_id,
        reason=data.reason,
        actor_user_id=current_user.id
    )



