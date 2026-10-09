"""Add is_platform_admin column to users table

Revision ID: 0004_platform_admin_identity
Revises: 0003_r3_tables_and_orders
Create Date: 2026-10-10 03:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0004_platform_admin_identity'
down_revision: Union[str, None] = '0003_r3_tables_and_orders'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('is_platform_admin', sa.Boolean(), server_default='false', nullable=False)
    )


def downgrade() -> None:
    op.drop_column('users', 'is_platform_admin')
