import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, insert
from platform_core.api import make_app
from platform_core.config import Settings
from platform_core.db import engine_for, users
from platform_core.security import new_id, now

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'http://localhost:9010'


@pytest.fixture
def environment(tmp_path):
    database_url = 'sqlite:///' + str(tmp_path / 'platform.sqlite')
    env = {**os.environ, 'DATABASE_URL': database_url}
    result = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    engine = engine_for(database_url)
    timestamp = now()
    with engine.begin() as conn:
        for open_id, user_id, role in [
            ('ou_alice', '11111111-1111-4111-8111-111111111111', 'employee'),
            ('ou_bob', '22222222-2222-4222-8222-222222222222', 'manager'),
            ('ou_disabled', '33333333-3333-4333-8333-333333333333', 'admin'),
            ('ou_admin', '44444444-4444-4444-8444-444444444444', 'admin'),
        ]:
            conn.execute(insert(users).values(id=user_id, tenant_id='test-team',
               feishu_open_id=open_id, display_name=open_id, role=role,
               status='disabled' if open_id == 'ou_disabled' else 'active',
               created_at=timestamp, updated_at=timestamp))
    settings = Settings(database_url=database_url, app_origin=ORIGIN, tenant_id='test-team',
        feishu_app_id='test-app', feishu_app_secret='test-secret', cookie_secure=False,
        session_ttl_seconds=3600, feishu_api_base='https://open.feishu.cn',
        module_service_keys={'coach': 'coach_secret_for_backend_only_0123456789',
                             'review': 'review_secret_for_backend_only_0123456789',
                             'daily': 'daily_secret_for_backend_only_0123456789'})
    return settings, engine


@pytest.fixture
def client(environment, monkeypatch):
    settings, engine = environment
    async def fake_verify(_settings, code):
        if code not in ('alice-code', 'bob-code', 'disabled-code', 'admin-code'):
            from platform_core.feishu import FeishuIdentityError
            raise FeishuIdentityError('invalid')
        return {'open_id': {'alice-code': 'ou_alice', 'bob-code': 'ou_bob', 'disabled-code': 'ou_disabled', 'admin-code': 'ou_admin'}[code], 'name': 'example'}
    monkeypatch.setattr('platform_core.api.resolve_feishu_user', fake_verify)
    with TestClient(make_app(settings=settings, engine=engine)) as c:
        yield c


def login(c, code='alice-code'):
    return c.post('/v1/auth/feishu/exchange', headers={'origin': ORIGIN}, json={'code': code})
