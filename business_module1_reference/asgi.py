"""FastAPI shell; sync model calls execute in its thread pool."""
import asyncio,mimetypes,os,secrets,json
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse,FileResponse
from knowledge import ROOT,LESSONS,VISITS
from materials import snapshot,search_materials
from workflow import Engine,Problem
from voice_runtime import VoiceService,voice_config
from app import RemoteDoctorProvider


def create_app(db=None,provider=None,test_mode=False):
    provider=provider or RemoteDoctorProvider()
    engine=Engine(db or ROOT/'runtime/module1.sqlite',provider)
    voice=VoiceService(engine)
    @asynccontextmanager
    async def lifecycle(app):
        yield
        await asyncio.to_thread(voice.close)
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifecycle)
    app.state.engine=engine;app.state.provider=provider;app.state.voice=voice

    @app.middleware('http')
    async def boundaries(request:Request,call_next):
        if request.url.hostname!='127.0.0.1':
            return JSONResponse({'error':'请使用本机127.0.0.1地址'},status_code=403)
        if request.method not in ('GET','HEAD') and request.headers.get('origin')!=str(request.base_url).rstrip('/'):
            return JSONResponse({'error':'请从本机页面操作'},status_code=403)
        length=request.headers.get('content-length','0')
        if request.method=='POST':
            if 'application/json' not in request.headers.get('content-type',''):
                return JSONResponse({'error':'需要JSON请求'},status_code=415)
            if not length.isdigit() or int(length)>6_100_000:
                return JSONResponse({'error':'请求过大'},status_code=413)
        owner=request.cookies.get('medrep_owner','')
        new_owner=len(owner)!=43 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in owner)
        request.state.owner=secrets.token_urlsafe(32) if new_owner else owner
        response=await call_next(request)
        if new_owner:response.set_cookie('medrep_owner',request.state.owner,httponly=True,samesite='strict')
        response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff'
        parsed=urlparse(os.environ.get('LIVEKIT_URL','ws://127.0.0.1:7880'))
        allowed=f'{parsed.scheme}://{parsed.netloc}' if parsed.scheme in ('ws','wss') else ''
        response.headers['Content-Security-Policy']=f"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' {allowed}; media-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        return response

    @app.exception_handler(Problem)
    async def problem(request,exc):return JSONResponse({'error':str(exc)},status_code=exc.status)
    @app.exception_handler(ValueError)
    async def value_error(request,exc):return JSONResponse({'error':str(exc)[:160]},status_code=400)
    @app.exception_handler(Exception)
    async def failure(request,exc):return JSONResponse({'error':'服务暂时不可用；已保存内容不会被自动改写。'},status_code=503)

    @app.get('/api/config')
    def config():return {'lessons':[{k:d.get(k) for k in ['id','title','kind','status','duration']} for d in LESSONS.values() if test_mode or d.get('source_path')], 'visits':[{'id':v['id'],'title':v['title']} for v in VISITS.values()] if test_mode else [], 'model':app.state.provider.readiness(),'test_mode':test_mode}
    @app.get('/api/courses/{key}')
    def course(key:str):
        if not test_mode:
            from live_knowledge import real_lesson
            real_lesson(key)
        try:return snapshot(key)
        except ValueError as e:raise Problem(str(e),404)
    @app.get('/api/history')
    def history(request:Request):return {'runs':engine.listing(request.state.owner),'evidence':engine.history(request.state.owner)}
    @app.get('/api/knowledge/catalog')
    def knowledge_catalog():
        from live_knowledge import catalog
        return catalog()
    @app.get('/api/knowledge/search')
    def knowledge_search(lessonId:str,q:str):
        from live_knowledge import search
        return search(lessonId,q)
    @app.get('/api/integration/tasks')
    def integration_tasks(request:Request):
        from live_knowledge import owned_tasks
        return {'system':'MODULE1','tasks':owned_tasks(engine,request.state.owner)}
    @app.get('/api/integration/tasks/{kind}/{key}')
    def integration_task(kind:str,key:str,request:Request):
        from live_knowledge import export_task
        return export_task(engine,request.state.owner,kind,key)
    @app.get('/api/runs/{key}')
    def run(key:str,request:Request):
        value=engine.load('runs',key,request.state.owner)
        if not test_mode:
            from live_knowledge import real_lesson
            real_lesson(value.get('lesson_id'))
        return engine.view(value)
    @app.get('/api/sheets')
    def sheets(request:Request):return {'sheets':engine.sheets_listing(request.state.owner)}
    @app.get('/api/sheets/{key}')
    def sheet(key:str,request:Request):
        value=engine.load('sheets',key,request.state.owner)
        if not test_mode:
            from live_knowledge import real_lesson
            real_lesson((value.get('material') or {}).get('lesson_id'))
        return value
    @app.get('/api/voice/config')
    def voice_settings():return voice_config(app.state.provider)
    @app.post('/api/materials/search')
    def search(body:dict):return {'blocks':search_materials(body.get('lesson_id'),body.get('query'),body.get('limit',5)),'retrieval':'haystack-bm25'}
    @app.post('/api/prepare')
    def prepare(body:dict,request:Request):
        if not test_mode:
            from live_knowledge import real_lesson
            if body.get('visit_id')!='custom':raise Problem('请选择真实课程并填写本次背景，不使用虚构场景')
            real_lesson((body.get('context') or {}).get('lesson_id'))
        approved_method=None
        if body.get('platform_method'):
            import base64,hashlib,hmac,time
            try:
                encoded,signature=body['platform_method'].split('.')
                secret=os.environ.get('MEDREP_MODULE1_OWNER_SECRET','')
                expected=hmac.new(secret.encode(),encoded.encode(),hashlib.sha256).hexdigest()
                value=json.loads(base64.urlsafe_b64decode(encoded))
                if len(secret)<32 or not hmac.compare_digest(expected,signature) or value['owner']!=request.state.owner or value['lesson_id']!=(body.get('context') or {}).get('lesson_id') or not time.time()<value['expires']<time.time()+120:
                    raise ValueError()
                approved_method=value['method']
            except Exception:raise Problem('平台方法授权失效或不匹配',403)
        if body.get('use_approved_methods') is True:
            if body.get('visit_id')!='custom':raise Problem('仅自填真实课程准备可选用获准测试方法')
            from method_client import approved_method_for_lesson, MethodUnavailable
            try:
                approved_method=approved_method_for_lesson(request.headers.get('cookie',''), (body.get('context') or {}).get('lesson_id',''))
            except MethodUnavailable as e:raise Problem(str(e),503)
            if approved_method is None:raise Problem('本课程暂无获准且来源有效的测试方法，未改变准备单',409)
        shared=[];budget=None
        if body.get('platform_evolution'):
            import base64,hashlib,hmac,time
            try:
                encoded,signature=body['platform_evolution'].split('.')
                secret=os.environ.get('MEDREP_MODULE1_OWNER_SECRET','')
                expected=hmac.new(secret.encode(),encoded.encode(),hashlib.sha256).hexdigest()
                value=json.loads(base64.urlsafe_b64decode(encoded))
                if len(secret)<32 or not hmac.compare_digest(expected,signature) or value['owner']!=request.state.owner or value['lesson_id']!=(body.get('context') or {}).get('lesson_id') or not time.time()<value['expires']<time.time()+120:raise ValueError()
                shared=value['releases'];budget=value['budget']
                if not isinstance(shared,list) or not 1<=len(shared)<=10:raise ValueError()
            except Exception:raise Problem('平台共享版本签名失效或不匹配',403)
        return engine.prepare(body.get('visit_id',''),request.state.owner,body.get('context'),approved_method,shared,budget)
    @app.post('/api/sheets/{key}/freeze')
    def freeze_sheet(key:str,body:dict,request:Request):
        return engine.freeze_forecast(key,request.state.owner,body.get('selected_ids'),body.get('previsit_confirmed'))

    @app.post('/api/runs',status_code=201)
    def create(body:dict,request:Request):
        if not test_mode and body.get('mode')=='learn':
            from live_knowledge import real_lesson
            real_lesson(body.get('lesson_id'))
        return engine.create(body,request.state.owner)
    @app.post('/api/runs/{key}/{action}')
    def operate(key:str,action:str,body:dict,request:Request):
        owner=request.state.owner
        if action=='answer':return engine.answer(key,body,owner)
        if action=='playback':return engine.playback(key,body,owner)
        if action=='resume':return engine.resume(key,owner)
        if action=='support':return engine.support(key,owner)
        if action=='retry':return engine.retry(key,owner)
        if action=='correct':return engine.correct(key,body,owner)
        if action=='finish':return engine.finish(key,owner)
        if action=='voice':return voice.start(key,owner)
        raise Problem('接口不存在',404)
    @app.post('/api/credentials')
    def credentials(body:dict):
        from app import set_credits_runtime_key
        key=body.get('key','')
        if not isinstance(key,str) or not key.startswith('sk-') or not 12<=len(key)<=256:raise Problem('请输入有效API Key')
        new_provider=RemoteDoctorProvider(key_override=key)
        new_provider.chat('连接检查，只回复OK。','OK',max_tokens=30,fast=True)
        set_credits_runtime_key(key)
        engine.provider=app.state.provider=RemoteDoctorProvider()
        return {'ready':True}
    files={'':'index.html','app.js':'app.js','materials.js':'materials.js','voice.js':'voice.js','style.css':'style.css','livekit-client.js':'vendor/livekit-client.js'}
    # Public presentation assets only; never expose source trees or local settings.
    files.update({f'visual/{name}':f'visual/{name}' for name in ('glass.css','coach.js','pet.js','mascot.png','instrument-400.ttf','instrument-500.ttf','instrument-600.ttf','instrument-700.ttf')})
    @app.get('/{path:path}')
    def static(path:str):
        if path not in files:raise Problem('页面不存在',404)
        return FileResponse(ROOT/'web'/files[path],media_type=mimetypes.guess_type(files[path])[0],headers={'Access-Control-Allow-Origin':'*'} if path.startswith('visual/') else None)
    return app
