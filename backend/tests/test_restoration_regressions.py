from sqlalchemy import insert, select
from platform_core.db import users, teams, team_members, audit
from platform_core.security import now
from platform_core import review_bridge
from scripts.provision_mobile_user import provision


def login(client,environment,name,role='employee'):
    settings,engine=environment
    provision(engine,settings.tenant_id,name,name,role,'LocalOnlyPassword2026!')
    r=client.post('/v1/mobile/auth/login',json={'username':name,'password':'LocalOnlyPassword2026!'}).json()
    return {'Authorization':'Bearer '+r['access_token']},r['user']['id']


def test_article_full_snapshot_survives_and_is_owner_scoped(client,environment):
    h,_=login(client,environment,'reader')
    other,_=login(client,environment,'other')
    article={'id':'https://example.org/a','title':'原文','abstract':'完整摘要。'*300,'originalTitle':'Original title','limitations':'未核验','sourceUrl':'https://example.org/a'}
    assert client.post('/v1/mobile/daily/article',headers=h,json={'article':article}).status_code==200
    assert client.get('/v1/mobile/daily/article',headers=h,params={'id':article['id']}).json()['article']==article
    assert client.get('/v1/mobile/daily/article',headers=other,params={'id':article['id']}).status_code==404
    assert client.post('/v1/mobile/daily/article',headers=h,json={'article':{**article,'abstract':'a'*61000}}).status_code==413
    assert client.get('/v1/mobile/daily/article',headers=h,params={'id':article['id']}).json()['article']==article


def test_manager_review_limited_to_led_team_and_audits_actual_actor(client,environment,monkeypatch):
    manager,mid=login(client,environment,'manager','manager')
    _,member=login(client,environment,'member')
    _,outside=login(client,environment,'outside')
    settings,engine=environment
    with engine.begin() as conn:
        conn.execute(insert(teams).values(id='team-a',tenant_id=settings.tenant_id,name='A',created_at=now()))
        for uid,role in [(mid,'lead'),(member,'member')]:
            conn.execute(insert(team_members).values(team_id='team-a',user_id=uid,team_role=role,created_at=now()))
    monkeypatch.setattr(review_bridge,'fetch_review',lambda *args,**kw:{'ok':True})
    ids={s['id'] for s in client.get('/v1/mobile/review/staff',headers=manager).json()['staff']}
    assert member in ids and outside not in ids
    body={'action':'approve','id':'method-a','reason':'已完成独立案例核对','target_user_id':outside}
    assert client.post('/v1/mobile/review/methods',headers=manager,json=body).status_code==404
    assert client.post('/v1/mobile/review/methods',headers=manager,json={**body,'target_user_id':member}).status_code==200
    with engine.connect() as conn:
        event=conn.execute(select(audit).where(audit.c.action=='method.approve')).mappings().one()
        assert event['actor_user_id']==mid and event['target_id']==member+':method-a'


def test_live_evolution_signs_real_membership_and_actual_reviewer(client,environment,monkeypatch):
    monkeypatch.setenv('MEDREP_MODULE1_OWNER_SECRET','protocol-owner-secret-at-least-32-chars')
    manager,mid=login(client,environment,'evolution-manager','manager')
    employee,eid=login(client,environment,'evolution-member')
    _,outside=login(client,environment,'evolution-outsider')
    settings,engine=environment
    with engine.begin() as conn:
        conn.execute(insert(teams).values(id='evolution-team',tenant_id=settings.tenant_id,name='Actual team',created_at=now()))
        for uid,role in [(mid,'lead'),(eid,'member')]:
            conn.execute(insert(team_members).values(team_id='evolution-team',user_id=uid,team_role=role,created_at=now()))
    calls=[]
    def fetch(*args,**kwargs):calls.append((args,kwargs));return {'releases':[],'ok':True}
    monkeypatch.setattr(review_bridge,'fetch_review',fetch)
    assert client.get('/v1/mobile/review/evolution',headers=employee).status_code==200
    scope=calls[-1][1]['scope_context']
    assert scope['actorId']==eid and not scope['reviewer'] and len(scope['teams'])==1
    assert scope['teams'][0]['id']=='evolution-team' and len(scope['teams'][0]['owners'])==2
    body={'action':'approve','id':'candidate','expectedRevision':2,'reason':'独立验证及脱敏审核完成','target_user_id':eid}
    assert client.post('/v1/mobile/review/evolution',headers=employee,json=body).status_code==403
    assert client.post('/v1/mobile/review/evolution',headers=manager,json={**body,'target_user_id':outside}).status_code==404
    assert client.post('/v1/mobile/review/evolution',headers=manager,json=body).status_code==200
    assert calls[-1][1]['scope_context']['actorId']==mid and calls[-1][0][2]['id']==eid
    assert client.post('/v1/mobile/review/evolution',headers=manager,json={**body,'action':'propose'}).status_code==403
    with engine.connect() as conn:
        event=conn.execute(select(audit).where(audit.c.action=='evolution.approve')).mappings().one()
        assert event['actor_user_id']==mid


def test_revoked_shared_scene_cannot_start_new_training_or_freeze(client,environment,monkeypatch):
    from platform_core import coach_bridge
    h,_=login(client,environment,'shared-consumer')
    sheet={'priorities':[{'id':'shared_option','shared_release':{'id':'release','version':3}}],
           'evolution':{'proposed':['shared_option'],'applied':[]}}
    calls=[]
    def upstream(method,path,user,payload=None):calls.append((method,path));return sheet
    monkeypatch.setattr(coach_bridge,'upstream',upstream)
    monkeypatch.setattr(review_bridge,'fetch_review',lambda *args,**kwargs:{'releases':[]})
    assert client.post('/v1/mobile/coach/runs/visit',headers=h,json={'sheet_id':'sheet_12345','option_id':'shared_option'}).status_code==409
    assert client.post('/v1/mobile/coach/sheets/sheet_12345/freeze',headers=h,json={'selected_ids':['shared_option'],'previsit_confirmed':True}).status_code==409
    assert all(method=='GET' for method,path in calls)
