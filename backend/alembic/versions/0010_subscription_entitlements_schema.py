"""Subscription Entitlements Schema, Plans, Features, Seed Data & Backfill

Revision ID: 0010_subscription_entitlements_schema
Revises: 0009_order_number_unique_constraint
Create Date: 2026-10-11 01:30:00.000000

"""
import uuid
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0010_subscription_entitlements_schema'
down_revision: Union[str, None] = '0009_order_number_unique_constraint'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RECOGNIZED_PLANS = {'starter', 'growth', 'pro', 'enterprise', 'digital_menu', 'free'}

PLAN_MAP = {
    'starter': 'starter_pos',
    'growth': 'growth_pos',
    'pro': 'pro_kds',
    'enterprise': 'enterprise',
    'digital_menu': 'free_qr',
    'free': 'free_qr',
}


def upgrade() -> None:
    bind = op.get_bind()

    # Pre-check: Find any business with unmapped non-empty plan_name
    result = bind.execute(
        sa.text(
            "SELECT id, plan_name FROM businesses "
            "WHERE plan_name IS NOT NULL AND plan_name != '' "
            "AND plan_name NOT IN ('starter', 'growth', 'pro', 'enterprise', 'digital_menu', 'free')"
        )
    ).fetchall()

    if result:
        unmapped_info = [f"id={r[0]}, plan_name='{r[1]}'" for r in result]
        raise RuntimeError(
            f"Migration 0010 aborted: Businesses found with unmapped plan_name values: {', '.join(unmapped_info)}"
        )

    # 1. Create plans table
    op.create_table(
        'plans',
        sa.Column('id', sa.UUID(), primary_key=True, default=uuid.uuid4),
        sa.Column('code', sa.String(length=50), nullable=False, unique=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 2. Create features table
    op.create_table(
        'features',
        sa.Column('id', sa.UUID(), primary_key=True, default=uuid.uuid4),
        sa.Column('code', sa.String(length=100), nullable=False, unique=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 3. Create plan_features table
    op.create_table(
        'plan_features',
        sa.Column('id', sa.UUID(), primary_key=True, default=uuid.uuid4),
        sa.Column('plan_id', sa.UUID(), sa.ForeignKey('plans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('feature_id', sa.UUID(), sa.ForeignKey('features.id', ondelete='CASCADE'), nullable=False),
        sa.Column('limit_value', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('plan_id', 'feature_id', name='uq_plan_feature'),
    )

    # 4. Create business_subscriptions table
    op.create_table(
        'business_subscriptions',
        sa.Column('id', sa.UUID(), primary_key=True, default=uuid.uuid4),
        sa.Column('business_id', sa.UUID(), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plan_id', sa.UUID(), sa.ForeignKey('plans.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='trial'),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create partial unique index on business_subscriptions
    dialect_name = bind.dialect.name
    if dialect_name == 'sqlite':
        op.create_index(
            'uq_business_current_subscription',
            'business_subscriptions',
            ['business_id'],
            unique=True,
            sqlite_where=sa.text('is_current = 1')
        )
    else:
        op.create_index(
            'uq_business_current_subscription',
            'business_subscriptions',
            ['business_id'],
            unique=True,
            postgresql_where=sa.text('is_current = true')
        )

    # 5. Create entitlement_overrides table
    op.create_table(
        'entitlement_overrides',
        sa.Column('id', sa.UUID(), primary_key=True, default=uuid.uuid4),
        sa.Column('business_id', sa.UUID(), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('outlet_id', sa.UUID(), sa.ForeignKey('outlets.id', ondelete='CASCADE'), nullable=True),
        sa.Column('feature_code', sa.String(length=100), nullable=False),
        sa.Column('override_type', sa.String(length=20), nullable=False),
        sa.Column('limit_value', sa.Integer(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_user_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- Seed Plans ---
    plans_data = [
        {'id': uuid.uuid4(), 'code': 'free_qr', 'name': 'Free QR Menu', 'description': 'Digital QR Menu viewing', 'sort_order': 1},
        {'id': uuid.uuid4(), 'code': 'starter_pos', 'name': 'Starter POS', 'description': 'Single-outlet POS and digital menu', 'sort_order': 2},
        {'id': uuid.uuid4(), 'code': 'growth_pos', 'name': 'Growth POS', 'description': 'Multi-outlet POS and Ordering', 'sort_order': 3},
        {'id': uuid.uuid4(), 'code': 'pro_kds', 'name': 'Pro KDS & Ordering', 'description': 'Full POS, KDS, and Digital Ordering', 'sort_order': 4},
        {'id': uuid.uuid4(), 'code': 'enterprise', 'name': 'Enterprise', 'description': 'Unlimited outlets, all features', 'sort_order': 5},
    ]
    plan_id_map = {}
    for p in plans_data:
        plan_id_map[p['code']] = p['id']
        bind.execute(
            sa.text(
                "INSERT INTO plans (id, code, name, description, is_active, sort_order, created_at, updated_at) "
                "VALUES (:id, :code, :name, :description, true, :sort_order, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            p
        )

    # --- Seed Features ---
    features_data = [
        {'id': uuid.uuid4(), 'code': 'menu.digital', 'name': 'Digital Menu Viewing', 'category': 'menu', 'description': 'View public digital menu'},
        {'id': uuid.uuid4(), 'code': 'ordering.customer', 'name': 'Customer QR Ordering', 'category': 'ordering', 'description': 'Customer self-ordering via QR'},
        {'id': uuid.uuid4(), 'code': 'ordering.staff', 'name': 'Staff POS Ordering', 'category': 'ordering', 'description': 'Staff order creation in POS'},
        {'id': uuid.uuid4(), 'code': 'kds.enabled', 'name': 'Kitchen Display System', 'category': 'kitchen', 'description': 'KDS station interface'},
        {'id': uuid.uuid4(), 'code': 'outlets.max_count', 'name': 'Maximum Outlet Count', 'category': 'billing', 'description': 'Maximum active outlets allowed'},
        {'id': uuid.uuid4(), 'code': 'payments.online', 'name': 'Online Payment Gateway', 'category': 'billing', 'description': 'Accept online customer payments'},
        {'id': uuid.uuid4(), 'code': 'notifications.whatsapp', 'name': 'WhatsApp Notifications', 'category': 'marketing', 'description': 'WhatsApp order updates'},
    ]
    feature_id_map = {}
    for f in features_data:
        feature_id_map[f['code']] = f['id']
        bind.execute(
            sa.text(
                "INSERT INTO features (id, code, name, category, description, created_at, updated_at) "
                "VALUES (:id, :code, :name, :category, :description, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            f
        )

    # --- Seed Plan Features ---
    # (plan_code, feature_code, limit_value)
    plan_features_data = [
        # free_qr
        ('free_qr', 'menu.digital', None),
        ('free_qr', 'outlets.max_count', 1),
        # starter_pos
        ('starter_pos', 'menu.digital', None),
        ('starter_pos', 'ordering.staff', None),
        ('starter_pos', 'outlets.max_count', 1),
        # growth_pos
        ('growth_pos', 'menu.digital', None),
        ('growth_pos', 'ordering.staff', None),
        ('growth_pos', 'ordering.customer', None),
        ('growth_pos', 'outlets.max_count', 3),
        # pro_kds
        ('pro_kds', 'menu.digital', None),
        ('pro_kds', 'ordering.staff', None),
        ('pro_kds', 'ordering.customer', None),
        ('pro_kds', 'kds.enabled', None),
        ('pro_kds', 'outlets.max_count', 10),
        # enterprise
        ('enterprise', 'menu.digital', None),
        ('enterprise', 'ordering.staff', None),
        ('enterprise', 'ordering.customer', None),
        ('enterprise', 'kds.enabled', None),
        ('enterprise', 'payments.online', None),
        ('enterprise', 'notifications.whatsapp', None),
        ('enterprise', 'outlets.max_count', None),
    ]

    for p_code, f_code, limit_val in plan_features_data:
        pf_id = uuid.uuid4()
        bind.execute(
            sa.text(
                "INSERT INTO plan_features (id, plan_id, feature_id, limit_value, created_at, updated_at) "
                "VALUES (:id, :plan_id, :feature_id, :limit_value, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                'id': pf_id,
                'plan_id': plan_id_map[p_code],
                'feature_id': feature_id_map[f_code],
                'limit_value': limit_val,
            }
        )

    # --- Backfill Existing Businesses ---
    businesses = bind.execute(
        sa.text("SELECT id, plan_name, subscription_status, trial_ends_at FROM businesses")
    ).fetchall()

    for b in businesses:
        b_id, raw_plan_name, sub_status, trial_ends = b[0], b[1], b[2], b[3]

        # Map legacy plan
        if raw_plan_name and raw_plan_name.lower() in PLAN_MAP:
            target_plan_code = PLAN_MAP[raw_plan_name.lower()]
        else:
            target_plan_code = 'free_qr'

        target_plan_id = plan_id_map[target_plan_code]
        sub_id = uuid.uuid4()
        status_val = sub_status if sub_status else 'trial'

        bind.execute(
            sa.text(
                "INSERT INTO business_subscriptions "
                "(id, business_id, plan_id, status, is_current, trial_ends_at, created_at, updated_at) "
                "VALUES (:id, :business_id, :plan_id, :status, true, :trial_ends_at, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                'id': sub_id,
                'business_id': b_id,
                'plan_id': target_plan_id,
                'status': status_val,
                'trial_ends_at': trial_ends,
            }
        )


def downgrade() -> None:
    op.drop_table('entitlement_overrides')
    op.drop_index('uq_business_current_subscription', table_name='business_subscriptions')
    op.drop_table('business_subscriptions')
    op.drop_table('plan_features')
    op.drop_table('features')
    op.drop_table('plans')
