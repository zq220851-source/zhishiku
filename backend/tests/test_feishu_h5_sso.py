"""No real Feishu traffic; checks server-only exchange and preprovisioned employee isolation."""
from platform_core import feishu


def test_feishu_code_only_login_to_existing_employee(client, monkeypatch):
    async def verify(_settings, code):
        assert code == 'alice-one-time-code'
        return {'open_id':'ou_alice','name':'Alice'}
    monkeypatch.setattr(feishu, 'resolve_feishu_user', verify)
    response = client.post('/v1/mobile/auth/feishu', json={'code':'alice-one-time-code'})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['user']['role'] == 'employee'
    assert data['access_token'].startswith('mr_m_')
    header = {'authorization': 'Bearer ' + data['access_token']}
    assert client.get('/v1/mobile/auth/me', headers=header).status_code == 200
    assert client.post('/v1/mobile/auth/logout', headers=header).status_code == 204
    assert client.get('/v1/mobile/auth/me', headers=header).status_code == 401


def test_feishu_disabled_or_unknown_user_never_self_provisions(client, monkeypatch):
    async def verify(_settings, code):
        return {'open_id':'ou_disabled' if code == 'disabled-code' else 'ou_some_unregistered_user', 'name':'nobody'}
    monkeypatch.setattr(feishu, 'resolve_feishu_user', verify)
    for value in ('disabled-code','unknown-code'):
        assert client.post('/v1/mobile/auth/feishu', json={'code': value}).status_code == 403


def test_feishu_code_validation_and_exchange_failure(client, monkeypatch):
    assert client.post('/v1/mobile/auth/feishu', json={'code':'x'}).status_code == 422
    async def invalid(_settings,_code):
        raise feishu.FeishuIdentityError('bad code')
    monkeypatch.setattr(feishu, 'resolve_feishu_user', invalid)
    assert client.post('/v1/mobile/auth/feishu', json={'code':'invalid-one-time-code'}).status_code == 401
