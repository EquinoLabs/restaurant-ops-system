import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    plan_features = relationship("PlanFeature", back_populates="plan", cascade="all, delete-orphan")
    subscriptions = relationship("BusinessSubscription", back_populates="plan")


class Feature(Base, TimestampMixin):
    __tablename__ = "features"

    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    plan_features = relationship("PlanFeature", back_populates="feature", cascade="all, delete-orphan")


class PlanFeature(Base, TimestampMixin):
    __tablename__ = "plan_features"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False
    )
    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("features.id", ondelete="CASCADE"), nullable=False
    )
    limit_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    plan = relationship("Plan", back_populates="plan_features")
    feature = relationship("Feature", back_populates="plan_features")

    __table_args__ = (
        UniqueConstraint("plan_id", "feature_id", name="uq_plan_feature"),
    )


class BusinessSubscription(Base, TimestampMixin):
    __tablename__ = "business_subscriptions"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="trial")
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    business = relationship("Business", backref="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")


class EntitlementOverride(Base, TimestampMixin):
    __tablename__ = "entitlement_overrides"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    outlet_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("outlets.id", ondelete="CASCADE"), nullable=True
    )
    feature_code: Mapped[str] = mapped_column(String(100), nullable=False)
    override_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "grant" or "restrict"
    limit_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    business = relationship("Business", backref="entitlement_overrides")
    outlet = relationship("Outlet", backref="entitlement_overrides")
