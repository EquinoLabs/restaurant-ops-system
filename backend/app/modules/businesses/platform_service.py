import uuid
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.staff.models import User, OutletMembership
from app.modules.businesses.schemas import (
    PlatformBusinessCreate,
    PlatformOutletCreate,
    PlatformAssignOwner,
    PlatformSubscriptionUpdate,
    PlatformBusinessProfileUpdate,
    PlatformOutletProfileUpdate,
)
from app.core.security import hash_password
from app.core.errors import NotFoundError, ValidationError, ForbiddenError
from datetime import timedelta
from sqlalchemy import text, select
from app.db.base import utc_now
from app.modules.audit.service import log_audit
from app.modules.subscriptions.models import Plan, BusinessSubscription
from app.modules.subscriptions.service import EntitlementService, compute_annual_period_end, ensure_utc

PLAN_MAP = {
    'starter': 'starter_pos',
    'growth': 'growth_pos',
    'pro': 'pro_kds',
    'enterprise': 'enterprise',
    'digital_menu': 'free_qr',
    'free': 'free_qr',
    'starter plan': 'starter_pos',
    'growth plan': 'growth_pos',
    'pro plan': 'pro_kds',
    'enterprise plan': 'enterprise',
}


def resolve_plan(db: Session, plan_identifier: Optional[str]) -> Plan:
    if not plan_identifier or not plan_identifier.strip():
        raise ValidationError("Plan identifier cannot be empty.")
    raw = plan_identifier.strip()

    # 1. Canonical Plan.code match
    plan = db.scalar(select(Plan).where(Plan.code == raw, Plan.is_active == True))
    if plan:
        return plan

    # 2. Canonical Plan.code case-insensitive match
    plan = db.scalar(select(Plan).where(Plan.code.ilike(raw), Plan.is_active == True))
    if plan:
        return plan

    # 3. Canonical Plan.name case-insensitive match
    plan = db.scalar(select(Plan).where(Plan.name.ilike(raw), Plan.is_active == True))
    if plan:
        return plan

    # 4. Approved legacy alias in PLAN_MAP
    alias_code = PLAN_MAP.get(raw.lower())
    if not alias_code:
        normalized = raw.lower().removesuffix(' plan').strip()
        alias_code = PLAN_MAP.get(normalized)

    if alias_code:
        plan = db.scalar(select(Plan).where(Plan.code == alias_code, Plan.is_active == True))
        if plan:
            return plan

    raise ValidationError(f"Unknown or inactive plan code '{plan_identifier}'.")


def list_canonical_plans(db: Session) -> List[Plan]:
    return (
        db.query(Plan)
        .filter(Plan.is_active == True)
        .order_by(Plan.sort_order.asc(), Plan.code.asc())
        .all()
    )


def list_business_subscriptions(db: Session, business_id: uuid.UUID) -> List[BusinessSubscription]:
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise NotFoundError(f"Business with ID '{business_id}' not found.")
    return (
        db.query(BusinessSubscription)
        .options(joinedload(BusinessSubscription.plan))
        .filter(BusinessSubscription.business_id == business_id)
        .order_by(BusinessSubscription.created_at.desc())
        .all()
    )


VALID_SUBSCRIPTION_STATUSES = {"trial", "active", "past_due", "cancelled"}
VALID_ACCOUNT_STATUSES = {"active", "suspended"}
ADMIN_PRIVILEGE_LOCK_KEY = 424242111


def _acquire_admin_serialization_lock(db: Session) -> None:
    """
    Acquires a transaction-scoped advisory lock in PostgreSQL to serialize platform-admin privilege mutations.
    Safe and ignored in non-PostgreSQL (e.g. SQLite) test environments.
    """
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": ADMIN_PRIVILEGE_LOCK_KEY})


def list_platform_businesses(db: Session) -> List[Business]:
    """
    Returns all businesses across tenants with preloaded outlets sorted by created_at desc.
    """
    return (
        db.query(Business)
        .options(joinedload(Business.outlets))
        .order_by(Business.created_at.desc())
        .all()
    )


def create_platform_business(
    db: Session, data: PlatformBusinessCreate, actor_user_id: Optional[uuid.UUID] = None
) -> Business:
    """
    Provisions a new Business, its initial BusinessSubscription, and primary Outlet in a single transaction.
    Enforces exactly 30-day trial initialization from creation timestamp.
    """
    slug = data.public_slug.strip().lower()

    existing_slug = db.query(Outlet).filter(Outlet.public_slug == slug).first()
    if existing_slug:
        raise ValidationError(f"Public slug '{slug}' is already in use by another outlet.")

    if data.subscription_status and data.subscription_status not in VALID_SUBSCRIPTION_STATUSES:
        raise ValidationError(
            f"Invalid subscription_status '{data.subscription_status}'. Allowed: {sorted(list(VALID_SUBSCRIPTION_STATUSES))}"
        )

    if data.max_outlets is not None and data.max_outlets < 1:
        raise ValidationError("max_outlets must be at least 1 or None.")

    now = utc_now()
    sub_status = data.subscription_status or "trial"
    trial_ends = ensure_utc(data.trial_ends_at)
    if sub_status == "trial" and trial_ends is None:
        trial_ends = now + timedelta(days=30)

    business = Business(
        name=data.name.strip(),
        status="active",
        subscription_status=sub_status,
        plan_name=data.plan_name,
        max_outlets=data.max_outlets,
        trial_ends_at=trial_ends,
        created_at=now,
        updated_at=now,
    )
    db.add(business)
    db.flush()

    # Create initial BusinessSubscription
    if data.plan_name:
        plan = resolve_plan(db, data.plan_name)
    else:
        target_code = 'starter_pos' if (data.max_outlets == 1) else 'growth_pos'
        plan = resolve_plan(db, target_code)

    if plan:
        sub = BusinessSubscription(
            business_id=business.id,
            plan_id=plan.id,
            status=business.subscription_status,
            is_current=True,
            trial_ends_at=business.trial_ends_at,
            created_at=now,
            updated_at=now,
        )
        db.add(sub)
        db.flush()

    primary_outlet = Outlet(
        business_id=business.id,
        name=data.primary_outlet_name.strip(),
        public_slug=slug,
        currency=data.currency,
        timezone=data.timezone,
        address=data.address.strip() if data.address else None,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(primary_outlet)
    db.flush()

    try:
        log_audit(
            db=db,
            business_id=business.id,
            outlet_id=primary_outlet.id,
            actor_user_id=actor_user_id,
            action="platform.business.create",
            entity_type="business",
            entity_id=business.id,
            metadata_json={
                "outcome": "success",
                "name": business.name,
                "primary_outlet_name": primary_outlet.name,
                "public_slug": primary_outlet.public_slug,
                "subscription_status": business.subscription_status,
                "plan_name": business.plan_name,
                "max_outlets": business.max_outlets,
                "trial_ends_at": business.trial_ends_at.isoformat() if business.trial_ends_at else None,
            }
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(business)
    return business


def update_business_subscription(
    db: Session, business_id: uuid.UUID, data: PlatformSubscriptionUpdate, actor_user_id: Optional[uuid.UUID] = None
) -> Business:
    """
    Updates subscription lifecycle, plan, account status, max outlets, and audit history.
    Enforces atomic row replacement, strict 1-calendar-year annual commitments, and transactional consistency.
    """
    if db.bind and db.bind.dialect.name == "postgresql":
        business = db.query(Business).with_for_update().filter(Business.id == business_id).first()
    else:
        business = db.query(Business).filter(Business.id == business_id).first()

    if not business:
        raise NotFoundError(f"Business with ID '{business_id}' not found.")

    curr_sub = db.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == business_id,
        BusinessSubscription.is_current == True
    ).first()

    now = utc_now()

    before_state = {
        "status": business.status,
        "subscription_status": business.subscription_status,
        "plan_name": business.plan_name,
        "max_outlets": business.max_outlets,
        "trial_ends_at": business.trial_ends_at.isoformat() if business.trial_ends_at else None,
        "current_period_start": curr_sub.current_period_start.isoformat() if (curr_sub and curr_sub.current_period_start) else None,
        "current_period_end": curr_sub.current_period_end.isoformat() if (curr_sub and curr_sub.current_period_end) else None,
        "cancel_at_period_end": curr_sub.cancel_at_period_end if curr_sub else False,
        "cancelled_at": curr_sub.cancelled_at.isoformat() if (curr_sub and curr_sub.cancelled_at) else None,
    }

    action_type = (data.action_type or "").strip()
    audit_action = "platform.subscription.update"
    audit_metadata: dict = {"reason": data.reason}

    # 1. Handle max_outlets update if supplied
    if data.max_outlets is not None:
        if data.max_outlets < 1:
            raise ValidationError("max_outlets must be at least 1 or None.")
        business.max_outlets = data.max_outlets

    # 2. Handle business operational status (status) update if supplied
    if data.status is not None:
        if data.status not in VALID_ACCOUNT_STATUSES:
            raise ValidationError(
                f"Invalid status '{data.status}'. Allowed: {sorted(list(VALID_ACCOUNT_STATUSES))}"
            )
        business.status = data.status

    # 3. Action Dispatcher
    if action_type == "activate":
        # Trial to paid conversion OR Reactivation after expiry/cancellation
        plan_identifier = data.plan_code or data.plan_name or (curr_sub.plan.code if (curr_sub and curr_sub.plan) else business.plan_name)
        if not plan_identifier:
            raise ValidationError("A valid plan_code or plan_name is required for activation.")
        target_plan = resolve_plan(db, plan_identifier)

        # Start date
        if data.current_period_start is not None:
            start_dt = ensure_utc(data.current_period_start)
            if start_dt < now - timedelta(days=1):
                reason_clean = (data.reason or "").strip()
                if not reason_clean:
                    raise ValidationError("A meaningful administrative reason is required when supplying a historical contractual start date.")
                audit_metadata["historical_start_reason"] = reason_clean
        else:
            start_dt = now

        expected_end = compute_annual_period_end(start_dt)
        if data.current_period_end is not None:
            end_dt = ensure_utc(data.current_period_end)
            if end_dt != expected_end:
                raise ValidationError(
                    f"current_period_end must be exactly one calendar year after current_period_start ({expected_end.isoformat()}). Got {end_dt.isoformat()}."
                )
        else:
            end_dt = expected_end

        if end_dt <= now:
            raise ValidationError("current_period_end must be strictly in the future.")

        # Atomic row swap
        if curr_sub:
            curr_sub.is_current = False

        new_sub = BusinessSubscription(
            business_id=business_id,
            plan_id=target_plan.id,
            status="active",
            is_current=True,
            trial_ends_at=None,
            current_period_start=start_dt,
            current_period_end=end_dt,
            cancel_at_period_end=False,
            cancelled_at=None,
        )
        db.add(new_sub)

        business.subscription_status = "active"
        business.plan_name = (data.plan_name.strip() if data.plan_name else None) or target_plan.code
        business.trial_ends_at = None
        audit_action = "platform.subscription.activate"

    elif action_type == "renew":
        curr_period_end_utc = ensure_utc(curr_sub.current_period_end) if (curr_sub and curr_sub.current_period_end) else None
        is_timely = (
            curr_sub is not None
            and curr_sub.status == "active"
            and curr_period_end_utc is not None
            and now < curr_period_end_utc
        )

        plan_identifier = data.plan_code or data.plan_name or (curr_sub.plan.code if (curr_sub and curr_sub.plan) else business.plan_name)
        target_plan = resolve_plan(db, plan_identifier) if plan_identifier else (curr_sub.plan if curr_sub else None)
        if not target_plan:
            raise ValidationError("A valid plan is required for renewal.")

        if is_timely:
            start_dt = curr_period_end_utc
            expected_end = compute_annual_period_end(start_dt)
            if data.current_period_end is not None:
                end_dt = ensure_utc(data.current_period_end)
                if end_dt != expected_end:
                    raise ValidationError(
                        f"current_period_end must be exactly one calendar year after contractual anniversary ({expected_end.isoformat()}). Got {end_dt.isoformat()}."
                    )
            else:
                end_dt = expected_end

            curr_sub.is_current = False
            new_sub = BusinessSubscription(
                business_id=business_id,
                plan_id=target_plan.id,
                status="active",
                is_current=True,
                trial_ends_at=None,
                current_period_start=start_dt,
                current_period_end=end_dt,
                cancel_at_period_end=False,
                cancelled_at=None,
            )
            db.add(new_sub)
            business.subscription_status = "active"
            business.plan_name = (data.plan_name.strip() if data.plan_name else None) or target_plan.code
            business.trial_ends_at = None
            audit_action = "platform.subscription.renew"
        else:
            if data.current_period_start is not None:
                start_dt = ensure_utc(data.current_period_start)
                if start_dt < now - timedelta(days=1):
                    reason_clean = (data.reason or "").strip()
                    if not reason_clean:
                        raise ValidationError("A meaningful administrative reason is required when supplying a historical contractual start date.")
                    audit_metadata["historical_start_reason"] = reason_clean
            else:
                start_dt = now

            expected_end = compute_annual_period_end(start_dt)
            if data.current_period_end is not None:
                end_dt = ensure_utc(data.current_period_end)
                if end_dt != expected_end:
                    raise ValidationError(
                        f"current_period_end must be exactly one calendar year after current_period_start ({expected_end.isoformat()}). Got {end_dt.isoformat()}."
                    )
            else:
                end_dt = expected_end

            if end_dt <= now:
                raise ValidationError("current_period_end must be strictly in the future.")

            if curr_sub:
                curr_sub.is_current = False

            new_sub = BusinessSubscription(
                business_id=business_id,
                plan_id=target_plan.id,
                status="active",
                is_current=True,
                trial_ends_at=None,
                current_period_start=start_dt,
                current_period_end=end_dt,
                cancel_at_period_end=False,
                cancelled_at=None,
            )
            db.add(new_sub)
            business.subscription_status = "active"
            business.plan_name = (data.plan_name.strip() if data.plan_name else None) or target_plan.code
            business.trial_ends_at = None
            audit_action = "platform.subscription.renew"

    elif action_type == "change_plan":
        if not curr_sub:
            raise ValidationError("Cannot perform mid-term plan change without an existing current subscription.")
        plan_identifier = data.plan_code or data.plan_name
        if not plan_identifier:
            raise ValidationError("plan_code or plan_name is required for plan change.")
        target_plan = resolve_plan(db, plan_identifier)

        curr_sub.is_current = False
        new_sub = BusinessSubscription(
            business_id=business_id,
            plan_id=target_plan.id,
            status=curr_sub.status,
            is_current=True,
            trial_ends_at=ensure_utc(curr_sub.trial_ends_at),
            current_period_start=ensure_utc(curr_sub.current_period_start),
            current_period_end=ensure_utc(curr_sub.current_period_end),
            cancel_at_period_end=curr_sub.cancel_at_period_end,
            cancelled_at=ensure_utc(curr_sub.cancelled_at),
        )
        db.add(new_sub)
        business.plan_name = (data.plan_name.strip() if data.plan_name else None) or target_plan.code
        audit_action = "platform.subscription.change_plan"

    elif action_type == "change_plan_new_term":
        plan_identifier = data.plan_code or data.plan_name
        if not plan_identifier:
            raise ValidationError("plan_code or plan_name is required for change_plan_new_term.")
        target_plan = resolve_plan(db, plan_identifier)

        if data.current_period_start is not None:
            start_dt = ensure_utc(data.current_period_start)
            if start_dt < now - timedelta(days=1):
                reason_clean = (data.reason or "").strip()
                if not reason_clean:
                    raise ValidationError("A meaningful administrative reason is required when supplying a historical contractual start date.")
                audit_metadata["historical_start_reason"] = reason_clean
        else:
            start_dt = now

        expected_end = compute_annual_period_end(start_dt)
        if data.current_period_end is not None:
            end_dt = ensure_utc(data.current_period_end)
            if end_dt != expected_end:
                raise ValidationError(
                    f"current_period_end must be exactly one calendar year after current_period_start ({expected_end.isoformat()}). Got {end_dt.isoformat()}."
                )
        else:
            end_dt = expected_end

        if end_dt <= now:
            raise ValidationError("current_period_end must be strictly in the future.")

        if curr_sub:
            curr_sub.is_current = False

        new_sub = BusinessSubscription(
            business_id=business_id,
            plan_id=target_plan.id,
            status="active",
            is_current=True,
            trial_ends_at=None,
            current_period_start=start_dt,
            current_period_end=end_dt,
            cancel_at_period_end=False,
            cancelled_at=None,
        )
        db.add(new_sub)
        business.subscription_status = "active"
        business.plan_name = (data.plan_name.strip() if data.plan_name else None) or target_plan.code
        business.trial_ends_at = None
        audit_action = "platform.subscription.change_plan_new_term"

    elif action_type == "extend_trial":
        if not data.trial_ends_at:
            raise ValidationError("trial_ends_at is required to extend trial.")
        trial_ends = ensure_utc(data.trial_ends_at)
        if trial_ends <= now:
            raise ValidationError("trial_ends_at must be strictly in the future.")

        if curr_sub:
            curr_sub.trial_ends_at = trial_ends
            curr_sub.status = "trial"
        business.trial_ends_at = trial_ends
        business.subscription_status = "trial"
        audit_action = "platform.subscription.extend_trial"

    elif action_type == "schedule_cancellation":
        if not curr_sub or curr_sub.status not in ("active", "past_due"):
            raise ValidationError("Can only schedule cancellation for an active or past_due subscription.")
        curr_end_utc = ensure_utc(curr_sub.current_period_end)
        if not curr_end_utc or curr_end_utc <= now:
            raise ValidationError("Cannot schedule cancellation for an expired subscription.")
        curr_sub.cancel_at_period_end = True
        curr_sub.cancelled_at = now
        audit_action = "platform.subscription.schedule_cancellation"

    elif action_type == "revoke_scheduled_cancellation":
        if not curr_sub or not curr_sub.cancel_at_period_end:
            raise ValidationError("No scheduled cancellation found to revoke.")
        curr_sub.cancel_at_period_end = False
        curr_sub.cancelled_at = None
        audit_action = "platform.subscription.revoke_scheduled_cancellation"

    elif action_type == "cancel_immediately":
        reason_clean = (data.reason or "").strip()
        if not reason_clean:
            raise ValidationError("Reason is required for immediate cancellation.")
        if curr_sub:
            curr_sub.status = "cancelled"
            curr_sub.cancelled_at = now
            curr_sub.cancel_at_period_end = False
        business.subscription_status = "cancelled"
        audit_action = "platform.subscription.cancel_immediately"

    elif action_type == "mark_past_due":
        if not curr_sub:
            raise ValidationError("No current subscription found.")
        curr_sub.status = "past_due"
        business.subscription_status = "past_due"
        audit_action = "platform.subscription.mark_past_due"

    elif action_type == "mark_past_due_with_extension":
        if not data.current_period_end:
            raise ValidationError("current_period_end is required for past-due recovery extension.")
        ext_end = ensure_utc(data.current_period_end)
        if ext_end <= now:
            raise ValidationError("current_period_end extension must be strictly in the future.")
        reason_clean = (data.reason or "").strip()
        if not reason_clean:
            raise ValidationError("Reason is required for past-due recovery extension.")
        if curr_sub:
            curr_sub.status = "past_due"
            curr_sub.current_period_end = ext_end
        business.subscription_status = "past_due"
        audit_metadata["extension_reason"] = reason_clean
        audit_action = "platform.subscription.mark_past_due_with_extension"

    elif not action_type:
        # Backward compatibility for direct scalar updates
        if data.subscription_status is not None:
            if data.subscription_status not in VALID_SUBSCRIPTION_STATUSES:
                raise ValidationError(
                    f"Invalid subscription_status '{data.subscription_status}'. Allowed: {sorted(list(VALID_SUBSCRIPTION_STATUSES))}"
                )
            business.subscription_status = data.subscription_status

        if data.plan_name is not None:
            business.plan_name = data.plan_name.strip() if data.plan_name else None

        if data.trial_ends_at is not None:
            trial_dt = ensure_utc(data.trial_ends_at)
            business.trial_ends_at = trial_dt

        # Plan lookup & sync
        plan_identifier = data.plan_code or business.plan_name
        target_plan = resolve_plan(db, plan_identifier) if plan_identifier else None

        if business.subscription_status in ("active", "past_due"):
            if data.current_period_end is not None:
                p_end = ensure_utc(data.current_period_end)
                p_start = ensure_utc(data.current_period_start) or (curr_sub.current_period_start if curr_sub else now)
                expected_end = compute_annual_period_end(p_start)
                if p_end != expected_end:
                    raise ValidationError(
                        f"current_period_end must be exactly one calendar year after current_period_start ({expected_end.isoformat()}). Got {p_end.isoformat()}."
                    )
            elif curr_sub and curr_sub.current_period_end and curr_sub.current_period_end > now:
                p_end = curr_sub.current_period_end
                p_start = curr_sub.current_period_start or now
            else:
                raise ValidationError("Activating an active paid subscription requires an explicit valid future current_period_end matching exactly one calendar year.")

        if target_plan:
            if curr_sub and curr_sub.plan_id != target_plan.id:
                curr_sub.is_current = False
                new_sub = BusinessSubscription(
                    business_id=business_id,
                    plan_id=target_plan.id,
                    status=business.subscription_status,
                    is_current=True,
                    trial_ends_at=business.trial_ends_at,
                    current_period_start=data.current_period_start or (curr_sub.current_period_start if curr_sub else None),
                    current_period_end=data.current_period_end or (curr_sub.current_period_end if curr_sub else None),
                )
                db.add(new_sub)
            elif curr_sub:
                curr_sub.status = business.subscription_status
                curr_sub.trial_ends_at = business.trial_ends_at
                if data.current_period_start:
                    curr_sub.current_period_start = ensure_utc(data.current_period_start)
                if data.current_period_end:
                    curr_sub.current_period_end = ensure_utc(data.current_period_end)
            else:
                new_sub = BusinessSubscription(
                    business_id=business_id,
                    plan_id=target_plan.id,
                    status=business.subscription_status,
                    is_current=True,
                    trial_ends_at=business.trial_ends_at,
                    current_period_start=ensure_utc(data.current_period_start),
                    current_period_end=ensure_utc(data.current_period_end),
                )
                db.add(new_sub)
        elif curr_sub:
            curr_sub.status = business.subscription_status
            curr_sub.trial_ends_at = business.trial_ends_at

        audit_action = "platform.business.update_subscription"
    else:
        raise ValidationError(f"Unknown lifecycle action_type '{action_type}'.")

    db.flush()
    curr_sub_after = db.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == business_id,
        BusinessSubscription.is_current == True
    ).first()

    after_state = {
        "status": business.status,
        "subscription_status": business.subscription_status,
        "plan_name": business.plan_name,
        "max_outlets": business.max_outlets,
        "trial_ends_at": business.trial_ends_at.isoformat() if business.trial_ends_at else None,
        "current_period_start": curr_sub_after.current_period_start.isoformat() if (curr_sub_after and curr_sub_after.current_period_start) else None,
        "current_period_end": curr_sub_after.current_period_end.isoformat() if (curr_sub_after and curr_sub_after.current_period_end) else None,
        "cancel_at_period_end": curr_sub_after.cancel_at_period_end if curr_sub_after else False,
        "cancelled_at": curr_sub_after.cancelled_at.isoformat() if (curr_sub_after and curr_sub_after.cancelled_at) else None,
    }

    if before_state["status"] != "suspended" and after_state["status"] == "suspended":
        audit_action = "platform.business.suspend"
    elif before_state["status"] == "suspended" and after_state["status"] == "active":
        audit_action = "platform.business.reactivate"

    try:
        log_audit(
            db=db,
            business_id=business.id,
            outlet_id=None,
            actor_user_id=actor_user_id,
            action=audit_action,
            entity_type="business",
            entity_id=business.id,
            metadata_json={
                "outcome": "success",
                "action_type": action_type or "legacy_update",
                "before": before_state,
                "after": after_state,
                **audit_metadata
            }
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(business)
    return business


def add_outlet_to_business(
    db: Session, business_id: uuid.UUID, data: PlatformOutletCreate, actor_user_id: Optional[uuid.UUID] = None
) -> Outlet:
    """
    Adds a new Outlet to an existing Business, enforcing central EntitlementService authorization and capacity limits.
    Uses pessimistic row locking on PostgreSQL to prevent concurrent outlet creation race conditions.
    """
    if db.bind and db.bind.dialect.name == "postgresql":
        business = db.query(Business).with_for_update().filter(Business.id == business_id).first()
    else:
        business = db.query(Business).filter(Business.id == business_id).first()

    if not business:
        raise NotFoundError(f"Business with ID '{business_id}' not found.")

    # Entitlement Check 1: Feature Authorization
    entitlement = EntitlementService.check_entitlement(db, business_id=business_id, feature_code="outlets.max_count")
    if not entitlement.authorized:
        if entitlement.reason == "BUSINESS_SUSPENDED":
            raise ForbiddenError("This business account is currently suspended.")
        raise ValidationError(
            f"Business '{business.name}' is not entitled to create outlets. Reason: {entitlement.reason}"
        )

    # Entitlement Check 2: Numeric Capacity Limit
    if entitlement.limit_value is not None:
        current_count = db.query(Outlet).filter(Outlet.business_id == business_id).count()
        if current_count >= entitlement.limit_value:
            raise ValidationError(
                f"Business '{business.name}' has reached its maximum allowed limit of {entitlement.limit_value} outlet(s)."
            )

    slug = data.public_slug.strip().lower()
    existing_slug = db.query(Outlet).filter(Outlet.public_slug == slug).first()
    if existing_slug:
        raise ValidationError(f"Public slug '{slug}' is already in use by another outlet.")

    outlet = Outlet(
        business_id=business_id,
        name=data.name.strip(),
        public_slug=slug,
        currency=data.currency,
        timezone=data.timezone,
        address=data.address.strip() if data.address else None,
        status="active"
    )
    db.add(outlet)
    db.flush()

    log_audit(
        db=db,
        business_id=business_id,
        outlet_id=outlet.id,
        actor_user_id=actor_user_id,
        action="platform.outlet.create",
        entity_type="outlet",
        entity_id=outlet.id,
        metadata_json={
            "outcome": "success",
            "name": outlet.name,
            "public_slug": outlet.public_slug,
            "currency": outlet.currency,
            "timezone": outlet.timezone,
        }
    )

    db.commit()
    db.refresh(outlet)
    return outlet


def assign_owner_to_outlet(
    db: Session, business_id: uuid.UUID, data: PlatformAssignOwner, actor_user_id: Optional[uuid.UUID] = None
) -> OutletMembership:
    """
    Creates or assigns a User as an 'owner' for a specific Outlet under a Business.
    """
    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise NotFoundError(f"Business with ID '{business_id}' not found.")

    outlet = db.query(Outlet).filter(
        Outlet.id == data.outlet_id,
        Outlet.business_id == business_id
    ).first()
    if not outlet:
        raise NotFoundError(f"Outlet with ID '{data.outlet_id}' not found under business '{business_id}'.")


    user: Optional[User] = None
    created_new_user = False

    if data.user_id:
        user = db.query(User).filter(User.id == data.user_id).first()
        if not user:
            raise NotFoundError(f"User with ID '{data.user_id}' not found.")
    elif data.email:
        email = data.email.strip().lower()
        user = db.query(User).filter(User.email == email).first()
        if not user:
            if not data.password or not data.display_name:
                raise ValidationError("password and display_name are required when creating a new owner user.")
            user = User(
                email=email,
                password_hash=hash_password(data.password),
                display_name=data.display_name.strip(),
                status="active",
                is_platform_admin=False
            )
            db.add(user)
            db.flush()
            created_new_user = True
    else:
        raise ValidationError("Either user_id or email must be provided to assign an owner.")

    membership = db.query(OutletMembership).filter(
        OutletMembership.user_id == user.id,
        OutletMembership.outlet_id == outlet.id
    ).first()

    if membership:
        membership.role = "owner"
    else:
        membership = OutletMembership(
            user_id=user.id,
            outlet_id=outlet.id,
            role="owner"
        )
        db.add(membership)

    db.flush()

    log_audit(
        db=db,
        business_id=business_id,
        outlet_id=outlet.id,
        actor_user_id=actor_user_id,
        action="platform.owner.assign",
        entity_type="membership",
        entity_id=membership.id,
        metadata_json={
            "outcome": "success",
            "assigned_user_id": str(user.id),
            "email": user.email,
            "role": "owner",
            "created_new_user": created_new_user,
        }
    )

    db.commit()
    db.refresh(membership)
    return membership


def list_platform_admins(db: Session) -> List[User]:
    """
    Returns all users with platform administrator privileges.
    """
    return (
        db.query(User)
        .filter(User.is_platform_admin == True)
        .order_by(User.created_at.asc())
        .all()
    )


def grant_platform_admin(
    db: Session, target_user_id: uuid.UUID, actor_user_id: Optional[uuid.UUID] = None
) -> User:
    """
    Grants platform administrator privileges to an existing user.
    """
    _acquire_admin_serialization_lock(db)

    user = db.query(User).filter(User.id == target_user_id).first()
    if not user:
        raise NotFoundError(f"User with ID '{target_user_id}' not found.")

    if user.is_platform_admin:
        return user

    user.is_platform_admin = True
    db.flush()

    log_audit(
        db=db,
        business_id=None,
        outlet_id=None,
        actor_user_id=actor_user_id,
        action="platform.admin.grant",
        entity_type="user",
        entity_id=user.id,
        metadata_json={
            "outcome": "success",
            "target_user_id": str(user.id),
            "target_email": user.email,
        }
    )

    db.commit()
    db.refresh(user)
    return user


def revoke_platform_admin(
    db: Session, target_user_id: uuid.UUID, actor_user_id: uuid.UUID
) -> User:
    """
    Revokes platform administrator privileges from a user, with concurrency-safe last-admin protection.
    """
    _acquire_admin_serialization_lock(db)

    if not actor_user_id:
        raise ValidationError("Actor user ID is required to revoke platform administrator privileges.")

    user = db.query(User).filter(User.id == target_user_id).first()
    if not user:
        raise NotFoundError(f"User with ID '{target_user_id}' not found.")

    if not user.is_platform_admin:
        return user

    if user.status == "active":
        active_admins = (
            db.query(User)
            .filter(User.is_platform_admin == True, User.status == "active")
            .order_by(User.id.asc())
            .all()
        )
        if len(active_admins) <= 1:
            raise ValidationError("Cannot revoke platform admin privileges from the last active platform administrator.")

    if target_user_id == actor_user_id:
        raise ValidationError("Platform administrators cannot revoke their own privileges.")

    user.is_platform_admin = False
    db.flush()

    log_audit(
        db=db,
        business_id=None,
        outlet_id=None,
        actor_user_id=actor_user_id,
        action="platform.admin.revoke",
        entity_type="user",
        entity_id=user.id,
        metadata_json={
            "outcome": "success",
            "target_user_id": str(user.id),
            "target_email": user.email,
        }
    )

    db.commit()
    db.refresh(user)
    return user


def get_platform_business(db: Session, business_id: uuid.UUID) -> Business:
    """
    Returns single business details with preloaded outlets.
    """
    business = (
        db.query(Business)
        .options(joinedload(Business.outlets))
        .filter(Business.id == business_id)
        .first()
    )
    if not business:
        raise NotFoundError(f"Business with ID '{business_id}' not found.")
    return business


def update_business_profile(
    db: Session,
    business_id: uuid.UUID,
    data: PlatformBusinessProfileUpdate,
    actor_user_id: Optional[uuid.UUID] = None
) -> Business:
    """
    Updates business general metadata (display/legal name).
    Enforces atomic transaction and audit logging.
    """
    if db.bind and db.bind.dialect.name == "postgresql":
        business = db.query(Business).with_for_update().filter(Business.id == business_id).first()
    else:
        business = db.query(Business).filter(Business.id == business_id).first()

    if not business:
        raise NotFoundError(f"Business with ID '{business_id}' not found.")

    before_name = business.name
    new_name = data.name.strip()
    if not new_name:
        raise ValidationError("Business name cannot be empty.")

    business.name = new_name
    db.flush()

    try:
        log_audit(
            db=db,
            business_id=business.id,
            outlet_id=None,
            actor_user_id=actor_user_id,
            action="platform.business.profile_update",
            entity_type="business",
            entity_id=business.id,
            metadata_json={
                "outcome": "success",
                "before": {"name": before_name},
                "after": {"name": business.name},
            }
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(business)
    return business


def get_platform_outlet(db: Session, outlet_id: uuid.UUID) -> Outlet:
    """
    Returns single outlet details with preloaded parent business.
    """
    outlet = (
        db.query(Outlet)
        .options(joinedload(Outlet.business))
        .filter(Outlet.id == outlet_id)
        .first()
    )
    if not outlet:
        raise NotFoundError(f"Outlet with ID '{outlet_id}' not found.")
    return outlet


def update_outlet_profile(
    db: Session,
    outlet_id: uuid.UUID,
    data: PlatformOutletProfileUpdate,
    actor_user_id: Optional[uuid.UUID] = None
) -> Outlet:
    """
    Updates outlet profile metadata and branding colors.
    Keeps public_slug immutable and verifies parent business association.
    Enforces atomic transaction and platform audit logging.
    """
    if db.bind and db.bind.dialect.name == "postgresql":
        outlet = db.query(Outlet).with_for_update().filter(Outlet.id == outlet_id).first()
    else:
        outlet = db.query(Outlet).filter(Outlet.id == outlet_id).first()

    if not outlet:
        raise NotFoundError(f"Outlet with ID '{outlet_id}' not found.")

    # Verify parent business exists
    business = db.query(Business).filter(Business.id == outlet.business_id).first()
    if not business:
        raise NotFoundError(f"Parent business for outlet '{outlet_id}' not found.")

    before_state = {
        "name": outlet.name,
        "address": outlet.address,
        "timezone": outlet.timezone,
        "currency": outlet.currency,
        "primary_color": outlet.primary_color,
        "accent_color": outlet.accent_color,
    }

    if data.name is not None:
        name_clean = data.name.strip()
        if not name_clean:
            raise ValidationError("Outlet name cannot be empty.")
        outlet.name = name_clean

    if data.address is not None:
        outlet.address = data.address.strip() if data.address.strip() else None

    if data.timezone is not None:
        import zoneinfo
        tz_clean = data.timezone.strip()
        try:
            zoneinfo.ZoneInfo(tz_clean)
        except Exception:
            raise ValidationError(f"Invalid timezone identifier: '{tz_clean}'. Must be a valid IANA timezone name.")
        outlet.timezone = tz_clean

    if data.currency is not None:
        curr_clean = data.currency.strip().upper()
        if len(curr_clean) != 3 or not curr_clean.isalpha():
            raise ValidationError(f"Invalid currency code: '{curr_clean}'. Must be a 3-letter ISO currency code.")
        outlet.currency = curr_clean

    if data.primary_color is not None:
        col = data.primary_color.strip()
        if col:
            import re
            if not re.match(r"^#[0-9a-fA-F]{6}$", col):
                raise ValidationError(f"Invalid primary_color format: '{col}'. Must be #RRGGBB.")
            outlet.primary_color = col.upper()
        else:
            outlet.primary_color = None

    if data.accent_color is not None:
        col = data.accent_color.strip()
        if col:
            import re
            if not re.match(r"^#[0-9a-fA-F]{6}$", col):
                raise ValidationError(f"Invalid accent_color format: '{col}'. Must be #RRGGBB.")
            outlet.accent_color = col.upper()
        else:
            outlet.accent_color = None

    db.flush()

    after_state = {
        "name": outlet.name,
        "address": outlet.address,
        "timezone": outlet.timezone,
        "currency": outlet.currency,
        "primary_color": outlet.primary_color,
        "accent_color": outlet.accent_color,
    }

    try:
        log_audit(
            db=db,
            business_id=outlet.business_id,
            outlet_id=outlet.id,
            actor_user_id=actor_user_id,
            action="platform.outlet.profile_update",
            entity_type="outlet",
            entity_id=outlet.id,
            metadata_json={
                "outcome": "success",
                "before": before_state,
                "after": after_state,
            }
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(outlet)
    return outlet
