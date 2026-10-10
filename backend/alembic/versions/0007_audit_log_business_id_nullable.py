"""Make audit_logs business_id column nullable for system-wide platform operations

Revision ID: 0007_audit_log_business_id_nullable
Revises: 0006_outlet_branding
Create Date: 2026-10-10 05:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0007_audit_log_business_id_nullable'
down_revision: Union[str, None] = '0006_outlet_branding'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'audit_logs',
        'business_id',
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True
    )


def downgrade() -> None:
    # Check if system-level audit logs with business_id IS NULL exist in database
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT COUNT(*) FROM audit_logs WHERE business_id IS NULL"))
    null_count = result.scalar() if result else 0

    if null_count > 0:
        raise RuntimeError(
            f"Cannot downgrade migration 0007: Found {null_count} system-level audit log record(s) "
            "where 'business_id' is NULL. Restoring NOT NULL constraint would fail or cause data loss. "
            "Please archive or delete these platform audit records manually before downgrading."
        )

    op.alter_column(
        'audit_logs',
        'business_id',
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False
    )
