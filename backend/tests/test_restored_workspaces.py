import asyncio
import base64
import json
from types import SimpleNamespace
import pytest
from starlette.websockets import WebSocketDisconnect
from platform_core import realtime_voice as voice
from platform_core import review_bridge as review
from platform_core import daily_workspace as daily
from scripts.provision_mobile_user import provision


def auth(client, environment):
    settings, engine = environment
    provision(engine, settings.tenant_id, 'restored', '测试用户', 'employee', 'LocalTestStrongPassword2026!')
    return client.post('/v1/mobile/auth/login', json={'username':'restored','password':'LocalTestStrongPassword2026!'}).json()['access_token']


def test_missing_voice_provider_is_explicit(client, environment, monkeypatch):
    token = auth(client, environment)
    monkeypatch.delenv('BAILIAN_API_KEY', raising=False)
    with client.websocket_connect('/v1/mobile/voice/review/task', headers={'origin':environment[0].app_origin}) as ws:
        ws.send_json({'type':'auth','token':token})
        r = ws.receive_json()
        assert r['type']=='error' and '实时语音' in r['message']


def test_voice_origin_and_auth_precede_upstream(client, environment, monkeypatch):
    seen=[]
    monkeypatch.setattr(voice.coach, 'upstream', lambda *a: seen.append(a))
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/v1/mobile/voice/coach/abcdefgh', headers={'origin':'https://foreign.invalid'}):
            pass
    with client.websocket_connect('/v1/mobile/voice/coach/abcdefgh', headers={'origin':environment[0].app_origin}) as ws:
        ws.send_json({'type':'auth','token':'invalid'})
        assert ws.receive_json()['type']=='error'
    assert not seen


def test_pcm_turn_reaches_owned_engine_once(client, environment, monkeypatch):
    token=auth(client, environment)
    monkeypatch.setattr(voice, 'configuration', lambda:('not-real','wss://not-real.invalid'))
    calls=[]
    def engine(method, path, user, payload=None):
        calls.append((method,path,user['id'],payload))
        if method=='GET':
            return {'id':'abcdefgh','state':'active','revision':2,'transcript':[{'role':'医生','text':'请说说课程要点'}]}
        if path.endswith('/playback'):return {'ok':True}
        assert payload['answer']=='测试语音转写' and payload['revision']==2
        return {'id':'abcdefgh','state':'review','revision':3,'transcript':[],'review':{'feedback':'完成'}}
    monkeypatch.setattr(voice.coach, 'upstream', engine)
    class Remote:
        def __init__(self): self.queue=asyncio.Queue()
        def __aiter__(self): return self
        async def __anext__(self): return await self.queue.get()
        async def send_json(self, data):
            assert data['type']=='input_audio_buffer.append'
            assert base64.b64decode(data['audio'])==b'\0\0'*640
            for d in [{'type':'input_audio_buffer.speech_started'},
                      {'type':'conversation.item.input_audio_transcription.completed','item_id':'same-turn','transcript':'测试语音转写'},
                      {'type':'conversation.item.input_audio_transcription.completed','item_id':'same-turn','transcript':'测试语音转写'}]:
                await self.queue.put(SimpleNamespace(type=voice.aiohttp.WSMsgType.TEXT,data=json.dumps(d)))
        async def close(self): pass
    async def open_remote(*args): return Remote()
    async def tts(client, text, send, generation, current):
        await send({'type':'speaking','generation':generation})
        await asyncio.Event().wait()
    monkeypatch.setattr(voice, 'open_remote', open_remote)
    monkeypatch.setattr(voice, 'synthesize', tts)
    with client.websocket_connect('/v1/mobile/voice/coach/abcdefgh', headers={'origin':environment[0].app_origin}) as ws:
        ws.send_json({'type':'auth','token':token})
        assert ws.receive_json()['type']=='ready'
        ws.send_bytes(b'\0\0'*640)
        messages=[]
        while True:
            m=ws.receive_json(); messages.append(m)
            if m['type']=='complete': break
        assert any(m['type']=='interrupt' for m in messages)
        assert any(m['type']=='run' and m['run']['state']=='review' for m in messages)
    writes=[c for c in calls if c[0]=='POST' and c[1].endswith('/answer')]
    assert len(writes)==1 and writes[0][3]['request_id']=='voice-same-turn'
    assert len({c[2] for c in calls})==1


def test_review_roles_and_allowlist(client, environment, monkeypatch):
    token=auth(client, environment); h={'Authorization':'Bearer '+token}; seen=[]
    monkeypatch.setattr(review, 'fetch_review', lambda *a,**kw:seen.append((a,kw)) or {'ok':True})
    assert client.get('/v1/mobile/review/workspace').status_code==401
    assert client.post('/v1/mobile/review/action',headers=h,json={'action':'grant-role'}).status_code==422
    assert client.post('/v1/mobile/review/methods',headers=h,json={'action':'approve','id':'m','reason':'不允许越权'}).status_code==403
    assert client.post('/v1/mobile/review/action',headers=h,json={'action':'saveRaw','taskId':'mine','raw':{'text':'原话'}}).status_code==200
    assert len(seen)==1


def test_daily_preserves_personal_learning(client, environment, monkeypatch):
    token=auth(client, environment); h={'Authorization':'Bearer '+token}; seen=[]
    r=client.put('/v1/mobile/state/daily/work_profile',headers=h,json={'value':{'productIds':['1'],'pipelineIds':['85'],'topicIds':[]},'expected_revision':0})
    assert r.status_code==200
    def feed(path):
        seen.append(path)
        return {'industry':[{'id':'news'}],'learning':[{'id':'personal'}],'sources':[]}
    monkeypatch.setattr(daily, 'fetch_daily', feed)
    r=client.get('/v1/mobile/daily/workspace',headers=h)
    assert r.status_code==200 and r.json()['learning']==[{'id':'personal'}]
    assert 'products=1' in seen[0] and 'pipeline=85' in seen[0] and 'mode=live' in seen[0]


def test_pause_drains_last_asr_turn_before_acknowledgement(client,environment,monkeypatch):
    token=auth(client,environment)
    monkeypatch.setattr(voice,'configuration',lambda:('not-real','wss://not-real.invalid'))
    saved=[]
    def engine(method,path,user,payload=None):
        if path.endswith('/playback'):return {'ok':True}
        if method=='POST':saved.append(payload['answer'])
        return {'id':'abcdefgh','state':'active','revision':len(saved)+1,'transcript':[{'role':'医生','text':'继续'}]}
    monkeypatch.setattr(voice.coach,'upstream',engine)
    class Remote:
        def __init__(self):self.queue=asyncio.Queue()
        def __aiter__(self):return self
        async def __anext__(self):return await self.queue.get()
        async def send_json(self,data):
            if data['type']=='session.finish':
                for d in [{'type':'conversation.item.input_audio_transcription.completed','item_id':'tail','transcript':'最后一段'}, {'type':'session.finished'}]:
                    await self.queue.put(SimpleNamespace(type=voice.aiohttp.WSMsgType.TEXT,data=json.dumps(d)))
        async def close(self):pass
    async def remote(*a):return Remote()
    async def tts(*a):await asyncio.Event().wait()
    monkeypatch.setattr(voice,'open_remote',remote);monkeypatch.setattr(voice,'synthesize',tts)
    with client.websocket_connect('/v1/mobile/voice/coach/abcdefgh',headers={'origin':environment[0].app_origin}) as ws:
        ws.send_json({'type':'auth','token':token});assert ws.receive_json()['type']=='ready';ws.send_json({'type':'stop'})
        messages=[]
        while True:
            message=ws.receive_json();messages.append(message)
            if message['type']=='paused':break
        assert any(m['type']=='run' for m in messages)
    assert saved==['最后一段']


def test_review_voice_requires_owned_task(client,environment,monkeypatch):
    from fastapi import HTTPException
    token=auth(client,environment)
    monkeypatch.setattr(voice,'configuration',lambda:('not-real','wss://not-real.invalid'))
    def deny(*a):raise HTTPException(404,'复盘任务不存在')
    monkeypatch.setattr(voice,'fetch_review',deny)
    with client.websocket_connect('/v1/mobile/voice/review/other-task',headers={'origin':environment[0].app_origin}) as ws:
        ws.send_json({'type':'auth','token':token})
        assert ws.receive_json()=={'type':'error','message':'复盘任务不存在'}
