"""Optional REAL PostgreSQL integration verification using a dedicated disposable CI DB.

CI: export TEST_POSTGRES_URL=postgresql+psycopg://postgres:...@127.0.0.1:5432/medrep_ci
Never point this test at company data or production infrastructure.
"""
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert

from platform_core.api import make_app
from platform_core.config import Settings
from platform_core.db import engine_for, users, ensure_schema
from platform_core.security import now

ROOT = Path(__file__).resolve().parents[1]


def test_dedicated_postgres_migrations_and_api(monkeypatch):
    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('No disposable PostgreSQL test database configured')
    # Require the exact dedicated database and explicit opt-in to avoid touching real company data.
    from sqlalchemy.engine import make_url
    parsed = make_url(url)
    if (parsed.drivername != 'postgresql+psycopg' or parsed.database != 'medrep_ci' or
        os.environ.get('MEDREP_ALLOW_TEST_DATABASE') != 'YES'):
        pytest.fail('Refusing to write to anything except explicitly approved medrep_ci test DB')

    migrate = subprocess.run(['alembic', 'upgrade', 'head'], cwd=ROOT,
        env={**os.environ, 'DATABASE_URL': url}, capture_output=True, text=True, timeout=60)
    assert migrate.returncode == 0, migrate.stderr[-2000:]
    engine = engine_for(url)
    ensure_schema(engine)
    unique = uuid4().hex[:16]
    alice_id, bob_id = str(uuid4()), str(uuid4())
    stamp = now()
    with engine.begin() as conn:
        conn.execute(insert(users), [
            dict(id=alice_id, tenant_id='ci-staging', feishu_open_id='ou_ci_a_'+unique,
                 display_name='CI Alice', role='employee', status='active', created_at=stamp, updated_at=stamp),
            dict(id=bob_id, tenant_id='ci-staging', feishu_open_id='ou_ci_b_'+unique,
                 display_name='CI Bob', role='manager', status='active', created_at=stamp, updated_at=stamp),
        ])

    async def fake_feishu(_settings, code):
        if code not in ('ci-a', 'ci-b'):
            raise ValueError('unknown mock identity')
        return {'open_id': 'ou_ci_'+('a_' if code == 'ci-a' else 'b_')+unique,
                'name': 'synthetic CI staff'}

    monkeypatch.setattr('platform_core.api.resolve_feishu_user', fake_feishu)
    settings = Settings(database_url=url, app_origin='http://localhost:9010', tenant_id='ci-staging',
        feishu_app_id='ci-test', feishu_app_secret='ci-test-only', cookie_secure=False,
        session_ttl_seconds=3600, feishu_api_base='https://open.feishu.cn',
        module_service_keys={'coach':'ci_only_long_service_key_0123456789_abc'})
    origin = {'origin':settings.app_origin}
    # Disposable CI DB only: do not reuse this database for manual or actual staff records.
    with TestClient(make_app(settings=settings, engine=engine)) as client:
        assert client.get('/v1/auth/me').status_code == 401
        assert client.post('/v1/auth/feishu/exchange', headers=origin,
                           json={'code':'ci-a'}).status_code == 200
        assert client.put('/v1/me/state/ui/theme', headers=origin,
                          json={'expected_revision':0, 'value':'dark'}).status_code == 200
        internal_headers = {'x-medrep-module':'coach',
                            'x-medrep-service-key':'ci_only_long_service_key_0123456789_abc'}
        result = client.post('/v1/internal/records', headers=internal_headers,
            json={'owner_user_id':alice_id, 'object_kind':'session',
                  'external_ref':'ci_'+unique})
        assert result.status_code == 201, result.text
        assert len(client.get('/v1/me/records').json()['items']) == 1
        assert client.post('/v1/auth/feishu/exchange', headers=origin,
                           json={'code':'ci-b'}).status_code == 200
        assert client.get('/v1/me/records').json()['items'] == []
        assert client.get('/v1/me/state/ui/theme').status_code == 404
        assert client.post('/v1/auth/logout', headers=origin).status_code == 204
        assert client.get('/v1/auth/me').status_code == 401
