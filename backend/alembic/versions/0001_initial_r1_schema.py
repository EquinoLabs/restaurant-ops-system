"""Initial R1 schema

Revision ID: 0001_initial_r1_schema
Revises: 
Create Date: 2026-10-09 22:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001_initial_r1_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create businesses table
    op.create_table(
        'businesses',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. Create outlets table
    op.create_table(
        'outlets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('business_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('public_slug', sa.String(length=100), nullable=False),
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='Asia/Kolkata'),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='INR'),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_outlets_public_slug'), 'outlets', ['public_slug'], unique=True)

    # 3. Create menu_categories table
    op.create_table(
        'menu_categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('outlet_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['outlet_id'], ['outlets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_menu_categories_outlet_id'), 'menu_categories', ['outlet_id'], unique=False)

    # 4. Create menu_items table
    op.create_table(
        'menu_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('outlet_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['menu_categories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['outlet_id'], ['outlets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_menu_items_category_id'), 'menu_items', ['category_id'], unique=False)
    op.create_index(op.f('ix_menu_items_outlet_id'), 'menu_items', ['outlet_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_menu_items_outlet_id'), table_name='menu_items')
    op.drop_index(op.f('ix_menu_items_category_id'), table_name='menu_items')
    op.drop_table('menu_items')
    op.drop_index(op.f('ix_menu_categories_outlet_id'), table_name='menu_categories')
    op.drop_table('menu_categories')
    op.drop_index(op.f('ix_outlets_public_slug'), table_name='outlets')
    op.drop_table('outlets')
    op.drop_table('businesses')
