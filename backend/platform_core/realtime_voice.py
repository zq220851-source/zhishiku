"""Authenticated PCM streaming: browser <-> Bailian ASR/TTS, existing task engine owns dialogue.
No upload/submit-per-turn UI, no browser credentials for cloud providers, no typed training.
"""
import asyncio
import base64
import json
import os
import re
import time
import uuid
from types import SimpleNamespace
import aiohttp
from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from . import coach_bridge as coach
from .review_bridge import fetch_review

ASR = 'qwen3-asr-flash-realtime'
TTS = 'qwen3-tts-flash-realtime'


def configuration():
    key = os.environ.get('BAILIAN_API_KEY', '').strip()
    workspace = os.environ.get('BAILIAN_WORKSPACE_ID', '').strip()
    region = os.environ.get('BAILIAN_REGION', 'beijing')
    if not key or not re.fullmatch(r'ws-[A-Za-z0-9_-]+', workspace) or region not in ('beijing', 'singapore'):
        raise HTTPException(503, '实时语音尚未配置百炼密钥、业务空间和地域')
    location = 'cn-beijing' if region == 'beijing' else 'ap-southeast-1'
    return key, f'wss://{workspace}.{location}.maas.aliyuncs.com/api-ws/v1/realtime'


def event(kind, **fields):
    return {'event_id': uuid.uuid4().hex, 'type': kind, **fields}


async def open_remote(client, model, session):
    key, base = configuration()
    if model == TTS:
        base='wss://'+('dashscope-intl.aliyuncs.com' if os.environ.get('BAILIAN_REGION')=='singapore' else 'dashscope.aliyuncs.com')+'/api-ws/v1/realtime'
    try:
        remote = await client.ws_connect(base+'?model='+model, headers={'Authorization':'Bearer '+key},
                                         heartbeat=15, max_msg_size=2_000_000)
    except aiohttp.WSServerHandshakeError as exc:
        raise ValueError(f'百炼语音握手被拒绝（HTTP {exc.status}），请核对北京地域密钥、Workspace 和模型权限') from None
    try:
        await remote.send_json(event('session.update', session=session))
        async with asyncio.timeout(12):
            async for message in remote:
                if message.type != aiohttp.WSMsgType.TEXT:
                    raise ValueError('语音连接中断')
                data = json.loads(message.data)
                if data.get('type') == 'error' or data.get('code'):
                    raise ValueError('百炼拒绝语音会话，请检查地域、业务空间与 ASR/TTS 模型权限')
                if data.get('type') == 'session.updated':
                    return remote
        raise ValueError('百炼未确认语音配置')
    except BaseException:
        await remote.close()
        raise


async def synthesize(client, text, send, generation, current):
    remote = await open_remote(client, TTS, {'voice': os.environ.get('BAILIAN_VOICE', 'Cherry'),
        'mode':'commit', 'language_type':'Chinese', 'response_format':'pcm', 'sample_rate':24000})
    try:
        await send({'type':'speaking', 'generation':generation})
        # Long feedback is split at provider limits while retaining the exact engine text.
        for offset in range(0, len(text), 500):
            await remote.send_json(event('input_text_buffer.append', text=text[offset:offset+500]))
        await remote.send_json(event('input_text_buffer.commit'))
        async with asyncio.timeout(60):
            async for message in remote:
                if current() != generation:
                    return
                if message.type != aiohttp.WSMsgType.TEXT:
                    raise ValueError('医生语音连接中断')
                data = json.loads(message.data)
                if data.get('type') == 'response.audio.delta':
                    await send({'type':'audio', 'audio':data['delta'], 'generation':generation, 'sample_rate':24000})
                elif data.get('type') == 'response.done':
                    if data.get('response', {}).get('status') != 'completed':
                        raise ValueError('医生语音生成未完成')
                    await send({'type':'listening', 'generation':generation})
                    return
                elif data.get('type') == 'error' or data.get('code'):
                    raise ValueError('医生语音合成被拒绝，请检查 TTS 模型权限')
        raise ValueError('医生语音连接提前结束')
    finally:
        await remote.close()


def attach_voice_routes(app, actor, settings):
    @app.get('/v1/mobile/voice/config')
    def config(_user=__import__('fastapi').Depends(actor)):
        configuration()
        return {'configured':True, 'transport':'pcm-websocket', 'asr_model':ASR, 'tts_model':TTS,
                'verified':False, 'notice':'配置存在；连接时验证供应商权限和音频链路。'}

    # A run can have only one active recording connection across tabs/devices.
    active = set()

    @app.websocket('/v1/mobile/voice/{kind}/{record_id}')
    async def voice(ws: WebSocket, kind: str, record_id: str):
        if ws.headers.get('origin') not in (settings.app_origin, *settings.mobile_origins):
            await ws.close(code=4403); return
        if kind not in ('coach', 'review'):
            await ws.close(code=4404); return
        await ws.accept()
        tasks = []
        connection_key = None
        registered = False
        send_lock = asyncio.Lock()
        async def send(data):
            async with send_lock:
                await ws.send_json(data)
        try:
            auth = await asyncio.wait_for(ws.receive_json(), timeout=8)
            if auth.get('type') != 'auth' or not isinstance(auth.get('token'), str):
                raise HTTPException(401, '请登录后连接语音')
            user = await asyncio.to_thread(actor, SimpleNamespace(headers={'authorization':'Bearer '+auth['token']}))
            configuration()
            run = None
            if kind == 'coach':
                coach.require_id(record_id)
                run = await asyncio.to_thread(coach.upstream, 'GET', '/api/runs/'+record_id, user)
                if run.get('state') != 'active':
                    raise ValueError('本轮练习已结束，请复练或选择仍在进行的记录')
            else:
                workspace=await asyncio.to_thread(fetch_review,'GET','/api/live?taskId='+__import__('urllib.parse',fromlist=['quote']).quote(record_id,safe=''),user)
                if workspace.get('task',{}).get('id')!=record_id:
                    raise HTTPException(404,'复盘任务不存在')
            connection_key = (user['tenant_id'], user['id'], kind, record_id)
            if connection_key in active:
                raise ValueError('本次语音已在另一连接中进行，请先暂停原连接')
            active.add(connection_key)
            registered = True
            queue = asyncio.Queue(maxsize=12)
            finished = asyncio.Event()
            seen = set()
            generation = 0
            speech = None
            thinking = False
            playback_turns = {}
            stopping = False
            async def speak(text):
                nonlocal generation, speech
                generation += 1
                if speech:
                    speech.cancel()
                    await asyncio.gather(speech, return_exceptions=True)
                g = generation
                if run:
                    turn=len(run.get('transcript',[]))-1
                    playback_turns[g]=turn
                    await asyncio.to_thread(coach.upstream,'POST','/api/runs/'+record_id+'/playback',user,{'turn_index':turn,'status':'pending','played_ms':0})
                async def perform():
                    try:
                        await synthesize(client, text, send, g, lambda:generation)
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        await send({'type':'error','message':str(exc) if isinstance(exc,ValueError) else '医生语音播放失败，请重连'})
                speech = asyncio.create_task(perform())
                tasks.append(speech)
            timeout = aiohttp.ClientTimeout(total=None, connect=12, sock_read=90)
            async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as client:
                remote = await open_remote(client, ASR, {'input_audio_format':'pcm','sample_rate':16000,
                    'input_audio_transcription':{'language':'zh'},
                    'turn_detection':{'type':'server_vad','threshold':.25,'silence_duration_ms':1000}})
                try:
                    await send({'type':'ready','sample_rate':16000})
                    if run:
                        await speak(next((m['text'] for m in reversed(run.get('transcript',[])) if m.get('role')=='医生'), '我们开始吧。'))
                    async def upload():
                        nonlocal stopping
                        started = time.monotonic()
                        checked = started
                        while time.monotonic()-started < 1200:
                            message = await ws.receive()
                            if message['type']=='websocket.disconnect':
                                return
                            raw = message.get('bytes')
                            if raw is not None:
                                if not 2 <= len(raw) <= 16384 or len(raw)%2:
                                    raise ValueError('语音格式不正确')
                                if time.monotonic()-checked>30:
                                    await asyncio.to_thread(actor,SimpleNamespace(headers={'authorization':'Bearer '+auth['token']}))
                                    checked=time.monotonic()
                                await remote.send_json(event('input_audio_buffer.append',audio=base64.b64encode(raw).decode()))
                            elif message.get('text'):
                                command=json.loads(message['text'])
                                if command.get('type')=='playback' and kind=='coach':
                                    turn=playback_turns.get(command.get('generation'))
                                    if turn is not None:
                                        await asyncio.to_thread(coach.upstream,'POST','/api/runs/'+record_id+'/playback',user,{'turn_index':turn,'status':'completed' if command.get('completed') is True else 'interrupted','played_ms':command.get('played_ms',0)})
                                if command.get('type')=='stop':
                                    stopping=True
                                    if speech:speech.cancel()
                                    await remote.send_json(event('session.finish'))
                                    await asyncio.wait_for(finished.wait(),timeout=12)
                                    return
                                # No typed answer command is accepted.
                        raise ValueError('语音已达到20分钟，请重新连接继续')
                    async def receive():
                        nonlocal generation
                        async for message in remote:
                            if message.type != aiohttp.WSMsgType.TEXT:
                                raise ValueError('实时识别连接中断，请重新连接')
                            data=json.loads(message.data); typ=data.get('type')
                            if typ=='input_audio_buffer.speech_started':
                                old_generation=generation
                                generation += 1
                                if speech:speech.cancel()
                                if old_generation in playback_turns:
                                    await asyncio.to_thread(coach.upstream,'POST','/api/runs/'+record_id+'/playback',user,{'turn_index':playback_turns[old_generation],'status':'interrupted','played_ms':0})
                                await send({'type':'interrupt','generation':generation})
                            elif typ=='conversation.item.input_audio_transcription.text':
                                await send({'type':'draft','text':str(data.get('text',''))+str(data.get('stash',''))})
                            elif typ=='conversation.item.input_audio_transcription.completed':
                                text=data.get('transcript','').strip(); item=data.get('item_id') or data.get('event_id') or uuid.uuid4().hex
                                if not text or item in seen:continue
                                if len(text)>1600:raise ValueError('单次发言太长，请分几次说')
                                seen.add(item)
                                if kind=='review':
                                    await send({'type':'transcript','text':text})
                                else:
                                    if queue.full():raise ValueError('发言过快，请等待医生回应')
                                    await queue.put((text,'voice-'+str(item or uuid.uuid4().hex)))
                            elif typ=='session.finished':
                                finished.set()
                                return
                            elif typ=='error' or typ=='conversation.item.input_audio_transcription.failed' or data.get('code'):
                                raise ValueError('百炼实时识别失败，请检查模型权限后重连')
                        raise ValueError('实时识别连接关闭')
                    async def respond():
                        nonlocal run, thinking
                        while True:
                            text, request_id=await queue.get()
                            # Revalidate the platform session before every durable update.
                            await asyncio.to_thread(actor,SimpleNamespace(headers={'authorization':'Bearer '+auth['token']}))
                            thinking=True
                            await send({'type':'thinking'})
                            run=await asyncio.to_thread(coach.upstream,'GET','/api/runs/'+record_id,user)
                            run=await asyncio.to_thread(coach.upstream,'POST','/api/runs/'+record_id+'/answer',user,
                                {'answer':text,'revision':run['revision'],'request_id':request_id})
                            thinking=False
                            await send({'type':'run','run':run})
                            queue.task_done()
                            if run.get('state')=='active':
                                if not stopping:await speak(run['transcript'][-1]['text'])
                            else:
                                await send({'type':'complete'});return
                    tasks.extend([asyncio.create_task(upload()),asyncio.create_task(receive())])
                    responder=None
                    if kind=='coach':
                        responder=asyncio.create_task(respond());tasks.append(responder)
                    done,_=await asyncio.wait(tasks[-(3 if kind=='coach' else 2):],return_when=asyncio.FIRST_COMPLETED)
                    for t in done:t.result()
                    if finished.is_set():
                        drain=asyncio.create_task(queue.join());tasks.append(drain)
                        watched=[drain]+([responder] if responder else [])
                        settled,_=await asyncio.wait(watched,timeout=110,return_when=asyncio.FIRST_COMPLETED)
                        if not settled:raise ValueError('最后一段仍在处理，请查看记录后恢复')
                        for item in settled:item.result()
                        if not drain.done() and not queue.empty():raise ValueError('训练已结束，后续语音未计入，请核对记录')
                        await send({'type':'paused'})
                finally:
                    await remote.close()
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            try:
                message=exc.detail if isinstance(exc,HTTPException) else str(exc) if isinstance(exc,ValueError) else '实时语音连接失败，请检查语音配置与网络后重连'
                await send({'type':'error','message':message})
            except (RuntimeError,WebSocketDisconnect):pass
        finally:
            if registered:active.discard(connection_key)
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            try:await ws.close()
            except (RuntimeError,WebSocketDisconnect):pass
