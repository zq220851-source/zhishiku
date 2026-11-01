"""Server-side code verification only. Never accept caller-supplied open_id as proof of login."""

import httpx


class FeishuIdentityError(Exception):
    pass


async def _json(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> dict:
    try:
        response = await client.request(method, url, **kwargs)
        response.raise_for_status()
        data = response.json()
        if data.get('code') != 0:
            raise FeishuIdentityError('Feishu did not accept the authorization request')
        # Feishu app_access_token/internal uses top-level fields, while authen/v1
        # endpoints generally return fields under `data`. Support both shapes.
        inner = data.get('data')
        return inner if isinstance(inner, dict) else data
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise FeishuIdentityError('Could not verify Feishu identity') from exc


async def resolve_feishu_user(settings, code: str) -> dict:
    """Feishu H5 temporary auth code -> verified open_id; no code or token ever logged."""
    if not settings.feishu_app_id or not settings.feishu_app_secret:
        raise FeishuIdentityError('Feishu app is not configured')
    base = settings.feishu_api_base
    async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
        app_data = await _json(
            client, 'POST', f'{base}/open-apis/auth/v3/app_access_token/internal',
            json={'app_id': settings.feishu_app_id, 'app_secret': settings.feishu_app_secret},
        )
        app_access_token = app_data.get('app_access_token')
        if not isinstance(app_access_token, str) or not app_access_token:
            raise FeishuIdentityError('Missing Feishu application token')
        token_data = await _json(
            client, 'POST', f'{base}/open-apis/authen/v1/access_token',
            headers={'Authorization': f'Bearer {app_access_token}'},
            json={'grant_type': 'authorization_code', 'code': code},
        )
        user_access_token = token_data.get('access_token')
        if not isinstance(user_access_token, str) or not user_access_token:
            raise FeishuIdentityError('Missing Feishu user token')
        identity = await _json(
            client, 'GET', f'{base}/open-apis/authen/v1/user_info',
            headers={'Authorization': f'Bearer {user_access_token}'},
        )
        open_id = identity.get('open_id')
        if not isinstance(open_id, str) or not open_id.startswith('ou_'):
            raise FeishuIdentityError('Feishu identity missing stable open_id')
        return {'open_id': open_id, 'name': str(identity.get('name') or '')[:128]}
