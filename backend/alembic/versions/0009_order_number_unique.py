"""Add unique constraint to orders order_number per outlet

Revision ID: 0009_order_number_unique
Revises: 0008_order_idempotency_keys
Create Date: 2026-10-11 00:16:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0009_order_number_unique'
down_revision: Union[str, None] = '0008_order_idempotency_keys'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_outlet_order_number',
        'orders',
        ['outlet_id', 'order_number']
    )


def downgrade() -> None:
    op.drop_constraint('uq_outlet_order_number', 'orders', type_='unique')
