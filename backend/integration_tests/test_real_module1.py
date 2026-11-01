"""Opt-in REAL module1 ASGI + platform bridge test, with a scripted AI provider.
Not production / not model correctness. Launches ephemeral localhost-only uvicorn on
port 8791 and SQLite temp databases; run explicitly, not in default backend CI.
"""
import os
import sys
import time
import socket
import threading
from pathlib import Path

import httpx
import pytest
import uvicorn
from scripts.provision_mobile_user import provision
from tests.conftest import client, environment

MODULE1 = Path(__file__).resolve().parents[2] / 'business_module1_reference'

@pytest.fixture
def module1(monkeypatch, tmp_path):
    # The hardened localhost adapter allows only 8791/8892. Do not disrupt an
    # already running service if the test port is in use.
    sock=socket.socket()
    try: sock.bind(('127.0.0.1',8791))
    except OSError:
        pytest.skip('127.0.0.1:8791 already in use')
    finally: sock.close()
    sys.path.insert(0,str(MODULE1))
    sys.path.insert(0,str(MODULE1/'tests'))
    from asgi import create_app
    from doubles import ScriptedProvider
    app=create_app(db=tmp_path/'real_module1.sqlite',provider=ScriptedProvider(),test_mode=True)
    uv=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8791,log_level='error',access_log=False))
    thread=threading.Thread(target=uv.run,daemon=True)
    thread.start()
    for i in range(80):
        if uv.started:break
        time.sleep(0.05)
    if not uv.started:raise AssertionError('Module 1 test server failed to start')
    monkeypatch.setenv('MEDREP_MODULE1_COACH_ORIGIN','http://127.0.0.1:8791')
    monkeypatch.setenv('MEDREP_MODULE1_OWNER_SECRET','development_owner_identity_secret_x'*2)
    try: yield
    finally:
        uv.should_exit=True
        thread.join(timeout=5)


def gettoken(client, env, username):
    settings,engine=env
    provision(engine,settings.tenant_id,username,username,'employee','StrongPracticePassword2026!')
    resp=client.post('/v1/mobile/auth/login',json={'username':username,'password':'StrongPracticePassword2026!'})
    assert resp.status_code==200,resp.text
    return {'Authorization':'Bearer '+resp.json()['access_token']}


def test_real_module1_prepare_freeze_and_training(client, environment,module1):
    alice=gettoken(client,environment,'coachreal1')
    bob=gettoken(client,environment,'coachreal2')
    content={'doctor':'某科室医生','goal':'确认研究适用范围','facts':'对方希望理解研究边界','lesson_id':'visit-communication'}
    prep=client.post('/v1/mobile/coach/prepare',headers=alice,json=content)
    assert prep.status_code==200,prep.text
    sheet=prep.json()
    assert sheet['priorities']
    sheet_id=sheet['id']
    assert client.get('/v1/mobile/coach/sheets/'+sheet_id,headers=bob).status_code==404
    candidate=sheet['priorities'][0]['id']
    freeze=client.post(f'/v1/mobile/coach/sheets/{sheet_id}/freeze',headers=alice,
                       json={'selected_ids':[candidate],'previsit_confirmed':True})
    assert freeze.status_code==200, freeze.text
    again=client.post(f'/v1/mobile/coach/sheets/{sheet_id}/freeze',headers=alice,
                       json={'selected_ids':[candidate],'previsit_confirmed':True})
    assert again.status_code==409
    # Real Module 1 scripted (not network AI) practice path.
    run=client.post('/v1/mobile/coach/runs/learn',headers=alice,json={'lesson_id':'demo-evidence'})
    assert run.status_code==201,run.text
    data=run.json()
    assert client.get('/v1/mobile/coach/runs/'+data['id'],headers=bob).status_code==404
    answer=client.post('/v1/mobile/coach/runs/'+data['id']+'/answer',headers=alice,json={
        'answer':'本次是软件测试材料，不能推断其他人群，后续查证来源并反馈。',
        'request_id':'original-request-001','revision':data['revision']})
    assert answer.status_code==200,answer.text
    assert answer.json()['revision'] >= 1
    assert client.get('/v1/mobile/coach/runs',headers=alice).json()['runs']
    assert client.get('/v1/mobile/coach/runs',headers=bob).json()['runs']==[]
