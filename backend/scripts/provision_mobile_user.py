"""Operator-only CLI for invite-only standalone app accounts. Never exposed as HTTP."""
import argparse
import getpass
import os
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from platform_core.config import load_settings
from platform_core.db import engine_for, ensure_schema, users, mobile_credentials
from platform_core.mobile_auth import LOGIN_RE, make_password_hash
from platform_core.security import ROLES, new_id, now


def provision(engine, tenant, username, display_name, role, password):
    username = username.strip().lower()
    if not LOGIN_RE.fullmatch(username):
        raise ValueError('Username: 3-64 lowercase letters, digits, dot, hyphen, underscore')
    if role not in ROLES:
        raise ValueError('Unknown role')
    if not 1 <= len(display_name) <= 128:
        raise ValueError('Invalid display name')
    pwd = make_password_hash(password)
    user_id, ts = new_id(), now()
    with engine.begin() as conn:
        if conn.execute(select(mobile_credentials.c.user_id).where(
                mobile_credentials.c.tenant_id == tenant,
                mobile_credentials.c.login_name == username)).first():
            raise ValueError('Login already exists')
        conn.execute(insert(users).values(id=user_id,tenant_id=tenant,feishu_open_id=None,
            display_name=display_name,role=role,status='active',created_at=ts,updated_at=ts))
        conn.execute(insert(mobile_credentials).values(user_id=user_id,tenant_id=tenant,
            login_name=username,password_hash=pwd,failed_attempts=0,locked_until=0))
    return user_id

if __name__ == '__main__':
    ap=argparse.ArgumentParser(description='Create an invitation-only mobile staff account')
    ap.add_argument('--username', required=True)
    ap.add_argument('--display-name', required=True)
    ap.add_argument('--role', choices=sorted(ROLES), default='employee')
    args=ap.parse_args()
    settings=load_settings()
    engine=engine_for(settings.database_url)
    ensure_schema(engine)
    password=getpass.getpass('New password (12-128 chars, will not echo): ')
    confirm=getpass.getpass('Confirm password: ')
    if password != confirm:
        raise SystemExit('Passwords do not match')
    print('Created user ID:',provision(engine,settings.tenant_id,args.username,args.display_name,args.role,password))
