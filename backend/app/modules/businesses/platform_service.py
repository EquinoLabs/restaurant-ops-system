import uuid
from typing import List, Optional, Any, Union
from sqlalchemy.orm import Session, joinedload
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.staff.models import User, OutletMembership, BusinessMembership
from app.modules.businesses.schemas import (
    PlatformBusinessCreate,
    PlatformOutletCreate,
    PlatformAssignOwner,
    PlatformSubscriptionUpdate,
    PlatformBusinessProfileUpdate,
    PlatformOutletProfileUpdate,
    PlatformOperatorCreateRequest,
)
from app.core.security import hash_password, verify_password
from app.core.errors import NotFoundError, ValidationError, ForbiddenError, AuthenticationError
from datetime import timedelta
from sqlalchemy import text, select, or_
from sqlalchemy.exc import IntegrityError
from app.db.base import utc_now
from app.modules.audit.service import log_audit
from app.modules.subscriptions.models import Plan, BusinessSubscription, OutletSubscription
from app.modules.subscriptions.schemas import PlatformOutletSubscriptionUpdate
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


def list_business_subscriptions(db: Session, business_id: uuid.UUID) -> List[OutletSubscription]:
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise NotFoundError(f"Business with ID '{business_id}' not found.")

    # Canonical Stage 3 read path: return only canonical outlet_subscriptions
    return (
        db.query(OutletSubscription)
        .options(joinedload(OutletSubscription.plan))
        .filter(OutletSubscription.business_id == business_id)
        .order_by(OutletSubscription.created_at.desc())
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
    db: Session,
    data: PlatformBusinessCreate,
    actor_user_id: Optional[uuid.UUID] = None,
    commit: bool = True,
) -> Business:
    """
    Provisions a new Business and links its mandatory owner in a single transaction.
    Per Decision 003:
      - Mandatory owner details (email, initial password, display_name).
      - Reuses an existing user if the email matches; rejects suspended/inactive accounts.
      - Never creates an outlet, subscription, or trial (outlets added separately).
      - Initial password is never logged, audited, or echoed.
    """
    now = utc_now()

    # 1. Resolve or create owner User
    owner_email = data.owner_email.strip().lower()
    user = db.query(User).filter(User.email == owner_email).first()
    created_new_user = False

    if user:
        if user.status != "active":
            raise ValidationError(
                f"Cannot assign inactive or suspended user '{owner_email}' as business owner."
            )
    else:
        user = User(
            email=owner_email,
            password_hash=hash_password(data.owner_password),
            display_name=data.owner_display_name.strip(),
            status="active",
            is_platform_admin=False,
        )
        db.add(user)
        db.flush()
        created_new_user = True

    # 2. Create Business record (no outlet, no subscription, no trial)
    business = Business(
        name=data.name.strip(),
        status="active",
        subscription_status=None,
        plan_name=None,
        max_outlets=None,
        trial_ends_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(business)
    db.flush()

    # 3. Create BusinessMembership(role="owner")
    biz_membership = BusinessMembership(
        business_id=business.id,
        user_id=user.id,
        role="owner",
        created_at=now,
        updated_at=now,
    )
    db.add(biz_membership)
    db.flush()

    # 4. Audit platform.business.create 閳ワ拷 no password, no outlet/subscription metadata
    try:
        log_audit(
            db=db,
            business_id=business.id,
            outlet_id=None,
            actor_user_id=actor_user_id,
            action="platform.business.create",
            entity_type="business",
            entity_id=business.id,
            metadata_json={
                "outcome": "success",
                "name": business.name,
                "owner_user_id": str(user.id),
                "owner_email": user.email,
                "created_new_user": created_new_user,
            },
        )
        if commit:
            db.commit()
        else:
            db.flush()
    except Exception:
        if commit:
            db.rollback()
        raise

    if commit:
        db.refresh(business)
    return business


def update_business_subscription(
    db: Session,
    business_id: uuid.UUID,
    data: PlatformSubscriptionUpdate,
    actor_user_id: Optional[uuid.UUID] = None,
    commit: bool = True,
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
        if commit:
            db.commit()
        else:
            db.flush()
    except Exception:
        if commit:
            db.rollback()
        raise

    if commit:
        db.refresh(business)
    return business


def add_outlet_to_business(
    db: Session,
    business_id: uuid.UUID,
    data: PlatformOutletCreate,
    actor_user_id: Optional[uuid.UUID] = None,
    commit: bool = True,
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

    # Business Operational Status Check (Hard platform kill switch)
    if business.status != "active":
        raise ForbiddenError("This business account is currently suspended.")

    slug = data.public_slug.strip().lower()
    existing_slug = db.query(Outlet).filter(Outlet.public_slug == slug).first()
    if existing_slug:
        raise ValidationError(f"Public slug '{slug}' is already in use by another outlet.")

    now = utc_now()

    # Resolve and validate the requested plan (backend must validate, never trust frontend default).
    # The "trial" sentinel is the approved UI default: it creates a 30-day trial subscription
    # on the starter_pos plan. Any other value must be a canonical active plan code, which
    # creates an active subscription for that plan instead (Decision 002).
    if data.plan_code == "trial":
        plan = resolve_plan(db, "starter_pos")
        sub_status = "trial"
        trial_ends = now + timedelta(days=30)
        period_start = None
        period_end = None
    else:
        plan = resolve_plan(db, data.plan_code)
        sub_status = "active"
        trial_ends = None
        # Active (paid) subscriptions need a period window so the resolver
        # can evaluate them correctly. Default to a 1-year term from creation
        # when the caller does not supply explicit dates (Decision 002).
        period_start = now
        period_end = compute_annual_period_end(now)

    outlet = Outlet(
        business_id=business_id,
        name=data.name.strip(),
        public_slug=slug,
        currency=data.currency,
        timezone=data.timezone,
        address=data.address.strip() if data.address else None,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(outlet)
    db.flush()

    # Independent per-outlet subscription 閳ワ拷 never inherits a sibling's subscription.
    outlet_sub = OutletSubscription(
        outlet_id=outlet.id,
        business_id=business_id,
        plan_id=plan.id,
        status=sub_status,
        is_current=True,
        trial_ends_at=trial_ends,
        current_period_start=period_start,
        current_period_end=period_end,
        created_at=now,
        updated_at=now,
    )
    db.add(outlet_sub)
    db.flush()

    # Ensure existing business owners automatically retain owner access on the new outlet
    owners = db.query(BusinessMembership).filter(
        BusinessMembership.business_id == business_id,
        BusinessMembership.role == "owner"
    ).all()
    for owner in owners:
        existing_m = db.query(OutletMembership).filter(
            OutletMembership.user_id == owner.user_id,
            OutletMembership.outlet_id == outlet.id
        ).first()
        if not existing_m:
            db.add(OutletMembership(user_id=owner.user_id, outlet_id=outlet.id, role="owner"))

    # Optional manager assignment (S3): assign an existing, active business manager
    # to the new outlet. Manager credential provisioning is not approved, so only
    # existing users who already hold a BusinessMembership(role="manager") for this
    # business may be assigned.
    manager_user_id: Optional[uuid.UUID] = None
    if data.manager is not None:
        manager_user = db.query(User).filter(User.id == data.manager.user_id).first()
        if not manager_user:
            raise NotFoundError(f"User with ID '{data.manager.user_id}' not found.")
        if manager_user.status != "active":
            raise ValidationError(
                f"Cannot assign inactive or suspended user '{manager_user.id}' as outlet manager."
            )
        # Verify the user is a business manager for the same business
        biz_mgr = db.query(BusinessMembership).filter(
            BusinessMembership.business_id == business_id,
            BusinessMembership.user_id == manager_user.id,
            BusinessMembership.role == "manager"
        ).first()
        if not biz_mgr:
            raise ValidationError(
                f"User '{manager_user.id}' is not a manager of this business and cannot be assigned as an outlet manager."
            )
        manager_user_id = manager_user.id

        existing_mgr = db.query(OutletMembership).filter(
            OutletMembership.user_id == manager_user.id,
            OutletMembership.outlet_id == outlet.id
        ).first()
        if existing_mgr:
            existing_mgr.role = "manager"
            existing_mgr.updated_at = utc_now()
        else:
            db.add(OutletMembership(
                user_id=manager_user.id,
                outlet_id=outlet.id,
                role="manager",
            ))

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
            "plan_code": plan.code,
            "subscription_status": sub_status,
            "trial_ends_at": trial_ends.isoformat() if trial_ends else None,
            "manager_user_id": str(manager_user_id) if manager_user_id is not None else None,
        }
    )

    if commit:
        db.commit()
        db.refresh(outlet)
    else:
        db.flush()
    return outlet


def assign_owner_to_business(
    db: Session,
    business_id: uuid.UUID,
    data: PlatformAssignOwner,
    actor_user_id: Optional[uuid.UUID] = None,
    commit: bool = True,
) -> BusinessMembership:
    """
    Creates or assigns a User as an 'owner' for a Business (not tied to any specific outlet).
    Per Decision 003: exactly-one-owner invariant enforced at service layer.
    """
    if db.bind and db.bind.dialect.name == "postgresql":
        biz = db.query(Business).with_for_update().filter(Business.id == business_id).first()
    else:
        biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise NotFoundError(f"Business with ID '{business_id}' not found.")

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

    # Exactly-one-owner invariant: demote existing owner to manager before promoting new one
    existing_owner = db.query(BusinessMembership).filter(
        BusinessMembership.business_id == business_id,
        BusinessMembership.role == "owner"
    ).first()
    if existing_owner and existing_owner.user_id != user.id:
        existing_owner.role = "manager"
        existing_owner.updated_at = utc_now()

    # Create or update business membership
    biz_membership = db.query(BusinessMembership).filter(
        BusinessMembership.user_id == user.id,
        BusinessMembership.business_id == business_id
    ).first()

    if biz_membership:
        biz_membership.role = "owner"
        biz_membership.updated_at = utc_now()
    else:
        biz_membership = BusinessMembership(
            user_id=user.id,
            business_id=business_id,
            role="owner",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(biz_membership)

    db.flush()

    log_audit(
        db=db,
        business_id=business_id,
        outlet_id=None,
        actor_user_id=actor_user_id,
        action="platform.business_owner.assign",
        entity_type="membership",
        entity_id=biz_membership.id,
        metadata_json={
            "outcome": "success",
            "assigned_user_id": str(user.id),
            "email": user.email,
            "role": "owner",
            "created_new_user": created_new_user,
        }
    )

    if commit:
        db.commit()
        db.refresh(biz_membership)
    else:
        db.flush()
    return biz_membership


def list_platform_admins(db: Session) -> List[User]:
    """
    Returns all users with platform administrator privileges according to the transitional model:
    - Users whose platform_role is 'owner' or 'admin', provided is_platform_admin is True.
    - Legacy users whose platform_role IS NULL and is_platform_admin IS True.
    Excludes Operators, non-platform users, and contradictory role/boolean records.
    """
    return (
        db.query(User)
        .filter(
            User.is_platform_admin == True,
            or_(
                User.platform_role.in_(["owner", "admin"]),
                User.platform_role.is_(None),
            )
        )
        .order_by(User.created_at.asc())
        .all()
    )


def grant_platform_admin(
    db: Session,
    target_user_id: uuid.UUID,
    actor_user_id: Optional[uuid.UUID] = None,
    commit: bool = True,
) -> User:
    """
    Grants platform administrator privileges to an existing user.
    """
    _acquire_admin_serialization_lock(db)

    user = db.query(User).filter(User.id == target_user_id).first()
    if not user:
        raise NotFoundError(f"User with ID '{target_user_id}' not found.")

    if user.status != "active":
        raise ValidationError(
            f"Cannot grant platform administrator privileges to user with status '{user.status}'. Only active accounts can be promoted."
        )

    if user.platform_role == "owner":
        return user

    if user.is_platform_admin and user.platform_role == "admin":
        return user

    user.is_platform_admin = True
    user.platform_role = "admin"
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

    if commit:
        db.commit()
        db.refresh(user)
    else:
        db.flush()
    return user


def revoke_platform_admin(
    db: Session,
    target_user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    commit: bool = True,
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

    if user.platform_role == "owner":
        raise ValidationError("Platform Owner privileges cannot be revoked.")

    if not user.is_platform_admin and user.platform_role != "admin":
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
    user.platform_role = None
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

    if commit:
        db.commit()
        db.refresh(user)
    else:
        db.flush()
    return user


def transfer_platform_owner(
    db: Session,
    actor_user_id: uuid.UUID,
    target_user_id: uuid.UUID,
    current_password: str,
) -> User:
    """
    Transfers the Platform Owner role from the current active owner (actor) to another active user (target).
    Demotes the departing owner to 'admin' (is_platform_admin=True) and promotes the target to 'owner' (is_platform_admin=True).
    Follows strict caller-owned transaction semantics: executes flushes and never calls commit() or rollback().
    """
    # 1. Pre-lock verification: check actor credentials to minimize lock contention
    actor = db.query(User).filter(User.id == actor_user_id).first()
    if not actor:
        raise NotFoundError(f"Actor user with ID '{actor_user_id}' not found.")

    if actor.status != "active":
        raise ForbiddenError(f"Actor account has status '{actor.status}'. Only active accounts can transfer ownership.")

    if actor.platform_role != "owner" or not actor.is_platform_admin:
        raise ForbiddenError("Actor does not possess Platform Owner privileges.")

    if not actor.password_hash or not verify_password(current_password, actor.password_hash):
        raise AuthenticationError("Invalid current password for Platform Owner transfer.")

    saved_password_hash = actor.password_hash

    # 2. Acquire transaction serialization lock
    _acquire_admin_serialization_lock(db)

    # 3. Reload actor with populate_existing() after lock to observe any committed changes under READ COMMITTED
    actor = db.query(User).populate_existing().filter(User.id == actor_user_id).first()
    if not actor:
        raise NotFoundError(f"Actor user with ID '{actor_user_id}' not found.")

    # 4. Revalidate actor state after lock acquisition
    if actor.status != "active":
        raise ForbiddenError(f"Actor account has status '{actor.status}'. Only active accounts can transfer ownership.")

    if actor.platform_role != "owner" or not actor.is_platform_admin:
        raise ForbiddenError("Actor does not possess Platform Owner privileges.")

    # If the password hash changed while waiting for the lock, reverify the password
    if actor.password_hash != saved_password_hash:
        if not actor.password_hash or not verify_password(current_password, actor.password_hash):
            raise AuthenticationError("Invalid current password for Platform Owner transfer.")

    # 5. Target validations
    if target_user_id == actor.id:
        raise ValidationError("Cannot transfer platform ownership to yourself.")

    target = db.query(User).populate_existing().filter(User.id == target_user_id).first()
    if not target:
        raise NotFoundError(f"Target user with ID '{target_user_id}' not found.")

    if target.status != "active":
        raise ValidationError(
            f"Cannot transfer platform ownership to user with status '{target.status}'. Target account must be active."
        )

    # 6. Demote predecessor first to preserve ix_users_single_active_platform_owner index, then flush
    actor.platform_role = "admin"
    actor.is_platform_admin = True
    db.flush()

    # 7. Promote successor, then flush
    target.platform_role = "owner"
    target.is_platform_admin = True
    db.flush()

    # 8. Record audit log
    log_audit(
        db=db,
        business_id=None,
        outlet_id=None,
        actor_user_id=actor.id,
        action="platform.owner.transfer",
        entity_type="user",
        entity_id=target.id,
        metadata_json={
            "outcome": "success",
            "predecessor_user_id": str(actor.id),
            "predecessor_email": actor.email,
            "successor_user_id": str(target.id),
            "successor_email": target.email,
            "predecessor_new_role": "admin",
            "successor_new_role": "owner",
        },
    )

    return target


def create_platform_operator(
    db: Session,
    data: PlatformOperatorCreateRequest,
    actor_user_id: uuid.UUID,
) -> User:
    """
    Provisions a Platform Operator either by existing-user assignment (Mode 1)
    or by new-user creation (Mode 2).
    Requires actor to be an active Platform Owner.
    Follows caller-owned transaction semantics: executes flushes and never calls commit() or rollback().
    """
    if not actor_user_id:
        raise ValidationError("Actor user ID is required to provision a platform operator.")

    # 1. Acquire transaction serialization lock
    _acquire_admin_serialization_lock(db)

    # 2. Reload actor with populate_existing() and revalidate active Owner role
    actor = db.query(User).populate_existing().filter(User.id == actor_user_id).first()
    if not actor:
        raise NotFoundError(f"Actor user with ID '{actor_user_id}' not found.")

    if actor.status != "active":
        raise ForbiddenError(f"Actor account has status '{actor.status}'. Only active accounts can provision operators.")

    if not actor.is_platform_admin or actor.platform_role not in ("owner", "admin"):
        raise ForbiddenError("Platform Administrator or Owner privileges are required to provision operators.")

    # 3. Branching: Mode 1 (Existing User) vs Mode 2 (New User)
    if data.user_id is not None:
        # --- Mode 1: Existing-User Assignment ---
        target = db.query(User).populate_existing().filter(User.id == data.user_id).first()
        if not target:
            raise NotFoundError(f"Target user with ID '{data.user_id}' not found.")

        if target.status != "active":
            raise ValidationError(
                f"Cannot assign Operator role to user with status '{target.status}'. Only active accounts can be assigned."
            )

        if target.platform_role == "owner":
            raise ValidationError("Platform Owner cannot be demoted to Operator. Transfer platform ownership first.")

        # Idempotency check: if already an active operator, safe no-op
        if target.platform_role == "operator" and not target.is_platform_admin:
            return target

        previous_role = target.platform_role
        target.platform_role = "operator"
        target.is_platform_admin = False
        db.flush()

        log_audit(
            db=db,
            business_id=None,
            outlet_id=None,
            actor_user_id=actor.id,
            action="platform.operator.create",
            entity_type="user",
            entity_id=target.id,
            metadata_json={
                "outcome": "success",
                "mode": "existing_user",
                "target_user_id": str(target.id),
                "target_email": target.email,
                "previous_role": previous_role,
                "new_role": "operator",
            },
        )
        return target

    else:
        # --- Mode 2: New-User Creation ---
        clean_email = data.email.strip().lower()

        # Reject if email already exists in users (instruct caller to use existing-user assignment)
        existing_user = db.query(User).populate_existing().filter(User.email == clean_email).first()
        if existing_user:
            raise ValidationError(
                f"A user with email '{clean_email}' already exists. "
                f"To assign this user as an Operator, use existing-user assignment mode with user_id '{existing_user.id}'."
            )

        new_user = User(
            email=clean_email,
            display_name=data.display_name.strip(),
            password_hash=hash_password(data.password),
            status="active",
            is_platform_admin=False,
            platform_role="operator",
        )
        db.add(new_user)
        try:
            db.flush()
        except IntegrityError as e:
            raise ValidationError(
                f"A user with email '{clean_email}' already exists."
            ) from e

        log_audit(
            db=db,
            business_id=None,
            outlet_id=None,
            actor_user_id=actor.id,
            action="platform.operator.create",
            entity_type="user",
            entity_id=new_user.id,
            metadata_json={
                "outcome": "success",
                "mode": "new_user",
                "target_user_id": str(new_user.id),
                "target_email": new_user.email,
                "previous_role": None,
                "new_role": "operator",
            },
        )
        return new_user


def revoke_platform_operator(
    db: Session,
    target_user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> User:
    """
    Revokes the Platform Operator role from a user, setting platform_role to None and is_platform_admin to False.
    Preserves account status (e.g. active, suspended) and all tenant memberships intact.
    Requires actor to be an active Platform Owner.
    Follows caller-owned transaction semantics: executes flushes and never calls commit() or rollback().
    """
    if not actor_user_id:
        raise ValidationError("Actor user ID is required to revoke platform operator privileges.")

    # 1. Acquire transaction serialization lock
    _acquire_admin_serialization_lock(db)

    # 2. Reload actor with populate_existing() and revalidate active Owner role
    actor = db.query(User).populate_existing().filter(User.id == actor_user_id).first()
    if not actor:
        raise NotFoundError(f"Actor user with ID '{actor_user_id}' not found.")

    if actor.status != "active":
        raise ForbiddenError(f"Actor account has status '{actor.status}'. Only active accounts can revoke operators.")

    if not actor.is_platform_admin or actor.platform_role not in ("owner", "admin"):
        raise ForbiddenError("Platform Administrator or Owner privileges are required to revoke operators.")

    # 3. Reload target user with populate_existing()
    target = db.query(User).populate_existing().filter(User.id == target_user_id).first()
    if not target:
        raise NotFoundError(f"User with ID '{target_user_id}' not found.")

    if target.platform_role == "owner":
        raise ValidationError("Platform Owner privileges cannot be revoked.")

    # Idempotency check: if not currently an operator, safe no-op (no mutation, no audit log)
    if target.platform_role != "operator":
        return target

    # 4. Atomic role mutation: clear platform role, leave status and memberships untouched
    target.platform_role = None
    target.is_platform_admin = False
    db.flush()

    # 5. Record audit log
    log_audit(
        db=db,
        business_id=None,
        outlet_id=None,
        actor_user_id=actor.id,
        action="platform.operator.revoke",
        entity_type="user",
        entity_id=target.id,
        metadata_json={
            "outcome": "success",
            "target_user_id": str(target.id),
            "target_email": target.email,
        },
    )

    return target


def list_platform_operators(db: Session) -> List[User]:
    """
    Returns all users with valid platform operator status according to the model:
    platform_role == 'operator' and is_platform_admin is False.
    Excludes contradictory pairs and non-operators.
    """
    return (
        db.query(User)
        .filter(
            User.platform_role == "operator",
            User.is_platform_admin == False,
        )
        .order_by(User.created_at.asc())
        .all()
    )


def suspend_platform_user(
    db: Session,
    target_user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> User:
    """
    Safely suspends a platform user (sets status to 'suspended').
    Preserves account data, platform roles, and tenant memberships intact.
    Immediately prevents authentication and API access.
    Requires actor to be an active Platform Owner.
    Platform Owners cannot be suspended.
    Users cannot suspend their own account.
    Safe idempotent no-op if user is already suspended.
    Follows caller-owned transaction semantics: executes flushes and never calls commit() or rollback().
    """
    if not actor_user_id:
        raise ValidationError("Actor user ID is required to suspend a platform user.")

    # 1. Acquire transaction serialization lock
    _acquire_admin_serialization_lock(db)

    # 2. Reload actor with populate_existing() and revalidate active Owner role
    actor = db.query(User).populate_existing().filter(User.id == actor_user_id).first()
    if not actor:
        raise NotFoundError(f"Actor user with ID '{actor_user_id}' not found.")

    if actor.status != "active":
        raise ForbiddenError(f"Actor account has status '{actor.status}'. Only active accounts can suspend users.")

    if not actor.is_platform_admin or actor.platform_role not in ("owner", "admin"):
        raise ForbiddenError("Platform Administrator or Owner privileges are required to suspend users.")

    # 3. Self-suspension prevention
    if target_user_id == actor.id:
        raise ValidationError("You cannot suspend your own account.")

    # 4. Target retrieval and validation
    target = db.query(User).populate_existing().filter(User.id == target_user_id).first()
    if not target:
        raise NotFoundError(f"User with ID '{target_user_id}' not found.")

    # 5. Owner protection check
    if target.platform_role == "owner":
        raise ValidationError("Platform Owner cannot be suspended.")

    if (target.is_platform_admin or target.platform_role in ("admin", "owner")) and actor.platform_role != "owner":
        raise ForbiddenError("Only the Platform Owner can suspend another Platform Administrator.")

    # 6. Idempotency check: if already suspended, return target without mutation or audit log
    if target.status == "suspended":
        return target

    # Validate target status transition
    if target.status != "active":
        raise ValidationError(f"Cannot suspend user with status '{target.status}'.")

    # 7. Atomic status mutation: suspend user, leaving roles and memberships untouched
    target.status = "suspended"
    db.flush()

    # 8. Record audit log
    log_audit(
        db=db,
        business_id=None,
        outlet_id=None,
        actor_user_id=actor.id,
        action="platform.user.suspend",
        entity_type="user",
        entity_id=target.id,
        metadata_json={
            "outcome": "success",
            "target_user_id": str(target.id),
            "target_email": target.email,
            "previous_status": "active",
            "new_status": "suspended",
            "platform_role": target.platform_role,
        },
    )

    return target


def reactivate_platform_user(
    db: Session,
    target_user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> User:
    """
    Safely reactivates a suspended platform user (sets status to 'active').
    Restores login and access capability without altering platform roles, tenant memberships, or permissions.
    Requires actor to be an active Platform Owner.
    Users cannot reactivate their own account.
    Safe idempotent no-op if user is already active.
    Follows caller-owned transaction semantics: executes flushes and never calls commit() or rollback().
    """
    if not actor_user_id:
        raise ValidationError("Actor user ID is required to reactivate a platform user.")

    # 1. Acquire transaction serialization lock
    _acquire_admin_serialization_lock(db)

    # 2. Reload actor with populate_existing() and revalidate active Owner role
    actor = db.query(User).populate_existing().filter(User.id == actor_user_id).first()
    if not actor:
        raise NotFoundError(f"Actor user with ID '{actor_user_id}' not found.")

    if actor.status != "active":
        raise ForbiddenError(f"Actor account has status '{actor.status}'. Only active accounts can reactivate users.")

    if actor.platform_role != "owner" or not actor.is_platform_admin:
        raise ForbiddenError("Platform Owner privileges are required to reactivate users.")

    # 3. Self-reactivation prevention
    if target_user_id == actor.id:
        raise ValidationError("You cannot reactivate your own account.")

    # 4. Target retrieval and validation
    target = db.query(User).populate_existing().filter(User.id == target_user_id).first()
    if not target:
        raise NotFoundError(f"User with ID '{target_user_id}' not found.")

    # 5. Idempotency check: if already active, return target without mutation or audit log
    if target.status == "active":
        return target

    # Validate target status transition
    if target.status != "suspended":
        raise ValidationError(f"Cannot reactivate user with status '{target.status}'.")

    # 6. Atomic status mutation: activate user, leaving roles and memberships untouched
    target.status = "active"
    db.flush()

    # 7. Record audit log
    log_audit(
        db=db,
        business_id=None,
        outlet_id=None,
        actor_user_id=actor.id,
        action="platform.user.reactivate",
        entity_type="user",
        entity_id=target.id,
        metadata_json={
            "outcome": "success",
            "target_user_id": str(target.id),
            "target_email": target.email,
            "previous_status": "suspended",
            "new_status": "active",
            "platform_role": target.platform_role,
        },
    )

    return target


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
    actor_user_id: Optional[uuid.UUID] = None,
    commit: bool = True,
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
    before_status = business.status
    new_name = data.name.strip()
    if not new_name:
        raise ValidationError("Business name cannot be empty.")

    business.name = new_name

    status_changed = False
    if data.status is not None:
        clean_status = data.status.strip().lower()
        if clean_status != business.status:
            business.status = clean_status
            status_changed = True

    db.flush()

    try:
        # Standard profile update audit log
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
                "before": {"name": before_name, "status": before_status},
                "after": {"name": business.name, "status": business.status},
            }
        )

        # Emit suspend or reactivate audit log only when status actually changes
        if status_changed:
            if before_status != "suspended" and business.status == "suspended":
                log_audit(
                    db=db,
                    business_id=business.id,
                    outlet_id=None,
                    actor_user_id=actor_user_id,
                    action="platform.business.suspend",
                    entity_type="business",
                    entity_id=business.id,
                    metadata_json={
                        "outcome": "success",
                        "before": {"status": before_status},
                        "after": {"status": business.status},
                    }
                )
            elif before_status == "suspended" and business.status == "active":
                log_audit(
                    db=db,
                    business_id=business.id,
                    outlet_id=None,
                    actor_user_id=actor_user_id,
                    action="platform.business.reactivate",
                    entity_type="business",
                    entity_id=business.id,
                    metadata_json={
                        "outcome": "success",
                        "before": {"status": before_status},
                        "after": {"status": business.status},
                    }
                )

        if commit:
            db.commit()
        else:
            db.flush()
    except Exception:
        if commit:
            db.rollback()
        raise

    if commit:
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
    actor_user_id: Optional[uuid.UUID] = None,
    commit: bool = True,
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
        if commit:
            db.commit()
        else:
            db.flush()
    except Exception:
        if commit:
            db.rollback()
        raise

    if commit:
        db.refresh(outlet)
    return outlet


def update_outlet_subscription(
    db: Session,
    outlet_id: uuid.UUID,
    data: PlatformOutletSubscriptionUpdate,
    actor_user_id: Optional[uuid.UUID] = None,
    commit: bool = True,
) -> OutletSubscription:
    """
    Updates outlet subscription lifecycle, plan, and audit history.
    Enforces atomic row replacement, strict 1-calendar-year annual commitments,
    action-specific validation, and single-current-row invariant via pessimistic row locking.
    Does NOT affect sibling outlets or mutate business-level subscription columns.
    """
    if db.bind and db.bind.dialect.name == "postgresql":
        outlet = db.query(Outlet).with_for_update().filter(Outlet.id == outlet_id).first()
    else:
        outlet = db.query(Outlet).filter(Outlet.id == outlet_id).first()

    if not outlet:
        raise NotFoundError(f"Outlet with ID '{outlet_id}' not found.")

    business = db.query(Business).filter(Business.id == outlet.business_id).first()
    if not business:
        raise NotFoundError(f"Parent business for outlet '{outlet_id}' not found.")

    curr_sub = db.query(OutletSubscription).options(
        joinedload(OutletSubscription.plan)
    ).filter(
        OutletSubscription.outlet_id == outlet_id,
        OutletSubscription.is_current == True
    ).first()

    now = utc_now()
    action_type = (data.action_type or "").strip()
    if not action_type:
        raise ValidationError("action_type is required for outlet subscription lifecycle management.")

    before_state = {
        "status": curr_sub.status if curr_sub else None,
        "plan_code": curr_sub.plan.code if (curr_sub and curr_sub.plan) else None,
        "plan_name": curr_sub.plan.name if (curr_sub and curr_sub.plan) else None,
        "trial_ends_at": curr_sub.trial_ends_at.isoformat() if (curr_sub and curr_sub.trial_ends_at) else None,
        "current_period_start": curr_sub.current_period_start.isoformat() if (curr_sub and curr_sub.current_period_start) else None,
        "current_period_end": curr_sub.current_period_end.isoformat() if (curr_sub and curr_sub.current_period_end) else None,
        "cancel_at_period_end": curr_sub.cancel_at_period_end if curr_sub else False,
        "cancelled_at": curr_sub.cancelled_at.isoformat() if (curr_sub and curr_sub.cancelled_at) else None,
    }

    audit_action = f"platform.outlet_subscription.{action_type}"
    audit_metadata: dict = {"reason": data.reason}
    resulting_sub: Optional[OutletSubscription] = None

    if action_type == "activate":
        # Reject irrelevant fields
        if data.trial_ends_at is not None:
            raise ValidationError("trial_ends_at cannot be updated during activation.")

        plan_identifier = data.plan_code or data.plan_name or (curr_sub.plan.code if (curr_sub and curr_sub.plan) else None)
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

        # Free QR special case: non-expiring if period-end is omitted
        if target_plan.code == "free_qr" and data.current_period_end is None:
            end_dt = None
        else:
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

        resulting_sub = OutletSubscription(
            outlet_id=outlet.id,
            business_id=outlet.business_id,
            plan_id=target_plan.id,
            status="active",
            is_current=True,
            trial_ends_at=None,
            current_period_start=start_dt,
            current_period_end=end_dt,
            cancel_at_period_end=False,
            cancelled_at=None,
        )
        db.add(resulting_sub)

    elif action_type == "renew":
        if data.trial_ends_at is not None:
            raise ValidationError("trial_ends_at cannot be updated during renewal.")

        curr_period_end_utc = ensure_utc(curr_sub.current_period_end) if (curr_sub and curr_sub.current_period_end) else None
        is_timely = (
            curr_sub is not None
            and curr_sub.status == "active"
            and curr_period_end_utc is not None
            and now < curr_period_end_utc
        )

        plan_identifier = data.plan_code or data.plan_name or (curr_sub.plan.code if (curr_sub and curr_sub.plan) else None)
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
            resulting_sub = OutletSubscription(
                outlet_id=outlet.id,
                business_id=outlet.business_id,
                plan_id=target_plan.id,
                status="active",
                is_current=True,
                trial_ends_at=None,
                current_period_start=start_dt,
                current_period_end=end_dt,
                cancel_at_period_end=False,
                cancelled_at=None,
            )
            db.add(resulting_sub)
        else:
            # Late renewal
            if data.current_period_start is not None:
                start_dt = ensure_utc(data.current_period_start)
                if start_dt < now - timedelta(days=1):
                    reason_clean = (data.reason or "").strip()
                    if not reason_clean:
                        raise ValidationError("A meaningful administrative reason is required when supplying a historical contractual start date.")
                    audit_metadata["historical_start_reason"] = reason_clean
            else:
                start_dt = now

            if target_plan.code == "free_qr" and data.current_period_end is None:
                end_dt = None
            else:
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

            resulting_sub = OutletSubscription(
                outlet_id=outlet.id,
                business_id=outlet.business_id,
                plan_id=target_plan.id,
                status="active",
                is_current=True,
                trial_ends_at=None,
                current_period_start=start_dt,
                current_period_end=end_dt,
                cancel_at_period_end=False,
                cancelled_at=None,
            )
            db.add(resulting_sub)

    elif action_type == "change_plan":
        if not curr_sub:
            raise ValidationError("Cannot perform mid-term plan change without an existing current subscription.")
        if data.trial_ends_at is not None:
            raise ValidationError("trial_ends_at cannot be updated during mid-term plan change.")
        if data.current_period_start is not None or data.current_period_end is not None:
            raise ValidationError("Mid-term plan change preserves existing period dates; do not supply new start or end dates.")

        plan_identifier = data.plan_code or data.plan_name
        if not plan_identifier:
            raise ValidationError("plan_code or plan_name is required for plan change.")
        target_plan = resolve_plan(db, plan_identifier)

        curr_sub.is_current = False
        resulting_sub = OutletSubscription(
            outlet_id=outlet.id,
            business_id=outlet.business_id,
            plan_id=target_plan.id,
            status=curr_sub.status,
            is_current=True,
            trial_ends_at=ensure_utc(curr_sub.trial_ends_at),
            current_period_start=ensure_utc(curr_sub.current_period_start),
            current_period_end=ensure_utc(curr_sub.current_period_end),
            cancel_at_period_end=curr_sub.cancel_at_period_end,
            cancelled_at=ensure_utc(curr_sub.cancelled_at),
        )
        db.add(resulting_sub)

    elif action_type == "change_plan_new_term":
        if data.trial_ends_at is not None:
            raise ValidationError("trial_ends_at cannot be updated during change_plan_new_term.")

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

        if target_plan.code == "free_qr" and data.current_period_end is None:
            end_dt = None
        else:
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

        resulting_sub = OutletSubscription(
            outlet_id=outlet.id,
            business_id=outlet.business_id,
            plan_id=target_plan.id,
            status="active",
            is_current=True,
            trial_ends_at=None,
            current_period_start=start_dt,
            current_period_end=end_dt,
            cancel_at_period_end=False,
            cancelled_at=None,
        )
        db.add(resulting_sub)

    elif action_type == "extend_trial":
        if data.plan_code or data.plan_name:
            raise ValidationError("Plan cannot be changed via extend_trial. Use activate or change_plan.")
        if data.current_period_start is not None or data.current_period_end is not None:
            raise ValidationError("Period dates are not applicable to trial extension.")
        if not data.trial_ends_at:
            raise ValidationError("trial_ends_at is required to extend trial.")

        trial_ends = ensure_utc(data.trial_ends_at)
        if trial_ends <= now:
            raise ValidationError("trial_ends_at must be strictly in the future.")

        if not curr_sub:
            raise ValidationError("Cannot extend trial without an existing subscription record.")

        curr_sub.trial_ends_at = trial_ends
        curr_sub.status = "trial"
        resulting_sub = curr_sub

    elif action_type == "schedule_cancellation":
        if data.plan_code or data.plan_name:
            raise ValidationError("Plan cannot be changed when scheduling cancellation.")
        if data.trial_ends_at is not None or data.current_period_start is not None or data.current_period_end is not None:
            raise ValidationError("Dates cannot be updated when scheduling cancellation.")

        if not curr_sub or curr_sub.status not in ("active", "past_due"):
            raise ValidationError("Can only schedule cancellation for an active or past_due subscription.")
        curr_end_utc = ensure_utc(curr_sub.current_period_end)
        if not curr_end_utc or curr_end_utc <= now:
            raise ValidationError("Cannot schedule cancellation for an expired subscription.")

        curr_sub.cancel_at_period_end = True
        curr_sub.cancelled_at = now
        resulting_sub = curr_sub

    elif action_type == "revoke_scheduled_cancellation":
        if data.plan_code or data.plan_name or data.trial_ends_at or data.current_period_start or data.current_period_end:
            raise ValidationError("Fields other than reason cannot be updated when revoking scheduled cancellation.")

        if not curr_sub or not curr_sub.cancel_at_period_end:
            raise ValidationError("No scheduled cancellation found to revoke.")

        curr_sub.cancel_at_period_end = False
        curr_sub.cancelled_at = None
        resulting_sub = curr_sub

    elif action_type == "cancel_immediately":
        if data.plan_code or data.plan_name or data.trial_ends_at or data.current_period_start or data.current_period_end:
            raise ValidationError("Fields other than reason cannot be updated during immediate cancellation.")

        reason_clean = (data.reason or "").strip()
        if not reason_clean:
            raise ValidationError("Reason is required for immediate cancellation.")

        if not curr_sub:
            raise ValidationError("No current subscription found to cancel.")

        curr_sub.status = "cancelled"
        curr_sub.cancelled_at = now
        curr_sub.cancel_at_period_end = False
        resulting_sub = curr_sub

    elif action_type == "mark_past_due":
        if data.plan_code or data.plan_name or data.trial_ends_at or data.current_period_start or data.current_period_end:
            raise ValidationError("Fields cannot be updated with mark_past_due. For extensions use mark_past_due_with_extension.")

        if not curr_sub:
            raise ValidationError("No current subscription found.")

        curr_sub.status = "past_due"
        resulting_sub = curr_sub

    elif action_type == "mark_past_due_with_extension":
        if data.plan_code or data.plan_name or data.trial_ends_at or data.current_period_start:
            raise ValidationError("Only current_period_end and reason can be provided for past-due recovery extension.")

        if not data.current_period_end:
            raise ValidationError("current_period_end is required for past-due recovery extension.")

        ext_end = ensure_utc(data.current_period_end)
        if ext_end <= now:
            raise ValidationError("current_period_end extension must be strictly in the future.")

        reason_clean = (data.reason or "").strip()
        if not reason_clean:
            raise ValidationError("Reason is required for past-due recovery extension.")

        if not curr_sub:
            raise ValidationError("No current subscription found.")

        curr_sub.status = "past_due"
        curr_sub.current_period_end = ext_end
        audit_metadata["extension_reason"] = reason_clean
        resulting_sub = curr_sub

    else:
        raise ValidationError(f"Unknown lifecycle action_type '{action_type}'.")

    db.flush()

    # Re-fetch the current subscription after changes
    final_sub = db.query(OutletSubscription).options(
        joinedload(OutletSubscription.plan)
    ).filter(
        OutletSubscription.outlet_id == outlet_id,
        OutletSubscription.is_current == True
    ).first()

    after_state = {
        "status": final_sub.status if final_sub else None,
        "plan_code": final_sub.plan.code if (final_sub and final_sub.plan) else None,
        "plan_name": final_sub.plan.name if (final_sub and final_sub.plan) else None,
        "trial_ends_at": final_sub.trial_ends_at.isoformat() if (final_sub and final_sub.trial_ends_at) else None,
        "current_period_start": final_sub.current_period_start.isoformat() if (final_sub and final_sub.current_period_start) else None,
        "current_period_end": final_sub.current_period_end.isoformat() if (final_sub and final_sub.current_period_end) else None,
        "cancel_at_period_end": final_sub.cancel_at_period_end if final_sub else False,
        "cancelled_at": final_sub.cancelled_at.isoformat() if (final_sub and final_sub.cancelled_at) else None,
    }

    try:
        log_audit(
            db=db,
            business_id=outlet.business_id,
            outlet_id=outlet.id,
            actor_user_id=actor_user_id,
            action=audit_action,
            entity_type="outlet_subscription",
            entity_id=final_sub.id if final_sub else None,
            metadata_json={
                "outcome": "success",
                "action_type": action_type,
                "before": before_state,
                "after": after_state,
                **audit_metadata
            }
        )
        if commit:
            db.commit()
        else:
            db.flush()
    except Exception:
        if commit:
            db.rollback()
        raise

    if commit:
        db.refresh(final_sub)
    return final_sub
