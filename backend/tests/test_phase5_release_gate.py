"""Release-gate tests: outdated migrations must stop API startup."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from platform_core.api import make_app
from platform_core.db import EXPECTED_SCHEMA_REVISION, ensure_schema


def test_phase5_migration_version_matches_release(environment):
    settings, engine = environment
    assert EXPECTED_SCHEMA_REVISION == '0004_mobile_identity'
    ensure_schema(engine)
    with engine.begin() as conn:
        conn.execute(text("UPDATE alembic_version SET version_num = '0002_records_teams'"))
    with pytest.raises(RuntimeError, match='migration revision'):
        with TestClient(make_app(settings=settings, engine=engine)):
            pass


def test_phase5_missing_migration_table_fails_closed(tmp_path):
    from platform_core.db import engine_for
    engine = engine_for('sqlite:///' + str(tmp_path / 'blank.sqlite'))
    with pytest.raises(Exception):
        ensure_schema(engine)
