"""Add payment status and manual bill settlement fields to orders

Revision ID: 0016_order_settlement_and_payment_status
Revises: 0015_approval_workflow_schema
Create Date: 2026-10-25

RATIONALE
=========
Introduces explicit manual bill-settlement tracking on the orders table:
- payment_status: 'unpaid' (default) or 'paid'. Existing and new orders begin unpaid.
- payment_method: manually recorded tender method, e.g. 'cash' or 'upi'.
- settled_at: timestamp when payment was confirmed.
- settled_by_user_id: foreign key to users.id recording the staff member who confirmed collection.

DOWNGRADE BEHAVIOR
==================
Drops indexes and columns in reverse order.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0016_order_settlement_and_payment_status'
down_revision: Union[str, None] = '0015_approval_workflow_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add payment columns to orders table
    op.add_column(
        'orders',
        sa.Column('payment_status', sa.String(length=30), nullable=False, server_default='unpaid')
    )
    op.add_column(
        'orders',
        sa.Column('payment_method', sa.String(length=30), nullable=True)
    )
    op.add_column(
        'orders',
        sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'orders',
        sa.Column(
            'settled_by_user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True
        )
    )

    # 2. Create indexes
    op.create_index(op.f('ix_orders_payment_status'), 'orders', ['payment_status'], unique=False)
    op.create_index(op.f('ix_orders_settled_by_user_id'), 'orders', ['settled_by_user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_orders_settled_by_user_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_payment_status'), table_name='orders')
    op.drop_column('orders', 'settled_by_user_id')
    op.drop_column('orders', 'settled_at')
    op.drop_column('orders', 'payment_method')
    op.drop_column('orders', 'payment_status')
