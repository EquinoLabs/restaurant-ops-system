"""Create order_idempotency_keys table

Revision ID: 0008_order_idempotency_keys
Revises: 0007_audit_log_biz_id_nullable
Create Date: 2026-10-11 00:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0008_order_idempotency_keys'
down_revision: Union[str, None] = '0007_audit_log_biz_id_nullable'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'order_idempotency_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('outlet_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('idempotency_key', sa.String(length=100), nullable=False),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['outlet_id'], ['outlets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('outlet_id', 'idempotency_key', name='uq_outlet_idempotency_key')
    )
    op.create_index(op.f('ix_order_idempotency_keys_outlet_id'), 'order_idempotency_keys', ['outlet_id'], unique=False)
    op.create_index(op.f('ix_order_idempotency_keys_idempotency_key'), 'order_idempotency_keys', ['idempotency_key'], unique=False)
    op.create_index(op.f('ix_order_idempotency_keys_order_id'), 'order_idempotency_keys', ['order_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_order_idempotency_keys_order_id'), table_name='order_idempotency_keys')
    op.drop_index(op.f('ix_order_idempotency_keys_idempotency_key'), table_name='order_idempotency_keys')
    op.drop_index(op.f('ix_order_idempotency_keys_outlet_id'), table_name='order_idempotency_keys')
    op.drop_table('order_idempotency_keys')
