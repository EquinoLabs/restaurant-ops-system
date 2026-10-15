"""Opt-in PostgreSQL integration tests for migration 0013 enforcement and
the migration 0014 index set.

Run ONLY against a dedicated, disposable, locally-migrated PostgreSQL test
database (never Neon, never production), with the explicit flag:

    pytest --pg-integration tests/test_postgres_migration_0014_verification.py

Prerequisite bootstrap (see scripts/init_postgres_test_db.py and
scripts/migrate_postgres_test_db.py): the target must carry the
roms_disposable_test_marker table and have alembic_version at the current
head 0014_add_missing_tenant_indexes (migrate_postgres_test_db.py applies
0001..0014 via the guarded runner). Migration 0014 is promoted into the
Alembic history but has not been applied to any database until that runner
is explicitly executed against a verified disposable target.

Tests:
1. uq_outlet_subscription_current (created by migration 0013) is enforced by
   the PostgreSQL engine: a second is_current=true row for the same outlet
   raises IntegrityError; historical is_current=false rows are allowed.
   This closes the honesty gap left by the SQLite-only suite.
2. The two indexes added by alembic/versions/0014_add_missing_tenant_indexes
   are absent (skipped — database not yet migrated through 0014) or, once
   applied, present, valid, btree, non-unique, non-partial.

All data mutations are performed inside transactions that are rolled back;
nothing is committed, so disposable-target verification for subsequent runs
stays intact. No schema is created or altered by these tests.
"""
import uuid
from datetime import timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.db.base import utc_now
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.subscriptions.models import Plan, OutletSubscription

pytestmark = pytest.mark.postgres_integration


def _index_row(engine, index_name: str):
    with engine.connect() as conn:
        return conn.execute(
            sa.text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' AND indexname = :name"
            ),
            {"name": index_name},
        ).scalar()


def _seed_minimal(db, suffix: str):
    plan = Plan(
        id=uuid.uuid4(),
        code=f"pgver_{suffix}",
        name="PG Verification Plan",
        sort_order=900,
    )
    biz = Business(id=uuid.uuid4(), name=f"PG Verify Business {suffix}", status="active")
    db.add_all([plan, biz])
    db.flush()
    outlet = Outlet(
        id=uuid.uuid4(),
        business_id=biz.id,
        name=f"PG Verify Outlet {suffix}",
        public_slug=f"pg-verify-{suffix}",
        timezone="UTC",
        currency="INR",
        address="PG verification",
        status="active",
    )
    db.add(outlet)
    db.flush()
    return plan, biz, outlet


def test_pg_partial_unique_rejects_duplicate_current_subscription(pg_engine):
    indexdef = _index_row(pg_engine, "uq_outlet_subscription_current")
    if indexdef is None:
        pytest.skip(
            "uq_outlet_subscription_current not found; target database is not "
            "migrated to the current head 0014_add_missing_tenant_indexes. Run "
            "scripts/migrate_postgres_test_db.py --confirm first."
        )
    assert "is_current" in indexdef, (
        f"uq_outlet_subscription_current must be partial over is_current; got: {indexdef}"
    )

    Session = sa.orm.sessionmaker(bind=pg_engine)
    db = Session()
    try:
        now = utc_now()
        suffix = uuid.uuid4().hex[:10]
        plan, biz, outlet = _seed_minimal(db, suffix)

        db.add(
            OutletSubscription(
                id=uuid.uuid4(),
                outlet_id=outlet.id,
                business_id=biz.id,
                plan_id=plan.id,
                status="trial",
                is_current=True,
                trial_ends_at=now + timedelta(days=30),
            )
        )
        db.flush()

        db.add(
            OutletSubscription(
                id=uuid.uuid4(),
                outlet_id=outlet.id,
                business_id=biz.id,
                plan_id=plan.id,
                status="active",
                is_current=True,
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

        # Fresh transaction: partial scope allows historical (is_current=false) rows.
        plan, biz, outlet = _seed_minimal(db, uuid.uuid4().hex[:10])
        now = utc_now()
        db.add(
            OutletSubscription(
                id=uuid.uuid4(),
                outlet_id=outlet.id,
                business_id=biz.id,
                plan_id=plan.id,
                status="trial",
                is_current=True,
                trial_ends_at=now + timedelta(days=30),
            )
        )
        db.add(
            OutletSubscription(
                id=uuid.uuid4(),
                outlet_id=outlet.id,
                business_id=biz.id,
                plan_id=plan.id,
                status="expired",
                is_current=False,
                current_period_start=now - timedelta(days=60),
                current_period_end=now - timedelta(days=30),
            )
        )
        db.flush()

        current_count = db.execute(
            sa.select(sa.func.count())
            .select_from(OutletSubscription)
            .where(
                OutletSubscription.outlet_id == outlet.id,
                OutletSubscription.is_current.is_(True),
            )
        ).scalar()
        assert current_count == 1
    finally:
        db.rollback()
        db.close()


def test_pg_proposed_0014_indexes_present_or_skip(pg_engine):
    expected = {"ix_outlet_subscriptions_outlet_id", "ix_business_memberships_business_id"}
    with pg_engine.connect() as conn:
        found = set(
            conn.execute(
                sa.text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = 'public' AND indexname IN "
                    "('ix_outlet_subscriptions_outlet_id','ix_business_memberships_business_id')"
                )
            ).scalars().all()
        )
    if not found:
        pytest.skip(
            "Migration 0014 has not been applied to this database yet "
            "(expected until scripts/migrate_postgres_test_db.py --confirm is "
            "run against a verified disposable target; see "
            "alembic/versions/0014_add_missing_tenant_indexes.py). "
            "After that run, this test asserts presence and shape of both indexes."
        )
    assert found == expected, (
        f"Partial 0014 application detected: expected both indexes, found {sorted(found)}"
    )

    with pg_engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT i.relname, ix.indisunique, (ix.indpred IS NOT NULL) AS is_partial, "
                "ix.indisvalid, am.amname "
                "FROM pg_index ix "
                "JOIN pg_class i ON i.oid = ix.indexrelid "
                "JOIN pg_class t ON t.oid = ix.indrelid "
                "JOIN pg_am am ON am.oid = i.relam "
                "WHERE t.relname IN ('outlet_subscriptions','business_memberships') "
                "AND i.relname IN "
                "('ix_outlet_subscriptions_outlet_id','ix_business_memberships_business_id')"
            )
        ).all()
    assert len(rows) == 2, f"Expected 2 catalog rows, got {len(rows)}: {rows}"
    for relname, is_unique, is_partial, is_valid, amname in rows:
        assert amname == "btree", f"{relname} must be btree, got {amname}"
        assert not is_unique, f"{relname} must not be unique"
        assert not is_partial, f"{relname} must not be partial"
        assert is_valid, f"{relname} must be a valid index (pg_index.indisvalid)"
