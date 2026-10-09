"""Add branding columns to outlets table

Revision ID: 0006_outlet_branding
Revises: 0005_business_subscriptions
Create Date: 2026-10-10 04:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0006_outlet_branding'
down_revision: Union[str, None] = '0005_business_subscriptions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'outlets',
        sa.Column('logo_url', sa.String(length=500), nullable=True)
    )
    op.add_column(
        'outlets',
        sa.Column('cover_image_url', sa.String(length=500), nullable=True)
    )
    op.add_column(
        'outlets',
        sa.Column('primary_color', sa.String(length=20), nullable=True)
    )
    op.add_column(
        'outlets',
        sa.Column('accent_color', sa.String(length=20), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('outlets', 'accent_color')
    op.drop_column('outlets', 'primary_color')
    op.drop_column('outlets', 'cover_image_url')
    op.drop_column('outlets', 'logo_url')
