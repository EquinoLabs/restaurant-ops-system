"""Add missing tenant-scoped indexes (ORM/schema parity gap from 0013)

Revision ID: 0014_add_missing_tenant_indexes
Revises: 0013_outlet_subscriptions
Create Date: 2026-10-15

STATUS: PROMOTED into the active Alembic history on 2026-10-15 after proposal
review and pre-promotion audit. Reviewed source of truth for the proposal and
its full preflight checklist remains at
backend/scratch/proposal/0014_add_missing_tenant_indexes.py (retained as the
historical record). This migration has NOT been applied to any database yet:
no Alembic upgrade/downgrade has been run in this stage, and any future
PostgreSQL verification must go exclusively through the guarded runner
scripts/migrate_postgres_test_db.py (which injects a verified disposable-
target connection into Alembic). Never use bare `alembic upgrade`/`alembic
downgrade` — alembic/env.py falls back to the APPLICATION database URL, and
an unset DATABASE_URL is NOT a safety measure. Neon apply is a separate,
explicitly authorized operation not covered by this migration's promotion.

RATIONALE
=========
Migration 0013 created these PostgreSQL indexes on outlet_subscriptions /
business_memberships:
  - uq_outlet_subscription_current   (partial unique on outlet_id WHERE is_current = true)
  - ix_outlet_subscriptions_business_id
  - ix_outlet_subscriptions_status
  - ix_business_memberships_user_id
  - uq_business_user_membership      (table-level UniqueConstraint)

The ORM models declare `index=True` on OutletSubscription.outlet_id and
BusinessMembership.business_id, which SQLAlchemy emits as
ix_outlet_subscriptions_outlet_id and ix_business_memberships_business_id when
it creates the schema itself (SQLite test databases). Migration 0013 did NOT
create these two indexes on PostgreSQL, leaving a schema/ORM parity gap.

Intended SQL on PostgreSQL (non-partial, non-unique, single-column):
  CREATE INDEX ix_outlet_subscriptions_outlet_id
      ON outlet_subscriptions (outlet_id);
  CREATE INDEX ix_business_memberships_business_id
      ON business_memberships (business_id);

DOWNGRADE BEHAVIOR
==================
downgrade() drops the two indexes named in _INDEX_SPECS, but only when the
inspector reports both the table and that index name present. It does NOT
attempt to determine which migration originally created an index: the check
is name-and-presence based, not provenance based. Consequently, if an index
with one of these names pre-existed before 0014 ran (upgrade would have
skipped it), downgrade would still drop it — the pre-existing-index case is
a known limitation, acceptable because the only sanctioned apply path is a
clean 0013-migrated disposable database where both indexes are absent.
Downgrading a database that never received 0014 is a no-op (indexes absent,
so nothing is dropped). No tables, columns, or data are touched in either
direction; both operations are pure index DDL and cannot lose rows.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0014_add_missing_tenant_indexes'
down_revision: Union[str, None] = '0013_outlet_subscriptions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX_SPECS = (
    ("ix_outlet_subscriptions_outlet_id", "outlet_subscriptions", ["outlet_id"]),
    ("ix_business_memberships_business_id", "business_memberships", ["business_id"]),
)


def _existing_index_names(conn, table_name: str) -> set:
    inspector = sa.inspect(conn)
    return {ix["name"] for ix in inspector.get_indexes(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    for index_name, table_name, columns in _INDEX_SPECS:
        if index_name in _existing_index_names(conn, table_name):
            continue
        op.create_index(index_name=index_name, table_name=table_name, columns=columns)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())
    for index_name, table_name, _columns in reversed(_INDEX_SPECS):
        if table_name not in existing_tables:
            continue
        if index_name not in _existing_index_names(conn, table_name):
            continue
        op.drop_index(index_name=index_name, table_name=table_name)
