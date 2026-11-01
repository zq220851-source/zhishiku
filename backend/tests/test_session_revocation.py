from sqlalchemy import select
from platform_core.db import sessions
from .conftest import login, ORIGIN


def test_logout_all_revokes_all_sessions(client, environment):
    login(client)
    token_first = client.cookies['medrep_sid']
    login(client)
    token_second = client.cookies['medrep_sid']
    assert token_first != token_second
    assert client.post('/v1/auth/logout-all', headers={'origin': ORIGIN}).status_code == 204
    for token in [token_first, token_second]:
        client.cookies.set('medrep_sid', token)
        assert client.get('/v1/auth/me').status_code == 401


def test_admin_change_revokes_target_sessions(client):
    login(client,'alice-code')
    alice_cookie = client.cookies['medrep_sid']
    login(client,'admin-code')
    admin_cookie = client.cookies['medrep_sid']
    res = client.patch('/v1/admin/users/11111111-1111-4111-8111-111111111111',
                       headers={'origin': ORIGIN}, json={'role': 'manager'})
    assert res.status_code == 200
    client.cookies.set('medrep_sid', alice_cookie)
    assert client.get('/v1/auth/me').status_code == 401
    client.cookies.set('medrep_sid', admin_cookie)
    assert client.get('/v1/auth/me').status_code == 200


def test_private_api_no_store(client):
    response = client.get('/v1/auth/me')
    assert response.headers['cache-control'] == 'no-store'
    response = login(client)
    assert response.headers['cache-control'] == 'no-store'
    assert client.get('/v1/me/teams').headers['cache-control'] == 'no-store'
