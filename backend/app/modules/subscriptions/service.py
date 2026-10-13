import calendar
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session, joinedload

from app.db.base import utc_now
from app.modules.businesses.models import Business
from app.modules.subscriptions.models import (
    Plan, Feature, PlanFeature, BusinessSubscription, EntitlementOverride
)
from app.modules.subscriptions.schemas import EntitlementCheckResult


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_annual_period_end(start_dt: datetime) -> datetime:
    """
    Computes the exact 1-calendar-year contractual anniversary.
    Preserves time and timezone (normalized to UTC).
    Handles leap days (Feb 29 -> Feb 28 in non-leap year) and month-end dates.
    """
    start_utc = ensure_utc(start_dt)
    target_year = start_utc.year + 1
    target_month = start_utc.month
    target_day = start_utc.day

    max_days = calendar.monthrange(target_year, target_month)[1]
    if target_day > max_days:
        target_day = max_days

    return start_utc.replace(year=target_year, day=target_day)


class EntitlementService:
    @staticmethod
    def evaluate_subscription_status(
        subscription: Optional[BusinessSubscription],
        now: Optional[datetime] = None
    ) -> str:
        """
        Evaluates subscription status with 0-day grace period rules.
        """
        if now is None:
            now = utc_now()
        now = ensure_utc(now)

        if subscription is None:
            return "expired"

        status = subscription.status

        # Standard status check
        if status not in ("active", "trial", "past_due", "cancelled"):
            return "expired"

        cancelled_at = ensure_utc(subscription.cancelled_at)
        trial_ends_at = ensure_utc(subscription.trial_ends_at)
        current_period_end = ensure_utc(subscription.current_period_end)

        # Immediate cancellation or past cancelled_at
        if status == "cancelled" or (
            cancelled_at is not None
            and cancelled_at <= now
            and not subscription.cancel_at_period_end
        ):
            return "cancelled"

        # Trial expiration check (0-day grace)
        if status == "trial":
            if trial_ends_at is None:
                return "expired"
            if now >= trial_ends_at:
                return "expired"
            return "trial"

        # Period expiration check for active / past_due (0-day grace, fail-closed if missing)
        if status in ("active", "past_due"):
            if current_period_end is None or now >= current_period_end:
                return "expired"
            return status

        return "expired"

    @classmethod
    def _evaluate_feature_entitlement(
        cls,
        business: Optional[Business],
        resolved_status: str,
        effective_plan_id: Optional[uuid.UUID],
        effective_plan_active: bool,
        feature_code: str,
        plan_features_dict: dict,
        active_restrictions: list,
        active_grants: list,
        outlet_id: Optional[uuid.UUID] = None,
        now: Optional[datetime] = None
    ) -> EntitlementCheckResult:
        # 1. Business Operational Status Check
        if not business or business.status != "active":
            return EntitlementCheckResult(
                authorized=False,
                limit_value=None,
                reason="BUSINESS_SUSPENDED",
                resolved_status=business.status if business else "unknown",
                source="business_suspended",
                scope="none"
            )

        # 2. Expiration Check & Read-only digital menu exception
        if resolved_status in ("expired", "cancelled"):
            if feature_code == "menu.digital":
                return EntitlementCheckResult(
                    authorized=True,
                    limit_value=None,
                    reason="READ_ONLY_MENU_ALLOWED",
                    resolved_status=resolved_status,
                    source="read_only_fallback",
                    scope="business"
                )
            return EntitlementCheckResult(
                authorized=False,
                limit_value=None,
                reason=f"SUBSCRIPTION_{resolved_status.upper()}",
                resolved_status=resolved_status,
                source="subscription_lifecycle",
                scope="none"
            )

        # 3. Active Restriction Overrides Check
        matching_restrictions = [
            r for r in active_restrictions
            if r.feature_code == feature_code
            and (r.outlet_id is None or (outlet_id is not None and r.outlet_id == outlet_id))
        ]
        if matching_restrictions:
            scope = "outlet" if any(r.outlet_id == outlet_id for r in matching_restrictions if outlet_id) else "business"
            return EntitlementCheckResult(
                authorized=False,
                limit_value=0,
                reason="RESTRICTION_OVERRIDE_ACTIVE",
                resolved_status=resolved_status,
                source="restriction_override",
                scope=scope
            )

        # 4. Authoritative Plan Feature Definition
        plan_limit = None
        plan_has_feature = False
        if effective_plan_id and effective_plan_active:
            if feature_code in plan_features_dict:
                plan_has_feature = True
                plan_limit = plan_features_dict[feature_code]

        # 5. Grant Overrides (Decision 001 Option A: Scope-Hierarchical Replacement)
        feature_grants = [g for g in active_grants if g.feature_code == feature_code]
        outlet_grants = [g for g in feature_grants if g.outlet_id == outlet_id] if outlet_id else []
        business_grants = [g for g in feature_grants if g.outlet_id is None]

        if outlet_id and outlet_grants:
            selected_grants = outlet_grants
            grant_scope = "outlet"
        else:
            selected_grants = business_grants
            grant_scope = "business"

        authorized = plan_has_feature or len(selected_grants) > 0
        if not authorized:
            return EntitlementCheckResult(
                authorized=False,
                limit_value=0,
                reason="FEATURE_NOT_INCLUDED_IN_PLAN",
                resolved_status=resolved_status,
                source="plan",
                scope="none"
            )

        # Determine source and scope
        if len(selected_grants) > 0:
            source = "grant_override"
            scope = grant_scope
        else:
            source = "plan"
            scope = "business"

        # 6. Numeric Limit Resolution
        numeric_grants = [g.limit_value for g in selected_grants if g.limit_value is not None]
        if numeric_grants:
            resolved_limit = max(numeric_grants)
        else:
            resolved_limit = plan_limit
            if feature_code == "outlets.max_count":
                if business.max_outlets is not None:
                    if resolved_limit is None:
                        resolved_limit = business.max_outlets
                        source = "legacy_scalar"
                    else:
                        if business.max_outlets < resolved_limit:
                            resolved_limit = business.max_outlets
                            source = "legacy_scalar"

        return EntitlementCheckResult(
            authorized=True,
            limit_value=resolved_limit,
            reason="AUTHORIZED",
            resolved_status=resolved_status,
            source=source,
            scope=scope
        )

    @classmethod
    def check_entitlement(
        cls,
        db: Session,
        business_id: uuid.UUID,
        feature_code: str,
        outlet_id: Optional[uuid.UUID] = None,
        now: Optional[datetime] = None
    ) -> EntitlementCheckResult:
        if now is None:
            now = utc_now()
        now = ensure_utc(now)

        business = db.scalar(select(Business).where(Business.id == business_id))
        if not business or business.status != "active":
            return EntitlementCheckResult(
                authorized=False,
                limit_value=None,
                reason="BUSINESS_SUSPENDED",
                resolved_status=business.status if business else "unknown",
                source="business_suspended",
                scope="none"
            )

        sub = db.scalar(
            select(BusinessSubscription)
            .where(
                and_(
                    BusinessSubscription.business_id == business_id,
                    BusinessSubscription.is_current == True
                )
            )
            .options(joinedload(BusinessSubscription.plan))
        )

        if sub:
            resolved_status = cls.evaluate_subscription_status(sub, now)
            effective_plan_id = sub.plan_id
            effective_plan_active = sub.plan.is_active if sub.plan else True
        else:
            sub_status = business.subscription_status or "active"
            if sub_status == "trial" and business.trial_ends_at and now >= ensure_utc(business.trial_ends_at):
                resolved_status = "expired"
            elif sub_status in ("active", "trial"):
                resolved_status = sub_status
            else:
                resolved_status = "expired"

            PLAN_MAP = {
                'starter': 'starter_pos',
                'growth': 'growth_pos',
                'pro': 'pro_kds',
                'enterprise': 'enterprise',
                'digital_menu': 'free_qr',
                'free': 'free_qr',
            }
            raw_plan = business.plan_name.lower() if business.plan_name else ""
            default_code = "growth_pos" if (business.max_outlets is None or business.max_outlets > 1) else "starter_pos"
            target_code = PLAN_MAP.get(raw_plan, default_code)
            fallback_plan = db.scalar(select(Plan).where(Plan.code == target_code))
            effective_plan_id = fallback_plan.id if fallback_plan else None
            effective_plan_active = fallback_plan.is_active if fallback_plan else True

        # Pre-load plan features dict
        plan_features_dict = {}
        if effective_plan_id and effective_plan_active:
            pfs = db.scalars(
                select(PlanFeature)
                .join(Feature, PlanFeature.feature_id == Feature.id)
                .where(
                    and_(
                        PlanFeature.plan_id == effective_plan_id,
                        Feature.code == feature_code
                    )
                )
            ).all()
            for pf in pfs:
                plan_features_dict[feature_code] = pf.limit_value

        # Pre-load active restrictions and grants
        all_overrides = db.scalars(
            select(EntitlementOverride).where(
                and_(
                    EntitlementOverride.business_id == business_id,
                    EntitlementOverride.feature_code == feature_code
                )
            )
        ).all()

        active_restrictions = [
            r for r in all_overrides
            if r.override_type == "restrict"
            and (r.expires_at is None or ensure_utc(r.expires_at) > now)
        ]
        active_grants = [
            g for g in all_overrides
            if g.override_type == "grant"
            and (g.expires_at is None or ensure_utc(g.expires_at) > now)
        ]

        return cls._evaluate_feature_entitlement(
            business=business,
            resolved_status=resolved_status,
            effective_plan_id=effective_plan_id,
            effective_plan_active=effective_plan_active,
            feature_code=feature_code,
            plan_features_dict=plan_features_dict,
            active_restrictions=active_restrictions,
            active_grants=active_grants,
            outlet_id=outlet_id,
            now=now
        )

    @classmethod
    def inspect_all_entitlements(
        cls,
        db: Session,
        business_id: uuid.UUID,
        outlet_id: Optional[uuid.UUID] = None,
        now: Optional[datetime] = None
    ):
        from app.core.errors import NotFoundError, ValidationError
        from app.modules.outlets.models import Outlet
        from app.modules.subscriptions.schemas import (
            PlatformBusinessEntitlementsOut,
            PlatformSubscriptionSummary,
            PlatformFeatureInspectionItem
        )

        if now is None:
            now = utc_now()
        now = ensure_utc(now)

        business = db.scalar(select(Business).where(Business.id == business_id))
        if not business:
            raise NotFoundError(f"Business with ID '{business_id}' not found.")

        target_outlet = None
        if outlet_id:
            target_outlet = db.scalar(select(Outlet).where(Outlet.id == outlet_id))
            if not target_outlet or target_outlet.business_id != business_id:
                raise ValidationError(f"Outlet '{outlet_id}' does not belong to business '{business_id}'.")

        # Query active subscription
        sub = db.scalar(
            select(BusinessSubscription)
            .where(
                and_(
                    BusinessSubscription.business_id == business_id,
                    BusinessSubscription.is_current == True
                )
            )
            .options(joinedload(BusinessSubscription.plan))
        )

        if sub:
            resolved_status = cls.evaluate_subscription_status(sub, now)
            effective_plan_id = sub.plan_id
            effective_plan_active = sub.plan.is_active if sub.plan else True
            plan_code = sub.plan.code if sub.plan else "unknown"
            plan_name = sub.plan.name if sub.plan else "Unknown"
            sub_summary = PlatformSubscriptionSummary(
                id=sub.id,
                status=sub.status,
                resolved_status=resolved_status,
                plan_code=plan_code,
                plan_name=plan_name,
                plan_is_active=effective_plan_active,
                trial_ends_at=sub.trial_ends_at,
                current_period_start=sub.current_period_start,
                current_period_end=sub.current_period_end,
                cancel_at_period_end=sub.cancel_at_period_end,
                cancelled_at=sub.cancelled_at
            )
        else:
            sub_status = business.subscription_status or "active"
            if sub_status == "trial" and business.trial_ends_at and now >= ensure_utc(business.trial_ends_at):
                resolved_status = "expired"
            elif sub_status in ("active", "trial"):
                resolved_status = sub_status
            else:
                resolved_status = "expired"

            PLAN_MAP = {
                'starter': 'starter_pos',
                'growth': 'growth_pos',
                'pro': 'pro_kds',
                'enterprise': 'enterprise',
                'digital_menu': 'free_qr',
                'free': 'free_qr',
            }
            raw_plan = business.plan_name.lower() if business.plan_name else ""
            default_code = "growth_pos" if (business.max_outlets is None or business.max_outlets > 1) else "starter_pos"
            target_code = PLAN_MAP.get(raw_plan, default_code)
            fallback_plan = db.scalar(select(Plan).where(Plan.code == target_code))
            effective_plan_id = fallback_plan.id if fallback_plan else None
            effective_plan_active = fallback_plan.is_active if fallback_plan else True
            plan_code = fallback_plan.code if fallback_plan else "unknown"
            plan_name = fallback_plan.name if fallback_plan else "Unknown"
            sub_summary = PlatformSubscriptionSummary(
                id=None,
                status=sub_status,
                resolved_status=resolved_status,
                plan_code=plan_code,
                plan_name=plan_name,
                plan_is_active=effective_plan_active,
                trial_ends_at=business.trial_ends_at,
                current_period_start=None,
                current_period_end=None,
                cancel_at_period_end=False,
                cancelled_at=None
            )

        # Batch load catalog features
        all_features = list(db.scalars(select(Feature).order_by(Feature.category, Feature.code)).all())

        # Batch load plan_features
        plan_features_dict = {}
        if effective_plan_id and effective_plan_active:
            pfs = db.scalars(
                select(PlanFeature)
                .join(Feature, PlanFeature.feature_id == Feature.id)
                .where(PlanFeature.plan_id == effective_plan_id)
            ).all()
            for pf in pfs:
                plan_features_dict[pf.feature.code] = pf.limit_value

        # Batch load active overrides
        all_overrides = list(db.scalars(
            select(EntitlementOverride).where(EntitlementOverride.business_id == business_id)
        ).all())

        active_restrictions = [
            r for r in all_overrides
            if r.override_type == "restrict"
            and (r.expires_at is None or ensure_utc(r.expires_at) > now)
        ]
        active_grants = [
            g for g in all_overrides
            if g.override_type == "grant"
            and (g.expires_at is None or ensure_utc(g.expires_at) > now)
        ]

        feature_items = []
        for feat in all_features:
            eval_res = cls._evaluate_feature_entitlement(
                business=business,
                resolved_status=resolved_status,
                effective_plan_id=effective_plan_id,
                effective_plan_active=effective_plan_active,
                feature_code=feat.code,
                plan_features_dict=plan_features_dict,
                active_restrictions=active_restrictions,
                active_grants=active_grants,
                outlet_id=outlet_id,
                now=now
            )

            # Determine limit_type
            if not eval_res.authorized:
                limit_type = "none"
            elif eval_res.limit_value is None:
                limit_type = "unlimited"
            else:
                limit_type = "numeric"

            feature_items.append(
                PlatformFeatureInspectionItem(
                    feature_code=feat.code,
                    feature_name=feat.name,
                    category=feat.category,
                    authorized=eval_res.authorized,
                    limit_value=eval_res.limit_value,
                    limit_type=limit_type,
                    reason=eval_res.reason,
                    source=eval_res.source,
                    scope=eval_res.scope
                )
            )

        return PlatformBusinessEntitlementsOut(
            business_id=business.id,
            business_name=business.name,
            business_status=business.status,
            outlet_id=target_outlet.id if target_outlet else None,
            outlet_name=target_outlet.name if target_outlet else None,
            subscription=sub_summary,
            features=feature_items
        )

    @classmethod
    def get_business_overrides_history(
        cls,
        db: Session,
        business_id: uuid.UUID,
        include_expired: bool = True,
        include_revoked: bool = True,
        now: Optional[datetime] = None
    ):
        from app.core.errors import NotFoundError
        from app.modules.outlets.models import Outlet
        from app.modules.staff.models import User
        from app.modules.audit.models import AuditLog
        from app.modules.subscriptions.schemas import (
            PlatformBusinessOverridesResponse,
            PlatformOverrideInspectionItem,
            PlatformRevocationAuditItem
        )

        if now is None:
            now = utc_now()
        now = ensure_utc(now)

        business = db.scalar(select(Business).where(Business.id == business_id))
        if not business:
            raise NotFoundError(f"Business with ID '{business_id}' not found.")

        # Query overrides
        stmt = (
            select(EntitlementOverride)
            .where(EntitlementOverride.business_id == business_id)
            .options(
                joinedload(EntitlementOverride.outlet),
                joinedload(EntitlementOverride.business)
            )
            .order_by(EntitlementOverride.created_at.desc())
        )
        overrides_list = list(db.scalars(stmt).all())

        # Pre-load features map
        features = list(db.scalars(select(Feature)).all())
        feat_map = {f.code: f.name for f in features}

        # Pre-load user emails
        user_ids = [o.created_by_user_id for o in overrides_list if o.created_by_user_id]
        users = list(db.scalars(select(User).where(User.id.in_(user_ids))).all()) if user_ids else []
        user_map = {u.id: u.email for u in users}

        override_items = []
        for o in overrides_list:
            is_active = o.expires_at is None or ensure_utc(o.expires_at) > now
            if not include_expired and not is_active:
                continue

            override_items.append(
                PlatformOverrideInspectionItem(
                    id=o.id,
                    business_id=o.business_id,
                    outlet_id=o.outlet_id,
                    outlet_name=o.outlet.name if o.outlet else None,
                    feature_code=o.feature_code,
                    feature_name=feat_map.get(o.feature_code, o.feature_code),
                    override_type=o.override_type,
                    limit_value=o.limit_value,
                    reason=o.reason,
                    expires_at=o.expires_at,
                    is_active=is_active,
                    created_by_user_id=o.created_by_user_id,
                    created_by_email=user_map.get(o.created_by_user_id) if o.created_by_user_id else None,
                    created_at=o.created_at
                )
            )

        # Query revocation audit logs
        revocation_items = []
        if include_revoked:
            audit_logs = list(
                db.scalars(
                    select(AuditLog)
                    .where(
                        and_(
                            AuditLog.business_id == business_id,
                            AuditLog.action == "platform.entitlement.override_revoke"
                        )
                    )
                    .options(joinedload(AuditLog.actor))
                    .order_by(AuditLog.created_at.desc())
                ).all()
            )
            for al in audit_logs:
                meta = al.metadata_json or {}
                revocation_items.append(
                    PlatformRevocationAuditItem(
                        audit_log_id=al.id,
                        revoked_override_id=meta.get("revoked_override_id"),
                        feature_code=meta.get("feature_code"),
                        override_type=meta.get("override_type"),
                        actor_user_id=al.actor_user_id,
                        actor_email=al.actor.email if al.actor else None,
                        revoked_at=al.created_at,
                        reason=meta.get("reason_for_revocation") or meta.get("reason")
                    )
                )

        return PlatformBusinessOverridesResponse(
            business_id=business_id,
            overrides=override_items,
            revocation_history=revocation_items
        )

    @classmethod
    def create_override(
        cls,
        db: Session,
        business_id: uuid.UUID,
        data,
        actor_user_id: Optional[uuid.UUID] = None,
        now: Optional[datetime] = None
    ):
        from app.core.errors import NotFoundError, ValidationError
        from app.modules.outlets.models import Outlet
        from app.modules.staff.models import User
        from app.modules.audit.service import log_audit
        from app.modules.subscriptions.schemas import PlatformOverrideInspectionItem

        if now is None:
            now = utc_now()
        now = ensure_utc(now)

        # 1. Clean and validate reason
        clean_reason = data.reason.strip() if data.reason else ""
        if not clean_reason:
            raise ValidationError("Override reason cannot be empty.")

        # 2. Validate override_type
        if data.override_type not in ("grant", "restrict"):
            raise ValidationError(f"Invalid override_type '{data.override_type}'. Allowed: 'grant', 'restrict'.")

        # 3. Validate expiry timestamp
        clean_expires_at = ensure_utc(data.expires_at)
        if clean_expires_at is not None and clean_expires_at <= now:
            raise ValidationError("Override expiry timestamp must be strictly in the future.")

        # 4. Validate business existence
        business = db.scalar(select(Business).where(Business.id == business_id))
        if not business:
            raise NotFoundError(f"Business with ID '{business_id}' not found.")

        # 5. Validate target outlet ownership if provided
        target_outlet = None
        if data.outlet_id:
            target_outlet = db.scalar(select(Outlet).where(Outlet.id == data.outlet_id))
            if not target_outlet or target_outlet.business_id != business_id:
                raise ValidationError(f"Outlet '{data.outlet_id}' does not belong to business '{business_id}'.")

        # 6. Validate feature code existence in catalog
        feat = db.scalar(select(Feature).where(Feature.code == data.feature_code))
        if not feat:
            raise ValidationError(f"Unknown feature code '{data.feature_code}'.")

        # 7. Validate and normalize limit_value
        limit_val = data.limit_value
        if data.override_type == "restrict":
            limit_val = None
        elif limit_val is not None and limit_val < 1:
            raise ValidationError("limit_value must be a positive integer >= 1 or None.")

        # 8. Create EntitlementOverride entity
        override = EntitlementOverride(
            id=uuid.uuid4(),
            business_id=business_id,
            outlet_id=data.outlet_id,
            feature_code=data.feature_code,
            override_type=data.override_type,
            limit_value=limit_val,
            reason=clean_reason,
            expires_at=clean_expires_at,
            created_by_user_id=actor_user_id
        )
        db.add(override)
        db.flush()

        # 9. Audit log entry in same transaction
        log_audit(
            db=db,
            business_id=business_id,
            outlet_id=data.outlet_id,
            actor_user_id=actor_user_id,
            action="platform.entitlement.override_create",
            entity_type="EntitlementOverride",
            entity_id=override.id,
            metadata_json={
                "override_id": str(override.id),
                "feature_code": override.feature_code,
                "override_type": override.override_type,
                "limit_value": override.limit_value,
                "reason": override.reason,
                "expires_at": override.expires_at.isoformat() if override.expires_at else None,
            }
        )

        db.commit()
        db.refresh(override)

        # Pre-load actor email if available
        actor_email = None
        if actor_user_id:
            actor = db.scalar(select(User).where(User.id == actor_user_id))
            if actor:
                actor_email = actor.email

        return PlatformOverrideInspectionItem(
            id=override.id,
            business_id=override.business_id,
            outlet_id=override.outlet_id,
            outlet_name=target_outlet.name if target_outlet else None,
            feature_code=override.feature_code,
            feature_name=feat.name,
            override_type=override.override_type,
            limit_value=override.limit_value,
            reason=override.reason,
            expires_at=override.expires_at,
            is_active=override.expires_at is None or ensure_utc(override.expires_at) > now,
            created_by_user_id=override.created_by_user_id,
            created_by_email=actor_email,
            created_at=override.created_at
        )

    @classmethod
    def revoke_override(
        cls,
        db: Session,
        business_id: uuid.UUID,
        override_id: uuid.UUID,
        reason: str,
        actor_user_id: Optional[uuid.UUID] = None
    ):
        from app.core.errors import NotFoundError, ValidationError
        from app.modules.audit.service import log_audit

        clean_reason = reason.strip() if reason else ""
        if not clean_reason:
            raise ValidationError("Revocation reason cannot be empty.")

        business = db.scalar(select(Business).where(Business.id == business_id))
        if not business:
            raise NotFoundError(f"Business with ID '{business_id}' not found.")

        override = db.scalar(
            select(EntitlementOverride).where(
                and_(
                    EntitlementOverride.id == override_id,
                    EntitlementOverride.business_id == business_id
                )
            )
        )
        if not override:
            raise NotFoundError(f"Entitlement override with ID '{override_id}' not found for business '{business_id}'.")

        # Capture metadata before deletion
        feature_code = override.feature_code
        override_type = override.override_type
        limit_value = override.limit_value
        outlet_id = override.outlet_id
        orig_reason = override.reason
        orig_creator = override.created_by_user_id

        db.delete(override)
        db.flush()

        log_audit(
            db=db,
            business_id=business_id,
            outlet_id=outlet_id,
            actor_user_id=actor_user_id,
            action="platform.entitlement.override_revoke",
            entity_type="EntitlementOverride",
            entity_id=override_id,
            metadata_json={
                "revoked_override_id": str(override_id),
                "feature_code": feature_code,
                "override_type": override_type,
                "limit_value": limit_value,
                "reason_for_revocation": clean_reason,
                "original_reason": orig_reason,
                "original_created_by_user_id": str(orig_creator) if orig_creator else None,
            }
        )

        db.commit()
        return {"status": "success", "message": f"Override '{override_id}' revoked successfully."}

    @classmethod
    def get_owner_subscription_summary(
        cls,
        db: Session,
        business_id: uuid.UUID,
        now: Optional[datetime] = None
    ):
        from app.core.errors import NotFoundError
        from app.modules.outlets.models import Outlet
        from app.modules.subscriptions.schemas import (
            OwnerSubscriptionSummaryOut,
            OwnerPlanSummary,
            OwnerSubscriptionDetail,
            OwnerOutletUsage,
            OwnerFeatureItem,
            OwnerSupportAction,
        )

        if now is None:
            now = utc_now()
        now = ensure_utc(now)

        business = db.scalar(select(Business).where(Business.id == business_id))
        if not business:
            raise NotFoundError(f"Business with ID '{business_id}' not found.")

        # Query active subscription
        sub = db.scalar(
            select(BusinessSubscription)
            .where(
                and_(
                    BusinessSubscription.business_id == business_id,
                    BusinessSubscription.is_current == True
                )
            )
            .options(joinedload(BusinessSubscription.plan))
        )

        if sub:
            resolved_status = cls.evaluate_subscription_status(sub, now)
            effective_plan_id = sub.plan_id
            effective_plan_active = sub.plan.is_active if sub.plan else True
            plan_code = sub.plan.code if sub.plan else "unknown"
            plan_name = sub.plan.name if sub.plan else "Unknown"
            plan_desc = sub.plan.description if sub.plan else None
            is_current = sub.is_current
            trial_ends_at = sub.trial_ends_at
            current_period_start = sub.current_period_start
            current_period_end = sub.current_period_end
            cancel_at_period_end = sub.cancel_at_period_end
        else:
            sub_status = business.subscription_status or "active"
            if sub_status == "trial" and business.trial_ends_at and now >= ensure_utc(business.trial_ends_at):
                resolved_status = "expired"
            elif sub_status in ("active", "trial"):
                resolved_status = sub_status
            else:
                resolved_status = "expired"

            PLAN_MAP = {
                'starter': 'starter_pos',
                'growth': 'growth_pos',
                'pro': 'pro_kds',
                'enterprise': 'enterprise',
                'digital_menu': 'free_qr',
                'free': 'free_qr',
            }
            raw_plan = business.plan_name.lower() if business.plan_name else ""
            default_code = "growth_pos" if (business.max_outlets is None or business.max_outlets > 1) else "starter_pos"
            target_code = PLAN_MAP.get(raw_plan, default_code)
            fallback_plan = db.scalar(select(Plan).where(Plan.code == target_code))
            effective_plan_id = fallback_plan.id if fallback_plan else None
            effective_plan_active = fallback_plan.is_active if fallback_plan else True
            plan_code = fallback_plan.code if fallback_plan else (business.plan_name or "none")
            plan_name = fallback_plan.name if fallback_plan else (business.plan_name or "No Plan Assigned")
            plan_desc = fallback_plan.description if fallback_plan else None
            is_current = True
            trial_ends_at = business.trial_ends_at
            current_period_start = None
            current_period_end = None
            cancel_at_period_end = False

        # Outlet usage & limit
        current_outlet_count = db.query(Outlet).filter(Outlet.business_id == business_id).count()
        outlet_entitlement = cls.check_entitlement(
            db=db,
            business_id=business_id,
            feature_code="outlets.max_count",
            now=now
        )
        max_allowed_outlets = outlet_entitlement.limit_value
        is_limit_reached = (max_allowed_outlets is not None and current_outlet_count >= max_allowed_outlets)

        # Batch load catalog features
        all_features = list(db.scalars(select(Feature).order_by(Feature.category, Feature.code)).all())

        # Pre-load plan features dict
        plan_features_dict = {}
        if effective_plan_id and effective_plan_active:
            pfs = db.scalars(
                select(PlanFeature)
                .join(Feature, PlanFeature.feature_id == Feature.id)
                .where(PlanFeature.plan_id == effective_plan_id)
            ).all()
            for pf in pfs:
                plan_features_dict[pf.feature.code] = pf.limit_value

        # Pre-load active overrides
        all_overrides = list(db.scalars(
            select(EntitlementOverride).where(EntitlementOverride.business_id == business_id)
        ).all())

        active_restrictions = [
            r for r in all_overrides
            if r.override_type == "restrict"
            and (r.expires_at is None or ensure_utc(r.expires_at) > now)
        ]
        active_grants = [
            g for g in all_overrides
            if g.override_type == "grant"
            and (g.expires_at is None or ensure_utc(g.expires_at) > now)
        ]

        feature_items = []
        for feat in all_features:
            eval_res = cls._evaluate_feature_entitlement(
                business=business,
                resolved_status=resolved_status,
                effective_plan_id=effective_plan_id,
                effective_plan_active=effective_plan_active,
                feature_code=feat.code,
                plan_features_dict=plan_features_dict,
                active_restrictions=active_restrictions,
                active_grants=active_grants,
                outlet_id=None,
                now=now
            )
            feature_items.append(
                OwnerFeatureItem(
                    code=feat.code,
                    name=feat.name,
                    category=feat.category,
                    authorized=eval_res.authorized,
                    limit_value=eval_res.limit_value
                )
            )

        # Support CTA derivation
        is_trial_expired = (resolved_status == "expired")
        
        if is_trial_expired and is_limit_reached:
            support_cta = OwnerSupportAction(
                requires_action=True,
                reason="TRIAL_EXPIRED_AND_OUTLET_LIMIT_REACHED",
                support_email="support@roms.com",
                message=f"Your trial has expired and you have reached your outlet limit of {max_allowed_outlets}. Please contact support@roms.com to upgrade your plan."
            )
        elif is_trial_expired:
            support_cta = OwnerSupportAction(
                requires_action=True,
                reason="TRIAL_EXPIRED",
                support_email="support@roms.com",
                message="Your trial has expired. Please contact support@roms.com to upgrade your subscription."
            )
        elif is_limit_reached:
            support_cta = OwnerSupportAction(
                requires_action=True,
                reason="OUTLET_LIMIT_REACHED",
                support_email="support@roms.com",
                message=f"You have reached your limit of {max_allowed_outlets} outlet(s). Contact support@roms.com to add more outlets."
            )
        else:
            support_cta = OwnerSupportAction(
                requires_action=False,
                reason=None,
                support_email="support@roms.com",
                message=None
            )

        return OwnerSubscriptionSummaryOut(
            business_id=business.id,
            business_name=business.name,
            business_status=business.status,
            plan=OwnerPlanSummary(
                code=plan_code,
                name=plan_name,
                description=plan_desc
            ),
            subscription=OwnerSubscriptionDetail(
                status=resolved_status,
                is_current=is_current,
                trial_ends_at=trial_ends_at,
                current_period_start=current_period_start,
                current_period_end=current_period_end,
                cancel_at_period_end=cancel_at_period_end
            ),
            outlets=OwnerOutletUsage(
                current_count=current_outlet_count,
                max_allowed=max_allowed_outlets,
                is_limit_reached=is_limit_reached
            ),
            features=feature_items,
            support_cta=support_cta
        )


