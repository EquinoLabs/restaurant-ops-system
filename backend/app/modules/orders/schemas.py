import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class OrderItemCreate(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = 1
    special_instructions: Optional[str] = None


class OrderCreate(BaseModel):
    table_id: Optional[uuid.UUID] = None
    order_type: str = "dine_in"  # dine_in, takeaway, delivery
    items: List[OrderItemCreate]
    notes: Optional[str] = None


class OrderStatusUpdate(BaseModel):
    status: str  # pending, confirmed, in_kitchen, served, completed, cancelled


class OrderItemOut(BaseModel):
    id: uuid.UUID
    menu_item_id: Optional[uuid.UUID] = None
    item_name: str
    unit_price: Decimal
    quantity: int
    subtotal: Decimal
    special_instructions: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OrderOut(BaseModel):
    id: uuid.UUID
    outlet_id: uuid.UUID
    table_id: Optional[uuid.UUID] = None
    table_number: Optional[str] = None
    waiter_user_id: Optional[uuid.UUID] = None
    waiter_name: Optional[str] = None
    order_number: str
    status: str
    order_type: str
    total_amount: Decimal
    notes: Optional[str] = None
    items: List[OrderItemOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
