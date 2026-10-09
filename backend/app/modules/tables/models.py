import uuid
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.outlets.models import Outlet


class DiningTable(Base, TimestampMixin):
    __tablename__ = "tables"
    __table_args__ = (
        UniqueConstraint("outlet_id", "table_number", name="uq_outlet_table_number"),
    )

    outlet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outlets.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    table_number: Mapped[str] = mapped_column(String(30), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="available", nullable=False)  # available, occupied, reserved

    outlet: Mapped["Outlet"] = relationship("Outlet")
