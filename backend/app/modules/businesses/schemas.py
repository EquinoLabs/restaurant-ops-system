import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict


class PlatformOutletOut(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    name: str
    public_slug: str
    currency: str
    timezone: str
    address: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlatformBusinessOut(BaseModel):
    id: uuid.UUID
    name: str
    status: str
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
