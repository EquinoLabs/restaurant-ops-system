import logging
import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.modules.outlets.models import Outlet
from app.modules.businesses.models import Business
from app.modules.menus.models import MenuCategory, MenuItem
from app.modules.menus.schemas import (
    AdminOutletMenuResponse,
    AdminMenuCategorySchema,
    AdminMenuItemSchema,
    CategoryCreate,
    CategoryUpdate,
    MenuItemCreate,
    MenuItemUpdate,
)
from app.modules.menus import admin_service
from app.modules.audit.service import log_audit
from app.core.errors import NotFoundError, ValidationError

logger = logging.getLogger("roms.platform_menu_service")


def _get_verified_outlet(db: Session, outlet_id: uuid.UUID) -> Outlet:
    """
    Validates that the outlet exists and belongs to a valid Business record.
    Raises NotFoundError if either the outlet or its business cannot be found.

    NOTE (Known Limitation - L-01):
    Platform mutation operations validate outlet and business existence via this helper
    without filtering on `Outlet.status == 'active'`. However, `get_platform_outlet_menu`
    delegates to `admin_service.get_admin_menu`, which enforces `Outlet.status == 'active'`.
    Consequently, platform operators may mutate categories/items for an inactive outlet,
    while `GET /outlets/{id}/menu` returns 404 until the outlet is activated.
    This asymmetric behavior is preserved as a documented limitation; aligning the
    inactive-outlet policy across read and write operations requires a separate
    product/architectural decision before behavior is changed.
    """
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    if not outlet:
        raise NotFoundError(f"Outlet with ID '{outlet_id}' not found")
    if not outlet.business_id:
        raise NotFoundError(f"Outlet with ID '{outlet_id}' is not associated with a business")
    business = db.query(Business).filter(Business.id == outlet.business_id).first()
    if not business:
        raise NotFoundError(f"Business associated with outlet '{outlet_id}' not found")
    return outlet


def get_platform_outlet_menu(db: Session, outlet_id: uuid.UUID) -> AdminOutletMenuResponse:
    """
    Retrieves full outlet menu structure for platform operators without requiring OutletMembership.
    """
    _get_verified_outlet(db, outlet_id=outlet_id)
    return admin_service.get_admin_menu(db, outlet_id=outlet_id)


def create_platform_category(
    db: Session,
    outlet_id: uuid.UUID,
    actor_id: uuid.UUID,
    data: CategoryCreate,
) -> MenuCategory:
    """
    Provisions a new menu category for the specified outlet.
    Emits a platform audit log event within the same database transaction.
    """
    outlet = _get_verified_outlet(db, outlet_id=outlet_id)

    category = MenuCategory(
        outlet_id=outlet_id,
        name=data.name.strip(),
        description=data.description.strip() if data.description else None,
        sort_order=data.sort_order,
        is_active=data.is_active,
    )
    db.add(category)
    db.flush()

    log_audit(
        db=db,
        business_id=outlet.business_id,
        outlet_id=outlet_id,
        actor_user_id=actor_id,
        action="platform.outlet.menu_category.create",
        entity_type="menu_category",
        entity_id=category.id,
        metadata_json={
            "source": "platform_operator",
            "name": category.name,
            "sort_order": category.sort_order,
        },
    )
    db.commit()
    db.refresh(category)
    return category


def update_platform_category(
    db: Session,
    outlet_id: uuid.UUID,
    category_id: uuid.UUID,
    actor_id: uuid.UUID,
    data: CategoryUpdate,
) -> MenuCategory:
    """
    Updates an existing menu category.
    Validates that the category belongs to the specified outlet.
    Emits a platform audit log event within the transaction if changes are made.
    """
    outlet = _get_verified_outlet(db, outlet_id=outlet_id)

    category = (
        db.query(MenuCategory)
        .filter(MenuCategory.id == category_id, MenuCategory.outlet_id == outlet_id)
        .first()
    )
    if not category:
        raise NotFoundError(f"Menu category with ID '{category_id}' not found in outlet '{outlet_id}'")

    changes: Dict[str, Any] = {}

    if data.name is not None and data.name.strip() != category.name:
        changes["name"] = {"old": category.name, "new": data.name.strip()}
        category.name = data.name.strip()

    if data.description is not None and data.description != category.description:
        changes["description"] = {"old": category.description, "new": data.description}
        category.description = data.description

    if data.sort_order is not None and data.sort_order != category.sort_order:
        changes["sort_order"] = {"old": category.sort_order, "new": data.sort_order}
        category.sort_order = data.sort_order

    if data.is_active is not None and data.is_active != category.is_active:
        changes["is_active"] = {"old": category.is_active, "new": data.is_active}
        category.is_active = data.is_active

    if changes:
        log_audit(
            db=db,
            business_id=outlet.business_id,
            outlet_id=outlet_id,
            actor_user_id=actor_id,
            action="platform.outlet.menu_category.update",
            entity_type="menu_category",
            entity_id=category.id,
            metadata_json={"source": "platform_operator", "changes": changes},
        )

    db.commit()
    db.refresh(category)
    return category


def create_platform_menu_item(
    db: Session,
    outlet_id: uuid.UUID,
    actor_id: uuid.UUID,
    data: MenuItemCreate,
) -> MenuItem:
    """
    Creates a new menu item in the specified outlet.
    Validates that the category exists and belongs to this outlet.
    Emits a platform audit log event within the transaction.
    """
    outlet = _get_verified_outlet(db, outlet_id=outlet_id)

    category = (
        db.query(MenuCategory)
        .filter(MenuCategory.id == data.category_id, MenuCategory.outlet_id == outlet_id)
        .first()
    )
    if not category:
        raise ValidationError(f"Category with ID '{data.category_id}' does not belong to outlet '{outlet_id}'")

    item = MenuItem(
        outlet_id=outlet_id,
        category_id=data.category_id,
        name=data.name.strip(),
        description=data.description.strip() if data.description else None,
        price=data.price,
        image_url=data.image_url.strip() if data.image_url else None,
        is_available=data.is_available,
        is_active=data.is_active,
        sort_order=data.sort_order,
    )
    db.add(item)
    db.flush()

    log_audit(
        db=db,
        business_id=outlet.business_id,
        outlet_id=outlet_id,
        actor_user_id=actor_id,
        action="platform.outlet.menu_item.create",
        entity_type="menu_item",
        entity_id=item.id,
        metadata_json={
            "source": "platform_operator",
            "name": item.name,
            "price": str(item.price),
            "category_id": str(item.category_id),
        },
    )
    db.commit()
    db.refresh(item)
    return item


def update_platform_menu_item(
    db: Session,
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    actor_id: uuid.UUID,
    data: MenuItemUpdate,
) -> MenuItem:
    """
    Updates an existing menu item.
    Validates that the item belongs to the specified outlet.
    If category_id is modified (category reassignment), verifies that the new category belongs to the same outlet.
    Emits a platform audit log event within the transaction if changes are made.
    """
    outlet = _get_verified_outlet(db, outlet_id=outlet_id)

    item = (
        db.query(MenuItem)
        .filter(MenuItem.id == item_id, MenuItem.outlet_id == outlet_id)
        .first()
    )
    if not item:
        raise NotFoundError(f"Menu item with ID '{item_id}' not found in outlet '{outlet_id}'")

    if data.category_id is not None and data.category_id != item.category_id:
        target_category = (
            db.query(MenuCategory)
            .filter(MenuCategory.id == data.category_id, MenuCategory.outlet_id == outlet_id)
            .first()
        )
        if not target_category:
            raise ValidationError(f"Category with ID '{data.category_id}' does not belong to outlet '{outlet_id}'")

    changes: Dict[str, Any] = {}

    if data.name is not None and data.name.strip() != item.name:
        changes["name"] = {"old": item.name, "new": data.name.strip()}
        item.name = data.name.strip()

    if data.description is not None and data.description != item.description:
        changes["description"] = {"old": item.description, "new": data.description}
        item.description = data.description

    if data.price is not None and data.price != item.price:
        changes["price"] = {"old": str(item.price), "new": str(data.price)}
        item.price = data.price

    if data.image_url is not None and data.image_url != item.image_url:
        changes["image_url"] = {"old": item.image_url, "new": data.image_url}
        item.image_url = data.image_url

    if data.is_available is not None and data.is_available != item.is_available:
        changes["is_available"] = {"old": item.is_available, "new": data.is_available}
        item.is_available = data.is_available

    if data.is_active is not None and data.is_active != item.is_active:
        changes["is_active"] = {"old": item.is_active, "new": data.is_active}
        item.is_active = data.is_active

    if data.sort_order is not None and data.sort_order != item.sort_order:
        changes["sort_order"] = {"old": item.sort_order, "new": data.sort_order}
        item.sort_order = data.sort_order

    if data.category_id is not None and data.category_id != item.category_id:
        changes["category_id"] = {"old": str(item.category_id), "new": str(data.category_id)}
        item.category_id = data.category_id

    if changes:
        log_audit(
            db=db,
            business_id=outlet.business_id,
            outlet_id=outlet_id,
            actor_user_id=actor_id,
            action="platform.outlet.menu_item.update",
            entity_type="menu_item",
            entity_id=item.id,
            metadata_json={"source": "platform_operator", "changes": changes},
        )

    db.commit()
    db.refresh(item)
    return item


def toggle_platform_item_availability(
    db: Session,
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    actor_id: uuid.UUID,
    is_available: bool,
) -> MenuItem:
    """
    Toggles the in-stock availability of a menu item for platform operators.
    Validates that the item belongs to the specified outlet.
    Emits a platform audit log event within the transaction if changed.
    """
    outlet = _get_verified_outlet(db, outlet_id=outlet_id)

    item = (
        db.query(MenuItem)
        .filter(MenuItem.id == item_id, MenuItem.outlet_id == outlet_id)
        .first()
    )
    if not item:
        raise NotFoundError(f"Menu item with ID '{item_id}' not found in outlet '{outlet_id}'")

    old_val = item.is_available
    if old_val != is_available:
        item.is_available = is_available
        log_audit(
            db=db,
            business_id=outlet.business_id,
            outlet_id=outlet_id,
            actor_user_id=actor_id,
            action="platform.outlet.menu_item.availability",
            entity_type="menu_item",
            entity_id=item.id,
            metadata_json={"source": "platform_operator", "is_available": {"old": old_val, "new": is_available}},
        )
        db.commit()
        db.refresh(item)

    return item


def upload_platform_item_image(
    db: Session,
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    actor_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
) -> MenuItem:
    """
    Uploads a menu item image to Cloudflare R2 and persists the key in the database.
    Transactional safety & failure handling:
    1. Uploads new image object to R2.
    2. Updates DB and records platform audit event.
    3. If DB update or commit fails, catches exception, immediately rolls back DB,
       and executes best-effort deletion of the newly uploaded R2 object to avoid orphaned storage.
    4. Only after DB commit successfully persists is the previous object deleted from R2.
    """
    from app.core import r2_storage

    outlet = _get_verified_outlet(db, outlet_id=outlet_id)

    item = (
        db.query(MenuItem)
        .filter(MenuItem.id == item_id, MenuItem.outlet_id == outlet_id)
        .first()
    )
    if not item:
        raise NotFoundError(f"Menu item with ID '{item_id}' not found in outlet '{outlet_id}'")

    old_image_key = item.image_url

    # 1. Upload new image object to R2
    new_image_key = r2_storage.upload_item_image(
        outlet_id=outlet_id,
        item_id=item_id,
        file_bytes=file_bytes,
        filename=filename,
    )

    # 2. Update DB reference and log audit
    try:
        item.image_url = new_image_key
        log_audit(
            db=db,
            business_id=outlet.business_id,
            outlet_id=outlet_id,
            actor_user_id=actor_id,
            action="platform.outlet.menu_item.image_upload",
            entity_type="menu_item",
            entity_id=item.id,
            metadata_json={
                "source": "platform_operator",
                "old_key": old_image_key,
                "new_key": new_image_key,
            },
        )
        db.commit()
        db.refresh(item)
    except Exception as e:
        db.rollback()
        # Clean up newly uploaded object if DB update/commit fails
        r2_storage.delete_object(new_image_key)
        raise e

    # 3. Best effort cleanup of previous object if it existed
    if old_image_key:
        try:
            r2_storage.delete_object(old_image_key)
        except Exception as exc:
            logger.warning(
                f"Failed to delete previous R2 object '{old_image_key}' during post-commit cleanup for item '{item_id}' in outlet '{outlet_id}': {exc}"
            )

    return item


def delete_platform_item_image(
    db: Session,
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> MenuItem:
    """
    Deletes the menu item image from database and Cloudflare R2.
    Storage/database failure ordering:
    - Sets image_url = None and commits DB with platform audit log first.
    - Only deletes the R2 object AFTER DB commit succeeds.
    - If R2 deletion fails post-commit, the database state remains consistent (no dangling broken image URL).
      The failure is logged as a warning; the orphaned R2 object can be reconciled via storage lifecycle cleanup.
    """
    from app.core import r2_storage

    outlet = _get_verified_outlet(db, outlet_id=outlet_id)

    item = (
        db.query(MenuItem)
        .filter(MenuItem.id == item_id, MenuItem.outlet_id == outlet_id)
        .first()
    )
    if not item:
        raise NotFoundError(f"Menu item with ID '{item_id}' not found in outlet '{outlet_id}'")

    if not item.image_url:
        return item

    old_image_key = item.image_url
    item.image_url = None

    log_audit(
        db=db,
        business_id=outlet.business_id,
        outlet_id=outlet_id,
        actor_user_id=actor_id,
        action="platform.outlet.menu_item.image_delete",
        entity_type="menu_item",
        entity_id=item.id,
        metadata_json={"source": "platform_operator", "old_key": old_image_key},
    )
    db.commit()
    db.refresh(item)

    # Post-commit cleanup of R2 object (defensively handled so unexpected storage exceptions cannot fail a committed mutation)
    try:
        r2_storage.delete_object(old_image_key)
    except Exception as exc:
        logger.warning(
            f"Failed to delete R2 object '{old_image_key}' during post-commit cleanup for item '{item_id}' in outlet '{outlet_id}': {exc}"
        )

    return item
