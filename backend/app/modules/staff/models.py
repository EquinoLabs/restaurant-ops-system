import uuid
from typing import List, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.outlets.models import Outlet


class User(Base, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    memberships: Mapped[List["OutletMembership"]] = relationship(
        "OutletMembership",
        back_populates="user",
        cascade="all, delete-orphan"
    )


class OutletMembership(Base, TimestampMixin):
    __tablename__ = "outlet_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "outlet_id", name="uq_user_outlet_membership"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    outlet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outlets.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False)  # owner, manager, waiter, kitchen

    user: Mapped["User"] = relationship("User", back_populates="memberships")
    outlet: Mapped["Outlet"] = relationship("Outlet")
