from sqlalchemy import (
    MetaData, Table, Column, String, BigInteger, Integer, ForeignKey,
    Index, create_engine, text
)

# Update together with the newest Alembic migration revision.
EXPECTED_SCHEMA_REVISION = '0004_mobile_identity'

metadata = MetaData()

users = Table(
    'platform_users', metadata,
    Column('id', String(36), primary_key=True),
    Column('tenant_id', String(64), nullable=False),
    Column('feishu_open_id', String(128), nullable=True),
    Column('display_name', String(128), nullable=False),
    Column('role', String(24), nullable=False),
    Column('status', String(16), nullable=False),
    Column('created_at', BigInteger, nullable=False),
    Column('updated_at', BigInteger, nullable=False),
)
Index('ix_platform_tenant_feishu', users.c.tenant_id, users.c.feishu_open_id, unique=True)

sessions = Table(
    'platform_sessions', metadata,
    Column('token_hash', String(64), primary_key=True),
    Column('user_id', String(36), ForeignKey('platform_users.id', ondelete='CASCADE'), nullable=False),
    Column('created_at', BigInteger, nullable=False),
    Column('expires_at', BigInteger, nullable=False),
    Column('revoked_at', BigInteger, nullable=True),
)
Index('ix_sessions_user_id', sessions.c.user_id)
Index('ix_sessions_expires_at', sessions.c.expires_at)

states = Table(
    'platform_user_states', metadata,
    Column('user_id', String(36), ForeignKey('platform_users.id', ondelete='CASCADE'), primary_key=True),
    Column('module', String(24), primary_key=True),
    Column('state_key', String(96), primary_key=True),
    Column('json_value', String(65536), nullable=False),
    Column('revision', Integer, nullable=False),
    Column('updated_at', BigInteger, nullable=False),
)

audit = Table(
    'platform_audit_events', metadata,
    Column('id', String(36), primary_key=True),
    Column('actor_user_id', String(36), nullable=True),
    Column('action', String(60), nullable=False),
    Column('target_id', String(128), nullable=True),
    Column('created_at', BigInteger, nullable=False),
)
Index('ix_audit_time', audit.c.created_at)


def engine_for(url: str):
    return create_engine(url, pool_pre_ping=True)


def ensure_schema(engine):
    """Fail closed if required tables are absent OR DB migrations are outdated.

    Schema migration is a separate deployment step; the API never mutates schema.
    """
    with engine.connect() as connection:
        current = connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
        if current != [EXPECTED_SCHEMA_REVISION]:
            raise RuntimeError('Database migration revision does not match this platform release')
        for table in ('alembic_version', 'platform_users', 'platform_sessions', 'platform_user_states', 'platform_audit_events', 'platform_record_links', 'platform_teams', 'platform_team_members', 'platform_import_batches', 'platform_import_evidence', 'platform_mobile_credentials'):
            connection.execute(text(f'SELECT 1 FROM {table} LIMIT 1'))

# Phase 2: links to records remain metadata-only. Business payloads stay in their own databases.
record_links = Table(
    'platform_record_links', metadata,
    Column('id', String(36), primary_key=True),
    Column('tenant_id', String(64), nullable=False),
    Column('owner_user_id', String(36), ForeignKey('platform_users.id', ondelete='CASCADE'), nullable=False),
    Column('source_module', String(24), nullable=False),
    Column('object_kind', String(32), nullable=False),
    Column('external_ref', String(128), nullable=False),
    Column('created_at', BigInteger, nullable=False),
)
Index('ix_record_unique_source', record_links.c.tenant_id, record_links.c.source_module,
      record_links.c.object_kind, record_links.c.external_ref, unique=True)
Index('ix_record_owner', record_links.c.tenant_id, record_links.c.owner_user_id,
      record_links.c.created_at)

teams = Table(
    'platform_teams', metadata,
    Column('id', String(36), primary_key=True),
    Column('tenant_id', String(64), nullable=False),
    Column('name', String(128), nullable=False),
    Column('created_at', BigInteger, nullable=False),
)
Index('ix_teams_tenant', teams.c.tenant_id)

team_members = Table(
    'platform_team_members', metadata,
    Column('team_id', String(36), ForeignKey('platform_teams.id', ondelete='CASCADE'), primary_key=True),
    Column('user_id', String(36), ForeignKey('platform_users.id', ondelete='CASCADE'), primary_key=True),
    Column('team_role', String(16), nullable=False),
    Column('created_at', BigInteger, nullable=False),
)
Index('ix_team_member_user', team_members.c.user_id)


# Phase 3: only provenance of human-approved ownership mappings; no medical payloads.
import_batches = Table(
    'platform_import_batches', metadata,
    Column('id', String(36), primary_key=True),
    Column('tenant_id', String(64), nullable=False),
    Column('manifest_sha256', String(64), nullable=False),
    Column('approval_reference', String(128), nullable=False),
    Column('approved_by_user_id', String(36), ForeignKey('platform_users.id'), nullable=False),
    Column('record_count', Integer, nullable=False),
    Column('created_at', BigInteger, nullable=False),
)
Index('ix_import_batch_manifest', import_batches.c.tenant_id, import_batches.c.manifest_sha256, unique=True)

import_evidence = Table(
    'platform_import_evidence', metadata,
    Column('record_link_id', String(36), ForeignKey('platform_record_links.id', ondelete='CASCADE'), primary_key=True),
    Column('batch_id', String(36), ForeignKey('platform_import_batches.id'), nullable=False),
    Column('evidence_ref', String(128), nullable=False),
    Column('imported_at', BigInteger, nullable=False),
)
Index('ix_import_evidence_batch', import_evidence.c.batch_id)


# Phase 6: standalone mobile credentials, separate from Feishu identifiers.
mobile_credentials = Table(
    'platform_mobile_credentials', metadata,
    Column('user_id', String(36), ForeignKey('platform_users.id', ondelete='CASCADE'), primary_key=True),
    Column('tenant_id', String(64), nullable=False),
    Column('login_name', String(128), nullable=False),
    Column('password_hash', String(256), nullable=False),
    Column('failed_attempts', Integer, nullable=False),
    Column('locked_until', BigInteger, nullable=False),
)
Index('ix_mobile_login_name', mobile_credentials.c.tenant_id, mobile_credentials.c.login_name, unique=True)
