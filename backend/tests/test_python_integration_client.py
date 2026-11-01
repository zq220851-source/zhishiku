import httpx
import pytest
from integrations.python.platform_client import PlatformClient, PlatformActor, PlatformUnavailable

SECRET='test_secret_must_be_long_12345678901234567890'
ACTOR=PlatformActor('11111111-1111-4111-8111-111111111111', 'test-team', 'employee', 'Alice')

@pytest.mark.asyncio
async def test_adapter_scopes_and_rejects_wrong_owner():
    seen=[]
    def handler(req):
        seen.append(req)
        if req.url.path == '/v1/auth/me':
            assert req.headers['cookie']=='medrep_sid=secret'
            return httpx.Response(200, json={'user': ACTOR.__dict__})
        if req.url.path == '/v1/internal/records' and req.method == 'POST':
            assert req.headers['x-medrep-module']=='coach'
            assert req.headers['x-medrep-service-key']==SECRET
            return httpx.Response(201, json={'created': True})
        if req.url.path == '/v1/internal/records/owner':
            return httpx.Response(200, json={'owner_user_id': 'not-current-user'})
        raise AssertionError(str(req.url))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        platform=PlatformClient('http://platform:8080','coach',SECRET,client=client)
        actor=await platform.resolve_actor('other=one; medrep_sid=secret; other2=two')
        assert actor.id==ACTOR.id
        assert (await platform.register_record(actor, 'session', 's001'))['created']
        with pytest.raises(PlatformUnavailable):
            await platform.require_record_owner(actor, 'session', 's001')
    assert len(seen)==3


@pytest.mark.asyncio
async def test_adapter_fails_closed_on_session_error():
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req: httpx.Response(401, json={'detail':'expired'}))) as client:
        platform=PlatformClient('http://platform:8080','coach',SECRET,client=client)
        with pytest.raises(PlatformUnavailable):
            await platform.resolve_actor('medrep_sid=expired')
        with pytest.raises(PlatformUnavailable):
            await platform.resolve_actor('other=value')
