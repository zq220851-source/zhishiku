"""Focused security check for restored original Module 1 support/retry actions."""
from platform_core import coach_bridge as bridge
from scripts.provision_mobile_user import provision


def test_support_retry_routes_require_auth_and_bind_employee(client, environment, monkeypatch):
    settings, engine = environment
    provision(engine, settings.tenant_id, 'practice_owner', 'Practice Owner', 'employee', 'TestOnlyStrongPass2026!')
    token_resp=client.post('/v1/mobile/auth/login',json={'username':'practice_owner','password':'TestOnlyStrongPass2026!'})
    assert token_resp.status_code == 200
    headers={'Authorization':'Bearer '+token_resp.json()['access_token']}
    seen=[]
    def internal(method,path,user,payload=None):
        seen.append((method,path,user['id'],payload))
        return {'id':'abcdefgh','state':'review'}
    monkeypatch.setattr(bridge,'upstream',internal)
    for name in ('support','retry'):
        url=f'/v1/mobile/coach/runs/abcdefgh/{name}'
        assert client.post(url).status_code==401
        assert client.post(f'/v1/mobile/coach/runs/not%20safe/{name}',headers=headers).status_code==404
        assert client.post(url,headers=headers).status_code==200
    assert len(seen)==2
    assert seen[0][1]=='/api/runs/abcdefgh/support'
    assert seen[1][1]=='/api/runs/abcdefgh/retry'
    assert all(call[0]=='POST' and call[3]=={} for call in seen)
    assert seen[0][2]==seen[1][2]
