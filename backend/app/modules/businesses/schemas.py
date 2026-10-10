import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
from app.core.config import get_public_image_url


class PlatformOutletOut(BaseModel):
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
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("logo_url", "cover_image_url", mode="before")
    @classmethod
    def resolve_outlet_branding_url(cls, v: Optional[str]) -> Optional[str]:
        return get_public_image_url(v)



class PlatformBusinessOut(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    subscription_status: str = "trial"
    plan_name: Optional[str] = None
    max_outlets: Optional[int] = None
    trial_ends_at: Optional[datetime] = None
    outlets: List[PlatformOutletOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlatformBusinessCreate(BaseModel):
    name: str
    primary_outlet_name: str
    public_slug: str
    currency: str = "INR"
    timezone: str = "Asia/Kolkata"
    address: Optional[str] = None
    subscription_status: Optional[str] = "trial"
    plan_name: Optional[str] = None
    max_outlets: Optional[int] = None
    trial_ends_at: Optional[datetime] = None


class PlatformSubscriptionUpdate(BaseModel):
    subscription_status: Optional[str] = None
    status: Optional[str] = None
    plan_name: Optional[str] = None
    max_outlets: Optional[int] = None
    trial_ends_at: Optional[datetime] = None


class PlatformOutletCreate(BaseModel):
    name: str
    public_slug: str
    currency: str = "INR"
    timezone: str = "Asia/Kolkata"
    address: Optional[str] = None


class PlatformAssignOwner(BaseModel):
    outlet_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    display_name: Optional[str] = None


class PlatformAdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    status: str
    is_platform_admin: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

