from sqlalchemy import insert
from platform_core.db import users
from platform_core.security import now
from .conftest import ORIGIN, login

ALICE='11111111-1111-4111-8111-111111111111'
BOB='22222222-2222-4222-8222-222222222222'


def test_admin_team_creation_and_roster_access(client):
    login(client)
    assert client.post('/v1/admin/teams',headers={'origin':ORIGIN},json={'name':'East'}).status_code==403
    login(client,'admin-code')
    assert client.post('/v1/admin/teams',json={'name':'East'}).status_code==403
    creation=client.post('/v1/admin/teams',headers={'origin':ORIGIN},json={'name':'East'})
    assert creation.status_code==201
    team=creation.json()['id']
    assert client.get('/v1/admin/teams').json()['teams'][0]['id']==team
    def assign(id,role):
        return client.put(f'/v1/admin/teams/{team}/members', headers={'origin':ORIGIN},
            json={'user_id':id, 'team_role':role})
    assert assign(BOB,'lead').status_code==200
    assert assign(ALICE,'member').status_code==200
    assert assign(ALICE,'member').status_code==200  # idempotent update
    roster=client.get(f'/v1/teams/{team}/members')
    assert roster.status_code==200 and len(roster.json()['members'])==2
    login(client,'alice-code')
    assert client.get('/v1/me/teams').json()['teams'][0]['name']=='East'
    assert client.get(f'/v1/teams/{team}/members').status_code==403
    assert client.get('/v1/admin/teams').status_code==403
    login(client,'bob-code')
    assert client.get(f'/v1/teams/{team}/members').status_code==200
    # Team lead cannot read other members' owned records through platform endpoints.
    assert client.get('/v1/me/records').json()['items']==[]
    login(client,'admin-code')
    assert client.delete(f'/v1/admin/teams/{team}/members/{BOB}', headers={'origin':ORIGIN}).status_code==204
    login(client,'bob-code')
    assert client.get(f'/v1/teams/{team}/members').status_code==403


def test_team_assignment_rejects_cross_tenant_or_disabled(client, environment):
    _,engine=environment
    with engine.begin() as conn:
        conn.execute(insert(users).values(id='55555555-5555-4555-8555-555555555555',
            tenant_id='other-tenant',feishu_open_id='ou_other',display_name='Other',
            role='employee',status='active',created_at=now(),updated_at=now()))
    login(client,'admin-code')
    team=client.post('/v1/admin/teams',headers={'origin':ORIGIN},json={'name':'West'}).json()['id']
    for id in ['55555555-5555-4555-8555-555555555555','33333333-3333-4333-8333-333333333333']:
        assert client.put(f'/v1/admin/teams/{team}/members', headers={'origin':ORIGIN},
            json={'user_id':id,'team_role':'lead'}).status_code==404
    assert client.put(f'/v1/admin/teams/{team}/members', headers={'origin':ORIGIN},
            json={'user_id':ALICE,'team_role':'superuser'}).status_code==422
