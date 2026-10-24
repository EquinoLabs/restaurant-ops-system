"""Pydantic schemas for the platform approval workflow HTTP API.

Exposes read-only representations of approval requests and query parameters.
Ensures zero exposure of sensitive fields (password hashes, secret keys, tokens,
connection URIs, raw un-sanitized internal execution exceptions).
"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

from app.modules.approvals.models import ApprovalStatus, ExecutionStatus


class ApprovalClarificationItemOut(BaseModel):
    id: uuid.UUID
    approval_request_id: uuid.UUID
    author_user_id: uuid.UUID
    author_email: Optional[str] = None
    author_display_name: Optional[str] = None
    clarification_type: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalRequestItemOut(BaseModel):
    """
    Summary view of an approval request for list endpoints.
    """
    id: uuid.UUID
    business_id: Optional[uuid.UUID] = None
    outlet_id: Optional[uuid.UUID] = None
    requester_user_id: uuid.UUID
    requester_email: Optional[str] = None
    requester_display_name: Optional[str] = None
    approver_user_id: Optional[uuid.UUID] = None
    approver_email: Optional[str] = None
    approver_display_name: Optional[str] = None
    request_type: str
    target_entity_type: str
    target_entity_id: Optional[uuid.UUID] = None
    status: str
    execution_status: str
    justification: Optional[str] = None
    expires_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalRequestDetailOut(ApprovalRequestItemOut):
    """
    Detailed view of an approval request.
    Includes sanitized payload_snapshot, safe execution metadata,
    and clarification timeline. Excludes raw secrets and database credentials.
    """
    payload_snapshot: Dict[str, Any] = Field(default_factory=dict)
    decision_reason: Optional[str] = None
    execution_started_at: Optional[datetime] = None
    execution_completed_at: Optional[datetime] = None
    execution_error: Optional[str] = None
    execution_details_json: Optional[Dict[str, Any]] = None
    parent_request_id: Optional[uuid.UUID] = None
    clarifications: List[ApprovalClarificationItemOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ApprovalRequestsListResponse(BaseModel):
    """
    Paginated list response container for approval requests.
    """
    items: List[ApprovalRequestItemOut]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)


class ApprovalDecisionRequest(BaseModel):
    """
    Payload for deciding an approval request.
    Enforces that both 'approve' and 'reject' require a non-empty, non-whitespace reason
    as mandated by the authoritative decide_approval_request service.
    """
    decision: str = Field(..., description="Decision must be 'approve' or 'reject'")
    reason: str = Field(..., description="Mandatory non-empty decision justification or reason")

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def model_validate(cls, *args, **kwargs):
        instance = super().model_validate(*args, **kwargs)
        clean_dec = instance.decision.strip().lower() if instance.decision else ""
        if clean_dec not in ("approve", "reject"):
            raise ValueError("decision must be either 'approve' or 'reject'.")
        instance.decision = clean_dec

        if not instance.reason or not instance.reason.strip():
            raise ValueError("A non-empty reason is strictly required to decide an approval request.")
        instance.reason = instance.reason.strip()
        return instance


class ApprovalSubmissionRequest(BaseModel):
    """
    Payload for submitting a new approval request.
    Validates request_type, target_entity_type, payload snapshot, justification,
    and optional idempotency_key. Disallows unknown fields.
    """
    request_type: str = Field(..., min_length=1, max_length=100, description="Type of operation, e.g. operator_creation")
    target_entity_type: str = Field(..., min_length=1, max_length=100, description="Target entity type, e.g. user, operator")
    target_entity_id: Optional[uuid.UUID] = Field(None, description="Optional target entity ID if modifying existing entity")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Operation payload to be sanitized and snapshotted")
    justification: Optional[str] = Field(None, max_length=1000, description="Optional business justification for the request")
    idempotency_key: Optional[str] = Field(None, max_length=255, description="Client idempotency key to prevent duplicate submissions")

    model_config = ConfigDict(extra="forbid")



