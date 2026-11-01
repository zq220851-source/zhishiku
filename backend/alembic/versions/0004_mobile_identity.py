"""Add standalone app login identity without inventing a Feishu open_id."""
from alembic import op
import sqlalchemy as sa

revision = '0004_mobile_identity'
down_revision = '0003_legacy_evidence'
branch_labels = None
depends_on = None

def upgrade():
    # SQLite migrations use batch mode; PostgreSQL ALTERs in place.
    with op.batch_alter_table('platform_users') as batch:
        batch.alter_column('feishu_open_id', existing_type=sa.String(128), nullable=True)
    op.create_table('platform_mobile_credentials',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('platform_users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('login_name', sa.String(128), nullable=False),
        sa.Column('password_hash', sa.String(256), nullable=False),
        sa.Column('failed_attempts', sa.Integer, nullable=False, server_default='0'),
        sa.Column('locked_until', sa.BigInteger, nullable=False, server_default='0'))
    op.create_index('ix_mobile_login_name','platform_mobile_credentials',['tenant_id','login_name'],unique=True)

def downgrade():
    raise RuntimeError('Downgrade disabled; back up and restore explicitly')
