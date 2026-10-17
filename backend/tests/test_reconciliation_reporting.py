"""Tests for ROMS Phase 0 read-only ownership and subscription reconciliation reporting.

All scenarios run against the repository's standard SQLite in-memory fixture
database (backend/tests/conftest.py); no production database connection is
required. Tests also prove the report builder has no mutation path.
"""

import uuid
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.staff.models import BusinessMembership, OutletMembership, User
from app.modules.subscriptions.models import (
    BusinessSubscription,
    OutletSubscription,
    Plan,
)
from app.modules.audit.models import AuditLog
from app.core.errors import ValidationError

from scripts.reconcile_ownership_subscriptions import (
    CURRENT_ROW_CRITERIA,
    build_reconciliation_report,
    format_reconciliation_report,
    main as cli_main,
    validate_reconciliation_database_target,
)

NOW = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers (same conventions as tests/test_outlet_subscriptions_phase1.py)
# ---------------------------------------------------------------------------

def _make_business(db, name, subscription_status="trial", plan_name=None, trial_ends_at=None):
    b = Business(
        id=uuid.uuid4(),
        name=name,
        status="active",
        subscription_status=subscription_status,
        plan_name=plan_name,
        trial_ends_at=trial_ends_at,
    )
    db.add(b)
    db.commit()
    return b


def _make_outlet(db, business_id, name, status="active"):
    o = Outlet(
        id=uuid.uuid4(),
        business_id=business_id,
        name=name,
        public_slug=f"slug-{uuid.uuid4().hex[:6]}",
        timezone="UTC",
        currency="INR",
        address="Test Address",
        status=status,
    )
    db.add(o)
    db.commit()
    return o


def _make_user(db, email):
    u = User(
        id=uuid.uuid4(),
        email=email,
        password_hash="hash",
        display_name="Recon Test User",
        status="active",
    )
    db.add(u)
    db.commit()
    return u


def _make_business_membership(db, user_id, business_id, role="owner"):
    m = BusinessMembership(id=uuid.uuid4(), user_id=user_id, business_id=business_id, role=role)
    db.add(m)
    db.commit()
    return m


def _make_outlet_membership(db, user_id, outlet_id, role="owner"):
    m = OutletMembership(id=uuid.uuid4(), user_id=user_id, outlet_id=outlet_id, role=role)
    db.add(m)
    db.commit()
    return m


def _make_outlet_sub(db, outlet_id, business_id, plan_id, status="trial",
                     trial_ends_at=None, current_period_end=None, is_current=True):
    sub = OutletSubscription(
        id=uuid.uuid4(),
        outlet_id=outlet_id,
        business_id=business_id,
        plan_id=plan_id,
        status=status,
        is_current=is_current,
        trial_ends_at=trial_ends_at,
        current_period_start=None,
        current_period_end=current_period_end,
        cancel_at_period_end=False,
        cancelled_at=None,
    )
    db.add(sub)
    db.commit()
    return sub


def _make_business_sub(db, business_id, plan_id, status="trial",
                       trial_ends_at=None, current_period_end=None, is_current=True):
    sub = BusinessSubscription(
        id=uuid.uuid4(),
        business_id=business_id,
        plan_id=plan_id,
        status=status,
        is_current=is_current,
        trial_ends_at=trial_ends_at,
        current_period_start=None,
        current_period_end=current_period_end,
        cancel_at_period_end=False,
        cancelled_at=None,
    )
    db.add(sub)
    db.commit()
    return sub


def _plan(db, code):
    plan = db.query(Plan).filter(Plan.code == code).first()
    assert plan is not None, f"Canonical plan '{code}' should be seeded by conftest"
    return plan


# ---------------------------------------------------------------------------
# Shared scenario fixture covering every report condition
# ---------------------------------------------------------------------------

@pytest.fixture
def recon_data(db_session: Session):
    plan_starter = _plan(db_session, "starter_pos")
    plan_growth = _plan(db_session, "growth_pos")

    # 1. Business with TWO canonical owners (+ one manager row)
    biz_multi = _make_business(db_session, "Multi Owner Co")
    u_multi_a = _make_user(db_session, "multi-a@leak-canary.test")
    u_multi_b = _make_user(db_session, "multi-b@leak-canary.test")
    u_multi_mgr = _make_user(db_session, "multi-mgr@leak-canary.test")
    _make_business_membership(db_session, u_multi_a.id, biz_multi.id, role="owner")
    _make_business_membership(db_session, u_multi_b.id, biz_multi.id, role="owner")
    _make_business_membership(db_session, u_multi_mgr.id, biz_multi.id, role="manager")
    out_multi = _make_outlet(db_session, biz_multi.id, "Multi Outlet")
    _make_outlet_sub(
        db_session, out_multi.id, biz_multi.id, plan_starter.id,
        status="trial", trial_ends_at=NOW + timedelta(days=30),
    )

    # 2. Business with EXACTLY one canonical owner
    biz_single = _make_business(db_session, "Single Owner Co")
    u_single = _make_user(db_session, "single@leak-canary.test")
    _make_business_membership(db_session, u_single.id, biz_single.id, role="owner")
    out_single = _make_outlet(db_session, biz_single.id, "Single Outlet")
    _make_outlet_sub(
        db_session, out_single.id, biz_single.id, plan_starter.id,
        status="trial", trial_ends_at=NOW + timedelta(days=30),
    )

    # 3. Zero-owner business with NO membership rows of any role;
    #    outlet has NO subscription rows at all (C1) and the business has no
    #    BusinessSubscription -> tier-3 legacy-column fallback candidate.
    biz_zero_nomem = _make_business(db_session, "Zero Owner NoMembers Co")
    out_nomem = _make_outlet(db_session, biz_zero_nomem.id, "NoSub Outlet")

    # 4. Zero-owner business with only non-owner canonical memberships,
    #    but a LEGACY outlet-level owner (gated fallback), a current
    #    BusinessSubscription (tier-2 cohort), and an outlet whose only
    #    subscription row is history (no is_current flag) (C2).
    biz_zero_nonowner = _make_business(
        db_session, "Zero Owner NonOwner Co",
        subscription_status="active", plan_name="growth_pos", trial_ends_at=None,
    )
    u_nonowner_mgr = _make_user(db_session, "nonowner-mgr@leak-canary.test")
    u_legacy_owner = _make_user(db_session, "legacy-owner@leak-canary.test")
    _make_business_membership(db_session, u_nonowner_mgr.id, biz_zero_nonowner.id, role="manager")
    out_nonowner = _make_outlet(db_session, biz_zero_nonowner.id, "HistorySub Outlet")
    _make_outlet_membership(db_session, u_legacy_owner.id, out_nonowner.id, role="owner")
    _make_business_sub(
        db_session, biz_zero_nonowner.id, plan_growth.id,
        status="active", trial_ends_at=None, current_period_end=NOW + timedelta(days=10),
    )
    _make_outlet_sub(
        db_session, out_nonowner.id, biz_zero_nonowner.id, plan_growth.id,
        status="cancelled", trial_ends_at=None, is_current=False,
    )

    # 5. Business whose outlet has an is_current row resolved EXPIRED (C3)
    biz_expired = _make_business(db_session, "Expired Current Sub Co")
    u_expired = _make_user(db_session, "expired-owner@leak-canary.test")
    _make_business_membership(db_session, u_expired.id, biz_expired.id, role="owner")
    out_expired = _make_outlet(db_session, biz_expired.id, "ExpiredSub Outlet")
    _make_outlet_sub(
        db_session, out_expired.id, biz_expired.id, plan_starter.id,
        status="trial", trial_ends_at=NOW - timedelta(days=1), is_current=True,
    )

    # 6. Business with denormalized column drift vs its current BusinessSubscription
    biz_drift = _make_business(
        db_session, "Drift Co",
        subscription_status="trial", plan_name="starter",
        trial_ends_at=NOW + timedelta(days=5),
    )
    u_drift = _make_user(db_session, "drift-owner@leak-canary.test")
    _make_business_membership(db_session, u_drift.id, biz_drift.id, role="owner")
    _make_business_sub(
        db_session, biz_drift.id, plan_growth.id,
        status="active", trial_ends_at=None, current_period_end=NOW + timedelta(days=10),
    )

    return {
        "db": db_session,
        "plan_starter": plan_starter,
        "plan_growth": plan_growth,
        "biz_multi": biz_multi,
        "biz_single": biz_single,
        "biz_zero_nomem": biz_zero_nomem,
        "biz_zero_nonowner": biz_zero_nonowner,
        "biz_expired": biz_expired,
        "biz_drift": biz_drift,
        "u_multi_a": u_multi_a,
        "u_multi_b": u_multi_b,
        "u_nonowner_mgr": u_nonowner_mgr,
        "u_legacy_owner": u_legacy_owner,
        "out_multi": out_multi,
        "out_single": out_single,
        "out_nomem": out_nomem,
        "out_nonowner": out_nonowner,
        "out_expired": out_expired,
    }


@pytest.fixture
def recon_report(recon_data):
    return build_reconciliation_report(recon_data["db"], now=NOW)


def _by_id(entries, key="business_id"):
    return {e[key]: e for e in entries}


# ---------------------------------------------------------------------------
# A. Multiple owner memberships
# ---------------------------------------------------------------------------

def test_multiple_canonical_owners_reported_and_blocking(recon_data, recon_report):
    multi = recon_report["multiple_owner_memberships"]
    assert multi["blocking_for_uq_business_one_owner"] is True
    entries = _by_id(multi["businesses"])
    entry = entries[str(recon_data["biz_multi"].id)]
    assert entry["owner_count"] == 2
    assert set(entry["owner_user_ids"]) == {
        str(recon_data["u_multi_a"].id),
        str(recon_data["u_multi_b"].id),
    }
    # Businesses without multi-owner state must not be listed
    assert str(recon_data["biz_single"].id) not in entries
    assert str(recon_data["biz_zero_nomem"].id) not in entries
    assert str(recon_data["biz_expired"].id) not in entries
    assert str(recon_data["biz_drift"].id) not in entries


def test_single_owner_business_reported_in_neither_a_nor_b(recon_data, recon_report):
    single_id = str(recon_data["biz_single"].id)
    multi_ids = {e["business_id"] for e in recon_report["multiple_owner_memberships"]["businesses"]}
    zero_ids = {e["business_id"] for e in recon_report["zero_owner_memberships"]["businesses"]}
    assert single_id not in multi_ids
    assert single_id not in zero_ids


def test_supplementary_legacy_outlet_multi_owner(recon_data, recon_report):
    # Scenario fixture has at most one distinct legacy owner per business,
    # so the supplementary report stays empty for this dataset.
    assert recon_report["multiple_legacy_outlet_owners"]["businesses"] == []


# ---------------------------------------------------------------------------
# B. Zero owner memberships (must include businesses with no membership rows)
# ---------------------------------------------------------------------------

def test_zero_owner_includes_business_with_no_membership_rows(recon_data, recon_report):
    zero = recon_report["zero_owner_memberships"]
    entries = _by_id(zero["businesses"])
    entry = entries[str(recon_data["biz_zero_nomem"].id)]
    assert entry["classification"] == "no_business_membership_rows"
    assert entry["total_business_memberships"] == 0
    assert entry["legacy_owned_via_gated_fallback"] is False
    assert entry["legacy_outlet_owner_user_ids"] == []
    # created_at is included per architecture doc 9.3 item 1
    assert entry["created_at"] is not None


def test_zero_owner_with_non_owner_memberships_and_legacy_fallback(recon_data, recon_report):
    zero = recon_report["zero_owner_memberships"]
    entries = _by_id(zero["businesses"])
    entry = entries[str(recon_data["biz_zero_nonowner"].id)]
    assert entry["classification"] == "non_owner_memberships_only"
    assert entry["non_owner_membership_roles"] == {"manager": 1}
    assert entry["legacy_owned_via_gated_fallback"] is True
    assert entry["legacy_outlet_owner_user_ids"] == [str(recon_data["u_legacy_owner"].id)]


def test_zero_owner_classification_counts_cover_all_businesses(recon_data, recon_report):
    zero = recon_report["zero_owner_memberships"]
    counts = zero["classification_counts"]
    # Fixture businesses without canonical owners:
    # conftest's baseline "Test Business" (no membership rows) + biz_zero_nomem
    assert counts["no_business_membership_rows"] == 2
    assert counts["non_owner_memberships_only"] == 1
    # Every zero-owner business carries a classification
    assert len(zero["businesses"]) == sum(counts.values())
    # Businesses with at least one canonical owner are never zero-owner
    zero_ids = {e["business_id"] for e in zero["businesses"]}
    assert str(recon_data["biz_multi"].id) not in zero_ids
    assert str(recon_data["biz_expired"].id) not in zero_ids
    assert str(recon_data["biz_drift"].id) not in zero_ids


# ---------------------------------------------------------------------------
# C. Outlet subscription gaps
# ---------------------------------------------------------------------------

def test_outlet_with_no_subscription_rows(recon_data, recon_report):
    gaps = _by_id(recon_report["outlet_subscription_gaps"]["outlets"], key="outlet_id")
    entry = gaps[str(recon_data["out_nomem"].id)]
    assert entry["gap_category"] == "no_subscription_rows"
    assert entry["subscription_row_count"] == 0
    assert entry["current_subscription_id"] is None
    assert entry["fallback_tier"] == "legacy_business_columns"
    assert entry["fallback_potentially_supplies_entitlements"] is True


def test_outlet_with_rows_but_no_current_flag(recon_data, recon_report):
    gaps = _by_id(recon_report["outlet_subscription_gaps"]["outlets"], key="outlet_id")
    entry = gaps[str(recon_data["out_nonowner"].id)]
    assert entry["gap_category"] == "rows_without_current_flag"
    assert entry["subscription_row_count"] == 1
    assert entry["current_subscription_id"] is None
    assert entry["fallback_tier"] == "business_subscription"
    assert entry["fallback_potentially_supplies_entitlements"] is True


def test_outlet_with_current_row_resolved_non_current(recon_data, recon_report):
    gaps = _by_id(recon_report["outlet_subscription_gaps"]["outlets"], key="outlet_id")
    entry = gaps[str(recon_data["out_expired"].id)]
    assert entry["gap_category"] == "current_row_non_current_status"
    assert entry["current_subscription_resolved_status"] == "expired"
    assert entry["current_subscription_stored_status"] == "trial"
    # The resolver consumes the non-current is_current row: no fallback tier applies
    assert entry["fallback_tier"] == "none_resolver_consumes_current_row"
    assert entry["fallback_potentially_supplies_entitlements"] is False


def test_outlet_with_valid_current_subscription_excluded(recon_data, recon_report):
    gap_ids = {e["outlet_id"] for e in recon_report["outlet_subscription_gaps"]["outlets"]}
    assert str(recon_data["out_multi"].id) not in gap_ids
    assert str(recon_data["out_single"].id) not in gap_ids
    assert recon_report["totals"]["outlets_with_valid_current_subscription"] == 2
    # Category counts add up to the full gap list (including conftest baseline outlet)
    cat = recon_report["outlet_subscription_gaps"]["category_counts"]
    total_gaps = len(recon_report["outlet_subscription_gaps"]["outlets"])
    assert sum(cat.values()) == total_gaps == recon_report["totals"]["outlets_with_subscription_gap"]
    # Documented criteria are exposed on the report
    assert "is_current == True" in recon_report["outlet_subscription_gaps"]["criteria"]


# ---------------------------------------------------------------------------
# D. Legacy entitlement fallback cohort
# ---------------------------------------------------------------------------

def test_legacy_fallback_cohort_static_candidates(recon_data, recon_report):
    fallback = recon_report["legacy_fallback_cohort"]
    assert fallback["runtime_usage_measured"] is False
    assert "NOT measured" in fallback["limitation"]

    cohort_ids = {
        e["business_id"]
        for e in fallback["businesses_with_current_business_subscription"]
    }
    # biz_zero_nonowner (tier-2 supplier for its outlet) and biz_drift both hold
    # a current BusinessSubscription in the fixture scenario.
    assert cohort_ids == {
        str(recon_data["biz_zero_nonowner"].id),
        str(recon_data["biz_drift"].id),
    }

    served = fallback["outlets_served_by_business_subscription_fallback"]
    assert [e["outlet_id"] for e in served] == [str(recon_data["out_nonowner"].id)]

    # Tier-3 legacy-column candidates: the scenario outlet plus conftest's
    # baseline outlet (no subscription rows, no business-level subscription).
    baseline_outlet = (
        recon_data["db"].query(Outlet).filter(Outlet.name == "Test Camp Outlet").one()
    )
    to_columns = fallback["outlets_falling_to_legacy_business_columns"]
    assert {e["outlet_id"] for e in to_columns} == {
        str(recon_data["out_nomem"].id),
        str(baseline_outlet.id),
    }


def test_resolver_order_documented(recon_report):
    order = recon_report["legacy_fallback_cohort"]["resolver_order"]
    assert "OutletSubscription" in order
    assert "BusinessSubscription" in order
    assert "legacy business columns" in order


# ---------------------------------------------------------------------------
# E. Denormalized column drift
# ---------------------------------------------------------------------------

def test_denormalized_column_drift_reported(recon_data, recon_report):
    drift = _by_id(recon_report["denormalized_column_drift"]["businesses"])
    entry = drift[str(recon_data["biz_drift"].id)]
    fields = entry["drift_fields"]
    assert set(fields.keys()) == {"subscription_status", "plan_name", "trial_ends_at"}
    assert fields["subscription_status"] == {
        "business_column": "trial",
        "subscription_row": "active",
    }
    assert fields["plan_name"]["business_column"] == "starter"
    assert fields["plan_name"]["subscription_row"] == "growth_pos"
    # max_outlets is explicitly excluded from drift comparison
    assert "max_outlets" not in fields
    assert "max_outlets" in recon_report["denormalized_column_drift"]["excluded_columns"]


def test_no_drift_when_columns_match_subscription(recon_data, recon_report):
    drift_ids = {e["business_id"] for e in recon_report["denormalized_column_drift"]["businesses"]}
    assert str(recon_data["biz_zero_nonowner"].id) not in drift_ids
    assert str(recon_data["biz_single"].id) not in drift_ids


# ---------------------------------------------------------------------------
# Read-only proof: no mutation path exists
# ---------------------------------------------------------------------------

def _table_counts(db: Session):
    return {
        "businesses": db.query(Business).count(),
        "outlets": db.query(Outlet).count(),
        "users": db.query(User).count(),
        "business_memberships": db.query(BusinessMembership).count(),
        "outlet_memberships": db.query(OutletMembership).count(),
        "outlet_subscriptions": db.query(OutletSubscription).count(),
        "business_subscriptions": db.query(BusinessSubscription).count(),
        "audit_logs": db.query(AuditLog).count(),
    }


def test_report_builder_preserves_all_row_counts(recon_data):
    db = recon_data["db"]
    before = _table_counts(db)
    report = build_reconciliation_report(db, now=NOW)
    text = format_reconciliation_report(report)
    assert isinstance(text, str) and text
    after = _table_counts(db)
    assert before == after


def test_report_builder_has_no_mutation_path(recon_data):
    db = recon_data["db"]
    forbidden = ("commit", "flush", "add", "add_all", "delete")
    with ExitStack() as stack:
        for name in forbidden:
            stack.enter_context(
                patch.object(db, name, side_effect=AssertionError(f"session.{name}() called"))
            )
        report = build_reconciliation_report(db, now=NOW)
        format_reconciliation_report(report)
    assert report["metadata"]["read_only"] is True


def test_report_metadata_documents_criteria(recon_report):
    meta = recon_report["metadata"]
    assert meta["read_only"] is True
    assert meta["criteria"]["current_outlet_subscription"] == CURRENT_ROW_CRITERIA
    assert "is_current == True" in meta["criteria"]["current_outlet_subscription"]
    assert meta["criteria"]["canonical_owner"] == "BusinessMembership.role == 'owner'"


# ---------------------------------------------------------------------------
# CLI wrapper
# ---------------------------------------------------------------------------

_FAKE_TARGET_INFO = {
    "target_env": "test",
    "host": "localhost",
    "port": 8000,
    "database": "recon_test",
    "scheme": "sqlite",
    "masked_uri": "sqlite:///:memory:",
    "is_explicit": False,
}


def test_cli_runs_read_only_report_and_exits_zero(recon_data, capsys):
    db = recon_data["db"]
    before = _table_counts(db)
    test_args = ["reconcile_ownership_subscriptions.py", "--target-env", "test"]
    with patch("sys.argv", test_args), \
         patch("scripts.reconcile_ownership_subscriptions.validate_reconciliation_database_target",
               return_value=_FAKE_TARGET_INFO), \
         patch("scripts.reconcile_ownership_subscriptions.SessionLocal", return_value=db), \
         patch.object(db, "close"), \
         pytest.raises(SystemExit) as exc_info:
        cli_main()
    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert "READ-ONLY" in captured.out
    assert "MULTIPLE OWNER MEMBERSHIPS" in captured.out
    assert "Multi Owner Co" in captured.out
    assert "ZERO OWNER MEMBERSHIPS" in captured.out
    assert "OUTLET SUBSCRIPTION GAPS" in captured.out
    assert "LEGACY ENTITLEMENT FALLBACK COHORT" in captured.out
    assert "DENORMALIZED BUSINESS-COLUMN DRIFT" in captured.out
    assert "SELECT-only" in captured.out
    # No writes occurred during the CLI run
    assert before == _table_counts(db)


def test_cli_output_never_leaks_user_emails(recon_report, recon_data):
    text = format_reconciliation_report(recon_report, target_info=_FAKE_TARGET_INFO)
    for email in (
        "multi-a@leak-canary.test",
        "legacy-owner@leak-canary.test",
        "drift-owner@leak-canary.test",
        "staff@test.com",
    ):
        assert email not in text


def test_cli_fails_closed_when_validation_raises(recon_data, capsys):
    db = recon_data["db"]
    test_args = ["reconcile_ownership_subscriptions.py", "--target-env", "production"]
    with patch("sys.argv", test_args), \
         patch(
             "scripts.reconcile_ownership_subscriptions.validate_reconciliation_database_target",
             side_effect=ValidationError("refused"),
         ), \
         pytest.raises(SystemExit) as exc_info:
        cli_main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "[FATAL]" in captured.err


def test_cli_requires_target_env_argument(capsys):
    test_args = ["reconcile_ownership_subscriptions.py"]
    with patch("sys.argv", test_args), pytest.raises(SystemExit) as exc_info:
        cli_main()
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# Target validation (fail-closed + secret redaction)
# ---------------------------------------------------------------------------

def test_validate_masks_database_password():
    info = validate_reconciliation_database_target(
        "test",
        database_uri="postgresql://recon_user:S3cretPass@db.example.com:5432/roms",
        explicit_database_url="postgresql://recon_user:S3cretPass@db.example.com:5432/roms",
    )
    assert "S3cretPass" not in info["masked_uri"]
    assert ":****@" in info["masked_uri"]
    assert info["target_env"] == "test"


def test_validate_rejects_production_without_explicit_url():
    with pytest.raises(Exception, match="explicitly configured DATABASE_URL"):
        validate_reconciliation_database_target(
            "production",
            database_uri="postgresql://localhost/roms",
            explicit_database_url=None,
        )


def test_validate_rejects_production_on_localhost():
    with pytest.raises(Exception, match="localhost"):
        validate_reconciliation_database_target(
            "production",
            database_uri="postgresql://user:pass@localhost/roms",
            explicit_database_url="postgresql://user:pass@localhost/roms",
        )


def test_validate_rejects_staging_on_localhost():
    with pytest.raises(Exception, match="localhost"):
        validate_reconciliation_database_target(
            "staging",
            database_uri="postgresql://user:pass@localhost/roms",
            explicit_database_url="postgresql://user:pass@localhost/roms",
        )


def test_validate_rejects_staging_without_explicit_url():
    with pytest.raises(Exception, match="explicitly configured DATABASE_URL"):
        validate_reconciliation_database_target(
            "staging",
            database_uri="postgresql://localhost/roms",
            explicit_database_url="",
        )


def test_validate_rejects_local_targeting_remote_host():
    with pytest.raises(Exception, match="mismatch"):
        validate_reconciliation_database_target(
            "local",
            database_uri="postgresql://user:pass@remote.example.com/roms",
            explicit_database_url="postgresql://user:pass@remote.example.com/roms",
        )


def test_validate_rejects_missing_and_unknown_environments():
    with pytest.raises(Exception, match="required"):
        validate_reconciliation_database_target(None)
    with pytest.raises(Exception, match="Invalid target environment"):
        validate_reconciliation_database_target("qa-unknown")


def test_validate_accepts_explicit_remote_development_target_trusted_by_repo_env():
    # Environment identity comes from the repository-root .env marker, NOT the
    # hostname: this host is deliberately NOT a Neon-style hostname.
    dev_url = "postgresql://recon_user:S3cretDevPass@db-dev.internal.example.com:5432/roms_dev"
    info = validate_reconciliation_database_target(
        "development",
        database_uri=dev_url,
        explicit_database_url=dev_url,
        repository_root_database_url=dev_url,
    )
    assert info["target_env"] == "development"
    assert info["host"] == "db-dev.internal.example.com"
    assert info["database"] == "roms_dev"
    assert "S3cretDevPass" not in info["masked_uri"]
    assert ":****@" in info["masked_uri"]


def test_validate_accepts_local_localhost_development_target_trusted_by_repo_env():
    dev_url = "postgresql://roms_user:devpass@localhost:5432/roms_db"
    info = validate_reconciliation_database_target(
        "development",
        database_uri=dev_url,
        explicit_database_url=dev_url,
        repository_root_database_url=dev_url,
    )
    assert info["target_env"] == "development"
    assert info["host"] == "localhost"


def test_validate_development_rejects_missing_database_url():
    # Implicit localhost fallback must never be classified as development.
    with pytest.raises(Exception, match="explicitly configured DATABASE_URL"):
        validate_reconciliation_database_target(
            "development",
            database_uri="postgresql://localhost/roms_db",
            explicit_database_url="",
            repository_root_database_url="postgresql://user:pass@db-dev.example.com/roms_dev",
        )


def test_validate_development_rejects_without_repository_env_marker():
    dev_url = "postgresql://user:pass@ep-anything.neon.tech:5432/neondb"
    with pytest.raises(Exception, match="repository-root .env"):
        validate_reconciliation_database_target(
            "development",
            database_uri=dev_url,
            explicit_database_url=dev_url,
            repository_root_database_url=None,
        )


def test_validate_neon_hostname_alone_does_not_grant_development():
    # A Neon-looking hostname without the trusted repository-root .env marker
    # must still fail closed: environment identity is never hostname-inferred.
    neonish_url = "postgresql://user:pass@ep-looks-like-dev.neon.tech:5432/neondb"
    with pytest.raises(Exception, match="repository-root .env"):
        validate_reconciliation_database_target(
            "development",
            database_uri=neonish_url,
            explicit_database_url=neonish_url,
            repository_root_database_url=None,
        )


def test_validate_development_rejects_mismatched_repository_env_target():
    effective = "postgresql://user:pass@ep-other-host.example.com:5432/roms_dev"
    repo_env = "postgresql://user:pass@ep-approved-dev.example.com:5432/roms_dev"
    with pytest.raises(Exception, match="mismatch"):
        validate_reconciliation_database_target(
            "development",
            database_uri=effective,
            explicit_database_url=effective,
            repository_root_database_url=repo_env,
        )


def test_validate_errors_and_results_never_leak_credentials():
    secret = "Sup3rSecretCanary99"
    effective = f"postgresql://user:{secret}@ep-bad.example.com:5432/roms"
    repo_env = f"postgresql://user:{secret}@ep-good.example.com:5432/roms_dev"
    with pytest.raises(Exception) as exc_info:
        validate_reconciliation_database_target(
            "development",
            database_uri=effective,
            explicit_database_url=effective,
            repository_root_database_url=repo_env,
        )
    assert secret not in str(exc_info.value)

    with pytest.raises(Exception) as exc_info:
        validate_reconciliation_database_target(
            "production",
            database_uri=f"postgresql://user:{secret}@localhost/roms",
            explicit_database_url=f"postgresql://user:{secret}@localhost/roms",
        )
    assert secret not in str(exc_info.value)

    info = validate_reconciliation_database_target(
        "development",
        database_uri=effective,
        explicit_database_url=effective,
        repository_root_database_url=effective,
    )
    assert secret not in info["masked_uri"]
    assert secret not in str(info)
