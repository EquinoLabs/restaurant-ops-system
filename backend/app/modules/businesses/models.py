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


# =============================================================================
# PROPOSED FUTURE MODEL SPECIFICATION (Phase 2 Design — Not Migrated in DB Yet)
# =============================================================================
# The following model design specification defines the proposed schema for
# database-enforced idempotency and concurrent serialization for platform
# governance operations (e.g. ownership transfer).
#
# DESIGN CONTRACT (To be migrated in future Phase 3 upon approval):
#
# class PlatformIdempotencyRecord(Base, TimestampMixin):
#     __tablename__ = "idempotency_records"
#     __table_args__ = (
#         UniqueConstraint(
#             "key", "operation_type", "actor_user_id",
#             name="uq_idempotency_key_operation_actor"
#         ),
#     )
#
#     id: Mapped[uuid.UUID] = mapped_column(
#         UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
#     )
#     key: Mapped[uuid.UUID] = mapped_column(
#         UUID(as_uuid=True), nullable=False, index=True
#     )
#     operation_type: Mapped[str] = mapped_column(String(50), nullable=False)
#     actor_user_id: Mapped[uuid.UUID] = mapped_column(
#         UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
#     )
#     payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
#     status: Mapped[str] = mapped_column(String(20), nullable=False)  # 'in_progress', 'committed', 'aborted'
#     response_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
#     response_body: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
#     expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
# =============================================================================

