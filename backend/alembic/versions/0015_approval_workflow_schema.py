"""Create approval requests and clarifications tables

Revision ID: 0015_approval_workflow_schema
Revises: 0014_add_missing_tenant_indexes
Create Date: 2026-10-21

RATIONALE
=========
Introduces the core approval-request workflow tables for ROMS:
- approval_requests: stores approval workflow entities, status transitions,
  execution outcomes, temporal expiry (14 days), optimistic locking (version),
  retry counters, and payload snapshots.
- approval_clarifications: stores immutable clarification questions, responses,
  and notes exchanged during review without mutating the submitted payload snapshot.

TENANT DELETION POLICY:
business_id is nullable with ON DELETE SET NULL to ensure business deletion
never destroys immutable platform approval and compliance audit history.

DOWNGRADE BEHAVIOR
==================
Drops approval_clarifications and approval_requests tables cleanly in reverse
dependency order.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0015_approval_workflow_schema'
down_revision: Union[str, None] = '0014_add_missing_tenant_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create approval_requests table
    op.create_table(
        'approval_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('business_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('businesses.id', ondelete='SET NULL'), nullable=True),
        sa.Column('outlet_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('outlets.id', ondelete='SET NULL'), nullable=True),
        sa.Column('requester_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('approver_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('request_type', sa.String(length=100), nullable=False),
        sa.Column('target_entity_type', sa.String(length=100), nullable=False),
        sa.Column('target_entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='pending'),
        sa.Column('execution_status', sa.String(length=30), nullable=False, server_default='not_started'),
        sa.Column('payload_snapshot', sa.JSON(), nullable=False),
        sa.Column('previous_state_snapshot', sa.JSON(), nullable=True),
        sa.Column('justification', sa.Text(), nullable=True),
        sa.Column('decision_reason', sa.Text(), nullable=True),
        sa.Column('execution_error', sa.Text(), nullable=True),
        sa.Column('execution_details_json', sa.JSON(), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('parent_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('approval_requests.id', ondelete='SET NULL'), nullable=True),
    )

    # Indexes on approval_requests
    op.create_index('ix_approval_requests_status', 'approval_requests', ['status'])
    op.create_index('ix_approval_requests_request_type', 'approval_requests', ['request_type'])
    op.create_index('ix_approval_requests_requester_user_id', 'approval_requests', ['requester_user_id'])
    op.create_index('ix_approval_requests_approver_user_id', 'approval_requests', ['approver_user_id'])
    op.create_index('ix_approval_requests_business_id', 'approval_requests', ['business_id'])
    op.create_index('ix_approval_requests_target_entity_id', 'approval_requests', ['target_entity_id'])
    op.create_index('ix_approval_requests_expires_at', 'approval_requests', ['expires_at'])
    op.create_index('ix_approval_requests_parent_request_id', 'approval_requests', ['parent_request_id'])
    op.create_index(
        'ix_approval_requests_idempotency_key',
        'approval_requests',
        ['idempotency_key'],
        unique=True,
        postgresql_where=sa.text('idempotency_key IS NOT NULL'),
        sqlite_where=sa.text('idempotency_key IS NOT NULL'),
    )

    # 2. Create approval_clarifications table
    op.create_table(
        'approval_clarifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('approval_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('approval_requests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('author_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('clarification_type', sa.String(length=30), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
    )

    op.create_index('ix_approval_clarifications_request_id', 'approval_clarifications', ['approval_request_id'])
    op.create_index('ix_approval_clarifications_author_id', 'approval_clarifications', ['author_user_id'])


def downgrade() -> None:
    op.drop_table('approval_clarifications')
    op.drop_table('approval_requests')
