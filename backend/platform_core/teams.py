"""Explicit organizational membership with no implied access to employee business records."""
from uuid import UUID
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, insert, delete, update
from sqlalchemy.exc import IntegrityError

from .db import audit, users, teams, team_members
from .security import new_id, now


class NewTeam(BaseModel):
    name: str = Field(min_length=2, max_length=128)


class NewMembership(BaseModel):
    user_id: UUID
    team_role: str = 'member'


def attach_team_routes(app, engine, current_user, forbid_cross_site):
    def admin_required(user):
        if user['role'] != 'admin':
            raise HTTPException(status_code=403, detail='Admin access required')

    @app.post('/v1/admin/teams', status_code=201)
    def create_team(body: NewTeam, request: Request, user=Depends(current_user)):
        forbid_cross_site(request)
        admin_required(user)
        if not body.name.strip():
            raise HTTPException(status_code=422, detail='Team name must not be blank')
        team_id, timestamp = new_id(), now()
        with engine.begin() as conn:
            conn.execute(insert(teams).values(id=team_id, tenant_id=user['tenant_id'],
                                              name=body.name.strip(), created_at=timestamp))
            conn.execute(insert(audit).values(id=new_id(), actor_user_id=user['id'],
                                              action='team.create', target_id=team_id, created_at=timestamp))
        return {'id': team_id, 'name': body.name.strip()}

    @app.get('/v1/admin/teams')
    def list_teams(user=Depends(current_user)):
        admin_required(user)
        with engine.connect() as conn:
            rows = conn.execute(select(teams).where(teams.c.tenant_id == user['tenant_id'])
                                .order_by(teams.c.created_at)).mappings().all()
        return {'teams': [{'id': row['id'], 'name': row['name']} for row in rows]}

    @app.put('/v1/admin/teams/{team_id}/members', status_code=200)
    def upsert_member(team_id: UUID, body: NewMembership, request: Request, user=Depends(current_user)):
        forbid_cross_site(request)
        admin_required(user)
        if body.team_role not in ('member', 'lead'):
            raise HTTPException(status_code=422, detail='Invalid team role')
        team_id, member_id = str(team_id), str(body.user_id)
        with engine.begin() as conn:
            exists = conn.execute(select(teams.c.id).where(teams.c.id == team_id,
                teams.c.tenant_id == user['tenant_id'])).scalar_one_or_none()
            member = conn.execute(select(users.c.id).where(users.c.id == member_id,
                users.c.tenant_id == user['tenant_id'], users.c.status == 'active')).scalar_one_or_none()
            if not exists or not member:
                raise HTTPException(status_code=404, detail='Team or active employee not found')
            updated = conn.execute(update(team_members).where(team_members.c.team_id == team_id,
                team_members.c.user_id == member_id).values(team_role=body.team_role))
            if updated.rowcount == 0:
                try:
                    with conn.begin_nested():
                        conn.execute(insert(team_members).values(team_id=team_id, user_id=member_id,
                                         team_role=body.team_role, created_at=now()))
                except IntegrityError:
                    # Concurrent team assignment; no privilege escalation, fail so caller retries.
                    raise HTTPException(status_code=409, detail='Membership updated concurrently')
            conn.execute(insert(audit).values(id=new_id(), actor_user_id=user['id'],
                action='team.assign', target_id=team_id, created_at=now()))
        return {'team_id': team_id, 'user_id': member_id, 'team_role': body.team_role}

    @app.delete('/v1/admin/teams/{team_id}/members/{member_id}', status_code=204)
    def remove_member(team_id: UUID, member_id: UUID, request: Request, user=Depends(current_user)):
        forbid_cross_site(request)
        admin_required(user)
        with engine.begin() as conn:
            exists = conn.execute(select(teams.c.id).where(teams.c.id == str(team_id),
                teams.c.tenant_id == user['tenant_id'])).scalar_one_or_none()
            if not exists:
                raise HTTPException(status_code=404, detail='Team not found')
            conn.execute(delete(team_members).where(team_members.c.team_id == str(team_id),
                team_members.c.user_id == str(member_id)))
            conn.execute(insert(audit).values(id=new_id(), actor_user_id=user['id'],
                action='team.remove', target_id=str(team_id), created_at=now()))

    @app.get('/v1/me/teams')
    def my_teams(user=Depends(current_user)):
        with engine.connect() as conn:
            rows = conn.execute(select(teams.c.id, teams.c.name, team_members.c.team_role)
                .join(team_members, teams.c.id == team_members.c.team_id)
                .where(teams.c.tenant_id == user['tenant_id'], team_members.c.user_id == user['id'])
                .order_by(teams.c.name)).mappings().all()
        return {'teams': [dict(row) for row in rows]}

    @app.get('/v1/teams/{team_id}/members')
    def team_roster(team_id: UUID, user=Depends(current_user)):
        team_id = str(team_id)
        with engine.connect() as conn:
            team = conn.execute(select(teams.c.id).where(teams.c.id == team_id,
                teams.c.tenant_id == user['tenant_id'])).scalar_one_or_none()
            if not team:
                raise HTTPException(status_code=404, detail='Team not found')
            is_lead = conn.execute(select(team_members.c.user_id).where(
                team_members.c.team_id == team_id,
                team_members.c.user_id == user['id'],
                team_members.c.team_role == 'lead')).scalar_one_or_none()
            if user['role'] != 'admin' and not (user['role'] == 'manager' and is_lead):
                raise HTTPException(status_code=403, detail='Team roster access denied')
            rows = conn.execute(select(users.c.id, users.c.display_name,
                users.c.role, team_members.c.team_role)
                .join(team_members, users.c.id == team_members.c.user_id)
                .where(team_members.c.team_id == team_id, users.c.tenant_id == user['tenant_id'],
                       users.c.status == 'active')
                .order_by(users.c.display_name)).mappings().all()
        return {'members': [dict(row) for row in rows]}
