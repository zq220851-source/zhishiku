"""Standalone App security acceptance tests; use temporary SQLite, never production data."""
import pytest
from sqlalchemy import select, update
from platform_core.db import users, sessions, mobile_credentials
from scripts.provision_mobile_user import provision


def cred(client, name='staff01', password='LongStrongPass!2026'):
    r=client.post('/v1/mobile/auth/login',json={'username':name,'password':password})
    return r

def auth(token):
    return {'Authorization':'Bearer '+token}

def test_account_login_notes_owner_logout(client, environment):
    settings, engine=environment
    alice=provision(engine,settings.tenant_id,'staff01','张某','employee','LongStrongPass!2026')
    bob=provision(engine,settings.tenant_id,'staff02','王某','employee','OtherStrongPass!2026')
    x=cred(client)
    assert x.status_code==200,x.text
    tok=x.json()['access_token']
    assert tok.startswith('mr_m_')
    assert x.json()['user']['id']==alice
    assert client.get('/v1/mobile/auth/me',headers=auth(tok)).status_code==200
    assert client.get('/v1/auth/me',headers=auth(tok)).status_code==401  # cookie API stays distinct
    assert client.get('/v1/mobile/state/ui/personal_notes').status_code==401
    first=client.put('/v1/mobile/state/ui/personal_notes',headers=auth(tok),json={'value':'private note A','expected_revision':0})
    assert first.status_code==200,first.text
    assert first.json()['revision']==1
    assert client.put('/v1/mobile/state/ui/personal_notes',headers=auth(tok),json={'value':'overwrite','expected_revision':0}).status_code==409
    other=cred(client,'staff02','OtherStrongPass!2026')
    assert other.status_code==200
    tok2=other.json()['access_token']
    assert other.json()['user']['id']==bob
    assert client.get('/v1/mobile/state/ui/personal_notes',headers=auth(tok2)).json()=={'value':None,'revision':0}
    assert client.get('/v1/mobile/state/ui/personal_notes',headers=auth(tok)).json()['value']=='private note A'
    assert client.post('/v1/mobile/auth/logout',headers=auth(tok)).status_code==204
    assert client.get('/v1/mobile/auth/me',headers=auth(tok)).status_code==401
    assert client.get('/v1/mobile/auth/me',headers=auth(tok2)).status_code==200

def test_invalid_password_lock_and_disabled(client,environment):
    settings,engine=environment
    uid=provision(engine,settings.tenant_id,'lock01','测试员工','employee','LongStrongPass!2026')
    assert cred(client,'lock01','wrong').status_code==401
    with engine.connect() as conn:
        assert conn.execute(select(mobile_credentials.c.failed_attempts).where(mobile_credentials.c.user_id==uid)).scalar_one()==1
    for i in range(4):
        assert cred(client,'lock01','wrong').status_code==401
    assert cred(client,'lock01','LongStrongPass!2026').status_code==429
    uid2=provision(engine,settings.tenant_id,'disabled01','停用成员','employee','LongStrongPass!2026')
    with engine.begin() as conn:
        conn.execute(update(users).where(users.c.id==uid2).values(status='disabled'))
    assert cred(client,'disabled01','LongStrongPass!2026').status_code==403

def test_no_public_signup_and_cors(client,environment):
    assert client.post('/v1/mobile/auth/register',json={'name':'any'}).status_code==404
    pre=client.options('/v1/mobile/auth/login',headers={'Origin':'capacitor://localhost',
        'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'})
    assert pre.status_code==200
    assert pre.headers['access-control-allow-origin']=='capacitor://localhost'
    disallowed=client.options('/v1/mobile/auth/login',headers={'Origin':'https://evil.example.com',
        'Access-Control-Request-Method':'POST'})
    assert disallowed.status_code==400

def test_password_hash_is_salted():
    from platform_core.mobile_auth import make_password_hash,verify_password
    p1=make_password_hash('LongStrongPass!2026')
    p2=make_password_hash('LongStrongPass!2026')
    assert p1!=p2
    assert verify_password('LongStrongPass!2026',p1)
    assert not verify_password('incorrect',p1)
