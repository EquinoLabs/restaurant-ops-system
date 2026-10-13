"""Enforce platform role consistency check constraint and single active owner index

Revision ID: 0012_platform_role_constraints
Revises: 0011_add_platform_role_column
Create Date: 2026-10-13 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0012_platform_role_constraints'
down_revision: Union[str, None] = '0011_add_platform_role_column'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect_name = conn.dialect.name

    # 1. Lock users table against concurrent writers in EXCLUSIVE mode (PostgreSQL only)
    if dialect_name == "postgresql":
        conn.execute(sa.text("LOCK TABLE users IN EXCLUSIVE MODE;"))

    # 2. Pre-check gate: Fail closed on corrupt, malformed, or contradictory role/boolean records
    fatal_anomalies = conn.execute(sa.text("""
        SELECT COUNT(*) FROM users
        WHERE is_platform_admin IS NULL
           OR status IS NULL
           OR status NOT IN ('active', 'suspended')
           OR platform_role = ''
           OR (platform_role IS NOT NULL AND platform_role != TRIM(platform_role))
           OR (platform_role IS NOT NULL AND platform_role NOT IN ('owner', 'admin', 'operator'))
           OR (platform_role = 'operator' AND is_platform_admin IS TRUE)
           OR (platform_role IN ('admin', 'owner') AND is_platform_admin IS NOT TRUE);
    """)).scalar()
    if fatal_anomalies > 0:
        raise RuntimeError(
            f"Migration 0012 aborted: Found {fatal_anomalies} corrupt, malformed, or contradictory user records."
        )

    # 3. Pre-check gate: Fail closed if multiple active owners already exist
    active_owners = conn.execute(sa.text("""
        SELECT COUNT(*) FROM users WHERE platform_role = 'owner' AND status = 'active';
    """)).scalar()
    if active_owners > 1:
        raise RuntimeError(
            f"Migration 0012 aborted: Found {active_owners} active Platform Owners. Maximum allowed is 1."
        )

    # 4. Apply approved legacy-admin backfill (platform_role IS NULL and is_platform_admin IS TRUE -> 'admin')
    conn.execute(sa.text("""
        UPDATE users
        SET platform_role = 'admin'
        WHERE is_platform_admin IS TRUE AND platform_role IS NULL;
    """))

    # 5. Inline post-backfill reconciliation check (Must be 0 non-compliant rows)
    invalid_rows = conn.execute(sa.text("""
        SELECT COUNT(*) FROM users
        WHERE NOT (
            CASE
                WHEN platform_role IN ('owner', 'admin') THEN is_platform_admin IS TRUE
                WHEN platform_role = 'operator' OR platform_role IS NULL THEN is_platform_admin IS FALSE
                ELSE FALSE
            END
        );
    """)).scalar()
    if invalid_rows > 0:
        raise RuntimeError(
            f"Migration 0012 aborted: Post-backfill check failed. Found {invalid_rows} non-compliant rows."
        )

    # 6. Add strict NULL-safe CHECK constraint using IS TRUE / IS FALSE
    check_condition = (
        "CASE "
        "WHEN platform_role IN ('owner', 'admin') THEN is_platform_admin IS TRUE "
        "WHEN platform_role = 'operator' OR platform_role IS NULL THEN is_platform_admin IS FALSE "
        "ELSE FALSE "
        "END"
    )
    if dialect_name == "sqlite":
        with op.batch_alter_table('users') as batch_op:
            batch_op.create_check_constraint(
                constraint_name='ck_users_platform_role_consistency',
                condition=check_condition
            )
    else:
        op.create_check_constraint(
            constraint_name='ck_users_platform_role_consistency',
            table_name='users',
            condition=check_condition
        )

    # 7. Create single active owner partial unique index
    if dialect_name == "sqlite":
        op.create_index(
            index_name='ix_users_single_active_platform_owner',
            table_name='users',
            columns=['platform_role'],
            unique=True,
            sqlite_where=sa.text("platform_role = 'owner' AND status = 'active'")
        )
    else:
        op.create_index(
            index_name='ix_users_single_active_platform_owner',
            table_name='users',
            columns=['platform_role'],
            unique=True,
            postgresql_where=sa.text("platform_role = 'owner' AND status = 'active'")
        )


def downgrade() -> None:
    conn = op.get_bind()
    dialect_name = conn.dialect.name

    # 1. Drop the single active owner partial unique index
    op.drop_index(
        index_name='ix_users_single_active_platform_owner',
        table_name='users'
    )

    # 2. Drop the consistency check constraint
    if dialect_name == "sqlite":
        with op.batch_alter_table('users') as batch_op:
            batch_op.drop_constraint('ck_users_platform_role_consistency', type_='check')
    else:
        op.drop_constraint(
            constraint_name='ck_users_platform_role_consistency',
            table_name='users',
            type_='check'
        )
