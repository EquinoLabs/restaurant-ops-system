import uuid
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class Outlet(Base, TimestampMixin):
    __tablename__ = "outlets"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    public_slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    address: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    # Dynamic branding fields
    logo_url: Mapped[str] = mapped_column(String(500), nullable=True)
    cover_image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[str] = mapped_column(String(20), nullable=True)
    accent_color: Mapped[str] = mapped_column(String(20), nullable=True)

    business = relationship("Business", back_populates="outlets")
    categories = relationship("MenuCategory", back_populates="outlet", cascade="all, delete-orphan")
    items = relationship("MenuItem", back_populates="outlet", cascade="all, delete-orphan")

