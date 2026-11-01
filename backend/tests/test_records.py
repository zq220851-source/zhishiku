from sqlalchemy import select, insert
from platform_core.db import users, record_links
from platform_core.security import now
from .conftest import login, ORIGIN

ALICE = '11111111-1111-4111-8111-111111111111'
BOB = '22222222-2222-4222-8222-222222222222'
DISABLED = '33333333-3333-4333-8333-333333333333'
HEADERS = {'x-medrep-module':'coach', 'x-medrep-service-key':'coach_secret_for_backend_only_0123456789'}
PATH = '/v1/internal/records'


def register(client, owner=ALICE, kind='session', ref='s001', headers=HEADERS):
    return client.post(PATH, headers=headers, json={'owner_user_id':owner, 'object_kind':kind,'external_ref':ref})


def test_internal_registration_requires_per_module_credentials(client):
    assert register(client, headers={}).status_code == 403
    assert register(client, headers={'x-medrep-module':'coach','x-medrep-service-key':'bad'}).status_code == 403
    assert register(client, headers={'x-medrep-module':'review', 'x-medrep-service-key':HEADERS['x-medrep-service-key']}).status_code == 403
    assert register(client).status_code == 201
    assert client.get('/v1/internal/records/owner', params={'object_kind':'session','external_ref':'s001'}).status_code == 403
    response = client.get('/v1/internal/records/owner', headers=HEADERS, params={'object_kind':'session','external_ref':'s001'})
    assert response.status_code == 200
    assert response.json()['owner_user_id'] == ALICE
    review_headers={'x-medrep-module':'review','x-medrep-service-key':'review_secret_for_backend_only_0123456789'}
    assert client.get('/v1/internal/records/owner',headers=review_headers,params={'object_kind':'session','external_ref':'s001'}).status_code == 404


def test_immutable_owner_and_idempotent_registration(client):
    first = register(client)
    assert first.status_code == 201 and first.json()['created']
    second = register(client)
    assert second.status_code == 201 and not second.json()['created']
    assert second.json()['id'] == first.json()['id']
    assert register(client, owner=BOB).status_code == 409
    assert register(client, owner=DISABLED, ref='z').status_code == 404
    assert register(client, kind='INVALID KIND', ref='z').status_code == 422
    assert register(client, ref='../a/b').status_code == 422


def test_records_are_visible_only_to_owner(client):
    assert register(client).status_code == 201
    assert register(client, owner=BOB, ref='s002').status_code == 201
    assert client.get('/v1/me/records').status_code == 401
    assert login(client).status_code == 200
    alice = client.get('/v1/me/records').json()['items']
    assert len(alice) == 1 and alice[0]['external_ref'] == 's001'
    link_id = alice[0]['id']
    assert client.get('/v1/me/records/'+link_id).status_code == 200
    assert client.get('/v1/me/records?module=review').json()['items'] == []
    assert client.get('/v1/me/records?limit=101').status_code == 422
    assert login(client,'bob-code').status_code == 200
    assert [x['external_ref'] for x in client.get('/v1/me/records').json()['items']] == ['s002']
    assert client.get('/v1/me/records/'+link_id).status_code == 404


def test_cross_tenant_owner_cannot_be_registered(client, environment):
    _, engine = environment
    with engine.begin() as conn:
        conn.execute(insert(users).values(id='55555555-5555-4555-8555-555555555555',
            tenant_id='someone-else',feishu_open_id='ou_else',display_name='Else',
            role='employee',status='active',created_at=now(),updated_at=now()))
    assert register(client, owner='55555555-5555-4555-8555-555555555555').status_code == 404


def test_no_bearer_session_bypass_and_csrf_origin(client):
    login(client)
    token = client.cookies['medrep_sid']
    client.cookies.clear()
    assert client.get('/v1/auth/me', headers={'authorization':'Bearer '+token}).status_code == 401
    assert client.post('/v1/auth/logout', headers={'authorization':'Bearer '+token}).status_code == 401
    assert client.put('/v1/me/state/ui/theme',headers={'authorization':'Bearer '+token},
           json={'value': 'dark', 'expected_revision':0}).status_code == 401
