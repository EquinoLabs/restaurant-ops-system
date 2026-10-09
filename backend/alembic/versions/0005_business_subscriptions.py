"""Add subscription and account status fields to businesses table

Revision ID: 0005_business_subscriptions
Revises: 0004_platform_admin_identity
Create Date: 2026-10-10 04:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0005_business_subscriptions'
down_revision: Union[str, None] = '0004_platform_admin_identity'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'businesses',
        sa.Column('subscription_status', sa.String(length=20), server_default='trial', nullable=False)
    )
    op.add_column(
        'businesses',
        sa.Column('plan_name', sa.String(length=50), nullable=True)
    )
    op.add_column(
        'businesses',
        sa.Column('max_outlets', sa.Integer(), nullable=True)
    )
    op.add_column(
        'businesses',
        sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('businesses', 'trial_ends_at')
    op.drop_column('businesses', 'max_outlets')
    op.drop_column('businesses', 'plan_name')
    op.drop_column('businesses', 'subscription_status')
