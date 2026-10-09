import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator
from app.core.config import get_public_image_url


class OutletBrandingUpdate(BaseModel):
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    primary_color: Optional[str] = None
    accent_color: Optional[str] = None


class OutletBrandingOut(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    name: str
    public_slug: str
    currency: str
    timezone: str
    address: Optional[str] = None
    status: str
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    primary_color: Optional[str] = None
    accent_color: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("logo_url", "cover_image_url", mode="before")
    @classmethod
    def resolve_outlet_branding_url(cls, v: Optional[str]) -> Optional[str]:
        return get_public_image_url(v)
