"""Phase 7 knowledge adapter must never expose legacy local-owner API sessions."""
import os
import pytest
from fastapi import HTTPException
from platform_core.learning_bridge import internal_origin, fetch_module1
from scripts.provision_mobile_user import provision


def token(client, environment):
    settings, engine = environment
    provision(engine, settings.tenant_id, 'lesson01', '课程员工', 'employee', 'StrongLessonPass!2026')
    result = client.post('/v1/mobile/auth/login', json={'username':'lesson01','password':'StrongLessonPass!2026'})
    assert result.status_code == 200
    return {'Authorization': 'Bearer ' + result.json()['access_token']}


def test_disabled_and_unauthorized(client, environment, monkeypatch):
    monkeypatch.delenv('MEDREP_MODULE1_READONLY_ORIGIN', raising=False)
    assert client.get('/v1/mobile/learning/catalog').status_code == 401
    headers = token(client, environment)
    resp = client.get('/v1/mobile/learning/catalog', headers=headers)
    assert resp.status_code == 503
    assert client.get('/v1/mobile/learning/courses/a', headers=headers).status_code == 503


def test_rejects_public_or_tainted_origins(monkeypatch):
    for origin in ('https://example.com', 'http://127.0.0.1:8080',
                   'http://evil@127.0.0.1:8892', 'http://127.0.0.1:8892/path',
                   'http://169.254.169.254:8892'):
        monkeypatch.setenv('MEDREP_MODULE1_READONLY_ORIGIN', origin)
        with pytest.raises(HTTPException) as e: internal_origin()
        assert e.value.status_code == 503


def test_no_upstream_credential_forwarding(client, environment, monkeypatch):
    headers=token(client,environment)
    monkeypatch.setenv('MEDREP_MODULE1_READONLY_ORIGIN','http://127.0.0.1:8892')
    observed=[]
    def mock_fetch(path):
        observed.append(path)
        if path=='/api/config': return {'lessons':[{'id':'course-1','title':'真实课程','status':'PENDING_REVIEW'}]}
        if path=='/api/courses/course-1': return {'lesson_id':'course-1','title':'真实课程','status':'PENDING_REVIEW','blocks':[{},{}],'references':[{}]}
        raise AssertionError('unexpected upstream path')
    monkeypatch.setattr('platform_core.learning_bridge.fetch_module1',mock_fetch)
    r=client.get('/v1/mobile/learning/catalog',headers=headers)
    assert r.status_code==200 and r.json()['lessons'][0]['title']=='真实课程'
    assert r.json()['lessons'][0]['status']=='PENDING_REVIEW'
    r=client.get('/v1/mobile/learning/courses/course-1',headers=headers)
    assert r.status_code==200 and r.json()['block_count']==2
    assert len(r.json()['blocks'])==2 and len(r.json()['references'])==1
    assert observed==['/api/config','/api/courses/course-1']


def test_no_path_traversal(client,environment,monkeypatch):
    headers=token(client,environment)
    monkeypatch.setenv('MEDREP_MODULE1_READONLY_ORIGIN','http://127.0.0.1:8892')
    assert client.get('/v1/mobile/learning/courses/course%2Fother',headers=headers).status_code in (404,405)
    assert client.get('/v1/mobile/learning/courses/bad%20id',headers=headers).status_code == 404
