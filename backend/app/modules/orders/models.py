import uuid
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Numeric, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.outlets.models import Outlet
    from app.modules.tables.models import DiningTable
    from app.modules.staff.models import User
    from app.modules.menus.models import MenuItem


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    outlet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outlets.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    table_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tables.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    waiter_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    order_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)  # pending, confirmed, in_kitchen, served, completed, cancelled
    order_type: Mapped[str] = mapped_column(String(30), default="dine_in", nullable=False)  # dine_in, takeaway, delivery
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    outlet: Mapped["Outlet"] = relationship("Outlet")
    table: Mapped[Optional["DiningTable"]] = relationship("DiningTable")
    waiter: Mapped[Optional["User"]] = relationship("User")
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan"
    )


class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    menu_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("menu_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    special_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    menu_item: Mapped[Optional["MenuItem"]] = relationship("MenuItem")
