"""Phase 8 digest bridge tests: live-only, no cookies, safe presentation."""
import os
import pytest
from fastapi import HTTPException
from platform_core.digest_bridge import daily_origin, present_digest, fetch_daily
from scripts.provision_mobile_user import provision


def staff_headers(client, environment):
    settings, engine = environment
    provision(engine, settings.tenant_id, 'daily_user', '日报测试员工', 'employee', 'SafeDailyPass!2026')
    login = client.post('/v1/mobile/auth/login', json={'username': 'daily_user', 'password': 'SafeDailyPass!2026'})
    assert login.status_code == 200
    return {'Authorization': 'Bearer ' + login.json()['access_token']}


def live_payload():
    return {'mode': 'live', 'status': 'partial', 'date': '2026-11-01',
            'generatedAt': '2026-11-01T08:00:00Z',
            'profile': {'name':'not-for-client'},
            'industry': [
                {'id': 'news1','title':'真实来源 · 医保政策动态','source':'官方公开来源',
                 'url':'https://example.org/source','publishedAt':'2026-11-01',
                 'kind':'政策','summary':'此为测试数据（合成），仅用于接口测试',
                 'limitations':'不代表具体药品获批','reviewStatus':'not_reviewed',
                 'abstract':'HIDDEN PRIVATE FIELD','evidence':['should not leak']},
                {'id':'bad1','title':'诱导攻击内容','url':'javascript:alert(1)'},
                {'id':'bad2','title':'内网访问','url':'https://127.0.0.1:443/secret'},
            ], 'learning':[{'secret':'private'}]}


def test_requires_login_and_explicit_origin(client, environment, monkeypatch):
    monkeypatch.delenv('MEDREP_DAILY_READONLY_ORIGIN', raising=False)
    assert client.get('/v1/mobile/daily/industry').status_code == 401
    headers = staff_headers(client, environment)
    assert client.get('/v1/mobile/daily/industry', headers=headers).status_code == 503


def test_rejects_unsafe_upstream_origin(monkeypatch):
    for origin in [
        'http://example.org', 'http://169.254.169.254:8787',
        'https://127.0.0.1:443', 'https://metadata.internal',
        'https://evil@daily.example.com', 'https://daily.example.com/secret',
        'https://daily.example.com?mode=sample', 'https://daily.example.com:8443',
        'file:///etc/passwd', 'http://localhost:8787',
    ]:
        monkeypatch.setenv('MEDREP_DAILY_READONLY_ORIGIN', origin)
        with pytest.raises(HTTPException) as err:
            daily_origin()
        assert err.value.status_code == 503
    monkeypatch.setenv('MEDREP_DAILY_READONLY_ORIGIN', 'http://127.0.0.1:8787')
    assert daily_origin() == 'http://127.0.0.1:8787'
    monkeypatch.setenv('MEDREP_DAILY_READONLY_ORIGIN', 'https://medrep.example.com')
    assert daily_origin() == 'https://medrep.example.com'


def test_only_returns_approved_industry_fields(client, environment, monkeypatch):
    headers = staff_headers(client, environment)
    monkeypatch.setattr('platform_core.digest_bridge.fetch_daily', live_payload)
    result = client.get('/v1/mobile/daily/industry', headers=headers)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body['status'] == 'partial'
    assert len(body['items']) == 1
    assert body['items'][0]['review_status'] == 'not_reviewed'
    assert body['items'][0]['url'] == 'https://example.org/source'
    for forbidden in ('profile', 'learning', 'abstract', 'evidence', 'productIds', 'employee'):
        assert forbidden not in result.text
    assert result.headers.get('cache-control') == 'no-store'


def test_never_serves_demo_failed_or_stale():
    for change in ({'mode':'sample'}, {'mode':'untrusted'},
                   {'status':'failed'}, {'stale':True}, {'industry':None}):
        obj = live_payload() | change
        with pytest.raises(HTTPException) as err:
            present_digest(obj)
        assert err.value.status_code == 503


def test_fetch_uses_fixed_live_query_without_user_credentials(monkeypatch):
    import httpx
    monkeypatch.setenv('MEDREP_DAILY_READONLY_ORIGIN', 'https://trusted.example.org')
    requests = []
    payload = live_payload()
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=payload)
    class Client(httpx.Client):
        def __init__(self, *args, **kwargs):
            kwargs['transport'] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)
    monkeypatch.setattr('platform_core.digest_bridge.httpx.Client', Client)
    assert fetch_daily()['mode'] == 'live'
    assert requests[0].url == 'https://trusted.example.org/api/digest?mode=live&length=brief'
    assert requests[0].headers.get('authorization') is None
    assert requests[0].headers.get('cookie') is None


def test_large_response_rejected(monkeypatch):
    import httpx
    monkeypatch.setenv('MEDREP_DAILY_READONLY_ORIGIN', 'https://trusted.example.org')
    class Client(httpx.Client):
        def __init__(self, *args, **kwargs):
            kwargs['transport'] = httpx.MockTransport(lambda r: httpx.Response(200, headers={'Content-Type':'application/json'}, content=b'x'*1_500_001))
            super().__init__(*args, **kwargs)
    monkeypatch.setattr('platform_core.digest_bridge.httpx.Client', Client)
    with pytest.raises(HTTPException) as err:
        fetch_daily()
    assert err.value.status_code == 502


def test_logout_revokes_daily_access(client, environment, monkeypatch):
    headers = staff_headers(client, environment)
    monkeypatch.setattr('platform_core.digest_bridge.fetch_daily', live_payload)
    assert client.get('/v1/mobile/daily/industry', headers=headers).status_code == 200
    assert client.post('/v1/mobile/auth/logout', headers=headers).status_code == 204
    assert client.get('/v1/mobile/daily/industry', headers=headers).status_code == 401
