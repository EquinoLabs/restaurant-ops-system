import uuid
import re
import zoneinfo
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, Field
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



class PlatformBusinessProfileOut(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    outlets: List[PlatformOutletOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlatformBusinessOut(PlatformBusinessProfileOut):
    subscription_status: str = "trial"
    plan_name: Optional[str] = None
    max_outlets: Optional[int] = None
    trial_ends_at: Optional[datetime] = None


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

    @field_validator("trial_ends_at", mode="before")
    @classmethod
    def validate_utc_datetime(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError as e:
                raise ValueError(f"Invalid ISO datetime string: {v}") from e
        elif isinstance(v, datetime):
            dt = v
        else:
            raise ValueError("Expected datetime string or datetime object.")

        if dt.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware (UTC). Ambiguous naive datetimes are rejected.")
        return dt.astimezone(timezone.utc)


class PlatformSubscriptionUpdate(BaseModel):
    action_type: Optional[str] = None
    plan_code: Optional[str] = None
    plan_name: Optional[str] = None
    subscription_status: Optional[str] = None
    status: Optional[str] = None
    max_outlets: Optional[int] = None
    trial_ends_at: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: Optional[bool] = None
    reason: Optional[str] = None

    @field_validator("trial_ends_at", "current_period_start", "current_period_end", mode="before")
    @classmethod
    def validate_utc_datetime(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError as e:
                raise ValueError(f"Invalid ISO datetime string: {v}") from e
        elif isinstance(v, datetime):
            dt = v
        else:
            raise ValueError("Expected datetime string or datetime object.")

        if dt.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware (UTC). Ambiguous naive datetimes are rejected.")
        return dt.astimezone(timezone.utc)


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
    platform_role: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlatformBusinessProfileUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Business legal/display name")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Business name cannot be empty or whitespace only.")
        return clean


class PlatformOutletDetailOut(PlatformOutletOut):
    business_name: Optional[str] = None


class PlatformOutletProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    address: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
    primary_color: Optional[str] = None
    accent_color: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if not clean:
                raise ValueError("Outlet name cannot be empty or whitespace only.")
            return clean
        return None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if not clean:
                raise ValueError("Timezone cannot be empty or whitespace.")
            try:
                zoneinfo.ZoneInfo(clean)
            except Exception:
                raise ValueError(f"Invalid timezone identifier: '{clean}'. Must be a valid IANA timezone name (e.g. 'Asia/Kolkata').")
            return clean
        return None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip().upper()
            if len(clean) != 3 or not clean.isalpha():
                raise ValueError(f"Invalid currency code: '{clean}'. Must be a 3-letter ISO currency code (e.g. 'INR', 'USD').")
            return clean
        return None

    @field_validator("primary_color", "accent_color")
    @classmethod
    def validate_hex_color(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if clean == "":
                return None
            if not re.match(r"^#[0-9a-fA-F]{6}$", clean):
                raise ValueError(f"Invalid hex color format: '{clean}'. Must be in #RRGGBB format (e.g. '#4F46E5').")
            return clean.upper()
        return None

