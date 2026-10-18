import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlanBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0


class PlanCreate(PlanBase):
    pass


class PlanRead(PlanBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeatureRead(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    category: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanFeatureRead(BaseModel):
    id: uuid.UUID
    plan_id: uuid.UUID
    feature_id: uuid.UUID
    limit_value: Optional[int] = None
    feature: Optional[FeatureRead] = None

    model_config = ConfigDict(from_attributes=True)


class BusinessSubscriptionRead(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    plan_id: uuid.UUID
    status: str
    is_current: bool
    trial_ends_at: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    cancelled_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    plan: Optional[PlanRead] = None

    model_config = ConfigDict(from_attributes=True)


class OutletSubscriptionRead(BaseModel):
    id: uuid.UUID
    outlet_id: uuid.UUID
    business_id: uuid.UUID
    plan_id: uuid.UUID
    status: str
    is_current: bool
    trial_ends_at: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    cancelled_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    plan: Optional[PlanRead] = None

    model_config = ConfigDict(from_attributes=True)


class PlatformOutletSubscriptionUpdate(BaseModel):
    action_type: str
    plan_code: Optional[str] = None
    plan_name: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    reason: Optional[str] = None

    @field_validator("trial_ends_at", "current_period_start", "current_period_end", mode="before")
    @classmethod
    def validate_utc_datetime(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError as e:
                raise ValueError(f"Invalid ISO datetime string: {v}") from e
        elif isinstance(v, datetime):
            dt = v
        else:
            raise ValueError("Expected datetime string or datetime object.")

        if dt.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware (UTC). Ambiguous naive datetimes are rejected.")
        from datetime import timezone
        return dt.astimezone(timezone.utc)


class EntitlementOverrideCreate(BaseModel):
    business_id: uuid.UUID
    outlet_id: Optional[uuid.UUID] = None
    feature_code: str
    override_type: str  # "grant" or "restrict"
    limit_value: Optional[int] = None
    reason: str
    expires_at: Optional[datetime] = None


class EntitlementOverrideRead(EntitlementOverrideCreate):
    id: uuid.UUID
    created_by_user_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EntitlementCheckResult(BaseModel):
    authorized: bool
    limit_value: Optional[int] = None
    reason: str
    resolved_status: str
    source: str = "plan"
    scope: str = "none"


class PlatformSubscriptionSummary(BaseModel):
    id: Optional[uuid.UUID] = None
    status: str
    resolved_status: str
    plan_code: str
    plan_name: str
    plan_is_active: bool
    trial_ends_at: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    cancelled_at: Optional[datetime] = None


class PlatformFeatureInspectionItem(BaseModel):
    feature_code: str
    feature_name: str
    category: str
    authorized: bool
    limit_value: Optional[int] = None
    limit_type: str  # "unlimited", "numeric", "none"
    reason: str
    source: str
    scope: str


class PlatformBusinessEntitlementsOut(BaseModel):
    business_id: uuid.UUID
    business_name: str
    business_status: str
    outlet_id: Optional[uuid.UUID] = None
    outlet_name: Optional[str] = None
    subscription: PlatformSubscriptionSummary
    features: List[PlatformFeatureInspectionItem]


class PlatformOverrideInspectionItem(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    outlet_id: Optional[uuid.UUID] = None
    outlet_name: Optional[str] = None
    feature_code: str
    feature_name: str
    override_type: str
    limit_value: Optional[int] = None
    reason: str
    expires_at: Optional[datetime] = None
    is_active: bool
    created_by_user_id: Optional[uuid.UUID] = None
    created_by_email: Optional[str] = None
    created_at: datetime


class PlatformRevocationAuditItem(BaseModel):
    audit_log_id: uuid.UUID
    revoked_override_id: Optional[str] = None
    feature_code: Optional[str] = None
    override_type: Optional[str] = None
    actor_user_id: Optional[uuid.UUID] = None
    actor_email: Optional[str] = None
    revoked_at: datetime
    reason: Optional[str] = None


class PlatformBusinessOverridesResponse(BaseModel):
    business_id: uuid.UUID
    overrides: List[PlatformOverrideInspectionItem]
    revocation_history: List[PlatformRevocationAuditItem]


class PlatformOverrideCreate(BaseModel):
    feature_code: str
    override_type: str  # "grant" or "restrict"
    outlet_id: Optional[uuid.UUID] = None
    limit_value: Optional[int] = Field(default=None, ge=1)
    reason: str = Field(..., min_length=1, max_length=500)
    expires_at: Optional[datetime] = None


class PlatformOverrideRevoke(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


# --- Owner Subscription Self-Inspection (OP-05) Schemas ---

class OwnerPlanSummary(BaseModel):
    code: str
    name: str
    description: Optional[str] = None


class OwnerSubscriptionDetail(BaseModel):
    status: str
    is_current: bool
    trial_ends_at: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False


class OwnerOutletUsage(BaseModel):
    current_count: int
    max_allowed: Optional[int] = None
    is_limit_reached: bool = False


class OwnerFeatureItem(BaseModel):
    code: str
    name: str
    category: str
    authorized: bool
    limit_value: Optional[int] = None


class OwnerSupportAction(BaseModel):
    requires_action: bool = False
    reason: Optional[str] = None
    support_email: str = "support@roms.com"
    message: Optional[str] = None


class OwnerOutletSubscriptionItem(BaseModel):
    outlet_id: uuid.UUID
    outlet_name: str
    source: str
    status: str
    plan_code: str
    plan_name: str
    trial_ends_at: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    is_current: bool = True


class OwnerSubscriptionSummaryOut(BaseModel):
    business_id: uuid.UUID
    business_name: str
    business_status: str
    plan: OwnerPlanSummary
    subscription: OwnerSubscriptionDetail
    outlets: OwnerOutletUsage
    outlet_subscriptions: List[OwnerOutletSubscriptionItem] = []
    features: List[OwnerFeatureItem]
    support_cta: OwnerSupportAction


