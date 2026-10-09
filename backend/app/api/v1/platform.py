import uuid
from typing import List
from fastapi import APIRouter, Depends
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
)
from app.modules.businesses import platform_service

router = APIRouter(prefix="/platform", tags=["platform-admin"], dependencies=[Depends(get_current_platform_admin)])


@router.get("/businesses", response_model=List[PlatformBusinessOut])
def list_businesses(db: Session = Depends(get_db)):
    return platform_service.list_platform_businesses(db)


@router.post("/businesses", response_model=PlatformBusinessOut)
def create_business(data: PlatformBusinessCreate, db: Session = Depends(get_db)):
    biz = platform_service.create_platform_business(db, data)
    return PlatformBusinessOut.model_validate(biz)


@router.patch("/businesses/{business_id}/subscription", response_model=PlatformBusinessOut)
def update_subscription(
    business_id: uuid.UUID,
    data: PlatformSubscriptionUpdate,
    db: Session = Depends(get_db)
):
    biz = platform_service.update_business_subscription(db, business_id=business_id, data=data)
    return PlatformBusinessOut.model_validate(biz)


@router.post("/businesses/{business_id}/outlets", response_model=PlatformOutletOut)
def create_outlet(business_id: uuid.UUID, data: PlatformOutletCreate, db: Session = Depends(get_db)):
    outlet = platform_service.add_outlet_to_business(db, business_id=business_id, data=data)
    return PlatformOutletOut.model_validate(outlet)


@router.post("/businesses/{business_id}/assign-owner", response_model=OutletMembershipOut)
def assign_owner(business_id: uuid.UUID, data: PlatformAssignOwner, db: Session = Depends(get_db)):
    mem = platform_service.assign_owner_to_outlet(db, business_id=business_id, data=data)
    return OutletMembershipOut(
        outlet_id=mem.outlet.id,
        outlet_name=mem.outlet.name,
        public_slug=mem.outlet.public_slug,
        business_id=mem.outlet.business_id,
        business_name=mem.outlet.business.name if mem.outlet.business else "",
        role=mem.role
    )

