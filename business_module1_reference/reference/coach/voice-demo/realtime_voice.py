"""Bailian-only streaming ASR/TTS bridge. Credentials remain in server memory.
Protocol sources: https://help.aliyun.com/en/model-studio/qwen-asr-realtime-client-events
https://help.aliyun.com/en/model-studio/qwen-tts-realtime-client-events
"""
import asyncio
import base64
import json
import re
import ssl
import threading
import uuid
from pathlib import Path
import aiohttp
from aiohttp import web

ASR_MODEL = 'qwen3-asr-flash-realtime'
TTS_MODEL = 'qwen3-tts-flash-realtime'
REGIONS = {'beijing': 'cn-beijing', 'singapore': 'ap-southeast-1'}
_lock = threading.Lock()
_config = None
_bridge_port = None


def public_config():
    with _lock:
        c = _config
        return {'ready': bool(c and _bridge_port), 'configured': bool(c), 'port': _bridge_port,
                'region': c['region'] if c else 'beijing', 'asr_model': ASR_MODEL, 'tts_model': TTS_MODEL}


def parse_config(data):
    key = str(data.get('api_key', '')).strip()
    workspace = str(data.get('workspace_id', '')).strip()
    region = str(data.get('region', 'beijing'))
    if not key.startswith('sk-') or not 12 <= len(key) <= 256:
        raise ValueError('请输入百炼 API Key；不是 Credits Key 或活动 ID')
    if region not in REGIONS or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', workspace):
        raise ValueError('请选择地域并填写同一地域的 Workspace ID')
    return {'key': key, 'workspace': workspace, 'region': region}


def endpoint(c, model):
    return f"wss://{c['workspace']}.{REGIONS[c['region']]}.maas.aliyuncs.com/api-ws/v1/realtime?model={model}"


def event(kind, **fields):
    return {'event_id': uuid.uuid4().hex, 'type': kind, **fields}


def asr_settings(gap=1200):
    if gap not in (1200, 5000):
        raise ValueError('不支持的接话间隔')
    return event('session.update', session={'input_audio_format': 'pcm', 'sample_rate': 16000,
        'input_audio_transcription': {'language': 'zh'},
        'turn_detection': {'type': 'server_vad', 'threshold': .2, 'silence_duration_ms': gap}})


def tts_settings(voice='Maia'):
    if voice not in ('Maia', 'Andre'):
        raise ValueError('流式模式请选择 Maia 或 Andre')
    return event('session.update', session={'voice': voice, 'mode': 'commit',
        'language_type': 'Chinese', 'response_format': 'pcm', 'sample_rate': 24000})


def tls_context():
    return ssl.create_default_context(cafile='/etc/ssl/cert.pem') if Path('/etc/ssl/cert.pem').is_file() else ssl.create_default_context()


async def connect(client, c, model, settings):
    ws = await client.ws_connect(endpoint(c, model), headers={'Authorization': 'Bearer '+c['key']},
                                  ssl=tls_context(), heartbeat=15, max_msg_size=2_000_000)
    try:
        await ws.send_json(settings)
        async with asyncio.timeout(10):
            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    raise ValueError('语音连接未完成配置')
                d = json.loads(msg.data)
                # Some entitlement errors are top-level code/message objects,
                # not Realtime error events; report them before the socket closes.
                code = d.get('code') or (d.get('error', {}).get('code') if isinstance(d.get('error'), dict) else None)
                if code == 'AccessDenied.Unpurchased':
                    raise ValueError(f'百炼 {model} 尚未获得使用权限（AccessDenied.Unpurchased），请用主账号完成百炼服务开通并确认模型权限')
                if d.get('type') == 'error' or code:
                    raise ValueError(f'百炼 {model} 拒绝会话配置，请检查模型权限、地域与业务空间')
                if d.get('type') == 'session.updated':
                    return ws
        raise ValueError('百炼语音连接提前关闭')
    except BaseException:
        await ws.close()
        raise


async def verify_config(c):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as client:
        async def check(model, settings):
            try:
                ws = await connect(client, c, model, settings)
                await ws.close()
                return True
            except aiohttp.WSServerHandshakeError as exc:
                raise ValueError(f'百炼 {model} 握手失败（HTTP {exc.status}），请检查该地域密钥、业务空间与模型权限') from None
            except (aiohttp.ClientError, TimeoutError):
                raise ValueError(f'百炼 {model} 连接失败或超时，请检查网络和地域') from None
        result = await asyncio.gather(check(ASR_MODEL, asr_settings()), check(TTS_MODEL, tts_settings()), return_exceptions=True)
        for r in result:
            if isinstance(r, BaseException): raise r


def configure(data):
    global _config
    c = parse_config(data)
    asyncio.run(verify_config(c))
    with _lock: _config = c
    return public_config()


def clear_config():
    global _config
    with _lock: _config = None


def snapshot():
    with _lock:
        if not _config: raise ValueError('百炼流式语音尚未配置')
        return dict(_config)


async def relay_asr(local, remote, active):
    async def upload():
        async for msg in local:
            if not active(): raise ValueError('会话已结束')
            if msg.type != aiohttp.WSMsgType.BINARY or not 2 <= len(msg.data) <= 16384 or len(msg.data) % 2:
                raise ValueError('无效的 PCM 音频片段')
            await remote.send_json(event('input_audio_buffer.append', audio=base64.b64encode(msg.data).decode()))
    async def download():
        async for msg in remote:
            if msg.type != aiohttp.WSMsgType.TEXT: break
            d = json.loads(msg.data); kind = d.get('type')
            if kind == 'error' or kind == 'conversation.item.input_audio_transcription.failed':
                raise ValueError('百炼实时转写失败，本段未提交；可重新说或使用文字输入')
            if kind == 'conversation.item.input_audio_transcription.text':
                await local.send_json({'type':'draft','text':str(d.get('text',''))+str(d.get('stash',''))})
            elif kind == 'conversation.item.input_audio_transcription.completed':
                text = d.get('transcript')
                if not isinstance(text,str) or len(text)>1200: raise ValueError('转写结果无效或发言过长')
                if text.strip():
                    await local.send_json({'type':'done','text':text.strip()})
                    return  # One complete speaker turn; avoid double submission.
            elif kind in ('input_audio_buffer.speech_started','input_audio_buffer.speech_stopped'):
                await local.send_json({'type': 'speech_started' if kind.endswith('started') else 'speech_stopped'})
        raise ValueError('实时转写连接中断，本段未提交')
    async def guard():
        while True:
            await asyncio.sleep(.25)
            if not active(): raise ValueError('会话已结束')
    tasks = [asyncio.create_task(f()) for f in (upload,download,guard)]
    try:
        done,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
        for t in done: t.result()
    finally:
        for t in tasks: t.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)


async def relay_tts(local, remote, text, active):
    await remote.send_json(event('input_text_buffer.append', text=text))
    await remote.send_json(event('input_text_buffer.commit'))
    count = 0
    async def receive():
        nonlocal count
        async for msg in remote:
            if not active(): raise ValueError('会话已结束')
            if msg.type != aiohttp.WSMsgType.TEXT: break
            d=json.loads(msg.data); kind=d.get('type')
            if kind=='error': raise ValueError('百炼流式合成失败')
            if kind=='response.audio.delta':
                raw=base64.b64decode(d['delta'],validate=True); count+=len(raw)
                if count>2_000_000: raise ValueError('语音过长')
                await local.send_bytes(raw)
            elif kind=='response.done':
                if d.get('response',{}).get('status')!='completed' or not count:
                    raise ValueError('语音生成未完整结束')
                await local.send_json({'type':'done'})
                return
        raise ValueError('合成连接中断')
    async def disconnected():
        async for _ in local: pass
    async def guard():
        while True:
            await asyncio.sleep(.25)
            if not active(): raise ValueError('会话已结束')
    tasks=[asyncio.create_task(f()) for f in (receive,disconnected,guard)]
    try:
        async with asyncio.timeout(30):
            done,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
            for t in done:t.result()
    finally:
        for t in tasks:t.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)


def make_app(origin, active_session, speech_text):
    async def handler(request):
        if request.headers.get('Origin')!=origin or request.host!=f'127.0.0.1:{_bridge_port}':
            raise web.HTTPForbidden(text='仅允许本机演示页面')
        kind=request.match_info['kind']; args=dict(request.query)
        if kind not in ('asr','tts'):raise web.HTTPNotFound()
        try:
            c=snapshot()
            preview=kind=='tts' and args.get('preview')=='true'
            active=lambda: preview or active_session(args.get('session_id',''))
            if not active(): raise ValueError('会话已结束或失效')
            settings=asr_settings(int(args.get('gap','1200'))) if kind=='asr' else tts_settings(args.get('voice','Maia'))
            text=speech_text(args) if kind=='tts' else None
        except ValueError as exc:raise web.HTTPBadRequest(text=str(exc))
        local=web.WebSocketResponse(heartbeat=15,max_msg_size=16384)
        await local.prepare(request)
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as client:
                async with asyncio.timeout(12):
                    remote=await connect(client,c,ASR_MODEL if kind=='asr' else TTS_MODEL,settings)
                try:
                    if not active():raise ValueError('会话已结束')
                    await local.send_json({'type':'ready','sample_rate':16000 if kind=='asr' else 24000})
                    if kind=='asr':await relay_asr(local,remote,active)
                    else:await relay_tts(local,remote,text,active)
                finally:await remote.close()
        except (Exception, asyncio.CancelledError) as exc:
            if not local.closed:
                message=str(exc) if isinstance(exc,ValueError) else '百炼实时语音连接失败或超时，请检查网络、密钥与模型权限'
                await local.send_json({'type':'error','error':message})
        finally:await local.close()
        return local
    app=web.Application();app.router.add_get('/{kind}',handler)
    return app


def start_bridge(port, origin, active_session, speech_text):
    global _bridge_port
    _bridge_port=port
    ready=threading.Event(); failures=[]
    async def serve():
        runner=web.AppRunner(make_app(origin,active_session,speech_text),access_log=None)
        await runner.setup();await web.TCPSite(runner,'127.0.0.1',port).start();ready.set()
        await asyncio.Event().wait()
    def run():
        try:asyncio.run(serve())
        except Exception as exc:failures.append(type(exc).__name__);ready.set()
    threading.Thread(target=run,daemon=True).start()
    if not ready.wait(5) or failures:raise RuntimeError('流式语音本机端口无法启动')
