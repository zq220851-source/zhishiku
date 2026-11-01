from sqlalchemy import select
from platform_core.db import sessions
from .conftest import ORIGIN, login


def test_health_and_login_required(client):
    assert client.get('/healthz').status_code == 200
    assert client.get('/readyz').status_code == 200
    assert client.get('/v1/auth/me').status_code == 401
    assert client.get('/v1/me/state/daily/likes').status_code == 401


def test_code_is_verified_and_account_allowlisted(client):
    invalid = client.post('/v1/auth/feishu/exchange', headers={'origin': ORIGIN}, json={'code':'wrong123'})
    assert invalid.status_code == 401
    assert login(client, 'disabled-code').status_code == 403
    response = login(client)
    assert response.status_code == 200
    assert response.json()['user']['role'] == 'employee'
    assert 'medrep_sid' in client.cookies
    assert client.get('/v1/auth/me').json()['user']['role'] == 'employee'


def test_cookie_http_only_and_token_is_hashed(client, environment):
    result = login(client)
    assert result.status_code == 200
    cookie = result.headers['set-cookie']
    assert 'httponly' in cookie.lower()
    assert 'samesite=lax' in cookie.lower()
    raw = client.cookies['medrep_sid']
    _, engine = environment
    with engine.connect() as conn:
        stored = conn.execute(select(sessions.c.token_hash)).scalar_one()
    assert raw != stored
    assert len(stored) == 64


def test_cross_site_write_rejected(client):
    assert login(client).status_code == 200
    payload = {'value': {'read': ['article-1']}, 'expected_revision': 0}
    assert client.put('/v1/me/state/daily/read', json=payload).status_code == 403
    assert client.put('/v1/me/state/daily/read', headers={'origin':'https://evil.example'}, json=payload).status_code == 403
    assert client.put('/v1/me/state/daily/read', headers={'origin':ORIGIN}, json=payload).status_code == 200


def test_optimistic_versioning_and_ownership(client):
    login(client)
    path = '/v1/me/state/daily/read'
    header = {'origin': ORIGIN}
    assert client.put(path, headers=header, json={'value': {'saved': ['a']}, 'expected_revision': 0}).json()['revision'] == 1
    assert client.put(path, headers=header, json={'value': {'saved': ['z']}, 'expected_revision': 0}).status_code == 409
    assert client.put(path, headers=header, json={'value': {'saved': ['b']}, 'expected_revision': 1}).json()['revision'] == 2
    assert client.get(path).json()['value'] == {'saved': ['b']}
    login(client, 'bob-code')
    assert client.get(path).status_code == 404  # Bob cannot read Alice's data
    assert client.put(path, headers=header, json={'value':{'saved': ['bob']}, 'expected_revision':0}).status_code == 200
    assert client.get(path).json()['value'] == {'saved': ['bob']}


def test_logout_revokes_session(client):
    login(client)
    assert client.get('/v1/auth/me').status_code == 200
    assert client.post('/v1/auth/logout', headers={'origin': ORIGIN}).status_code == 204
    assert client.get('/v1/auth/me').status_code == 401


def test_invalid_state_namespace_and_size(client):
    login(client)
    header = {'origin': ORIGIN}
    assert client.put('/v1/me/state/unsupported/x', headers=header,
        json={'value':{}, 'expected_revision':0}).status_code == 404
    assert client.put('/v1/me/state/daily/x', headers=header,
        json={'value':'z'*70000, 'expected_revision':0}).status_code == 413
