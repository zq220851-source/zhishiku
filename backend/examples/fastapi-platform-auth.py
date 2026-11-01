"""Integration TEMPLATE only; not wired into V2 module1_source/asgi.py.

Use with FastAPI Depends(require_platform_user). Keep existing localhost restrictions
until every sensitive endpoint has proper identity and tenant-owner checks.
"""
import os
import httpx
from fastapi import HTTPException, Request


def require_platform_user(request: Request):
    base = os.getenv('PLATFORM_INTERNAL_URL')
    if not base:
        raise HTTPException(status_code=503, detail='Identity gateway not configured')
    sid = request.cookies.get('medrep_sid')
    if not sid:
        raise HTTPException(status_code=401, detail='Login required')
    try:
        with httpx.Client(timeout=3.0) as http:
            resp = http.get(base.rstrip('/') + '/v1/auth/me', cookies={'medrep_sid': sid})
        resp.raise_for_status()
        user = resp.json()['user']
        if not user.get('id') or not user.get('tenant_id'):
            raise ValueError('Missing identity')
        return user
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail='Login required')
