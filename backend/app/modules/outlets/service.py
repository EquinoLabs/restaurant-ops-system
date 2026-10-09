import uuid
from typing import Optional
from sqlalchemy.orm import Session
from app.modules.outlets.models import Outlet
from app.modules.outlets.schemas import OutletBrandingUpdate
from app.core.errors import NotFoundError, ValidationError
from app.core import r2_storage


def update_outlet_branding(
    db: Session,
    outlet_id: uuid.UUID,
    data: OutletBrandingUpdate
) -> Outlet:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    if not outlet:
        raise NotFoundError(f"Outlet with ID '{outlet_id}' not found")

    if data.primary_color is not None:
        outlet.primary_color = data.primary_color.strip() if data.primary_color else None

    if data.accent_color is not None:
        outlet.accent_color = data.accent_color.strip() if data.accent_color else None

    if data.logo_url is not None:
        outlet.logo_url = data.logo_url.strip() if data.logo_url else None

    if data.cover_image_url is not None:
        outlet.cover_image_url = data.cover_image_url.strip() if data.cover_image_url else None

    db.commit()
    db.refresh(outlet)
    return outlet


def upload_outlet_branding_image(
    db: Session,
    outlet_id: uuid.UUID,
    image_type: str,
    file_bytes: bytes,
    filename: str
) -> Outlet:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    if not outlet:
        raise NotFoundError(f"Outlet with ID '{outlet_id}' not found")

    if image_type not in ("logo", "cover"):
        raise ValidationError(f"Invalid branding image_type '{image_type}'. Must be 'logo' or 'cover'.")

    folder = f"outlets/{outlet_id}/branding"
    old_key = outlet.logo_url if image_type == "logo" else outlet.cover_image_url

    new_key = r2_storage.upload_image(file_bytes=file_bytes, filename=filename, folder=folder)

    if image_type == "logo":
        outlet.logo_url = new_key
    else:
        outlet.cover_image_url = new_key

    if old_key and old_key != new_key:
        r2_storage.delete_image(old_key)

    db.commit()
    db.refresh(outlet)
    return outlet
