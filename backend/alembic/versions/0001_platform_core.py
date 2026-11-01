"""Initial platform users, sessions, user state and metadata-only audit events.

Revision ID: 0001_platform_core
Revises:
Create Date: 2026-11-01
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_platform_core'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('platform_users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('feishu_open_id', sa.String(128), nullable=False),
        sa.Column('display_name', sa.String(128), nullable=False),
        sa.Column('role', sa.String(24), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('created_at', sa.BigInteger, nullable=False),
        sa.Column('updated_at', sa.BigInteger, nullable=False),
    )
    op.create_index('ix_platform_tenant_feishu', 'platform_users', ['tenant_id', 'feishu_open_id'], unique=True)
    op.create_table('platform_sessions',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('platform_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.BigInteger, nullable=False),
        sa.Column('expires_at', sa.BigInteger, nullable=False),
        sa.Column('revoked_at', sa.BigInteger, nullable=True),
    )
    op.create_index('ix_sessions_user_id', 'platform_sessions', ['user_id'])
    op.create_index('ix_sessions_expires_at', 'platform_sessions', ['expires_at'])
    op.create_table('platform_user_states',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('platform_users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('module', sa.String(24), primary_key=True),
        sa.Column('state_key', sa.String(96), primary_key=True),
        sa.Column('json_value', sa.String(65536), nullable=False),
        sa.Column('revision', sa.Integer, nullable=False),
        sa.Column('updated_at', sa.BigInteger, nullable=False),
    )
    op.create_table('platform_audit_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('actor_user_id', sa.String(36), nullable=True),
        sa.Column('action', sa.String(60), nullable=False),
        sa.Column('target_id', sa.String(128), nullable=True),
        sa.Column('created_at', sa.BigInteger, nullable=False),
    )
    op.create_index('ix_audit_time', 'platform_audit_events', ['created_at'])


def downgrade():
    # Never downgrade production data without an independently verified backup.
    raise RuntimeError('Downgrade is intentionally disabled to prevent data loss')
