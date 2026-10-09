import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.modules.outlets.models import Outlet
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
from app.modules.audit.service import log_audit
from app.core.errors import NotFoundError, ValidationError, ForbiddenError


def get_admin_menu(db: Session, outlet_id: uuid.UUID) -> AdminOutletMenuResponse:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.status == "active").first()
    if not outlet:
        raise NotFoundError(f"Outlet with ID '{outlet_id}' not found")

    categories = (
        db.query(MenuCategory)
        .filter(MenuCategory.outlet_id == outlet_id)
        .order_by(MenuCategory.sort_order.asc(), MenuCategory.name.asc())
        .all()
    )

    items = (
        db.query(MenuItem)
        .filter(MenuItem.outlet_id == outlet_id)
        .order_by(MenuItem.sort_order.asc(), MenuItem.name.asc())
        .all()
    )

    items_by_category = {}
    for item in items:
        items_by_category.setdefault(item.category_id, []).append(
            AdminMenuItemSchema.model_validate(item)
        )

    categories_out = []
    for cat in categories:
        cat_schema = AdminMenuCategorySchema(
            id=cat.id,
            outlet_id=cat.outlet_id,
            name=cat.name,
            description=cat.description,
            sort_order=cat.sort_order,
            is_active=cat.is_active,
            items=items_by_category.get(cat.id, []),
            created_at=cat.created_at,
            updated_at=cat.updated_at
        )
        categories_out.append(cat_schema)

    return AdminOutletMenuResponse(
        outlet_id=outlet.id,
        outlet_name=outlet.name,
        public_slug=outlet.public_slug,
        business_id=outlet.business_id,
        currency=outlet.currency,
        categories=categories_out
    )


def create_category(
    db: Session, outlet_id: uuid.UUID, actor_id: uuid.UUID, data: CategoryCreate
) -> MenuCategory:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    if not outlet:
        raise NotFoundError(f"Outlet with ID '{outlet_id}' not found")

    category = MenuCategory(
        outlet_id=outlet_id,
        name=data.name.strip(),
        description=data.description.strip() if data.description else None,
        sort_order=data.sort_order,
        is_active=data.is_active
    )
    db.add(category)
    db.flush()

    log_audit(
        db=db,
        business_id=outlet.business_id,
        outlet_id=outlet_id,
        actor_user_id=actor_id,
        action="CATEGORY_CREATE",
        entity_type="menu_category",
        entity_id=category.id,
        metadata_json={"name": category.name, "sort_order": category.sort_order}
    )
    db.commit()
    db.refresh(category)
    return category


def update_category(
    db: Session, category_id: uuid.UUID, actor_id: uuid.UUID, data: CategoryUpdate
) -> MenuCategory:
    category = db.query(MenuCategory).filter(MenuCategory.id == category_id).first()
    if not category:
        raise NotFoundError(f"Category with ID '{category_id}' not found")

    outlet = db.query(Outlet).filter(Outlet.id == category.outlet_id).first()
    changes = {}

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

    if changes and outlet:
        log_audit(
            db=db,
            business_id=outlet.business_id,
            outlet_id=category.outlet_id,
            actor_user_id=actor_id,
            action="CATEGORY_UPDATE",
            entity_type="menu_category",
            entity_id=category.id,
            metadata_json=changes
        )

    db.commit()
    db.refresh(category)
    return category


def create_menu_item(
    db: Session, outlet_id: uuid.UUID, actor_id: uuid.UUID, data: MenuItemCreate
) -> MenuItem:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    if not outlet:
        raise NotFoundError(f"Outlet with ID '{outlet_id}' not found")

    category = db.query(MenuCategory).filter(
        MenuCategory.id == data.category_id,
        MenuCategory.outlet_id == outlet_id
    ).first()
    if not category:
        raise ValidationError(f"Category with ID '{data.category_id}' does not belong to this outlet")

    item = MenuItem(
        outlet_id=outlet_id,
        category_id=data.category_id,
        name=data.name.strip(),
        description=data.description.strip() if data.description else None,
        price=data.price,
        image_url=data.image_url.strip() if data.image_url else None,
        is_available=data.is_available,
        is_active=data.is_active,
        sort_order=data.sort_order
    )
    db.add(item)
    db.flush()

    log_audit(
        db=db,
        business_id=outlet.business_id,
        outlet_id=outlet_id,
        actor_user_id=actor_id,
        action="ITEM_CREATE",
        entity_type="menu_item",
        entity_id=item.id,
        metadata_json={"name": item.name, "price": str(item.price), "category_id": str(item.category_id)}
    )
    db.commit()
    db.refresh(item)
    return item


def update_menu_item(
    db: Session, item_id: uuid.UUID, actor_id: uuid.UUID, data: MenuItemUpdate
) -> MenuItem:
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise NotFoundError(f"Menu item with ID '{item_id}' not found")

    outlet = db.query(Outlet).filter(Outlet.id == item.outlet_id).first()

    if data.category_id is not None and data.category_id != item.category_id:
        category = db.query(MenuCategory).filter(
            MenuCategory.id == data.category_id,
            MenuCategory.outlet_id == item.outlet_id
        ).first()
        if not category:
            raise ValidationError(f"Category with ID '{data.category_id}' does not belong to this outlet")

    changes = {}

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

    if changes and outlet:
        action_name = "PRICE_CHANGE" if "price" in changes else "ITEM_UPDATE"
        log_audit(
            db=db,
            business_id=outlet.business_id,
            outlet_id=item.outlet_id,
            actor_user_id=actor_id,
            action=action_name,
            entity_type="menu_item",
            entity_id=item.id,
            metadata_json=changes
        )

    db.commit()
    db.refresh(item)
    return item


def toggle_item_availability(
    db: Session, item_id: uuid.UUID, actor_id: uuid.UUID, is_available: bool
) -> MenuItem:
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise NotFoundError(f"Menu item with ID '{item_id}' not found")

    outlet = db.query(Outlet).filter(Outlet.id == item.outlet_id).first()
    old_val = item.is_available

    if old_val != is_available:
        item.is_available = is_available
        if outlet:
            log_audit(
                db=db,
                business_id=outlet.business_id,
                outlet_id=item.outlet_id,
                actor_user_id=actor_id,
                action="AVAILABILITY_TOGGLE",
                entity_type="menu_item",
                entity_id=item.id,
                metadata_json={"is_available": {"old": old_val, "new": is_available}}
            )
        db.commit()
        db.refresh(item)

    return item


def upload_item_image(
    db: Session,
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    actor_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
) -> MenuItem:
    from app.core import r2_storage

    item = db.query(MenuItem).filter(MenuItem.id == item_id, MenuItem.outlet_id == outlet_id).first()
    if not item:
        raise NotFoundError(f"Menu item with ID '{item_id}' not found in outlet '{outlet_id}'")

    outlet = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    old_image_key = item.image_url

    # 1. Upload new image object to R2
    new_image_key = r2_storage.upload_item_image(
        outlet_id=outlet_id,
        item_id=item_id,
        file_bytes=file_bytes,
        filename=filename,
    )

    # 2. Update DB reference
    try:
        item.image_url = new_image_key
        if outlet:
            log_audit(
                db=db,
                business_id=outlet.business_id,
                outlet_id=outlet_id,
                actor_user_id=actor_id,
                action="ITEM_IMAGE_UPDATE",
                entity_type="menu_item",
                entity_id=item.id,
                metadata_json={"old_key": old_image_key, "new_key": new_image_key},
            )
        db.commit()
        db.refresh(item)
    except Exception as e:
        db.rollback()
        # Best effort cleanup of newly uploaded object if DB update fails
        r2_storage.delete_object(new_image_key)
        raise e

    # 3. Best effort cleanup of previous object if it existed
    if old_image_key:
        r2_storage.delete_object(old_image_key)

    return item


def delete_item_image(
    db: Session,
    outlet_id: uuid.UUID,
    item_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> MenuItem:
    from app.core import r2_storage

    item = db.query(MenuItem).filter(MenuItem.id == item_id, MenuItem.outlet_id == outlet_id).first()
    if not item:
        raise NotFoundError(f"Menu item with ID '{item_id}' not found in outlet '{outlet_id}'")

    if not item.image_url:
        return item

    outlet = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    old_image_key = item.image_url

    item.image_url = None
    if outlet:
        log_audit(
            db=db,
            business_id=outlet.business_id,
            outlet_id=outlet_id,
            actor_user_id=actor_id,
            action="ITEM_IMAGE_DELETE",
            entity_type="menu_item",
            entity_id=item.id,
            metadata_json={"old_key": old_image_key},
        )
    db.commit()
    db.refresh(item)

    # Best effort cleanup of R2 object after DB commit succeeds
    r2_storage.delete_object(old_image_key)

    return item

