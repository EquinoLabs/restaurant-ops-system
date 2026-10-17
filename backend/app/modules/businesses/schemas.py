import uuid
import re
import zoneinfo
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, Field, model_validator
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
    owner_email: EmailStr = Field(..., description="Owner email (required at business creation)")
    owner_password: str = Field(..., min_length=8, description="Initial owner password set by platform admin")
    owner_display_name: str = Field(..., min_length=1, max_length=150, description="Owner display name")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Business name cannot be empty or whitespace only.")
        if len(clean) < 2:
            raise ValueError("Business name must be at least 2 characters.")
        if len(clean) > 200:
            raise ValueError("Business name must be at most 200 characters.")
        return clean

    @field_validator("owner_password")
    @classmethod
    def validate_owner_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Owner password must be at least 8 characters.")
        return v

    @field_validator("owner_display_name")
    @classmethod
    def validate_owner_display_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Owner display name cannot be empty.")
        return clean


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


class PlatformOutletManagerPayload(BaseModel):
    """Optional manager assignment on outlet creation."""
    user_id: Optional[uuid.UUID] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=8)
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=150)

    @model_validator(mode="after")
    def validate_mutually_exclusive_modes(self):
        is_existing_mode = self.user_id is not None
        has_new_fields = (
            (self.email is not None)
            or (self.password is not None)
            or (self.display_name is not None)
        )
        if is_existing_mode and has_new_fields:
            raise ValueError(
                "Ambiguous manager request: specify either 'user_id' for existing-user assignment "
                "OR ('email', 'password', 'display_name') for new-user creation, not both."
            )
        if is_existing_mode:
            return self
        if has_new_fields:
            if not (self.email and self.password and self.display_name):
                raise ValueError(
                    "Incomplete manager request: new-user creation requires 'email', 'password', "
                    "and 'display_name'. Alternatively, supply 'user_id' to assign an existing user."
                )
        # If no fields provided, this is an unset/empty payload — allowed
        return self


class PlatformOutletCreate(BaseModel):
    name: str
    public_slug: str
    currency: str = "INR"
    timezone: str = "Asia/Kolkata"
    address: Optional[str] = None
    plan_code: str = "trial"
    manager: Optional[PlatformOutletManagerPayload] = None


class PlatformAssignOwner(BaseModel):
    """Business-scoped owner assignment. No outlet_id — owner applies to all outlets."""
    user_id: Optional[uuid.UUID] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    display_name: Optional[str] = None

    @model_validator(mode="after")
    def validate_mutually_exclusive_modes(self):
        is_existing_mode = self.user_id is not None
        has_new_fields = (
            (self.email is not None)
            or (self.password is not None)
            or (self.display_name is not None)
        )
        if is_existing_mode and has_new_fields:
            raise ValueError(
                "Ambiguous request: specify either 'user_id' for existing-user assignment "
                "OR ('email', 'password', 'display_name') for new-user creation, not both."
            )
        if not is_existing_mode and not has_new_fields:
            raise ValueError(
                "Incomplete request: either 'user_id' or ('email', 'password', 'display_name') required."
            )
        return self


class PlatformOwnerTransferRequest(BaseModel):
    target_user_id: uuid.UUID = Field(..., description="UUID of the active user receiving the Platform Owner role")
    current_password: str = Field(..., min_length=1, description="Current password of the authenticated Platform Owner")


class PlatformOperatorCreateRequest(BaseModel):
    user_id: Optional[uuid.UUID] = Field(
        default=None,
        description="UUID of an existing active user to promote to Operator (Existing-User Mode)"
    )
    email: Optional[EmailStr] = Field(
        default=None,
        description="Email address for new Operator account (New-User Mode)"
    )
    password: Optional[str] = Field(
        default=None,
        min_length=8,
        description="Password for new Operator account (New-User Mode)"
    )
    display_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=150,
        description="Display name for new Operator account (New-User Mode)"
    )

    @model_validator(mode="after")
    def validate_mutually_exclusive_modes(self):
        is_existing_mode = self.user_id is not None
        has_new_fields = (
            (self.email is not None)
            or (self.password is not None)
            or (self.display_name is not None)
        )

        if is_existing_mode and has_new_fields:
            raise ValueError(
                "Ambiguous request: specify either 'user_id' for existing-user assignment "
                "OR ('email', 'password', 'display_name') for new-user creation, not both."
            )

        if not is_existing_mode:
            if not (self.email and self.password and self.display_name):
                raise ValueError(
                    "Incomplete request: new-user creation requires 'email', 'password', "
                    "and 'display_name'. Alternatively, supply 'user_id' to promote an existing user."
                )

        return self


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
    status: Optional[str] = Field(default=None, description="Operational status: 'active' or 'suspended'")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Business name cannot be empty or whitespace only.")
        return clean

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.strip().lower()
        if clean not in ("active", "suspended"):
            raise ValueError(f"Invalid status '{clean}'. Allowed: ['active', 'suspended']")
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

