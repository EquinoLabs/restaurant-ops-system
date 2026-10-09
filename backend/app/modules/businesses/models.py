from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class Business(Base, TimestampMixin):
    __tablename__ = "businesses"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    # Subscription and account status fields
    subscription_status: Mapped[str] = mapped_column(String(20), nullable=False, default="trial")
    plan_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    max_outlets: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    outlets = relationship("Outlet", back_populates="business", cascade="all, delete-orphan")

