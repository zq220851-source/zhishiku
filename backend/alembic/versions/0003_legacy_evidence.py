"""Provenance for explicitly reviewed legacy *ownership metadata*, not business payloads.

Revision ID: 0003_legacy_evidence
Revises: 0002_records_teams
"""
from alembic import op
import sqlalchemy as sa

revision = '0003_legacy_evidence'
down_revision = '0002_records_teams'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('platform_import_batches',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('manifest_sha256', sa.String(64), nullable=False),
        sa.Column('approval_reference', sa.String(128), nullable=False),
        sa.Column('approved_by_user_id', sa.String(36), sa.ForeignKey('platform_users.id'), nullable=False),
        sa.Column('record_count', sa.Integer, nullable=False),
        sa.Column('created_at', sa.BigInteger, nullable=False),
    )
    op.create_index('ix_import_batch_manifest', 'platform_import_batches', ['tenant_id', 'manifest_sha256'], unique=True)
    op.create_table('platform_import_evidence',
        sa.Column('record_link_id', sa.String(36), sa.ForeignKey('platform_record_links.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('batch_id', sa.String(36), sa.ForeignKey('platform_import_batches.id'), nullable=False),
        sa.Column('evidence_ref', sa.String(128), nullable=False),
        sa.Column('imported_at', sa.BigInteger, nullable=False),
    )
    op.create_index('ix_import_evidence_batch', 'platform_import_evidence', ['batch_id'])


def downgrade():
    raise RuntimeError('Downgrade disabled: import provenance is immutable audit evidence')
