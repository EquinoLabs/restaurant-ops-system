import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user, RequireOutletRole
from app.modules.staff.models import User, OutletMembership
from app.modules.menus.schemas import (
    AdminOutletMenuResponse,
    AdminMenuCategorySchema,
    AdminMenuItemSchema,
    CategoryCreate,
    CategoryUpdate,
    MenuItemCreate,
    MenuItemUpdate,
    AvailabilityToggleRequest,
    AuditLogOut,
)
from app.modules.menus import admin_service
from app.modules.audit import service as audit_service
from app.modules.menus.models import MenuCategory, MenuItem
from app.core.errors import NotFoundError, ForbiddenError

router = APIRouter(tags=["admin-menu"])


def _verify_item_membership(db: Session, item_id: uuid.UUID, user_id: uuid.UUID, allowed_roles: Optional[List[str]] = None) -> MenuItem:
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise NotFoundError(f"Menu item with ID '{item_id}' not found")
    membership = db.query(OutletMembership).filter(
        OutletMembership.outlet_id == item.outlet_id,
        OutletMembership.user_id == user_id
    ).first()
    if not membership:
        raise ForbiddenError("You do not have access to this outlet")
    if allowed_roles and membership.role not in allowed_roles:
        raise ForbiddenError(f"Role '{membership.role}' is not authorized to perform this operation")
    return item


def _verify_category_membership(db: Session, category_id: uuid.UUID, user_id: uuid.UUID, allowed_roles: Optional[List[str]] = None) -> MenuCategory:
    cat = db.query(MenuCategory).filter(MenuCategory.id == category_id).first()
    if not cat:
        raise NotFoundError(f"Category with ID '{category_id}' not found")
    membership = db.query(OutletMembership).filter(
        OutletMembership.outlet_id == cat.outlet_id,
        OutletMembership.user_id == user_id
    ).first()
    if not membership:
        raise ForbiddenError("You do not have access to this outlet")
    if allowed_roles and membership.role not in allowed_roles:
        raise ForbiddenError(f"Role '{membership.role}' is not authorized to perform this operation")
    return cat


@router.get(
    "/outlets/{outlet_id}/admin/menu",
    response_model=AdminOutletMenuResponse,
    dependencies=[Depends(RequireOutletRole(["owner", "manager", "waiter", "kitchen"]))]
)
def get_admin_menu(outlet_id: uuid.UUID, db: Session = Depends(get_db)):
    return admin_service.get_admin_menu(db, outlet_id=outlet_id)


@router.post(
    "/outlets/{outlet_id}/categories",
    response_model=AdminMenuCategorySchema,
    dependencies=[Depends(RequireOutletRole(["owner", "manager"]))]
)
def create_category(
    outlet_id: uuid.UUID,
    data: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cat = admin_service.create_category(db, outlet_id=outlet_id, actor_id=current_user.id, data=data)
    return AdminMenuCategorySchema.model_validate(cat)


@router.patch("/categories/{category_id}", response_model=AdminMenuCategorySchema)
def update_category(
    category_id: uuid.UUID,
    data: CategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _verify_category_membership(db, category_id=category_id, user_id=current_user.id, allowed_roles=["owner", "manager"])
    cat = admin_service.update_category(db, category_id=category_id, actor_id=current_user.id, data=data)
    return AdminMenuCategorySchema.model_validate(cat)


@router.post(
    "/outlets/{outlet_id}/items",
    response_model=AdminMenuItemSchema,
    dependencies=[Depends(RequireOutletRole(["owner", "manager"]))]
)
def create_item(
    outlet_id: uuid.UUID,
    data: MenuItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    item = admin_service.create_menu_item(db, outlet_id=outlet_id, actor_id=current_user.id, data=data)
    return AdminMenuItemSchema.model_validate(item)


@router.patch("/items/{item_id}", response_model=AdminMenuItemSchema)
def update_item(
    item_id: uuid.UUID,
    data: MenuItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _verify_item_membership(db, item_id=item_id, user_id=current_user.id, allowed_roles=["owner", "manager"])
    item = admin_service.update_menu_item(db, item_id=item_id, actor_id=current_user.id, data=data)
    return AdminMenuItemSchema.model_validate(item)


@router.post("/items/{item_id}/availability", response_model=AdminMenuItemSchema)
def toggle_item_availability(
    item_id: uuid.UUID,
    request: AvailabilityToggleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _verify_item_membership(db, item_id=item_id, user_id=current_user.id, allowed_roles=["owner", "manager", "waiter", "kitchen"])
    item = admin_service.toggle_item_availability(
        db, item_id=item_id, actor_id=current_user.id, is_available=request.is_available
    )
    return AdminMenuItemSchema.model_validate(item)


@router.post(
    "/outlets/{outlet_id}/items/{item_id}/image",
    response_model=AdminMenuItemSchema,
    dependencies=[Depends(RequireOutletRole(["owner", "manager"]))]
)
async def upload_item_image(
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _verify_item_membership(db, item_id=item_id, user_id=current_user.id, allowed_roles=["owner", "manager"])
    file_bytes = await file.read()
    item = admin_service.upload_item_image(
        db=db,
        outlet_id=outlet_id,
        item_id=item_id,
        actor_id=current_user.id,
        file_bytes=file_bytes,
        filename=file.filename or "image.jpg",
    )
    return AdminMenuItemSchema.model_validate(item)


@router.delete(
    "/outlets/{outlet_id}/items/{item_id}/image",
    response_model=AdminMenuItemSchema,
    dependencies=[Depends(RequireOutletRole(["owner", "manager"]))]
)
def delete_item_image(
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _verify_item_membership(db, item_id=item_id, user_id=current_user.id, allowed_roles=["owner", "manager"])
    item = admin_service.delete_item_image(
        db=db,
        outlet_id=outlet_id,
        item_id=item_id,
        actor_id=current_user.id,
    )
    return AdminMenuItemSchema.model_validate(item)



@router.get(
    "/outlets/{outlet_id}/audit-logs",
    response_model=List[AuditLogOut],
    dependencies=[Depends(RequireOutletRole(["owner", "manager"]))]
)
def get_audit_logs(outlet_id: uuid.UUID, db: Session = Depends(get_db)):
    logs = audit_service.get_outlet_audit_logs(db, outlet_id=outlet_id)
    out = []
    for log in logs:
        out.append(
            AuditLogOut(
                id=log.id,
                actor_user_id=log.actor_user_id,
                actor_name=log.actor.display_name if log.actor else "System",
                action=log.action,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                metadata_json=log.metadata_json,
                created_at=log.created_at
            )
        )
    return out
