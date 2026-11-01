"""Native App API: independent invitation-only local accounts + bearer sessions.

The Phase 5 Feishu cookie endpoints are unchanged. Tokens are never stored in
plaintext in the database. No public signup or password-reset endpoint exists.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
from typing import Any
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, insert, update
from sqlalchemy.exc import IntegrityError
from .db import users, sessions, states, audit, mobile_credentials
from .security import MODULES, hash_token, new_id, new_token, now

LOGIN_RE = re.compile(r'^[a-z0-9][a-z0-9._-]{2,63}$')
KEY_RE = re.compile(r'^[A-Za-z0-9_-]{1,96}$')
SALT_BYTES = 16
MAX_FAILURES = 5
LOCK_SECONDS = 15 * 60


def make_password_hash(password: str) -> str:
    if not 12 <= len(password) <= 128:
        raise ValueError('Password length must be 12 to 128 characters')
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.scrypt(password.encode('utf8'), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return 'scrypt$16384$8$1$' + base64.b64encode(salt).decode() + '$' + base64.b64encode(digest).decode()


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, n, r, p, salt, value = encoded.split('$')
        if algo != 'scrypt' or (n, r, p) != ('16384', '8', '1'):
            return False
        candidate = hashlib.scrypt(password.encode('utf8'), salt=base64.b64decode(salt),
                                   n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(candidate, base64.b64decode(value))
    except (ValueError, TypeError):
        return False

# Used for nonexistent users to reduce simple timing-based account enumeration.
DUMMY_HASH = make_password_hash("unregistered_user_password")

class FeishuCodeBody(BaseModel):
    code: str = Field(min_length=5, max_length=512)


class LoginBody(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=128)

class StateBody(BaseModel):
    value: Any
    expected_revision: int = Field(ge=0)


def attach_mobile_routes(app, settings, engine):
    def actor(request: Request):
        header = request.headers.get('authorization', '')
        if not header.startswith('Bearer ') or len(header) > 280:
            raise HTTPException(status_code=401, detail='Missing mobile access token')
        token = header[7:]
        if len(token) < 32 or not token.startswith('mr_m_'):
            raise HTTPException(status_code=401, detail='Invalid access token')
        with engine.connect() as conn:
            row = conn.execute(select(users).join(sessions, users.c.id == sessions.c.user_id)
                 .where(sessions.c.token_hash == hash_token('mobile:'+token),
                        sessions.c.revoked_at.is_(None), sessions.c.expires_at > now(),
                        users.c.status == 'active', users.c.tenant_id == settings.tenant_id)
                 ).mappings().first()
        if row is None:
            raise HTTPException(status_code=401, detail='Session expired')
        return dict(row)

    def info(u):
        return {'id':u['id'], 'display_name':u['display_name'], 'role':u['role'], 'tenant_id':u['tenant_id']}

    @app.post('/v1/mobile/auth/login')
    def mobile_login(body: LoginBody):
        username = body.username.strip().lower()
        if not LOGIN_RE.fullmatch(username):
            raise HTTPException(status_code=401, detail='Invalid login')
        failed_login = False
        with engine.begin() as conn:
            row = conn.execute(select(mobile_credentials, users.c.status, users.c.display_name, users.c.role)
              .join(users, users.c.id == mobile_credentials.c.user_id)
              .where(mobile_credentials.c.tenant_id == settings.tenant_id,
                     mobile_credentials.c.login_name == username)).mappings().first()
            if not row:
                verify_password(body.password, DUMMY_HASH)
                raise HTTPException(status_code=401, detail='Invalid login')
            stamp = now()
            if row['locked_until'] > stamp:
                raise HTTPException(status_code=429, detail='Account temporarily locked')
            ok = verify_password(body.password, row['password_hash'])
            if not ok:
                failed = row['failed_attempts'] + 1
                conn.execute(update(mobile_credentials).where(mobile_credentials.c.user_id == row['user_id']).values(
                    failed_attempts=0 if failed >= MAX_FAILURES else failed,
                    locked_until=(stamp + LOCK_SECONDS) if failed >= MAX_FAILURES else 0))
                failed_login = True
            if failed_login:
                pass  # Commit attempt counter before responding with 401.
            elif row['status'] != 'active':
                raise HTTPException(status_code=403, detail='Account disabled')
            if not failed_login:
                conn.execute(update(mobile_credentials).where(mobile_credentials.c.user_id == row['user_id'])
                            .values(failed_attempts=0, locked_until=0))
                token = 'mr_m_' + new_token()
                conn.execute(insert(sessions).values(token_hash=hash_token('mobile:'+token),
                    user_id=row['user_id'], created_at=stamp, expires_at=stamp + settings.session_ttl_seconds,
                    revoked_at=None))
                conn.execute(insert(audit).values(id=new_id(), actor_user_id=row['user_id'],
                    action='mobile.login', target_id=None, created_at=stamp))
        if failed_login:
            raise HTTPException(status_code=401, detail='Invalid login')
        return {'access_token': token, 'token_type':'Bearer',
                'expires_in': settings.session_ttl_seconds,
                'user':info({**dict(row), 'id':row['user_id'], 'tenant_id':settings.tenant_id})}

    @app.post('/v1/mobile/auth/feishu')
    async def mobile_feishu_login(body: FeishuCodeBody):
        """Server-verified Feishu H5 SSO -> existing employee's bearer identity.

        No public enrollment, no client-supplied open_id, and no credentials in the H5.
        """
        if not settings.feishu_app_id or not settings.feishu_app_secret:
            raise HTTPException(status_code=503, detail='Feishu login is not configured')
        from .feishu import FeishuIdentityError, resolve_feishu_user
        try:
            identity = await resolve_feishu_user(settings, body.code)
        except FeishuIdentityError:
            raise HTTPException(status_code=401, detail='Feishu identity verification failed')
        with engine.begin() as conn:
            row = conn.execute(select(users).where(
                users.c.tenant_id == settings.tenant_id,
                users.c.feishu_open_id == identity['open_id'],
            )).mappings().first()
            if not row or row['status'] != 'active':
                raise HTTPException(status_code=403, detail='Feishu employee not provisioned or disabled')
            stamp = now()
            token = 'mr_m_' + new_token()
            conn.execute(insert(sessions).values(
                token_hash=hash_token('mobile:' + token), user_id=row['id'],
                created_at=stamp, expires_at=stamp + settings.session_ttl_seconds,
                revoked_at=None,
            ))
            conn.execute(insert(audit).values(
                id=new_id(), actor_user_id=row['id'], action='mobile.feishu_login',
                target_id=None, created_at=stamp,
            ))
        return {'access_token': token, 'token_type': 'Bearer',
                'expires_in': settings.session_ttl_seconds, 'user': info(row)}

    @app.get('/v1/mobile/auth/me')
    def mobile_me(user=Depends(actor)):
        return {'user':info(user)}

    @app.post('/v1/mobile/auth/logout', status_code=204)
    def mobile_logout(request: Request, user=Depends(actor)):
        token = request.headers['authorization'][7:]
        with engine.begin() as conn:
            conn.execute(update(sessions).where(sessions.c.token_hash == hash_token('mobile:'+token),
                       sessions.c.user_id == user['id']).values(revoked_at=now()))
            conn.execute(insert(audit).values(id=new_id(), actor_user_id=user['id'],
                         action='mobile.logout', target_id=None, created_at=now()))

    @app.get('/v1/mobile/state/{module}/{key}')
    def mobile_state(module: str, key: str, user=Depends(actor)):
        if module not in MODULES or not KEY_RE.fullmatch(key):
            raise HTTPException(status_code=404, detail='Unknown state')
        with engine.connect() as conn:
            row = conn.execute(select(states).where(states.c.user_id == user['id'],
                 states.c.module == module, states.c.state_key == key)).mappings().first()
        if row is None:
            return {'value': None, 'revision':0}
        return {'value':json.loads(row['json_value']), 'revision':row['revision']}

    @app.put('/v1/mobile/state/{module}/{key}')
    def set_mobile_state(module: str, key: str, body: StateBody, user=Depends(actor)):
        if module not in MODULES or not KEY_RE.fullmatch(key):
            raise HTTPException(status_code=404, detail='Unknown state')
        data = json.dumps(body.value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        if len(data.encode('utf8')) > 64*1024:
            raise HTTPException(status_code=413, detail='State too large')
        with engine.begin() as conn:
            row = conn.execute(select(states).where(states.c.user_id == user['id'],
                 states.c.module == module, states.c.state_key == key)).mappings().first()
            current = row['revision'] if row else 0
            if current != body.expected_revision:
                raise HTTPException(status_code=409, detail='Revision conflict')
            if row:
                conn.execute(update(states).where(states.c.user_id == user['id'],
                     states.c.module == module, states.c.state_key == key)
                     .values(json_value=data, revision=current+1, updated_at=now()))
            else:
                try:
                    with conn.begin_nested():
                        conn.execute(insert(states).values(user_id=user['id'],module=module,
                            state_key=key,json_value=data,revision=1,updated_at=now()))
                except IntegrityError:
                    raise HTTPException(status_code=409, detail='Revision conflict')
        return {'revision':current+1}

    # All knowledge access is authenticated with the SAME employee bearer identity.
    from .learning_bridge import attach_learning_routes
    attach_learning_routes(app, actor)

    # Read-only public-source industry digest from Module 3; employee bearer required.
    from .digest_bridge import attach_daily_routes
    attach_daily_routes(app, actor)

    # Phase 9: employee-scoped Module 1 text training and previsit freeze.
    from .coach_bridge import attach_coach_routes
    attach_coach_routes(app, actor, engine)

    from .realtime_voice import attach_voice_routes
    attach_voice_routes(app, actor, settings)

    from .review_bridge import attach_review_routes
    attach_review_routes(app, actor, engine)

    from .daily_workspace import attach_daily_workspace
    attach_daily_workspace(app, actor, engine)
