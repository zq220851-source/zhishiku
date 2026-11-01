"""Deterministic tests, no external account or public server required."""
from pathlib import Path
from sqlalchemy import insert, select
import pytest
import yaml
from platform_core.config import load_settings
from platform_core.db import sessions
from scripts.cleanup_sessions import prune_sessions
from scripts.preflight import check_environment
from scripts.verify_staging import assess, validate_base

ROOT = Path(__file__).resolve().parents[1]


def test_staging_compose_has_public_proxy_only_for_caddy():
    base = yaml.safe_load((ROOT / 'compose.yaml').read_text())
    extra = yaml.safe_load((ROOT / 'compose.staging.yaml').read_text())
    assert base['services']['db'].get('ports') is None
    assert base['services']['platform']['ports'] == ['127.0.0.1:18080:8080']
    assert extra['services']['caddy']['ports'] == ['80:80', '443:443']
    caddy = (ROOT / 'deploy/Caddyfile.staging').read_text()
    assert 'respond @internal 404' in caddy
    assert 'respond @ready 404' in caddy
    assert '/v1/admin/*' in caddy
    assert '/v1/teams/*' in caddy
    assert 'reverse_proxy platform:8080' in caddy
    assert 'Strict-Transport-Security' in caddy


def test_preflight_flags_unset_domain_or_example_secrets():
    env = {'APP_PUBLIC_ORIGIN': 'https://team.example.cn',
        'APP_DOMAIN': 'coach-staging.example.com',
        'DATABASE_URL': 'postgresql+psycopg://u:abc@db:5432/medrep',
        'COOKIE_SECURE': 'true', 'PLATFORM_TENANT_ID': 'company',
        'FEISHU_APP_ID': 'cli_demo', 'FEISHU_APP_SECRET': 'f' * 40,
        'POSTGRES_PASSWORD': 'abc'}
    checks = {name: passed for name, passed, _ in check_environment(env)}
    assert checks['Caddy hostname matches HTTPS origin'] is False
    assert checks['Strong DB password (>= 24 chars)'] is False
    env['APP_DOMAIN'] = 'team.example.cn'
    password = 'Axyz123._-' * 4
    env['POSTGRES_PASSWORD'] = password
    env['DATABASE_URL'] = f'postgresql+psycopg://u:{password}@db:5432/medrep'
    checks = {name: passed for name, passed, _ in check_environment(env)}
    assert all(checks.values()), checks


def test_config_fail_closed_for_public_sqlite(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///./tmp.sqlite')
    monkeypatch.setenv('APP_PUBLIC_ORIGIN', 'https://team.example.cn')
    monkeypatch.setenv('PLATFORM_TENANT_ID', 'company')
    with pytest.raises(RuntimeError, match='PostgreSQL'):
        load_settings()


def test_config_rejects_origins_and_partial_feishu(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://u:p@db:5432/d')
    monkeypatch.setenv('PLATFORM_TENANT_ID', 'company')
    monkeypatch.setenv('APP_PUBLIC_ORIGIN', 'https://team.example.cn/path')
    with pytest.raises(RuntimeError, match='strict origin'):
        load_settings()
    monkeypatch.setenv('APP_PUBLIC_ORIGIN', 'https://team.example.cn')
    monkeypatch.setenv('FEISHU_APP_ID', 'cli_test')
    monkeypatch.delenv('FEISHU_APP_SECRET', raising=False)
    with pytest.raises(RuntimeError, match='provided together'):
        load_settings()


def test_smoke_expected_boundaries_and_fail_closed():
    def good(path):
        return ({'/healthz': 200, '/v1/auth/me': 401,
                 '/v1/me/records': 401,
                 '/v1/teams/11111111-1111-4111-8111-111111111111/members': 401,
                 '/readyz': 404}.get(path, 404),
                {'cache-control': 'no-store'})
    assert assess(good)
    assert not assess(lambda path: (200, {}))
    assert validate_base('https://coach.example.cn/') == 'https://coach.example.cn'
    with pytest.raises(ValueError):
        validate_base('http://coach.example.cn')


def test_cleanup_never_deletes_active_session(environment):
    _, engine = environment
    with engine.begin() as conn:
        conn.execute(insert(sessions), [
          {'token_hash': 'a' * 64, 'user_id': '11111111-1111-4111-8111-111111111111',
           'created_at': 1, 'expires_at': 10, 'revoked_at': None},
          {'token_hash': 'b' * 64, 'user_id': '11111111-1111-4111-8111-111111111111',
           'created_at': 1, 'expires_at': 20000000, 'revoked_at': 20},
          {'token_hash': 'c' * 64, 'user_id': '11111111-1111-4111-8111-111111111111',
           'created_at': 1000, 'expires_at': 20000000, 'revoked_at': None},
        ])
    assert prune_sessions(engine, apply=False, retention_days=1, timestamp=100000) == 2
    with engine.connect() as conn:
        assert len(conn.execute(select(sessions)).all()) == 3
    assert prune_sessions(engine, apply=True, retention_days=1, timestamp=100000) == 2
    with engine.connect() as conn:
        assert [s.token_hash for s in conn.execute(select(sessions)).all()] == ['c' * 64]


def test_private_env_generator_never_overwrites_and_uses_distinct_secrets(tmp_path):
    from scripts.init_staging_env import create_env
    out = tmp_path / '.env'
    create_env(out, domain='coach.acme.internal.cn', tenant_id='org-test')
    content = out.read_text()
    assert 'DATABASE_URL=postgresql+psycopg://' in content
    assert 'CHANGE_ME' not in content
    assert 'FEISHU_APP_SECRET=\n' in content
    assert (out.stat().st_mode & 0o777) == 0o600
    with pytest.raises(FileExistsError):
        create_env(out, domain='coach.acme.internal.cn', tenant_id='org-test')


def test_env_generator_rejects_placeholder(tmp_path):
    from scripts.init_staging_env import create_env
    with pytest.raises(ValueError):
        create_env(tmp_path/'.env', domain='coach-staging.example.com', tenant_id='org-test')


def test_preflight_malformed_origin_fails_without_exception():
    assert not {name: ok for name, ok, _ in
        check_environment({'APP_PUBLIC_ORIGIN': 'https://bad.example.com:not-a-port'})}['HTTPS app origin']
