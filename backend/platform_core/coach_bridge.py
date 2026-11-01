"""Employee-scoped Module 1 integration for mobile text coaching and previsit freeze.

The upstream Module 1 is a trusted localhost-only service using an HttpOnly
``medrep_owner`` cookie. Derive a private stable upstream owner from a server-only
secret and the authenticated platform tenant/user. The client can neither choose
an upstream owner nor pass arbitrary URLs, headers, credentials, or action names.

NOT a public reverse proxy and NOT a medical compliance approval. Module 1 must
run inside the platform's trusted loopback network namespace; do not relax its
local-only host/origin checks to expose it publicly. No voice routes here.
"""
import base64
import hashlib
import hmac
import json
import os
import re
from urllib.parse import urlsplit

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

ID = re.compile(r'^[A-Za-z0-9_-]{8,100}$')
LESSON = re.compile(r'^[A-Za-z0-9_.-]{1,80}$')
MAX_UPSTREAM = 2_000_000


class VisitInput(BaseModel):
    use_approved_methods: bool = False
    shared_release_ids: list[str] = Field(default_factory=list,max_length=10)
    shared_budget: int = Field(default=1,ge=1,le=20)
    doctor: str = Field(min_length=1, max_length=80)
    goal: str = Field(min_length=1, max_length=300)
    facts: str = Field(min_length=1, max_length=2000)
    lesson_id: str = Field(min_length=1, max_length=80)


class FreezeInput(BaseModel):
    selected_ids: list[str] = Field(min_length=1, max_length=20)
    previsit_confirmed: bool


class StartLearningInput(BaseModel):
    lesson_id: str = Field(min_length=1, max_length=80)


class StartVisitInput(BaseModel):
    sheet_id: str = Field(min_length=8, max_length=100)
    option_id: str = Field(min_length=1, max_length=80)


class AnswerInput(BaseModel):
    answer: str = Field(min_length=1, max_length=1600)
    request_id: str = Field(min_length=8, max_length=100)
    revision: int = Field(ge=0)


def coach_origin() -> str:
    raw = os.environ.get('MEDREP_MODULE1_COACH_ORIGIN', '').strip().rstrip('/')
    parsed = urlsplit(raw)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
            or parsed.port not in (8791, 8892) or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        raise HTTPException(503, '演练服务尚未部署或内部地址配置不正确')
    return raw


def stable_owner(user: dict) -> str:
    secret = os.environ.get('MEDREP_MODULE1_OWNER_SECRET', '')
    if len(secret) < 32 or not all(isinstance(user.get(k), str) and user[k] for k in ('id', 'tenant_id')):
        raise HTTPException(503, '演练员工身份映射未配置')
    identity = f"medrep-module1-v1\0{user['tenant_id']}\0{user['id']}".encode()
    digest = hmac.new(secret.encode(), identity, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


def require_id(value: str, pattern=ID):
    if not pattern.fullmatch(value):
        raise HTTPException(404, '记录 ID 不合法')
    return value


def upstream(method: str, path: str, user: dict, payload: dict | None = None) -> dict:
    origin = coach_origin()
    owner = stable_owner(user)
    headers = {'Accept': 'application/json', 'Cookie': 'medrep_owner=' + owner}
    if method == 'POST':
        headers.update({'Content-Type': 'application/json', 'Origin': origin})
    try:
        # Preparation allows one structural repair plus speaker-perspective check.
        timeout=150.0 if path=='/api/prepare' else 100.0
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=4.0), follow_redirects=False,
                          trust_env=False) as client:
            with client.stream(method, origin + path, headers=headers, json=payload) as resp:
                if resp.status_code not in (200, 201):
                    if resp.status_code in (400, 404, 409, 422):
                        try:
                            body = b''
                            for piece in resp.iter_bytes():
                                body += piece
                                if len(body) > 8192:
                                    break
                            message = json.loads(body).get('error', '请求未完成') if len(body) <= 8192 else '请求未完成'
                        except (ValueError, TypeError, json.JSONDecodeError):
                            message = '请求未完成'
                        if not isinstance(message, str):
                            message = '请求未完成'
                        raise HTTPException(resp.status_code, message[:180])
                    raise HTTPException(503, '训练服务当前不可用或缺少模型配置')
                if 'application/json' not in resp.headers.get('content-type', '').lower():
                    raise HTTPException(502, '训练服务返回非 JSON 数据')
                chunks, size = [], 0
                for chunk in resp.iter_bytes():
                    size += len(chunk)
                    if size > MAX_UPSTREAM:
                        raise HTTPException(502, '训练结果超过安全限制')
                    chunks.append(chunk)
                result = json.loads(b''.join(chunks))
                if not isinstance(result, dict):
                    raise ValueError('Expected JSON object')
                return result
    except HTTPException:
        raise
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(502, '训练服务返回无效 JSON')
    except httpx.RequestError:
        raise HTTPException(503, '训练服务连接失败')


def attach_coach_routes(app, actor, engine=None):
    def active_releases(user):
        from .review_bridge import fetch_review,evolution_scope
        if engine is None:raise HTTPException(503,'团队权限服务未配置')
        return fetch_review('GET','/api/live/evolution?active=1',user,scope_context=evolution_scope(engine,user)).get('releases',[])

    def check_releases(user,sheet,selected,practice=False):
        required=[p['shared_release'] for p in sheet.get('priorities',[]) if p['id'] in selected and p.get('shared_release')]
        e=sheet.get('evolution') or {}
        if not practice and set(selected)==set(e.get('proposed',[])):required+=e.get('applied',[])
        if required:
            active={(r['id'],r['version']) for r in active_releases(user)}
            if any((r['id'],r['version']) not in active for r in required):raise HTTPException(409,'所选共享版本已撤回、原文已变化或团队权限已改变；请重新生成准备单')

    @app.get('/v1/mobile/coach/sheets')
    def sheets(user=Depends(actor)):
        data = upstream('GET', '/api/sheets', user)
        if not isinstance(data.get('sheets'), list):
            raise HTTPException(502, '准备记录格式错误')
        return data

    @app.get('/v1/mobile/coach/sheets/{sheet_id}')
    def sheet(sheet_id: str, user=Depends(actor)):
        return upstream('GET', '/api/sheets/' + require_id(sheet_id), user)

    @app.post('/v1/mobile/coach/prepare')
    def prepare(body: VisitInput, user=Depends(actor)):
        if not LESSON.fullmatch(body.lesson_id):
            raise HTTPException(422, '课程标识无效')
        signed_method=None
        if body.use_approved_methods:
            from .review_bridge import fetch_review
            available=fetch_review('GET','/api/live/methods?active=1',user)
            record=next((m for m in available.get('methods',[]) if body.lesson_id in m.get('lessonIds',[])),None)
            if not record:raise HTTPException(409,'本课程没有获准且来源有效的方法，请先完成验证授权或关闭方法选项')
            import time
            method=record['method']
            value={'owner':stable_owner(user),'lesson_id':body.lesson_id,'expires':int(time.time())+60,
                   'method':{'id':record['id'],'version':record['version'],'lesson_ids':record['lessonIds'],
                             'source_versions':record.get('sourceVersions',[]),**method}}
            encoded=base64.urlsafe_b64encode(json.dumps(value,separators=(',',':')).encode()).decode()
            signature=hmac.new(os.environ['MEDREP_MODULE1_OWNER_SECRET'].encode(),encoded.encode(),hashlib.sha256).hexdigest()
            signed_method=encoded+'.'+signature
        signed_evolution=None
        if body.shared_release_ids:
            records=[r for r in active_releases(user) if r['id'] in body.shared_release_ids and r['lessonId']==body.lesson_id]
            if len(records)!=len(body.shared_release_ids):raise HTTPException(409,'共享版本已失效或不属于本课程，请刷新后重选')
            import time
            value={'owner':stable_owner(user),'lesson_id':body.lesson_id,'expires':int(time.time())+60,'releases':records,'budget':body.shared_budget}
            encoded=base64.urlsafe_b64encode(json.dumps(value,separators=(',',':')).encode()).decode()
            signature=hmac.new(os.environ['MEDREP_MODULE1_OWNER_SECRET'].encode(),encoded.encode(),hashlib.sha256).hexdigest()
            signed_evolution=encoded+'.'+signature
        return upstream('POST', '/api/prepare', user, {
            'visit_id':'custom', 'context':{'doctor':body.doctor,'goal':body.goal,'facts':body.facts,'lesson_id':body.lesson_id},
            'platform_method':signed_method,'platform_evolution':signed_evolution,
        })

    @app.post('/v1/mobile/coach/sheets/{sheet_id}/freeze')
    def freeze(sheet_id: str, body: FreezeInput, user=Depends(actor)):
        if body.previsit_confirmed is not True:
            raise HTTPException(422, '必须由本人确认仍处于真实拜访之前')
        if len(set(body.selected_ids)) != len(body.selected_ids) or any(
                not LESSON.fullmatch(x) for x in body.selected_ids):
            raise HTTPException(422, '预测候选 ID 无效或重复')
        sheet=upstream('GET','/api/sheets/'+require_id(sheet_id),user)
        check_releases(user,sheet,body.selected_ids)
        return upstream('POST', '/api/sheets/' + require_id(sheet_id) + '/freeze', user,
                        {'selected_ids': body.selected_ids, 'previsit_confirmed': True})

    @app.get('/v1/mobile/coach/runs')
    def runs(user=Depends(actor)):
        data = upstream('GET', '/api/history', user)
        if not isinstance(data.get('runs'), list):
            raise HTTPException(502, '训练历史格式错误')
        # Never need to ship upstream history evidence to show a list.
        return {'runs': data['runs'][:30]}

    @app.get('/v1/mobile/coach/runs/{run_id}')
    def run(run_id: str, user=Depends(actor)):
        return upstream('GET', '/api/runs/' + require_id(run_id), user)

    @app.post('/v1/mobile/coach/runs/learn', status_code=201)
    def start_learning(body: StartLearningInput, user=Depends(actor)):
        if not LESSON.fullmatch(body.lesson_id):
            raise HTTPException(422, '课程标识无效')
        return upstream('POST', '/api/runs', user, {'mode': 'learn', 'lesson_id': body.lesson_id})

    @app.post('/v1/mobile/coach/runs/visit', status_code=201)
    def start_visit(body: StartVisitInput, user=Depends(actor)):
        if not LESSON.fullmatch(body.option_id):
            raise HTTPException(422, '候选项无效')
        sheet=upstream('GET','/api/sheets/'+require_id(body.sheet_id),user)
        check_releases(user,sheet,[body.option_id],practice=True)
        return upstream('POST', '/api/runs', user, {'mode': 'visit', 'sheet_id': require_id(body.sheet_id),
                                                  'option_id': body.option_id})

    @app.post('/v1/mobile/coach/runs/{run_id}/resume')
    def resume(run_id: str, user=Depends(actor)):
        return upstream('POST','/api/runs/'+require_id(run_id)+'/resume',user,{})

    @app.post('/v1/mobile/coach/runs/{run_id}/answer')
    def answer(run_id: str, body: AnswerInput, user=Depends(actor)):
        return upstream('POST', '/api/runs/' + require_id(run_id) + '/answer', user,
                        {'answer': body.answer, 'request_id': body.request_id,
                         'revision': body.revision})

    @app.post('/v1/mobile/coach/runs/{run_id}/finish')
    def finish(run_id: str, user=Depends(actor)):
        return upstream('POST', '/api/runs/' + require_id(run_id) + '/finish', user, {})

    # Original Module 1 guided review actions, scoped to the authenticated employee.
    @app.post('/v1/mobile/coach/runs/{run_id}/support')
    def run_support(run_id: str, user=Depends(actor)):
        return upstream('POST', '/api/runs/' + require_id(run_id) + '/support', user, {})

    @app.post('/v1/mobile/coach/runs/{run_id}/retry')
    def run_retry(run_id: str, user=Depends(actor)):
        return upstream('POST', '/api/runs/' + require_id(run_id) + '/retry', user, {})
