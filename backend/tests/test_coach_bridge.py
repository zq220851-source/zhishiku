"""Security contract for the real Module 1 mobile adapter. No real doctor data."""
import os
import json
import httpx
import pytest
from fastapi import HTTPException
from platform_core import coach_bridge as bridge
from scripts.provision_mobile_user import provision


def auth(client, environment, username):
    settings, engine = environment
    provision(engine, settings.tenant_id, username, username, 'employee', 'StrongPracticePassword2026!')
    resp=client.post('/v1/mobile/auth/login',json={'username':username,'password':'StrongPracticePassword2026!'})
    assert resp.status_code == 200
    return {'Authorization': 'Bearer ' + resp.json()['access_token']}


def test_guard_and_secret(client,environment,monkeypatch):
    assert client.get('/v1/mobile/coach/sheets').status_code == 401
    h=auth(client, environment,'coacha')
    assert client.get('/v1/mobile/coach/sheets',headers=h).status_code == 503
    monkeypatch.setenv('MEDREP_MODULE1_COACH_ORIGIN','http://127.0.0.1:8791')
    assert client.get('/v1/mobile/coach/sheets',headers=h).status_code == 503
    monkeypatch.setenv('MEDREP_MODULE1_OWNER_SECRET','S'*48)
    for src in ('https://example.org','http://metadata.google.internal:8791',
                'http://evil@127.0.0.1:8791','http://127.0.0.1:8787',
                'http://127.0.0.1:8791/secret'):
        monkeypatch.setenv('MEDREP_MODULE1_COACH_ORIGIN',src)
        with pytest.raises(HTTPException): bridge.coach_origin()


def test_stable_distinct_owner_secret(monkeypatch):
    monkeypatch.setenv('MEDREP_MODULE1_OWNER_SECRET','X'*48)
    a={'tenant_id':'t','id':'alice'}
    b={'tenant_id':'t','id':'bob'}
    assert bridge.stable_owner(a)==bridge.stable_owner(a)
    assert len(bridge.stable_owner(a))==43
    assert bridge.stable_owner(a)!=bridge.stable_owner(b)
    assert bridge.stable_owner(a)!=bridge.stable_owner({'tenant_id':'other','id':'alice'})
    monkeypatch.delenv('MEDREP_MODULE1_OWNER_SECRET')
    with pytest.raises(HTTPException):bridge.stable_owner(a)


def test_upstream_no_bearer_and_account_isolation(client,environment,monkeypatch):
    monkeypatch.setenv('MEDREP_MODULE1_COACH_ORIGIN','http://127.0.0.1:8791')
    monkeypatch.setenv('MEDREP_MODULE1_OWNER_SECRET','T'*48)
    h1=auth(client,environment,'coachb')
    h2=auth(client,environment,'coachc')
    seen=[]
    class Client:
        def __init__(self,**kwargs):
            assert kwargs['follow_redirects'] is False and kwargs['trust_env'] is False
        def __enter__(self):return self
        def __exit__(self,*args):return None
        def stream(self,method,url,headers,json=None):
            seen.append((method,url,headers,json))
            from contextlib import contextmanager
            @contextmanager
            def cm():
                req=httpx.Request(method,url)
                yield httpx.Response(200,json={'sheets':[]},request=req)
            return cm()
    monkeypatch.setattr(bridge.httpx,'Client',Client)
    for h in (h1,h2):
        assert client.get('/v1/mobile/coach/sheets',headers=h).json()=={'sheets':[]}
    assert seen[0][2]['Cookie'] != seen[1][2]['Cookie']
    assert 'Authorization' not in seen[0][2]
    assert all(x[1]=='http://127.0.0.1:8791/api/sheets' for x in seen)


def test_previsit_immutability_boundaries(client,environment,monkeypatch):
    h=auth(client,environment,'coachd')
    monkeypatch.setenv('MEDREP_MODULE1_COACH_ORIGIN','http://127.0.0.1:8791')
    monkeypatch.setenv('MEDREP_MODULE1_OWNER_SECRET','V'*48)
    calls=[]
    def fake_upstream(method,path,user,payload=None):
        calls.append((method,path,payload,user['id']))
        return {'id':'some_valid_id', 'forecast':{'status':'FROZEN'}}
    monkeypatch.setattr(bridge,'upstream',fake_upstream)
    bad=client.post('/v1/mobile/coach/sheets/abcdefgh/freeze',headers=h,
                    json={'selected_ids':['needs'],'previsit_confirmed':False})
    assert bad.status_code == 422 and not calls
    double=client.post('/v1/mobile/coach/sheets/abcdefgh/freeze',headers=h,
                       json={'selected_ids':['needs','needs'],'previsit_confirmed':True})
    assert double.status_code == 422 and not calls
    ok=client.post('/v1/mobile/coach/sheets/abcdefgh/freeze',headers=h,
                   json={'selected_ids':['needs'],'previsit_confirmed':True})
    assert ok.status_code == 200
    assert calls[-1][2]['previsit_confirmed'] is True
    prep=client.post('/v1/mobile/coach/prepare',headers=h,json={'doctor':'脱敏称呼','goal':'核查证据',
            'facts':'只记录非识别性背景','lesson_id':'visit-communication','use_approved_methods':False})
    assert prep.status_code == 200
    assert calls[-1][2]['platform_method'] is None
    invalid=client.get('/v1/mobile/coach/runs/bad%20id',headers=h)
    assert invalid.status_code == 404


def test_malformed_upstream_responses(client,environment,monkeypatch):
    h=auth(client,environment,'coache')
    monkeypatch.setenv('MEDREP_MODULE1_COACH_ORIGIN','http://127.0.0.1:8791')
    monkeypatch.setenv('MEDREP_MODULE1_OWNER_SECRET','X'*48)
    def response(status,body,content_type='application/json'):
        class Client:
            def __init__(self,**kwargs):pass
            def __enter__(self):return self
            def __exit__(self,*args):return None
            def stream(self,method,url,headers,json=None):
                from contextlib import contextmanager
                @contextmanager
                def cm():
                    yield httpx.Response(status,content=body,headers={'Content-Type':content_type},request=httpx.Request(method,url))
                return cm()
        return Client
    monkeypatch.setattr(bridge.httpx,'Client',response(200,b'<html>'))
    assert client.get('/v1/mobile/coach/sheets',headers=h).status_code == 502
    monkeypatch.setattr(bridge.httpx,'Client',response(200,b'{' + b'x' * (2_000_001) + b'}'))
    assert client.get('/v1/mobile/coach/sheets',headers=h).status_code == 502
    monkeypatch.setattr(bridge.httpx,'Client',response(409,'{"error":"冻结后不能修改"}'.encode()))
    assert client.post('/v1/mobile/coach/sheets/abcdefgh/freeze',headers=h,
        json={'selected_ids':['needs'],'previsit_confirmed':True}).status_code == 409
    monkeypatch.setattr(bridge.httpx,'Client',response(302,b''))
    assert client.get('/v1/mobile/coach/sheets',headers=h).status_code == 503
