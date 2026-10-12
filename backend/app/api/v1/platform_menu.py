import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user, RequirePlatformRole
from app.modules.staff.models import User
from app.modules.menus.schemas import (
    AdminOutletMenuResponse,
    AdminMenuCategorySchema,
    AdminMenuItemSchema,
    CategoryCreate,
    CategoryUpdate,
    MenuItemCreate,
    MenuItemUpdate,
    AvailabilityToggleRequest,
)
from app.modules.menus import platform_service
from app.core import r2_storage

# Dedicated Platform Menu Sub-Router
# Accessible strictly by Platform Owner, Platform Admin, and Platform Operator.
platform_menu_router = APIRouter(
    dependencies=[
        Depends(RequirePlatformRole(["owner", "admin", "operator"])),
    ]
)


@platform_menu_router.get(
    "/outlets/{outlet_id}/menu",
    response_model=AdminOutletMenuResponse,
)
def get_outlet_menu(
    outlet_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    return platform_service.get_platform_outlet_menu(db, outlet_id=outlet_id)


@platform_menu_router.post(
    "/outlets/{outlet_id}/menu/categories",
    response_model=AdminMenuCategorySchema,
)
def create_category(
    outlet_id: uuid.UUID,
    data: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cat = platform_service.create_platform_category(
        db, outlet_id=outlet_id, actor_id=current_user.id, data=data
    )
    return AdminMenuCategorySchema.model_validate(cat)


@platform_menu_router.patch(
    "/outlets/{outlet_id}/menu/categories/{category_id}",
    response_model=AdminMenuCategorySchema,
)
def update_category(
    outlet_id: uuid.UUID,
    category_id: uuid.UUID,
    data: CategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cat = platform_service.update_platform_category(
        db,
        outlet_id=outlet_id,
        category_id=category_id,
        actor_id=current_user.id,
        data=data,
    )
    return AdminMenuCategorySchema.model_validate(cat)


@platform_menu_router.post(
    "/outlets/{outlet_id}/menu/items",
    response_model=AdminMenuItemSchema,
)
def create_menu_item(
    outlet_id: uuid.UUID,
    data: MenuItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = platform_service.create_platform_menu_item(
        db, outlet_id=outlet_id, actor_id=current_user.id, data=data
    )
    return AdminMenuItemSchema.model_validate(item)


@platform_menu_router.patch(
    "/outlets/{outlet_id}/menu/items/{item_id}",
    response_model=AdminMenuItemSchema,
)
def update_menu_item(
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    data: MenuItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = platform_service.update_platform_menu_item(
        db,
        outlet_id=outlet_id,
        item_id=item_id,
        actor_id=current_user.id,
        data=data,
    )
    return AdminMenuItemSchema.model_validate(item)


@platform_menu_router.patch(
    "/outlets/{outlet_id}/menu/items/{item_id}/availability",
    response_model=AdminMenuItemSchema,
)
def toggle_item_availability(
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    request: AvailabilityToggleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = platform_service.toggle_platform_item_availability(
        db,
        outlet_id=outlet_id,
        item_id=item_id,
        actor_id=current_user.id,
        is_available=request.is_available,
    )
    return AdminMenuItemSchema.model_validate(item)


@platform_menu_router.post(
    "/outlets/{outlet_id}/menu/items/{item_id}/image",
    response_model=AdminMenuItemSchema,
)
def upload_item_image(
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contents = file.file.read()
    r2_storage.validate_image_file(contents, file.filename)
    item = platform_service.upload_platform_item_image(
        db,
        outlet_id=outlet_id,
        item_id=item_id,
        actor_id=current_user.id,
        file_bytes=contents,
        filename=file.filename,
    )
    return AdminMenuItemSchema.model_validate(item)


@platform_menu_router.delete(
    "/outlets/{outlet_id}/menu/items/{item_id}/image",
    response_model=AdminMenuItemSchema,
)
def delete_item_image(
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = platform_service.delete_platform_item_image(
        db,
        outlet_id=outlet_id,
        item_id=item_id,
        actor_id=current_user.id,
    )
    return AdminMenuItemSchema.model_validate(item)
