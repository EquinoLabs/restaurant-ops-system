from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, ConfigDict


# --- Public Schemas ---

class PublicMenuItemSchema(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    price: Decimal
    image_url: Optional[str] = None
    is_available: bool
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class PublicMenuCategorySchema(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    sort_order: int
    items: List[PublicMenuItemSchema] = []

    model_config = ConfigDict(from_attributes=True)


class PublicOutletMenuResponse(BaseModel):
    outlet_id: UUID
    outlet_name: str
    public_slug: str
    currency: str
    timezone: str
    address: Optional[str] = None
    categories: List[PublicMenuCategorySchema] = []

    model_config = ConfigDict(from_attributes=True)


# --- Admin Schemas ---

class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class MenuItemCreate(BaseModel):
    category_id: UUID
    name: str
    description: Optional[str] = None
    price: Decimal
    image_url: Optional[str] = None
    is_available: bool = True
    is_active: bool = True
    sort_order: int = 0


class MenuItemUpdate(BaseModel):
    category_id: Optional[UUID] = None
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    image_url: Optional[str] = None
    is_available: Optional[bool] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class AvailabilityToggleRequest(BaseModel):
    is_available: bool


class AdminMenuItemSchema(BaseModel):
    id: UUID
    outlet_id: UUID
    category_id: UUID
    name: str
    description: Optional[str] = None
    price: Decimal
    image_url: Optional[str] = None
    is_available: bool
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminMenuCategorySchema(BaseModel):
    id: UUID
    outlet_id: UUID
    name: str
    description: Optional[str] = None
    sort_order: int
    is_active: bool
    items: List[AdminMenuItemSchema] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminOutletMenuResponse(BaseModel):
    outlet_id: UUID
    outlet_name: str
    public_slug: str
    business_id: UUID
    currency: str
    categories: List[AdminMenuCategorySchema] = []

    model_config = ConfigDict(from_attributes=True)


class AuditLogOut(BaseModel):
    id: UUID
    actor_user_id: Optional[UUID] = None
    actor_name: Optional[str] = None
    action: str
    entity_type: str
    entity_id: UUID
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
