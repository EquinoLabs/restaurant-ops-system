import uuid
import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class PlatformAuditLogItemOut(BaseModel):
    id: uuid.UUID
    business_id: Optional[uuid.UUID] = None
    business_name: Optional[str] = None
    outlet_id: Optional[uuid.UUID] = None
    outlet_name: Optional[str] = None
    actor_user_id: Optional[uuid.UUID] = None
    actor_display_name: Optional[str] = None
    actor_email: Optional[str] = None
    action: str
    entity_type: str
    entity_id: uuid.UUID
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class PlatformAuditLogListOut(BaseModel):
    items: List[PlatformAuditLogItemOut]
    total: int
    limit: int
    offset: int
