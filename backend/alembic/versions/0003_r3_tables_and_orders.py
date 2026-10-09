"""R3 dining tables and orders schema

Revision ID: 0003_r3_tables_and_orders
Revises: 0002_r2_staff_and_audit
Create Date: 2026-10-10 03:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0003_r3_tables_and_orders'
down_revision: Union[str, None] = '0002_r2_staff_and_audit'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create tables table
    op.create_table(
        'tables',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('outlet_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('table_number', sa.String(length=30), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='available'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['outlet_id'], ['outlets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('outlet_id', 'table_number', name='uq_outlet_table_number')
    )
    op.create_index(op.f('ix_tables_outlet_id'), 'tables', ['outlet_id'], unique=False)

    # 2. Create orders table
    op.create_table(
        'orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('outlet_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('table_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('waiter_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('order_number', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='pending'),
        sa.Column('order_type', sa.String(length=30), nullable=False, server_default='dine_in'),
        sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['outlet_id'], ['outlets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['table_id'], ['tables.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['waiter_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_orders_order_number'), 'orders', ['order_number'], unique=False)
    op.create_index(op.f('ix_orders_outlet_id'), 'orders', ['outlet_id'], unique=False)
    op.create_index(op.f('ix_orders_status'), 'orders', ['status'], unique=False)
    op.create_index(op.f('ix_orders_table_id'), 'orders', ['table_id'], unique=False)
    op.create_index(op.f('ix_orders_waiter_user_id'), 'orders', ['waiter_user_id'], unique=False)

    # 3. Create order_items table
    op.create_table(
        'order_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('item_name', sa.String(length=200), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('special_instructions', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_items_menu_item_id'), 'order_items', ['menu_item_id'], unique=False)
    op.create_index(op.f('ix_order_items_order_id'), 'order_items', ['order_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_order_items_order_id'), table_name='order_items')
    op.drop_index(op.f('ix_order_items_menu_item_id'), table_name='order_items')
    op.drop_table('order_items')

    op.drop_index(op.f('ix_orders_waiter_user_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_table_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_status'), table_name='orders')
    op.drop_index(op.f('ix_orders_outlet_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_order_number'), table_name='orders')
    op.drop_table('orders')

    op.drop_index(op.f('ix_tables_outlet_id'), table_name='tables')
    op.drop_table('tables')
