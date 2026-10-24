import uuid
from datetime import datetime
from typing import Any, Dict, Optional, List, TYPE_CHECKING
from sqlalchemy import (
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    Index,
    text,
    JSON,
    event,
    inspect,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.orm.attributes import get_history

from app.db.base import Base, TimestampMixin
from app.modules.approvals.sanitization import (
    validate_and_sanitize_payload,
    sanitize_diagnostic_message,
    sanitize_diagnostic_details,
)

if TYPE_CHECKING:
    from app.modules.businesses.models import Business
    from app.modules.outlets.models import Outlet
    from app.modules.staff.models import User


class ApprovalStatus:
    PENDING = "pending"
    NEEDS_INFORMATION = "needs_information"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"

    ALL_STATUSES = {
        PENDING,
        NEEDS_INFORMATION,
        APPROVED,
        REJECTED,
        WITHDRAWN,
        EXPIRED,
    }

    TERMINAL_STATUSES = {
        REJECTED,
        WITHDRAWN,
        EXPIRED,
    }


class ExecutionStatus:
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"

    ALL_STATUSES = {
        NOT_STARTED,
        IN_PROGRESS,
        SUCCEEDED,
        FAILED,
        BLOCKED,
    }


class ApprovalRequest(Base, TimestampMixin):
    __tablename__ = "approval_requests"
    __table_args__ = (
        Index("ix_approval_requests_status", "status"),
        Index("ix_approval_requests_request_type", "request_type"),
        Index("ix_approval_requests_requester_user_id", "requester_user_id"),
        Index("ix_approval_requests_business_id", "business_id"),
        Index("ix_approval_requests_expires_at", "expires_at"),
        Index(
            "ix_approval_requests_idempotency_key",
            "idempotency_key",
            unique=True,
            sqlite_where=text("idempotency_key IS NOT NULL"),
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    # Tenant boundaries (nullable for platform-wide actions; ON DELETE SET NULL preserves audit history)
    business_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="SET NULL"),
        nullable=True,
    )
    outlet_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outlets.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Actor relationships
    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    approver_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Domain classification & target
    request_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Lifecycle & Execution States
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=ApprovalStatus.PENDING,
    )
    execution_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=ExecutionStatus.NOT_STARTED,
    )

    # Payloads & Snapshots (NO credentials / secrets allowed)
    payload_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    previous_state_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Reasons & Notes
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Execution Outcome & Error Diagnostic (Safe, bounded, sanitized diagnostics)
    execution_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_details_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Temporal & Lifecycle Metadata
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Concurrency, Retries & Lineage
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Optimistic Concurrency Control
    # Ensures SQLAlchemy increments version on UPDATE and emits:
    # UPDATE approval_requests ... WHERE id = :id AND version = :version
    # raising StaleDataError if concurrent modification occurred.
    __mapper_args__ = {
        "version_id_col": version
    }

    # Lineage link to previous or corrective request
    parent_request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approval_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ORM Relationships
    business: Mapped[Optional["Business"]] = relationship("Business")
    outlet: Mapped[Optional["Outlet"]] = relationship("Outlet")
    requester: Mapped["User"] = relationship("User", foreign_keys=[requester_user_id])
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approver_user_id])
    parent_request: Mapped[Optional["ApprovalRequest"]] = relationship(
        "ApprovalRequest",
        remote_side="ApprovalRequest.id",
        back_populates="child_requests",
    )
    child_requests: Mapped[List["ApprovalRequest"]] = relationship(
        "ApprovalRequest",
        back_populates="parent_request",
    )
    clarifications: Mapped[List["ApprovalClarification"]] = relationship(
        "ApprovalClarification",
        back_populates="approval_request",
        cascade="all, delete-orphan",
        order_by="ApprovalClarification.created_at.asc()",
    )

    @validates("payload_snapshot")
    def validate_payload_reassignment(self, key: str, value: Any) -> Any:
        insp = inspect(self)
        if insp.has_identity:
            raise ValueError("payload_snapshot is immutable and cannot be modified or reassigned after submission.")
        return value

    @validates("previous_state_snapshot")
    def validate_previous_state_reassignment(self, key: str, value: Any) -> Any:
        insp = inspect(self)
        if insp.has_identity:
            raise ValueError("previous_state_snapshot is immutable and cannot be modified or reassigned after submission.")
        return value

    @validates("execution_error")
    def validate_execution_error(self, key: str, value: Optional[str]) -> Optional[str]:
        return sanitize_diagnostic_message(value)

    @validates("execution_details_json")
    def validate_execution_details(self, key: str, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        return sanitize_diagnostic_details(value)


@event.listens_for(ApprovalRequest, "before_update")
def guard_approval_request_snapshot_immutability(mapper, connection, target: ApprovalRequest) -> None:
    """
    UOW-level listener guaranteeing that neither payload_snapshot nor previous_state_snapshot
    can be mutated (including in-place nested dict/list mutations) on any update flush.
    """
    hist_payload = get_history(target, "payload_snapshot")
    if hist_payload.has_changes():
        raise ValueError("payload_snapshot is strictly immutable once submitted.")

    hist_prev = get_history(target, "previous_state_snapshot")
    if hist_prev.has_changes() and hist_prev.deleted and hist_prev.deleted[0] is not None:
        raise ValueError("previous_state_snapshot is strictly immutable once submitted.")


class ApprovalClarification(Base, TimestampMixin):
    __tablename__ = "approval_clarifications"
    __table_args__ = (
        Index("ix_approval_clarifications_request_id", "approval_request_id"),
        Index("ix_approval_clarifications_author_id", "author_user_id"),
    )

    approval_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approval_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    clarification_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )  # "question", "response", "note"
    message: Mapped[str] = mapped_column(Text, nullable=False)

    approval_request: Mapped["ApprovalRequest"] = relationship(
        "ApprovalRequest",
        back_populates="clarifications",
    )
    author: Mapped["User"] = relationship("User")
