import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class OrderItemCreate(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = 1
    special_instructions: Optional[str] = None


class OrderCreate(BaseModel):
    table_id: Optional[uuid.UUID] = None
    order_type: str = "dine_in"  # dine_in, takeaway, delivery
    items: List[OrderItemCreate]
    notes: Optional[str] = None


class PublicOrderItemCreate(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = Field(default=1, ge=1, le=99)
    special_instructions: Optional[str] = Field(default=None, max_length=500)


class PublicOrderCreate(BaseModel):
    table_number: Optional[str] = Field(default=None, max_length=30)
    order_type: Optional[str] = Field(default=None, max_length=30)
    items: List[PublicOrderItemCreate] = Field(..., min_length=1, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=500)
    idempotency_key: Optional[str] = Field(default=None, max_length=100)



class OrderStatusUpdate(BaseModel):
    status: str  # pending, confirmed, in_kitchen, served, completed, cancelled


class OrderSettlementRequest(BaseModel):
    payment_method: str = Field(..., description="Payment method: cash or upi")
    confirm: bool = Field(True, description="Explicit confirmation that payment was collected")


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
    payment_status: str = "unpaid"
    payment_method: Optional[str] = None
    settled_at: Optional[datetime] = None
    settled_by_user_id: Optional[uuid.UUID] = None
    settled_by_name: Optional[str] = None
    items: List[OrderItemOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
