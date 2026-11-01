"""Restricted platform service: Feishu login, staff profile, role and owner-scoped small state.

Not a replacement for any existing MedRep business database or endpoint.
"""

import json
import re
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, update, insert, delete, text
from sqlalchemy.exc import IntegrityError

from .config import Settings, load_settings
from .db import engine_for, ensure_schema, users, sessions, states, audit
from .feishu import FeishuIdentityError, resolve_feishu_user
from .security import hash_token, new_id, new_token, now, MODULES, ROLES
from .records import attach_record_routes
from .teams import attach_team_routes
from .mobile_auth import attach_mobile_routes
from fastapi.middleware.cors import CORSMiddleware

COOKIE = 'medrep_sid'
KEY_RE = re.compile(r'^[A-Za-z0-9_-]{1,96}$')


class CodeRequest(BaseModel):
    code: str = Field(min_length=5, max_length=512)


class StateUpdate(BaseModel):
    value: Any
    expected_revision: int = Field(ge=0)


class StaffProvision(BaseModel):
    feishu_open_id: str = Field(pattern=r'^ou_[A-Za-z0-9_-]{1,125}$')
    display_name: str = Field(min_length=1, max_length=128)
    role: str = 'employee'


class StaffChange(BaseModel):
    role: str | None = None
    status: str | None = None


def make_app(settings: Settings | None = None, engine=None) -> FastAPI:
    settings = settings or load_settings()
    engine = engine or engine_for(settings.database_url)

    @asynccontextmanager
    async def startup(app: FastAPI):
        ensure_schema(engine)
        yield

    app = FastAPI(title='MedRep Platform API', docs_url=None, redoc_url=None, openapi_url=None, lifespan=startup)
    app.state.engine = engine
    # Only configured web/native origins may call Bearer-token mobile endpoints.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.mobile_origins),
        allow_credentials=False,
        allow_methods=['GET', 'POST', 'PUT', 'OPTIONS'],
        allow_headers=['Authorization', 'Content-Type'],
    )
    attach_mobile_routes(app, settings, engine)

    @app.middleware('http')
    async def private_api_no_store(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith('/v1/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    def forbid_cross_site(request: Request) -> None:
        """Only same-origin browser POST/PUT/DELETE, except explicit Authorization bearer clients."""
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return
        if request.headers.get('origin') != settings.app_origin:
            raise HTTPException(status_code=403, detail='Origin rejected')
        if request.headers.get('sec-fetch-site', 'same-origin') == 'cross-site':
            raise HTTPException(status_code=403, detail='Cross-site request rejected')

    def current_user(request: Request) -> dict:
        # Browser sessions are cookie-only. Never accept the cookie token in a
        # client-supplied Authorization header or bypass same-origin checks.
        raw = request.cookies.get(COOKIE, '')
        if len(raw) < 32 or len(raw) > 256:
            raise HTTPException(status_code=401, detail='Not authenticated')
        with engine.connect() as conn:
            row = conn.execute(
                select(users).join(sessions, users.c.id == sessions.c.user_id).where(
                    sessions.c.token_hash == hash_token(raw), sessions.c.revoked_at.is_(None),
                    sessions.c.expires_at > now(), users.c.status == 'active',
                )
            ).mappings().first()
        if not row:
            raise HTTPException(status_code=401, detail='Session expired or account disabled')
        return dict(row)

    def profile(row):
        return {'id': row['id'], 'display_name': row['display_name'], 'role': row['role'], 'tenant_id': row['tenant_id']}

    def state_location(module, key):
        if module not in MODULES or not KEY_RE.fullmatch(key):
            raise HTTPException(status_code=404, detail='Unknown state namespace')

    @app.get('/healthz')
    def healthz():
        return {'status': 'ok'}

    @app.get('/readyz')
    def readyz():
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        return {'status': 'ready'}

    @app.post('/v1/auth/feishu/exchange')
    async def exchange(request: Request, response: Response, body: CodeRequest):
        forbid_cross_site(request)
        try:
            verified = await resolve_feishu_user(settings, body.code)
        except FeishuIdentityError:
            # Do not leak credentials, tokens or raw identity provider errors.
            raise HTTPException(status_code=401, detail='Feishu identity verification failed')
        # Explicit admin provisioning only; never auto-grant employee/admin rights from client input.
        with engine.begin() as conn:
            row = conn.execute(select(users).where(
                users.c.feishu_open_id == verified['open_id'],
                users.c.tenant_id == settings.tenant_id, users.c.status == 'active',
            )).mappings().first()
            if not row:
                raise HTTPException(status_code=403, detail='This staff account is not enabled')
            token = new_token()
            stamp = now()
            conn.execute(insert(sessions).values(
                token_hash=hash_token(token), user_id=row['id'],
                created_at=stamp, expires_at=stamp + settings.session_ttl_seconds,
                revoked_at=None,
            ))
            conn.execute(insert(audit).values(
                id=new_id(), actor_user_id=row['id'], action='auth.login', target_id=None, created_at=stamp,
            ))
        response.set_cookie(
            COOKIE, token, httponly=True, secure=settings.cookie_secure,
            samesite='lax', path='/', max_age=settings.session_ttl_seconds,
        )
        response.headers['Cache-Control'] = 'no-store'
        return {'user': profile(row), 'expires_in': settings.session_ttl_seconds}

    @app.get('/v1/auth/me')
    def me(user=Depends(current_user)):
        return {'user': profile(user)}

    @app.post('/v1/auth/logout', status_code=204)
    def logout(request: Request, response: Response, user=Depends(current_user)):
        forbid_cross_site(request)
        raw = request.cookies.get(COOKIE, '')
        with engine.begin() as conn:
            conn.execute(update(sessions).where(
                sessions.c.token_hash == hash_token(raw), sessions.c.user_id == user['id']
            ).values(revoked_at=now()))
            conn.execute(insert(audit).values(
                id=new_id(), actor_user_id=user['id'], action='auth.logout', target_id=None, created_at=now(),
            ))
        response.delete_cookie(COOKIE, path='/', secure=settings.cookie_secure, httponly=True, samesite='lax')

    @app.post('/v1/auth/logout-all', status_code=204)
    def logout_everywhere(request: Request, response: Response, user=Depends(current_user)):
        forbid_cross_site(request)
        stamp = now()
        with engine.begin() as conn:
            conn.execute(update(sessions).where(
                sessions.c.user_id == user['id'], sessions.c.revoked_at.is_(None)
            ).values(revoked_at=stamp))
            conn.execute(insert(audit).values(
                id=new_id(), actor_user_id=user['id'], action='auth.revoke_all',
                target_id=None, created_at=stamp,
            ))
        response.delete_cookie(COOKIE, path='/', secure=settings.cookie_secure, httponly=True, samesite='lax')

    @app.get('/v1/admin/users')
    def list_staff(user=Depends(current_user)):
        if user['role'] != 'admin':
            raise HTTPException(status_code=403, detail='Admin access required')
        with engine.connect() as conn:
            rows = conn.execute(select(users).where(users.c.tenant_id == user['tenant_id']).order_by(
                users.c.created_at.desc()
            )).mappings().all()
        return {'users': [dict(id=row['id'], feishu_open_id=row['feishu_open_id'],
                               display_name=row['display_name'], role=row['role'], status=row['status']) for row in rows]}

    @app.post('/v1/admin/users', status_code=201)
    def create_staff(body: StaffProvision, request: Request, user=Depends(current_user)):
        forbid_cross_site(request)
        if user['role'] != 'admin':
            raise HTTPException(status_code=403, detail='Admin access required')
        if body.role not in ROLES:
            raise HTTPException(status_code=422, detail='Invalid role')
        staff_id, stamp = new_id(), now()
        with engine.begin() as conn:
            try:
                with conn.begin_nested():
                    conn.execute(insert(users).values(
                        id=staff_id, tenant_id=user['tenant_id'], feishu_open_id=body.feishu_open_id,
                        display_name=body.display_name, role=body.role, status='active',
                        created_at=stamp, updated_at=stamp,
                    ))
            except IntegrityError:
                raise HTTPException(status_code=409, detail='Staff identity already exists')
            conn.execute(insert(audit).values(
                id=new_id(), actor_user_id=user['id'], action='staff.provision',
                target_id=staff_id, created_at=stamp,
            ))
        return {'user': {'id': staff_id, 'role': body.role, 'status': 'active'}}

    @app.patch('/v1/admin/users/{staff_id}')
    def change_staff(staff_id: str, body: StaffChange, request: Request, user=Depends(current_user)):
        forbid_cross_site(request)
        if user['role'] != 'admin':
            raise HTTPException(status_code=403, detail='Admin access required')
        if staff_id == user['id']:
            raise HTTPException(status_code=403, detail='Admin cannot change their own status or role')
        if (body.role is not None and body.role not in ROLES) or (
            body.status is not None and body.status not in {'active', 'disabled'}
        ):
            raise HTTPException(status_code=422, detail='Invalid role or status')
        values = {'updated_at': now()}
        if body.role is not None:
            values['role'] = body.role
        if body.status is not None:
            values['status'] = body.status
        with engine.begin() as conn:
            result = conn.execute(update(users).where(
                users.c.id == staff_id, users.c.tenant_id == user['tenant_id']
            ).values(**values))
            if result.rowcount != 1:
                raise HTTPException(status_code=404, detail='Staff account not found')
            # Role or status changes invalidate every existing session of this staff account.
            conn.execute(update(sessions).where(
                sessions.c.user_id == staff_id, sessions.c.revoked_at.is_(None)
            ).values(revoked_at=now()))
            conn.execute(insert(audit).values(
                id=new_id(), actor_user_id=user['id'], action='staff.update',
                target_id=staff_id, created_at=now(),
            ))
        return {'ok': True}

    @app.get('/v1/me/state/{module}/{key}')
    def read_state(module: str, key: str, user=Depends(current_user)):
        state_location(module, key)
        with engine.connect() as conn:
            row = conn.execute(select(states).where(
                states.c.user_id == user['id'], states.c.module == module, states.c.state_key == key,
            )).mappings().first()
        if row is None:
            raise HTTPException(status_code=404, detail='No saved state')
        return {'value': json.loads(row['json_value']), 'revision': row['revision'], 'updated_at': row['updated_at']}

    @app.put('/v1/me/state/{module}/{key}')
    def write_state(module: str, key: str, body: StateUpdate, request: Request, user=Depends(current_user)):
        forbid_cross_site(request)
        state_location(module, key)
        encoded = json.dumps(body.value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        if len(encoded.encode('utf-8')) > 64 * 1024:
            raise HTTPException(status_code=413, detail='State exceeds 64 KB')
        stamp = now()
        with engine.begin() as conn:
            if body.expected_revision == 0:
                try:
                    # Use savepoint: failed insert must not poison surrounding PG transaction.
                    with conn.begin_nested():
                        conn.execute(insert(states).values(
                            user_id=user['id'], module=module, state_key=key, json_value=encoded,
                            revision=1, updated_at=stamp,
                        ))
                    next_revision = 1
                except IntegrityError:
                    raise HTTPException(status_code=409, detail='State was already created')
            else:
                result = conn.execute(update(states).where(
                    states.c.user_id == user['id'], states.c.module == module,
                    states.c.state_key == key, states.c.revision == body.expected_revision,
                ).values(json_value=encoded, revision=body.expected_revision + 1, updated_at=stamp))
                if result.rowcount != 1:
                    raise HTTPException(status_code=409, detail='State revision mismatch')
                next_revision = body.expected_revision + 1
            conn.execute(insert(audit).values(
                id=new_id(), actor_user_id=user['id'], action='state.write',
                target_id=f'{module}/{key}', created_at=stamp,
            ))
        return {'revision': next_revision, 'updated_at': stamp}

    @app.delete('/v1/me/state/{module}/{key}', status_code=204)
    def delete_state(module: str, key: str, request: Request, user=Depends(current_user)):
        forbid_cross_site(request)
        state_location(module, key)
        with engine.begin() as conn:
            conn.execute(delete(states).where(
                states.c.user_id == user['id'], states.c.module == module,
                states.c.state_key == key,
            ))
            conn.execute(insert(audit).values(
                id=new_id(), actor_user_id=user['id'], action='state.delete',
                target_id=f'{module}/{key}', created_at=now(),
            ))

    attach_record_routes(app, engine, settings, current_user)
    attach_team_routes(app, engine, current_user, forbid_cross_site)
    return app


app = None  # ASGI exported by platform_core.server, not imported at module load in tests.
