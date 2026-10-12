"""Add platform_role column to users table

Revision ID: 0011_add_platform_role_column
Revises: 0010_subscription_entitlements_schema
Create Date: 2026-10-12 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0011_add_platform_role_column'
down_revision: Union[str, None] = '0010_subscription_entitlements_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('platform_role', sa.String(length=20), nullable=True)
    )
    op.create_index(op.f('ix_users_platform_role'), 'users', ['platform_role'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_platform_role'), table_name='users')
    op.drop_column('users', 'platform_role')
