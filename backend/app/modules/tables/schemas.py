import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class TableCreate(BaseModel):
    table_number: str
    capacity: int = 4


class TableUpdate(BaseModel):
    table_number: Optional[str] = None
    capacity: Optional[int] = None
    status: Optional[str] = None  # available, occupied, reserved


class TableOut(BaseModel):
    id: uuid.UUID
    outlet_id: uuid.UUID
    table_number: str
    capacity: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
