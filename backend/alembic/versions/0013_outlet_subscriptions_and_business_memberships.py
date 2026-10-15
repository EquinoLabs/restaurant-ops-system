"""Outlet Subscriptions & Business Memberships Migration and Backfill

Revision ID: 0013_outlet_subscriptions_and_business_memberships
Revises: 0012_platform_role_constraints
Create Date: 2026-10-14 07:30:00.000000

"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0013_outlet_subscriptions'
down_revision: Union[str, None] = '0012_platform_role_constraints'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect_name = conn.dialect.name

    # 1. Lock relevant tables if running on PostgreSQL to prevent race conditions during DDL
    if dialect_name == "postgresql":
        conn.execute(sa.text("LOCK TABLE businesses, outlets, business_subscriptions IN EXCLUSIVE MODE;"))

    # 2. Create outlet_subscriptions table
    op.create_table(
        'outlet_subscriptions',
        sa.Column('id', sa.UUID(), primary_key=True, default=uuid.uuid4),
        sa.Column('outlet_id', sa.UUID(), sa.ForeignKey('outlets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('business_id', sa.UUID(), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plan_id', sa.UUID(), sa.ForeignKey('plans.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'trial'")),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Partial unique index: at most 1 current subscription per outlet
    if dialect_name == "sqlite":
        op.create_index(
            index_name='uq_outlet_subscription_current',
            table_name='outlet_subscriptions',
            columns=['outlet_id'],
            unique=True,
            sqlite_where=sa.text("is_current = 1")
        )
    else:
        op.create_index(
            index_name='uq_outlet_subscription_current',
            table_name='outlet_subscriptions',
            columns=['outlet_id'],
            unique=True,
            postgresql_where=sa.text("is_current = true")
        )

    op.create_index(
        index_name='ix_outlet_subscriptions_business_id',
        table_name='outlet_subscriptions',
        columns=['business_id']
    )
    op.create_index(
        index_name='ix_outlet_subscriptions_status',
        table_name='outlet_subscriptions',
        columns=['status']
    )

    # 3. Create business_memberships table
    op.create_table(
        'business_memberships',
        sa.Column('id', sa.UUID(), primary_key=True, default=uuid.uuid4),
        sa.Column('business_id', sa.UUID(), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(length=30), nullable=False, server_default=sa.text("'owner'")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('business_id', 'user_id', name='uq_business_user_membership'),
    )
    op.create_index(
        index_name='ix_business_memberships_user_id',
        table_name='business_memberships',
        columns=['user_id']
    )

    # 4. Backfill outlet_subscriptions for existing outlets
    now = datetime.now(timezone.utc)
    thirty_days_later = now + timedelta(days=30)

    # Resolve default plan id (growth_pos -> starter_pos -> first available)
    default_plan = conn.execute(
        sa.text("SELECT id FROM plans WHERE code = 'growth_pos'")
    ).fetchone()
    if not default_plan:
        default_plan = conn.execute(
            sa.text("SELECT id FROM plans WHERE code = 'starter_pos'")
        ).fetchone()
    if not default_plan:
        default_plan = conn.execute(
            sa.text("SELECT id FROM plans LIMIT 1")
        ).fetchone()
    default_plan_id = default_plan[0] if default_plan else None

    outlets = conn.execute(
        sa.text("SELECT id, business_id, created_at FROM outlets")
    ).fetchall()

    for row in outlets:
        outlet_id, business_id, o_created_at = row[0], row[1], row[2]

        bs = conn.execute(
            sa.text(
                "SELECT id, plan_id, status, trial_ends_at, current_period_start, "
                "current_period_end, cancel_at_period_end, cancelled_at "
                "FROM business_subscriptions "
                "WHERE business_id = :b_id AND is_current = true"
            ),
            {"b_id": business_id}
        ).fetchone()

        if bs:
            plan_id = bs[1] or default_plan_id
            status = bs[2] or "trial"
            bs_trial_ends = bs[3]
            current_period_start = bs[4]
            current_period_end = bs[5]
            cancel_at_period_end = bool(bs[6]) if bs[6] is not None else False
            cancelled_at = bs[7]

            if status == "trial":
                # Decision 1 Approved: If trial_ends_at is NULL or past, grant 30 days from migration timestamp
                if bs_trial_ends is not None:
                    dt_val = bs_trial_ends if bs_trial_ends.tzinfo else bs_trial_ends.replace(tzinfo=timezone.utc)
                    if dt_val > now:
                        trial_ends_at = bs_trial_ends
                    else:
                        trial_ends_at = thirty_days_later
                else:
                    trial_ends_at = thirty_days_later
            else:
                trial_ends_at = bs_trial_ends
        else:
            plan_id = default_plan_id
            status = "trial"
            trial_ends_at = thirty_days_later
            current_period_start = None
            current_period_end = None
            cancel_at_period_end = False
            cancelled_at = None

        conn.execute(
            sa.text("""
                INSERT INTO outlet_subscriptions (
                    id, outlet_id, business_id, plan_id, status, is_current,
                    trial_ends_at, current_period_start, current_period_end,
                    cancel_at_period_end, cancelled_at, created_at, updated_at
                ) VALUES (
                    :id, :outlet_id, :business_id, :plan_id, :status, :is_current,
                    :trial_ends_at, :current_period_start, :current_period_end,
                    :cancel_at_period_end, :cancelled_at, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": uuid.uuid4(),
                "outlet_id": outlet_id,
                "business_id": business_id,
                "plan_id": plan_id,
                "status": status,
                "is_current": True,
                "trial_ends_at": trial_ends_at,
                "current_period_start": current_period_start,
                "current_period_end": current_period_end,
                "cancel_at_period_end": cancel_at_period_end,
                "cancelled_at": cancelled_at,
            }
        )

    # 5. Backfill business_memberships from outlet_memberships where role = 'owner'
    owners = conn.execute(
        sa.text("""
            SELECT DISTINCT o.business_id, om.user_id
            FROM outlet_memberships om
            JOIN outlets o ON om.outlet_id = o.id
            WHERE om.role = 'owner'
        """)
    ).fetchall()

    for owner_row in owners:
        b_id, u_id = owner_row[0], owner_row[1]
        # Check if already inserted
        exists = conn.execute(
            sa.text("SELECT 1 FROM business_memberships WHERE business_id = :b_id AND user_id = :u_id"),
            {"b_id": b_id, "u_id": u_id}
        ).fetchone()
        if not exists:
            conn.execute(
                sa.text("""
                    INSERT INTO business_memberships (
                        id, business_id, user_id, role, created_at, updated_at
                    ) VALUES (
                        :id, :business_id, :user_id, 'owner', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                """),
                {
                    "id": uuid.uuid4(),
                    "business_id": b_id,
                    "user_id": u_id,
                }
            )

    # 6. Post-backfill validation check
    if len(outlets) > 0:
        actual_subs = conn.execute(
            sa.text("SELECT COUNT(*) FROM outlet_subscriptions WHERE is_current = true")
        ).scalar()
        if actual_subs != len(outlets):
            raise RuntimeError(
                f"Migration 0013 failed post-backfill check: expected {len(outlets)} current outlet subscriptions, found {actual_subs}"
            )


def downgrade() -> None:
    # 1. Drop business_memberships
    op.drop_index('ix_business_memberships_user_id', table_name='business_memberships')
    op.drop_table('business_memberships')

    # 2. Drop outlet_subscriptions
    op.drop_index('uq_outlet_subscription_current', table_name='outlet_subscriptions')
    op.drop_index('ix_outlet_subscriptions_business_id', table_name='outlet_subscriptions')
    op.drop_index('ix_outlet_subscriptions_status', table_name='outlet_subscriptions')
    op.drop_table('outlet_subscriptions')
