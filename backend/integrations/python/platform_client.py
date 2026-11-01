"""Server-side reusable platform identity/ownership client for the future FastAPI integration.

Never import this client from browser code or accept owner_user_id from a request body.
The consumer module must first validate the actual logged-in user with resolve_actor.
Do not expose this SDK as an HTTP endpoint; preserve existing localhost-only boundary until
all business reads/writes enforce the verified identity.
"""
from dataclasses import dataclass
from typing import Any
import httpx


class PlatformUnavailable(RuntimeError):
    """Fail closed if the identity/owner service cannot be verified."""


@dataclass(frozen=True)
class PlatformActor:
    id: str
    tenant_id: str
    role: str
    display_name: str


class PlatformClient:
    def __init__(self, internal_url: str, module: str, service_key: str, client: httpx.AsyncClient | None = None):
        if module not in {'coach', 'review', 'daily'}:
            raise ValueError('Unrecognized module')
        if not internal_url.startswith(('http://127.0.0.1:', 'http://localhost:', 'http://platform:', 'https://')):
            raise ValueError('Use a private service URL or HTTPS')
        if len(service_key) < 32:
            raise ValueError('A per-module service key of >=32 chars is required')
        self.internal_url = internal_url.rstrip('/')
        self.module = module
        self.service_key = service_key
        self.client = client

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            if self.client:
                response = await self.client.request(method, self.internal_url + path, **kwargs)
            else:
                async with httpx.AsyncClient(timeout=3, follow_redirects=False) as client:
                    response = await client.request(method, self.internal_url + path, **kwargs)
        except httpx.HTTPError as exc:
            raise PlatformUnavailable('Platform service unavailable') from exc
        if response.status_code >= 500:
            raise PlatformUnavailable('Platform service unavailable')
        return response

    async def resolve_actor(self, cookie_header: str) -> PlatformActor:
        # Only forward the platform session cookie, never arbitrary cookies like model keys.
        sid = next((item.strip() for item in cookie_header.split(';')
                    if item.strip().startswith('medrep_sid=')), '')
        if not sid:
            raise PlatformUnavailable('User session missing')
        response = await self._request('GET', '/v1/auth/me', headers={'Cookie': sid})
        if response.status_code != 200:
            raise PlatformUnavailable('User not authenticated')
        try:
            user: dict[str, Any] = response.json()['user']
            assert isinstance(user['id'], str) and len(user['id']) == 36
            assert isinstance(user['tenant_id'], str) and user['tenant_id']
            assert user['role'] in {'employee', 'manager', 'medical_reviewer', 'admin'}
            return PlatformActor(id=user['id'], tenant_id=user['tenant_id'],
                                 role=user['role'], display_name=user.get('display_name', ''))
        except (KeyError, AssertionError, ValueError, TypeError) as exc:
            raise PlatformUnavailable('Invalid platform identity response') from exc

    def _auth_headers(self) -> dict[str, str]:
        return {'x-medrep-module': self.module, 'x-medrep-service-key': self.service_key}

    async def register_record(self, actor: PlatformActor, object_kind: str, external_ref: str) -> dict:
        response = await self._request('POST', '/v1/internal/records',
            headers=self._auth_headers(), json={'owner_user_id': actor.id,
                                               'object_kind': object_kind, 'external_ref': external_ref})
        if response.status_code not in (200, 201):
            raise PlatformUnavailable(f'Record registration rejected ({response.status_code})')
        return response.json()

    async def require_record_owner(self, actor: PlatformActor, object_kind: str, external_ref: str) -> None:
        response = await self._request('GET', '/v1/internal/records/owner', headers=self._auth_headers(),
                                      params={'object_kind': object_kind, 'external_ref': external_ref})
        if response.status_code != 200:
            raise PlatformUnavailable('Business record ownership could not be verified')
        try:
            owner = response.json()['owner_user_id']
        except (KeyError, ValueError, TypeError) as exc:
            raise PlatformUnavailable('Invalid record ownership response') from exc
        if owner != actor.id:
            raise PlatformUnavailable('Access denied to another employee record')
