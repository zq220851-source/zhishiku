"""Phase-2 trusted-backend ownership registry. Never stores business data or voice transcripts.

Internal routes MUST only be reachable behind a private network + authenticated per-module
service keys. The public user listing is scoped to the authenticated user and tenant.
"""
import re
import secrets
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, insert, select
from sqlalchemy.exc import IntegrityError

from .db import audit, record_links, users
from .security import new_id, now

REF_RE = re.compile(r'^[A-Za-z0-9_.:-]{1,128}$')
KIND_RE = re.compile(r'^[a-z][a-z0-9_]{0,31}$')
BUSINESS_MODULES = {'coach', 'review', 'daily'}


class RecordLinkCreate(BaseModel):
    owner_user_id: UUID
    object_kind: str = Field(min_length=1, max_length=32)
    external_ref: str = Field(min_length=1, max_length=128)


def _validate(kind: str, external_ref: str | None = None):
    if not KIND_RE.fullmatch(kind) or (external_ref is not None and not REF_RE.fullmatch(external_ref)):
        raise HTTPException(status_code=422, detail='Invalid business record identifier')


def attach_record_routes(app, engine, settings, current_user):
    def require_module(request: Request) -> str:
        module = request.headers.get('x-medrep-module', '')
        token = request.headers.get('x-medrep-service-key', '')
        if module not in BUSINESS_MODULES:
            raise HTTPException(status_code=403, detail='Service not authorized')
        correct = settings.module_service_keys.get(module, '')
        if not correct or len(token) > 512 or not secrets.compare_digest(token, correct):
            raise HTTPException(status_code=403, detail='Service not authorized')
        return module

    @app.post('/v1/internal/records', status_code=201)
    def link_record(body: RecordLinkCreate, module: str = Depends(require_module)):
        """Trusted module registers a record only AFTER it saved it with verified platform user id.

        Never call from mobile/browser and never send arbitrary user IDs from clients.
        """
        _validate(body.object_kind, body.external_ref)
        owner = str(body.owner_user_id)
        stamp = now()
        with engine.begin() as conn:
            active = conn.execute(select(users.c.id).where(
                users.c.id == owner, users.c.tenant_id == settings.tenant_id,
                users.c.status == 'active',
            )).scalar_one_or_none()
            if not active:
                raise HTTPException(status_code=404, detail='Active staff account not found')
            link_id = new_id()
            try:
                with conn.begin_nested():
                    conn.execute(insert(record_links).values(
                        id=link_id, tenant_id=settings.tenant_id, owner_user_id=owner,
                        source_module=module, object_kind=body.object_kind,
                        external_ref=body.external_ref, created_at=stamp,
                    ))
            except IntegrityError:
                existing = conn.execute(select(record_links).where(
                    record_links.c.tenant_id == settings.tenant_id,
                    record_links.c.source_module == module,
                    record_links.c.object_kind == body.object_kind,
                    record_links.c.external_ref == body.external_ref,
                )).mappings().first()
                if existing and existing['owner_user_id'] == owner:
                    return {'id': existing['id'], 'created': False}
                raise HTTPException(status_code=409, detail='Business record already owned by another user')
            conn.execute(insert(audit).values(
                id=new_id(), actor_user_id=owner, action='record.link',
                target_id=link_id, created_at=stamp,
            ))
        return {'id': link_id, 'created': True}

    @app.get('/v1/internal/records/owner')
    def record_owner(object_kind: str, external_ref: str, module: str = Depends(require_module)):
        _validate(object_kind, external_ref)
        with engine.connect() as conn:
            record = conn.execute(select(record_links.c.owner_user_id).where(
                record_links.c.tenant_id == settings.tenant_id,
                record_links.c.source_module == module,
                record_links.c.object_kind == object_kind,
                record_links.c.external_ref == external_ref,
            )).scalar_one_or_none()
        if record is None:
            raise HTTPException(status_code=404, detail='Business record not registered')
        return {'owner_user_id': record}

    @app.get('/v1/me/records')
    def my_records(
        module: str | None = None, object_kind: str | None = None,
        limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
        user=Depends(current_user),
    ):
        if module is not None and module not in BUSINESS_MODULES:
            raise HTTPException(status_code=422, detail='Invalid module')
        if object_kind is not None:
            _validate(object_kind)
        conditions = [record_links.c.owner_user_id == user['id'],
                      record_links.c.tenant_id == user['tenant_id']]
        if module is not None:
            conditions.append(record_links.c.source_module == module)
        if object_kind is not None:
            conditions.append(record_links.c.object_kind == object_kind)
        with engine.connect() as conn:
            records = conn.execute(select(record_links).where(and_(*conditions))
                .order_by(record_links.c.created_at.desc(), record_links.c.id.desc())
                .limit(limit).offset(offset)).mappings().all()
        return {'items': [{k: row[k] for k in ('id', 'source_module', 'object_kind', 'external_ref', 'created_at')}
                          for row in records], 'limit': limit, 'offset': offset}

    @app.get('/v1/me/records/{record_id}')
    def my_record(record_id: UUID, user=Depends(current_user)):
        with engine.connect() as conn:
            record = conn.execute(select(record_links).where(
                record_links.c.id == str(record_id),
                record_links.c.owner_user_id == user['id'],
                record_links.c.tenant_id == user['tenant_id'],
            )).mappings().first()
        if not record:
            raise HTTPException(status_code=404, detail='Business record not found')
        return {k: record[k] for k in ('id', 'source_module', 'object_kind', 'external_ref', 'created_at')}
