import io
import qrcode
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.modules.businesses.models import Business  # noqa: F401
from app.modules.outlets.models import Outlet
from app.modules.menus.models import MenuCategory, MenuItem
from app.modules.menus.schemas import (
    PublicOutletMenuResponse,
    PublicMenuCategorySchema,
    PublicMenuItemSchema,
)
from app.core.errors import NotFoundException


def get_public_menu_by_slug(db: Session, public_slug: str) -> PublicOutletMenuResponse:
    # Fetch active outlet by public_slug
    stmt = select(Outlet).where(
        Outlet.public_slug == public_slug,
        Outlet.status == "active"
    )
    outlet = db.scalar(stmt)
    if not outlet:
        raise NotFoundException(
            code="OUTLET_NOT_FOUND",
            message=f"Outlet with slug '{public_slug}' was not found or is inactive."
        )

    # Fetch active categories sorted by sort_order
    cat_stmt = select(MenuCategory).where(
        MenuCategory.outlet_id == outlet.id,
        MenuCategory.is_active == True
    ).order_by(MenuCategory.sort_order.asc(), MenuCategory.name.asc())
    categories = db.scalars(cat_stmt).all()

    # Fetch active menu items for this outlet sorted by sort_order
    items_stmt = select(MenuItem).where(
        MenuItem.outlet_id == outlet.id,
        MenuItem.is_active == True
    ).order_by(MenuItem.sort_order.asc(), MenuItem.name.asc())
    items = db.scalars(items_stmt).all()

    # Group items by category_id
    items_by_category = {}
    for item in items:
        items_by_category.setdefault(item.category_id, []).append(
            PublicMenuItemSchema.model_validate(item)
        )

    category_schemas = []
    for cat in categories:
        cat_items = items_by_category.get(cat.id, [])
        cat_schema = PublicMenuCategorySchema(
            id=cat.id,
            name=cat.name,
            description=cat.description,
            sort_order=cat.sort_order,
            items=cat_items
        )
        category_schemas.append(cat_schema)

    return PublicOutletMenuResponse(
        outlet_id=outlet.id,
        outlet_name=outlet.name,
        public_slug=outlet.public_slug,
        currency=outlet.currency,
        timezone=outlet.timezone,
        address=outlet.address,
        categories=category_schemas
    )


def generate_outlet_qr_code(db: Session, public_slug: str, base_url: str = "http://localhost:5173") -> bytes:
    # Fetch active outlet by public_slug
    stmt = select(Outlet).where(
        Outlet.public_slug == public_slug,
        Outlet.status == "active"
    )
    outlet = db.scalar(stmt)
    if not outlet:
        raise NotFoundException(
            code="OUTLET_NOT_FOUND",
            message=f"Outlet with slug '{public_slug}' was not found or is inactive."
        )

    # Construct the permanent public menu URL
    target_url = f"{base_url.rstrip('/')}/m/{public_slug}"

    # Generate QR Code image in memory
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(target_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
