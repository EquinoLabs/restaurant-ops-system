import uuid
from typing import Any, Dict, Optional, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.businesses.models import Business
    from app.modules.outlets.models import Outlet
    from app.modules.staff.models import User


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    outlet_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outlets.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    business: Mapped["Business"] = relationship("Business")
    outlet: Mapped[Optional["Outlet"]] = relationship("Outlet")
    actor: Mapped[Optional["User"]] = relationship("User")
