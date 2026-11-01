from .conftest import ORIGIN, login


def test_only_admin_may_provision(client):
    assert login(client).status_code == 200
    assert client.get('/v1/admin/users').status_code == 403
    candidate = {'feishu_open_id': 'ou_new_employee', 'display_name': 'New Member', 'role': 'admin'}
    assert client.post('/v1/admin/users', headers={'origin':ORIGIN}, json=candidate).status_code == 403
    assert login(client, 'admin-code').status_code == 200
    assert client.get('/v1/admin/users').status_code == 200
    response = client.post('/v1/admin/users', headers={'origin':ORIGIN}, json=candidate)
    assert response.status_code == 201
    assert response.json()['user']['role'] == 'admin'
    assert client.post('/v1/admin/users', headers={'origin':ORIGIN}, json=candidate).status_code == 409


def test_disabling_staff_revokes_effective_access(client):
    assert login(client, 'admin-code').status_code == 200
    me = client.get('/v1/auth/me').json()['user']
    assert client.patch('/v1/admin/users/' + me['id'], headers={'origin':ORIGIN},
                        json={'status': 'disabled'}).status_code == 403
    assert client.patch('/v1/admin/users/11111111-1111-4111-8111-111111111111', headers={'origin':ORIGIN},
                        json={'status':'disabled'}).status_code == 200
    assert login(client,'alice-code').status_code == 403


def test_other_tenant_unavailable(client):
    assert login(client, 'admin-code').status_code == 200
    assert client.patch('/v1/admin/users/no-such-user', headers={'origin':ORIGIN},
                        json={'role':'employee'}).status_code == 404
    assert client.post('/v1/admin/users', headers={'origin':ORIGIN},
                       json={'feishu_open_id':'ou_new', 'display_name':'Employee', 'role':'superadmin'}).status_code == 422
