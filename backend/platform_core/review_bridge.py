"""Explicit Module-2 actions under server-signed employee identity; no public legacy proxy."""
import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from urllib.parse import urlencode
import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, insert
from .coach_bridge import stable_owner
from .db import users, teams, team_members, audit
from .security import new_id, now

class ReviewAction(BaseModel):
    action:str
    id:str|None=None
    kind:str|None=None
    taskId:str|None=None
    feedbackId:str|None=None
    runId:str|None=None
    expectedVersion:int|None=None
    exchangeMode:str|None=None
    raw:dict|None=None
    reason:str|None=Field(default=None,max_length=1000)
    cases:list[dict]|None=Field(default=None,max_length=24)
    target_user_id:str|None=None


def fetch_review(method,path,user,payload=None,role=None,scope_context=None):
    origin=os.environ.get('MEDREP_MODULE2_ORIGIN','http://127.0.0.1:3302')
    # Deliberately fixed loopback; the browser cannot choose an upstream URL.
    if origin not in ('http://127.0.0.1:3302','http://127.0.0.1:3402'):
        raise HTTPException(503,'复盘内部服务地址配置无效')
    key=os.environ.get('MEDREP_MODULE2_BRIDGE_SECRET','')
    if len(key)<32:raise HTTPException(503,'复盘身份连接尚未配置')
    owner=stable_owner(user)
    identity={'id':str(uuid.uuid5(uuid.NAMESPACE_URL,owner)), 'role':role or 'EMPLOYEE',
              'expires':int(time.time())+60}
    if scope_context is not None:identity['scope']=scope_context
    encoded=base64.urlsafe_b64encode(json.dumps(identity,separators=(',',':')).encode()).rstrip(b'=').decode()
    signature=hmac.new(key.encode(),encoded.encode(),hashlib.sha256).hexdigest()
    headers={'X-Medrep-Identity':encoded+'.'+signature,'Cookie':'medrep_owner='+owner,'Origin':origin,'Content-Type':'application/json','Idempotency-Key':uuid.uuid4().hex}
    try:
        with httpx.Client(timeout=150,trust_env=False,follow_redirects=False) as client:
            with client.stream(method,origin+path,headers=headers,json=payload) as response:
                content=bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content)>6_000_000:raise HTTPException(502,'复盘响应过大')
                data=json.loads(content)
                if response.status_code>=400:
                    raise HTTPException(response.status_code,str(data.get('error',{}).get('message','复盘操作失败'))[:240])
                if not isinstance(data.get('data'),dict):raise ValueError()
                return data['data']
    except HTTPException:raise
    except (httpx.HTTPError,ValueError):raise HTTPException(503,'复盘服务尚未启动或响应异常')


class EvolutionAction(BaseModel):
    action:str
    id:str|None=None
    level:str|None=None
    teamId:str|None=None
    feedbackId:str|None=None
    optionIndex:int|None=Field(default=None,ge=0,le=40)
    reason:str|None=Field(default=None,max_length=1000)
    caseFeedbackIds:list[str]|None=Field(default=None,max_length=2)
    expectedRevision:int|None=Field(default=None,ge=1)
    target_user_id:str|None=None


def evolution_scope(engine,user,owner=None):
    """Signed live membership; cookie test roles cannot manufacture this scope."""
    owner=owner or user
    with engine.connect() as conn:
        query=select(teams.c.id,teams.c.name).where(teams.c.tenant_id==user['tenant_id'])
        if user['role']!='admin':
            memberships=select(team_members.c.team_id).where(team_members.c.user_id==user['id'])
            if user['role']=='manager':memberships=memberships.where(team_members.c.team_role=='lead')
            query=query.where(teams.c.id.in_(memberships))
        available=[]
        for team in conn.execute(query).mappings():
            members=conn.execute(select(users).join(team_members,users.c.id==team_members.c.user_id).where(
                team_members.c.team_id==team['id'],users.c.tenant_id==user['tenant_id'],users.c.status=='active')).mappings().all()
            if owner['id'] not in {m['id'] for m in members}:continue
            available.append({'id':team['id'],'name':team['name'],'owners':[str(uuid.uuid5(uuid.NAMESPACE_URL,stable_owner(m))) for m in members]})
    return {'tenant':user['tenant_id'],'actorId':user['id'],'reviewer':user['role'] in ('manager','admin'),'teams':available}


def attach_review_routes(app,actor,engine):
    @app.get('/v1/mobile/review/workspace')
    def workspace(task_id:str|None=None,user=Depends(actor)):
        if task_id and len(task_id)>100:raise HTTPException(422,'任务标识过长')
        return fetch_review('GET','/api/live'+('?' +urlencode({'taskId':task_id}) if task_id else ''),user)

    @app.post('/v1/mobile/review/action')
    def action(body:ReviewAction,user=Depends(actor)):
        if body.action not in ('import','saveRaw','analyze','refreshPractice','linkPractice','refreshAssets'):
            raise HTTPException(422,'复盘操作无效')
        if body.raw and len(json.dumps(body.raw,ensure_ascii=False))>30000:raise HTTPException(413,'原文过长')
        return fetch_review('POST','/api/live',user,body.model_dump(exclude_none=True,exclude={'target_user_id'}))

    def review_scope(user):
        if user['role']=='admin':
            return select(users.c.id).where(users.c.tenant_id==user['tenant_id'])
        led=select(team_members.c.team_id).join(teams,teams.c.id==team_members.c.team_id).where(
            team_members.c.user_id==user['id'],team_members.c.team_role=='lead',teams.c.tenant_id==user['tenant_id'])
        return select(team_members.c.user_id).where(team_members.c.team_id.in_(led))

    @app.get('/v1/mobile/review/staff')
    def staff(user=Depends(actor)):
        if user['role'] not in ('manager','admin'):raise HTTPException(403,'需要培训审核职责')
        with engine.connect() as conn:
            rows=conn.execute(select(users.c.id,users.c.display_name).where(users.c.tenant_id==user['tenant_id'],users.c.status=='active',users.c.id.in_(review_scope(user)))).mappings().all()
        return {'staff':[dict(r) for r in rows]}

    @app.get('/v1/mobile/review/methods')
    def methods(target_user_id:str|None=None,user=Depends(actor)):
        owner=target(user,target_user_id)
        return fetch_review('GET','/api/live/methods',owner)

    def target(user,requested):
        if not requested or requested==user['id']:return user
        if user['role'] not in ('manager','admin'):raise HTTPException(403,'需要培训审核职责')
        with engine.connect() as conn:
            row=conn.execute(select(users).where(users.c.id==requested,users.c.tenant_id==user['tenant_id'],users.c.status=='active',users.c.id.in_(review_scope(user)))).mappings().first()
        if not row:raise HTTPException(404,'员工不存在')
        return dict(row)

    @app.post('/v1/mobile/review/methods')
    def method_action(body:ReviewAction,user=Depends(actor)):
        if body.action not in ('propose','evaluate','approve','revoke'):raise HTTPException(422,'方法操作无效')
        if body.action in ('evaluate','approve','revoke') and user['role'] not in ('manager','admin'):
            raise HTTPException(403,'方法授权需要培训审核职责')
        owner=target(user,body.target_user_id)
        payload=body.model_dump(exclude_none=True,exclude={'target_user_id'})
        if body.action in ('evaluate','approve','revoke'):
            payload['reason']=f"审核人 {user['id']}："+(body.reason or '')
        result=fetch_review('POST','/api/live/methods',owner,payload,
            role='TRAINING_REVIEWER' if body.action in ('evaluate','approve','revoke') else 'EMPLOYEE')
        with engine.begin() as conn:
            conn.execute(insert(audit).values(id=new_id(),actor_user_id=user['id'],action='method.'+body.action,target_id=owner['id']+':'+str(body.id or '')[:90],created_at=now()))
        return result

    @app.get('/v1/mobile/review/evolution')
    def evolution(target_user_id:str|None=None,user=Depends(actor)):
        owner=target(user,target_user_id)
        return fetch_review('GET','/api/live/evolution',owner,scope_context=evolution_scope(engine,user,owner))

    @app.post('/v1/mobile/review/evolution')
    def evolution_action(body:EvolutionAction,user=Depends(actor)):
        if body.action not in ('propose','evaluate','approve','revoke'):raise HTTPException(422,'共享内容操作无效')
        if body.action!='propose' and user['role'] not in ('manager','admin'):raise HTTPException(403,'需要团队审核职责')
        if body.action=='propose' and body.target_user_id and body.target_user_id!=user['id']:raise HTTPException(403,'只能从自己的记录提出候选')
        owner=target(user,body.target_user_id)
        result=fetch_review('POST','/api/live/evolution',owner,body.model_dump(exclude_none=True,exclude={'target_user_id'}),
            scope_context=evolution_scope(engine,user,owner))
        with engine.begin() as conn:
            conn.execute(insert(audit).values(id=new_id(),actor_user_id=user['id'],action='evolution.'+body.action,target_id=owner['id']+':'+str(body.id or '')[:90],created_at=now()))
        return result
