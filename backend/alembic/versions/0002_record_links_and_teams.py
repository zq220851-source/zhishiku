"""Phase 2: immutable business record owners + explicit team membership.

Revision ID: 0002_records_teams
Revises: 0001_platform_core
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_records_teams'
down_revision = '0001_platform_core'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('platform_record_links',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('owner_user_id', sa.String(36), sa.ForeignKey('platform_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_module', sa.String(24), nullable=False),
        sa.Column('object_kind', sa.String(32), nullable=False),
        sa.Column('external_ref', sa.String(128), nullable=False),
        sa.Column('created_at', sa.BigInteger, nullable=False),
    )
    op.create_index('ix_record_unique_source', 'platform_record_links',
        ['tenant_id', 'source_module', 'object_kind', 'external_ref'], unique=True)
    op.create_index('ix_record_owner', 'platform_record_links',
        ['tenant_id', 'owner_user_id', 'created_at'])
    op.create_table('platform_teams',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('created_at', sa.BigInteger, nullable=False),
    )
    op.create_index('ix_teams_tenant', 'platform_teams', ['tenant_id'])
    op.create_table('platform_team_members',
        sa.Column('team_id', sa.String(36), sa.ForeignKey('platform_teams.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('platform_users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('team_role', sa.String(16), nullable=False),
        sa.Column('created_at', sa.BigInteger, nullable=False),
    )
    op.create_index('ix_team_member_user', 'platform_team_members', ['user_id'])


def downgrade():
    raise RuntimeError('Downgrade disabled: preserve existing business ownership and teams')
