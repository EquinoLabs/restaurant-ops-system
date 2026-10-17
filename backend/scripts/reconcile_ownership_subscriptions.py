"""ROMS Phase 0 — Read-only ownership and subscription reconciliation reporting.

Purpose:
    Produce a trustworthy, SELECT-only report of the current ownership and
    subscription data state BEFORE Stage 3 ownership changes or migration 0015
    (uq_business_one_owner) are implemented. Report-only per Owner Decision 003:
    zero-owner businesses are never repaired automatically by this tool.

    Implements docs/architecture/stage_3_ownership_subscriptions_architecture.md
    section 9.3 (report items 1-5) plus a supplementary legacy-outlet-owner view.

Security / read-only guarantees:
    - SELECT-only: the builder queries ORM rows and never calls commit(), flush(),
      add(), add_all(), delete(), or delete_all() on the session.
    - The CLI wrapper always calls session.rollback() before exiting successfully,
      providing an explicit proof of zero writes.
    - Credentials are never printed; only settings-style masked URIs are shown.
    - Target verification is fail-closed: the development label is trusted only
      when the effective DATABASE_URL matches the repository-root .env
      development configuration (see migrate_0014_dev_neon.py's established
      convention); environment identity is never inferred from the hostname.

Exact criteria used (derived from application code, not invented):

    Ownership
      - Canonical business owner membership:
        BusinessMembership rows where role == 'owner'
        (the future target of partial unique index uq_business_one_owner,
        see architecture doc section 9.1/9.2; resolver: RequireBusinessOwner,
        backend/app/api/deps.py).
      - Legacy outlet-level owner membership:
        OutletMembership rows where role == 'owner', joined to outlets.business_id.
        Effective for business access ONLY while a user has zero canonical rows
        (gated fallback, backend/app/api/deps.py RequireBusinessOwner).
      - A business is reported as zero-owner when it has no canonical
        BusinessMembership row with role == 'owner'. Businesses with NO
        membership rows at all are always included (never omitted).
      - A business is multiple-owner when two or more DISTINCT users hold
        canonical owner rows; this blocks migration 0015 (architecture doc 9.2).

    Subscriptions ("current" definition, derived from EntitlementService)
      - Row selection uses ONLY the boolean flag is_current == True
        (EntitlementService.check_entitlement, service.py; partial unique index
        uq_outlet_subscription_current guarantees at most one per outlet).
        Status strings and date ranges are NEVER used to select the row.
      - After selection, row validity is the resolved status from
        EntitlementService.evaluate_subscription_status (0-day grace,
        fail-closed on NULL current_period_end). A row is treated as
        "present but not current" when the resolved status is expired or
        cancelled; past_due still counts as a current row.
      - Resolver fallback order (EntitlementService.check_entitlement):
        (1) OutletSubscription is_current row -> (2) BusinessSubscription
        is_current row -> (3) legacy business columns
        (businesses.subscription_status / trial_ends_at / plan_name /
        max_outlets). The resolver does NOT fall through when a non-current
        is_current outlet row exists; it consumes that row.

    Runtime usage limitation:
      - This report derives POTENTIAL fallback candidates from static data only.
        Confirmed runtime fallback usage is NOT measured here and must not be
        claimed; it would require request traces or entitlement-check logs.

Output contains business/outlet identifiers and display names only — no user
emails, credentials, password hashes, tokens, or connection secrets.
"""

import argparse
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

from sqlalchemy.orm import Session

# Ensure backend root is on sys.path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app.modules.businesses.models  # noqa: F401
import app.modules.outlets.models  # noqa: F401
import app.modules.menus.models  # noqa: F401
import app.modules.staff.models  # noqa: F401
import app.modules.subscriptions.models  # noqa: F401
import app.modules.audit.models  # noqa: F401
import app.modules.tables.models  # noqa: F401
import app.modules.orders.models  # noqa: F401

from app.core.config import settings
from app.core.errors import ValidationError
from app.db.base import utc_now
from app.db.session import SessionLocal
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.staff.models import BusinessMembership, OutletMembership
from app.modules.subscriptions.models import (
    BusinessSubscription,
    OutletSubscription,
    Plan,
)
from app.modules.subscriptions.service import EntitlementService, ensure_utc

VALID_TARGET_ENVIRONMENTS = ("production", "staging", "development", "local", "test")

READ_ONLY_STATEMENT = (
    "This report is SELECT-only. No database rows were created, updated, or "
    "deleted; session.rollback() was executed."
)

RUNTIME_USAGE_LIMITATION = (
    "Fallback entries are POTENTIAL candidates derived from static row state. "
    "Confirmed runtime fallback usage was NOT measured by this report."
)

CURRENT_ROW_CRITERIA = (
    "Row selection: OutletSubscription.is_current == True (resolver "
    "EntitlementService.check_entitlement). Validity: resolved status from "
    "EntitlementService.evaluate_subscription_status; resolved status in "
    "(expired, cancelled) is reported as present-but-not-current."
)

RESOLVER_ORDER_CRITERIA = (
    "EntitlementService.check_entitlement fallback order: "
    "(1) OutletSubscription is_current row -> (2) BusinessSubscription "
    "is_current row -> (3) legacy business columns "
    "(subscription_status / trial_ends_at / plan_name / max_outlets)."
)


# Sentinel: distinguishes "caller did not supply a value" (read the real
# repository-root .env) from "caller explicitly supplied None" (marker absent).
_REPO_ROOT_DATABASE_URL_UNSET = object()


def _read_repository_root_database_url() -> Optional[str]:
    """Return DATABASE_URL from the repository-root .env, or None when absent.

    The repository-root .env is the authoritative development configuration
    (convention established by backend/scripts/migrate_0014_dev_neon.py:
    "authoritative development configuration; never the CWD-relative fallback").
    The value is used only for host/database consistency comparison and is
    never printed or included in error messages.
    """
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root_env = os.path.join(os.path.dirname(backend_dir), ".env")
    if not os.path.isfile(root_env):
        return None
    try:
        with open(root_env, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, _, value = stripped.partition("=")
                if key.strip() != "DATABASE_URL":
                    continue
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                    value = value[1:-1].strip()
                return value or None
    except OSError:
        return None
    return None


def validate_reconciliation_database_target(
    target_env: Optional[str],
    database_uri: Optional[str] = None,
    explicit_database_url: Any = None,
    repository_root_database_url: Any = _REPO_ROOT_DATABASE_URL_UNSET,
) -> Dict[str, Any]:
    """Fails closed when the database target or environment selection is ambiguous.

    Target policy (ROMS topology: the authoritative development DATABASE_URL may
    target a remote Neon host, per backend/scripts/migrate_0014_dev_neon.py):

      1. An explicit target environment is required before any session opens.
      2. production/staging require an explicitly configured DATABASE_URL and
         may not target localhost/loopback hosts (unchanged).
      3. development is trusted only when ALL of the following hold:
         a. DATABASE_URL is explicitly configured — the implicit localhost
            POSTGRES_* fallback is refused, and
         b. the repository-root .env defines DATABASE_URL (the authoritative
            development configuration convention), and
         c. the effective DATABASE_URL matches that repository-root value on
            host, port, and database (protects against a process-environment
            override pointing at a different database).
         Both remote (e.g. Neon) and localhost development targets are
         acceptable under these conditions; environment identity is NEVER
         inferred from the hostname.
      4. local still rejects remote hosts (unchanged).
      5. Credentials are redacted; validation errors expose host/database
         names only — never URLs, usernames, or passwords.

    For tests, ``repository_root_database_url`` may be passed explicitly
    (a URL string or None for "marker absent") instead of reading the real
    repository-root .env.
    """
    if not target_env or not target_env.strip():
        raise ValidationError(
            "Target environment (--target-env) is required for reconciliation reporting. "
            f"Allowed environments: {list(VALID_TARGET_ENVIRONMENTS)}"
        )

    clean_env = target_env.strip().lower()
    if clean_env not in VALID_TARGET_ENVIRONMENTS:
        raise ValidationError(
            f"Invalid target environment '{target_env}'. "
            f"Allowed environments: {list(VALID_TARGET_ENVIRONMENTS)}"
        )

    raw_uri = database_uri if database_uri is not None else settings.SQLALCHEMY_DATABASE_URI
    configured_url = settings.DATABASE_URL if explicit_database_url is None else explicit_database_url
    is_explicit = bool(configured_url and str(configured_url).strip())

    try:
        parsed = urlparse(raw_uri)
    except Exception as e:
        raise ValidationError(f"Failed to parse database connection URI: {e}")

    host = (parsed.hostname or "").lower()
    port = parsed.port or 5432
    db_name = (parsed.path or "").lstrip("/")
    scheme = parsed.scheme.lower()
    is_localhost = host in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "")

    if clean_env in ("production", "staging"):
        if not is_explicit:
            raise ValidationError(
                f"Target environment '{clean_env}' requires an explicitly configured DATABASE_URL. "
                "Implicit fallback to default localhost settings is prohibited in reconciliation mode."
            )
        if is_localhost:
            raise ValidationError(
                f"Target environment '{clean_env}' cannot target a localhost/loopback database ('{host}'). "
                "An explicit remote database host is required."
            )

    if clean_env == "local":
        if is_explicit and not is_localhost and host not in ("testserver", "sqlite"):
            raise ValidationError(
                f"Target environment mismatch: --target-env is 'local', but DATABASE_URL points to "
                f"remote host '{host}'. If targeting production or staging, specify --target-env accordingly."
            )

    if clean_env == "development":
        if not is_explicit:
            raise ValidationError(
                "Target environment 'development' requires an explicitly configured DATABASE_URL. "
                "The implicit localhost POSTGRES_* fallback configuration is refused; refusing to guess a target."
            )
        root_env_url = (
            _read_repository_root_database_url()
            if repository_root_database_url is _REPO_ROOT_DATABASE_URL_UNSET
            else repository_root_database_url
        )
        root_env_url = (str(root_env_url).strip() if root_env_url else "") or None
        if not root_env_url:
            raise ValidationError(
                "Target environment 'development' requires DATABASE_URL to be defined in the "
                "repository-root .env (the authoritative development configuration, see "
                "backend/scripts/migrate_0014_dev_neon.py). No trusted development marker was "
                "found; refusing to classify this target as development."
            )
        try:
            root_parsed = urlparse(root_env_url)
            root_host = (root_parsed.hostname or "").lower()
            root_port = root_parsed.port or 5432
        except Exception:
            raise ValidationError(
                "The repository-root .env DATABASE_URL could not be parsed; refusing development target."
            )
        root_db = (root_parsed.path or "").lstrip("/")
        if not root_host or not root_db:
            raise ValidationError(
                "The repository-root .env DATABASE_URL is incomplete (host/database); "
                "refusing development target."
            )
        if (host, port, db_name) != (root_host, root_port, root_db):
            raise ValidationError(
                "Target environment mismatch: the effective DATABASE_URL targets host "
                f"'{host}' port {port} database '{db_name}', but the repository-root .env "
                f"development configuration targets host '{root_host}' port {root_port} "
                f"database '{root_db}'. Refusing. Run from the repository root so the .env "
                "file is loaded; do not override DATABASE_URL ad hoc."
            )

    if parsed.password:
        masked_netloc = parsed.netloc.replace(f":{parsed.password}@", ":****@")
        masked_uri = urlunparse(
            (parsed.scheme, masked_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
        )
    else:
        masked_uri = raw_uri

    return {
        "target_env": clean_env,
        "host": host or "localhost",
        "port": port,
        "database": db_name or "roms_db",
        "scheme": scheme,
        "masked_uri": masked_uri,
        "is_explicit": is_explicit,
    }


def _iso(value: Optional[datetime]) -> Optional[str]:
    normalized = ensure_utc(value)
    return normalized.isoformat() if normalized is not None else None


def _business_ref(business: Business) -> Dict[str, Any]:
    return {
        "business_id": str(business.id),
        "name": business.name,
        "status": business.status,
        "created_at": _iso(business.created_at),
    }


def build_reconciliation_report(db: Session, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Build the Phase 0 reconciliation report.

    Session Ownership Contract: receives a caller-owned session; performs
    SELECT-only queries; NEVER calls commit() or flush(). The caller owns the
    transaction lifecycle (the CLI wrapper rolls back to prove zero writes).
    """
    evaluated_at = ensure_utc(now) if now is not None else utc_now()

    businesses = db.query(Business).order_by(Business.created_at).all()
    outlets = db.query(Outlet).order_by(Outlet.created_at).all()
    plans = {p.id: p.code for p in db.query(Plan).all()}

    owner_rows = (
        db.query(BusinessMembership.business_id, BusinessMembership.user_id)
        .filter(BusinessMembership.role == "owner")
        .all()
    )
    all_business_memberships = db.query(BusinessMembership).all()
    legacy_owner_rows = (
        db.query(Outlet.business_id, OutletMembership.user_id)
        .join(Outlet, Outlet.id == OutletMembership.outlet_id)
        .filter(OutletMembership.role == "owner")
        .all()
    )
    outlet_subs = db.query(OutletSubscription).all()
    business_subs = db.query(BusinessSubscription).all()

    # ------------------------------------------------------------------
    # Grouping (dialect-agnostic, done in Python)
    # ------------------------------------------------------------------
    owner_users_by_business: Dict[Any, List[Any]] = {}
    for business_id, user_id in owner_rows:
        owner_users_by_business.setdefault(business_id, []).append(user_id)

    memberships_by_business: Dict[Any, List[BusinessMembership]] = {}
    for membership in all_business_memberships:
        memberships_by_business.setdefault(membership.business_id, []).append(membership)

    legacy_owner_users_by_business: Dict[Any, set] = {}
    for business_id, user_id in legacy_owner_rows:
        legacy_owner_users_by_business.setdefault(business_id, set()).add(user_id)

    outlet_subs_by_outlet: Dict[Any, List[OutletSubscription]] = {}
    for sub in outlet_subs:
        outlet_subs_by_outlet.setdefault(sub.outlet_id, []).append(sub)

    business_subs_by_business: Dict[Any, List[BusinessSubscription]] = {}
    for sub in business_subs:
        business_subs_by_business.setdefault(sub.business_id, []).append(sub)

    businesses_by_id = {b.id: b for b in businesses}

    # ------------------------------------------------------------------
    # A1. Multiple canonical owner memberships (blocks migration 0015)
    # ------------------------------------------------------------------
    multiple_owner_businesses: List[Dict[str, Any]] = []
    for business in businesses:
        user_ids = owner_users_by_business.get(business.id, [])
        distinct_user_ids = sorted({str(u) for u in user_ids})
        if len(distinct_user_ids) > 1:
            entry = _business_ref(business)
            entry["owner_count"] = len(distinct_user_ids)
            entry["owner_user_ids"] = distinct_user_ids
            multiple_owner_businesses.append(entry)

    # ------------------------------------------------------------------
    # A2 (supplementary). Multiple DISTINCT legacy outlet-level owners
    # ------------------------------------------------------------------
    multiple_legacy_owner_businesses: List[Dict[str, Any]] = []
    for business in businesses:
        legacy_ids = sorted({str(u) for u in legacy_owner_users_by_business.get(business.id, set())})
        if len(legacy_ids) > 1:
            entry = _business_ref(business)
            entry["distinct_legacy_owner_count"] = len(legacy_ids)
            entry["owner_user_ids"] = legacy_ids
            entry["canonical_owner_count"] = len(owner_users_by_business.get(business.id, []))
            multiple_legacy_owner_businesses.append(entry)

    # ------------------------------------------------------------------
    # B. Zero canonical owner memberships (covers ALL businesses,
    #    including those with no membership rows at all)
    # ------------------------------------------------------------------
    zero_owner_businesses: List[Dict[str, Any]] = []
    classification_counts: Dict[str, int] = {
        "no_business_membership_rows": 0,
        "non_owner_memberships_only": 0,
    }
    for business in businesses:
        if owner_users_by_business.get(business.id):
            continue
        memberships = memberships_by_business.get(business.id, [])
        legacy_ids = sorted({str(u) for u in legacy_owner_users_by_business.get(business.id, set())})
        non_owner_roles: Dict[str, int] = {}
        for membership in memberships:
            if membership.role != "owner":
                non_owner_roles[membership.role] = non_owner_roles.get(membership.role, 0) + 1

        if not memberships:
            classification = "no_business_membership_rows"
        else:
            classification = "non_owner_memberships_only"
        classification_counts[classification] += 1

        entry = _business_ref(business)
        entry["total_business_memberships"] = len(memberships)
        entry["non_owner_membership_roles"] = non_owner_roles
        entry["legacy_outlet_owner_user_ids"] = legacy_ids
        entry["legacy_owned_via_gated_fallback"] = bool(legacy_ids)
        entry["classification"] = classification
        zero_owner_businesses.append(entry)

    # ------------------------------------------------------------------
    # C. Outlet subscription gaps + per-outlet fallback analysis
    # ------------------------------------------------------------------
    def _current_row(rows: List[OutletSubscription]) -> Optional[OutletSubscription]:
        for row in rows:
            if row.is_current:
                return row
        return None

    def _business_current_sub(business_id) -> Optional[BusinessSubscription]:
        for row in business_subs_by_business.get(business_id, []):
            if row.is_current:
                return row
        return None

    subscription_gaps: List[Dict[str, Any]] = []
    category_counts: Dict[str, int] = {
        "no_subscription_rows": 0,
        "rows_without_current_flag": 0,
        "current_row_non_current_status": 0,
    }
    outlets_with_valid_current_subscription = 0

    for outlet in outlets:
        business = businesses_by_id.get(outlet.business_id)
        rows = outlet_subs_by_outlet.get(outlet.id, [])
        current = _current_row(rows)

        fallback_tier: str
        resolved_status: Optional[str] = None
        gap_category: Optional[str] = None

        if not rows:
            gap_category = "no_subscription_rows"
        elif current is None:
            gap_category = "rows_without_current_flag"
        else:
            resolved_status = EntitlementService.evaluate_subscription_status(current, now=evaluated_at)
            if resolved_status in ("expired", "cancelled"):
                gap_category = "current_row_non_current_status"
            else:
                outlets_with_valid_current_subscription += 1

        if gap_category is None:
            continue

        category_counts[gap_category] += 1
        biz_current_sub = _business_current_sub(outlet.business_id) if business else None

        if gap_category == "current_row_non_current_status":
            # The resolver consumes the non-current is_current row and does NOT
            # fall through to business-level or legacy-column sources.
            fallback_tier = "none_resolver_consumes_current_row"
            fallback_available = False
        elif biz_current_sub is not None:
            fallback_tier = "business_subscription"
            fallback_available = (
                business is not None
                and business.status == "active"
                and outlet.status == "active"
            )
        elif business is not None and business.status == "active":
            fallback_tier = "legacy_business_columns"
            fallback_available = outlet.status == "active"
        else:
            fallback_tier = "none_business_suspended"
            fallback_available = False

        entry: Dict[str, Any] = {
            "outlet_id": str(outlet.id),
            "outlet_name": outlet.name,
            "outlet_status": outlet.status,
            "business_id": str(outlet.business_id),
            "business_name": business.name if business else None,
            "business_status": business.status if business else None,
            "gap_category": gap_category,
            "subscription_row_count": len(rows),
            "current_subscription_id": str(current.id) if current is not None else None,
            "current_subscription_stored_status": current.status if current is not None else None,
            "current_subscription_resolved_status": resolved_status,
            "fallback_tier": fallback_tier,
            "fallback_potentially_supplies_entitlements": fallback_available,
        }
        subscription_gaps.append(entry)

    # ------------------------------------------------------------------
    # D. Legacy entitlement fallback cohort (static candidates only)
    # ------------------------------------------------------------------
    cohort: List[Dict[str, Any]] = []
    for business in businesses:
        current_sub = _business_current_sub(business.id)
        if current_sub is None:
            continue
        entry = _business_ref(business)
        entry["subscription_id"] = str(current_sub.id)
        entry["stored_status"] = current_sub.status
        entry["resolved_status"] = EntitlementService.evaluate_subscription_status(
            current_sub, now=evaluated_at
        )
        entry["plan_code"] = plans.get(current_sub.plan_id)
        cohort.append(entry)

    served_by_business_sub = [
        g for g in subscription_gaps if g["fallback_tier"] == "business_subscription"
    ]
    falling_to_legacy_columns = [
        g for g in subscription_gaps if g["fallback_tier"] == "legacy_business_columns"
    ]

    # ------------------------------------------------------------------
    # E. Denormalized business-column drift vs current BusinessSubscription
    #    (architecture doc 9.3 item 5). max_outlets has no subscription
    #    counterpart and is therefore excluded from drift comparison.
    # ------------------------------------------------------------------
    drift_businesses: List[Dict[str, Any]] = []
    for business in businesses:
        current_sub = _business_current_sub(business.id)
        if current_sub is None:
            continue
        drift_fields: Dict[str, Any] = {}
        if (business.subscription_status or None) != (current_sub.status or None):
            drift_fields["subscription_status"] = {
                "business_column": business.subscription_status,
                "subscription_row": current_sub.status,
            }
        sub_plan_code = plans.get(current_sub.plan_id)
        if (business.plan_name or None) != (sub_plan_code or None):
            drift_fields["plan_name"] = {
                "business_column": business.plan_name,
                "subscription_row": sub_plan_code,
            }
        column_trial = _iso(business.trial_ends_at)
        row_trial = _iso(current_sub.trial_ends_at)
        if column_trial != row_trial:
            drift_fields["trial_ends_at"] = {
                "business_column": column_trial,
                "subscription_row": row_trial,
            }
        if drift_fields:
            entry = _business_ref(business)
            entry["subscription_id"] = str(current_sub.id)
            entry["drift_fields"] = drift_fields
            drift_businesses.append(entry)

    return {
        "metadata": {
            "report": "roms_phase0_ownership_subscription_reconciliation",
            "generated_at": _iso(utc_now()),
            "evaluated_at": _iso(evaluated_at),
            "read_only": True,
            "read_only_statement": READ_ONLY_STATEMENT,
            "criteria": {
                "current_outlet_subscription": CURRENT_ROW_CRITERIA,
                "resolver_fallback_order": RESOLVER_ORDER_CRITERIA,
                "canonical_owner": "BusinessMembership.role == 'owner'",
                "legacy_outlet_owner": "OutletMembership.role == 'owner' joined via outlets.business_id",
            },
        },
        "totals": {
            "businesses": len(businesses),
            "outlets": len(outlets),
            "canonical_owner_memberships": len(owner_rows),
            "outlets_with_valid_current_subscription": outlets_with_valid_current_subscription,
            "outlets_with_subscription_gap": len(subscription_gaps),
            "businesses_with_current_business_subscription": len(cohort),
        },
        "multiple_owner_memberships": {
            "description": (
                "Canonical businesses with more than one distinct owner membership "
                "(BusinessMembership.role == 'owner'). Must be empty before "
                "migration 0015 (uq_business_one_owner) applies."
            ),
            "blocking_for_uq_business_one_owner": bool(multiple_owner_businesses),
            "businesses": multiple_owner_businesses,
        },
        "multiple_legacy_outlet_owners": {
            "description": (
                "Supplementary: businesses whose outlets carry more than one distinct "
                "legacy outlet-level owner (OutletMembership.role == 'owner')."
            ),
            "businesses": multiple_legacy_owner_businesses,
        },
        "zero_owner_memberships": {
            "description": (
                "Businesses with no canonical owner membership. Covers ALL businesses, "
                "including businesses with zero membership rows of any role. "
                "Report-only; no automatic repair (Owner Decision 003)."
            ),
            "classification_counts": classification_counts,
            "businesses": zero_owner_businesses,
        },
        "outlet_subscription_gaps": {
            "description": (
                "Outlets without a valid current OutletSubscription. Validity uses the "
                "application's own resolver semantics."
            ),
            "criteria": CURRENT_ROW_CRITERIA,
            "category_counts": category_counts,
            "outlets": subscription_gaps,
        },
        "legacy_fallback_cohort": {
            "description": (
                "Businesses holding a current BusinessSubscription (fallback tier 2) and "
                "outlets whose entitlement behavior may be supplied by tier-2 or tier-3 "
                "fallback sources."
            ),
            "resolver_order": RESOLVER_ORDER_CRITERIA,
            "runtime_usage_measured": False,
            "limitation": RUNTIME_USAGE_LIMITATION,
            "businesses_with_current_business_subscription": cohort,
            "outlets_served_by_business_subscription_fallback": [
                {"outlet_id": g["outlet_id"], "business_id": g["business_id"]}
                for g in served_by_business_sub
            ],
            "outlets_falling_to_legacy_business_columns": [
                {"outlet_id": g["outlet_id"], "business_id": g["business_id"]}
                for g in falling_to_legacy_columns
            ],
        },
        "denormalized_column_drift": {
            "description": (
                "Businesses where legacy columns disagree with the current "
                "BusinessSubscription row (architecture doc 9.3 item 5)."
            ),
            "excluded_columns": {
                "max_outlets": (
                    "Legacy scalar entitlement with no BusinessSubscription counterpart; "
                    "not drift-comparable."
                )
            },
            "businesses": drift_businesses,
        },
    }


def format_reconciliation_report(report: Dict[str, Any], target_info: Optional[Dict[str, Any]] = None) -> str:
    """Render the structured report as fixed-width operator text."""
    lines: List[str] = []
    meta = report["metadata"]
    totals = report["totals"]

    lines.append("")
    lines.append("========================================================")
    lines.append("  ROMS PHASE 0 - OWNERSHIP & SUBSCRIPTION RECONCILIATION ")
    lines.append("                  (READ-ONLY)                            ")
    lines.append("========================================================")
    if target_info:
        lines.append(f"Target Env:           {target_info.get('target_env')}")
        lines.append(f"Target DB Host:       {target_info.get('host')}:{target_info.get('port')}")
        lines.append(f"Target Database:      {target_info.get('database')}")
        lines.append(f"Masked URI:           {target_info.get('masked_uri')}")
    lines.append(f"Generated At (UTC):   {meta.get('generated_at')}")
    lines.append(f"Evaluated At (UTC):   {meta.get('evaluated_at')}")
    lines.append("")
    lines.append("SUMMARY")
    lines.append(f"  Businesses:                              {totals.get('businesses')}")
    lines.append(f"  Outlets:                                 {totals.get('outlets')}")
    lines.append(f"  Canonical owner memberships:             {totals.get('canonical_owner_memberships')}")
    lines.append(f"  Outlets w/ valid current subscription:   {totals.get('outlets_with_valid_current_subscription')}")
    lines.append(f"  Outlets w/ subscription gap:             {totals.get('outlets_with_subscription_gap')}")
    lines.append(f"  Businesses w/ current business sub:      {totals.get('businesses_with_current_business_subscription')}")

    multi = report["multiple_owner_memberships"]
    lines.append("")
    lines.append("A. MULTIPLE OWNER MEMBERSHIPS (canonical; blocks migration 0015)")
    lines.append(f"   {multi['description']}")
    if multi["businesses"]:
        lines.append(
            f"   Status: FAIL - {len(multi['businesses'])} business(es) would abort uq_business_one_owner"
        )
        for entry in multi["businesses"]:
            lines.append(
                f"  - {entry['name']} ({entry['business_id']}) - owners: {entry['owner_count']} "
                f"[{', '.join(entry['owner_user_ids'])}]"
            )
    else:
        lines.append("   Status: PASS - 0 businesses with multiple canonical owners")

    legacy_multi = report["multiple_legacy_outlet_owners"]
    lines.append("")
    lines.append("A2. MULTIPLE LEGACY OUTLET-LEVEL OWNERS (supplementary)")
    lines.append(f"   {legacy_multi['description']}")
    if legacy_multi["businesses"]:
        for entry in legacy_multi["businesses"]:
            lines.append(
                f"  - {entry['name']} ({entry['business_id']}) - distinct legacy owners: "
                f"{entry['distinct_legacy_owner_count']}, canonical owners: {entry['canonical_owner_count']}"
            )
    else:
        lines.append("   0 businesses with multiple distinct legacy outlet owners")

    zero = report["zero_owner_memberships"]
    lines.append("")
    lines.append("B. ZERO OWNER MEMBERSHIPS (canonical; report-only, no repair)")
    lines.append(f"   {zero['description']}")
    counts = zero["classification_counts"]
    lines.append(
        "   Breakdown: "
        f"no membership rows = {counts.get('no_business_membership_rows')}, "
        f"non-owner memberships only = {counts.get('non_owner_memberships_only')}"
    )
    if zero["businesses"]:
        for entry in zero["businesses"]:
            legacy_note = (
                f"legacy-owned via gated fallback ({len(entry['legacy_outlet_owner_user_ids'])} user(s))"
                if entry["legacy_owned_via_gated_fallback"]
                else "NO owner of any kind"
            )
            lines.append(
                f"  - {entry['name']} ({entry['business_id']}) - {entry['classification']}, "
                f"created {entry['created_at']} - {legacy_note}"
            )
    else:
        lines.append("   0 zero-owner businesses")

    gaps = report["outlet_subscription_gaps"]
    lines.append("")
    lines.append("C. OUTLET SUBSCRIPTION GAPS (no valid current OutletSubscription)")
    lines.append(f"   {gaps['description']}")
    lines.append(f"   Criteria: {gaps['criteria']}")
    cat = gaps["category_counts"]
    lines.append(
        "   Breakdown: "
        f"no subscription rows = {cat.get('no_subscription_rows')}, "
        f"rows without current flag = {cat.get('rows_without_current_flag')}, "
        f"current row resolved non-current = {cat.get('current_row_non_current_status')}"
    )
    if gaps["outlets"]:
        for entry in gaps["outlets"]:
            detail = f"resolved={entry['current_subscription_resolved_status']}" if entry["current_subscription_resolved_status"] else "no current row"
            lines.append(
                f"  - {entry['outlet_name']} ({entry['outlet_id']}) biz={entry['business_id']} "
                f"[{entry['gap_category']}; {detail}; fallback_tier={entry['fallback_tier']}; "
                f"fallback_may_supply={entry['fallback_potentially_supplies_entitlements']}]"
            )
    else:
        lines.append("   0 outlets with subscription gaps")

    fallback = report["legacy_fallback_cohort"]
    lines.append("")
    lines.append("D. LEGACY ENTITLEMENT FALLBACK COHORT (potential candidates only)")
    lines.append(f"   Resolver order: {fallback['resolver_order']}")
    lines.append(f"   Limitation: {fallback['limitation']}")
    cohort = fallback["businesses_with_current_business_subscription"]
    lines.append(f"   Businesses with current BusinessSubscription: {len(cohort)}")
    for entry in cohort:
        lines.append(
            f"  - {entry['name']} ({entry['business_id']}) sub={entry['subscription_id']} "
            f"stored={entry['stored_status']} resolved={entry['resolved_status']} plan={entry['plan_code']}"
        )
    lines.append(
        "   Outlets served by BusinessSubscription fallback (tier 2): "
        f"{len(fallback['outlets_served_by_business_subscription_fallback'])}"
    )
    lines.append(
        "   Outlets falling to legacy business columns (tier 3): "
        f"{len(fallback['outlets_falling_to_legacy_business_columns'])}"
    )

    drift = report["denormalized_column_drift"]
    lines.append("")
    lines.append("E. DENORMALIZED BUSINESS-COLUMN DRIFT vs CURRENT BUSINESS SUBSCRIPTION")
    lines.append(f"   {drift['description']}")
    lines.append("   Excluded: max_outlets (no subscription counterpart).")
    if drift["businesses"]:
        for entry in drift["businesses"]:
            fields = ", ".join(sorted(entry["drift_fields"].keys()))
            lines.append(f"  - {entry['name']} ({entry['business_id']}) - drift in: {fields}")
            for field, values in entry["drift_fields"].items():
                lines.append(
                    f"      {field}: column={values['business_column']!r} subscription={values['subscription_row']!r}"
                )
    else:
        lines.append("   0 businesses with denormalized column drift")

    lines.append("")
    lines.append("READ-ONLY GUARANTEE")
    lines.append(f"   {READ_ONLY_STATEMENT}")
    lines.append("   Static-data analysis only; no live entitlement checks were executed.")
    lines.append("========================================================")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "ROMS Phase 0 read-only ownership and subscription reconciliation report. "
            "SELECT-only: never creates, updates, or deletes any rows."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python backend/scripts/reconcile_ownership_subscriptions.py --target-env development
  python backend/scripts/reconcile_ownership_subscriptions.py --target-env test
""",
    )
    parser.add_argument(
        "--target-env",
        required=True,
        choices=list(VALID_TARGET_ENVIRONMENTS),
        help="Explicit target environment for fail-closed database verification.",
    )
    args = parser.parse_args()

    # Target environment verification: MUST succeed before SessionLocal() is created
    try:
        target_info = validate_reconciliation_database_target(args.target_env)
    except Exception as e:
        print(f"\n[FATAL] Database target verification failed: {e}\n", file=sys.stderr)
        sys.exit(1)

    session = SessionLocal()
    try:
        report = build_reconciliation_report(session)
        # Explicit proof of zero writes for this read-only tool
        session.rollback()
        print(format_reconciliation_report(report, target_info=target_info))
        sys.exit(0)
    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] Reconciliation report failed: {e}\n", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
