import json

import httpx
import pytest
from platform_core.config import Settings
from platform_core.feishu import resolve_feishu_user, FeishuIdentityError


@pytest.mark.asyncio
async def test_feishu_three_step_exchange(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        if request.url.path == '/open-apis/auth/v3/app_access_token/internal':
            sent = json.loads(request.content)
            assert sent == {'app_id': 'cli-test', 'app_secret': 'secret'}
            return httpx.Response(200, json={'code': 0, 'msg': 'ok', 'app_access_token': 'app-short-lived', 'expire': 7200})
        if request.url.path == '/open-apis/authen/v1/access_token':
            assert request.headers['authorization'] == 'Bearer app-short-lived'
            assert json.loads(request.content)['code'] == 'auth-code'
            return httpx.Response(200, json={'code': 0, 'data': {'access_token': 'user-short-lived'}})
        if request.url.path == '/open-apis/authen/v1/user_info':
            assert request.headers['authorization'] == 'Bearer user-short-lived'
            return httpx.Response(200, json={'code': 0, 'data': {'open_id': 'ou_123456', 'name': 'Test User'}})
        return httpx.Response(404)
    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=transport, **kwargs))
    settings = Settings('sqlite://', 'http://localhost:9010', 'tenant', 'cli-test', 'secret', False, 3600, 'https://open.feishu.cn')
    result = await resolve_feishu_user(settings, 'auth-code')
    assert result == {'open_id': 'ou_123456', 'name': 'Test User'}
    assert len(requests) == 3


@pytest.mark.asyncio
async def test_feishu_provider_error_is_not_revealed(monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'code': 1200, 'msg': 'credential invalid'}))
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=transport, **kwargs))
    settings = Settings('sqlite://', 'http://localhost:9010', 'tenant', 'cli-test', 'secret', False, 3600, 'https://open.feishu.cn')
    with pytest.raises(FeishuIdentityError, match='did not accept'):
        await resolve_feishu_user(settings, 'auth-code')
