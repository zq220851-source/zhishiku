"""Manual allowlisting: a verified Feishu open_id is the only login identifier.

Usage:
 python -m platform_core.cli provision --tenant-id company --open-id ou_... --name ... --role employee
 python -m platform_core.cli disable --tenant-id company --open-id ou_...
"""
import argparse
from sqlalchemy import select, insert, update
from .config import load_settings
from .db import engine_for, users, audit, sessions, ensure_schema
from .security import new_id, now, ROLES


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    add = sub.add_parser('provision')
    add.add_argument('--tenant-id', required=True)
    add.add_argument('--open-id', required=True)
    add.add_argument('--name', required=True)
    add.add_argument('--role', choices=sorted(ROLES), default='employee')
    dis = sub.add_parser('disable')
    dis.add_argument('--tenant-id', required=True)
    dis.add_argument('--open-id', required=True)
    args = parser.parse_args()
    if not args.open_id.startswith('ou_'):
        parser.error('Expected verified Feishu open_id beginning with ou_')
    engine = engine_for(load_settings().database_url)
    ensure_schema(engine)
    stamp = now()
    with engine.begin() as conn:
        row = conn.execute(select(users).where(users.c.tenant_id == args.tenant_id,
                                                users.c.feishu_open_id == args.open_id)).mappings().first()
        if args.action == 'disable':
            if row is None:
                parser.error('Account not found')
            conn.execute(update(users).where(users.c.id == row['id']).values(status='disabled', updated_at=stamp))
            action, user_id = 'admin.disable', row['id']
        else:
            if row:
                conn.execute(update(users).where(users.c.id == row['id']).values(
                    display_name=args.name[:128], role=args.role, status='active', updated_at=stamp))
                user_id = row['id']
            else:
                user_id = new_id()
                conn.execute(insert(users).values(id=user_id, tenant_id=args.tenant_id,
                    feishu_open_id=args.open_id, display_name=args.name[:128], role=args.role,
                    status='active', created_at=stamp, updated_at=stamp))
            action = 'admin.provision'
        if args.action == 'disable' or row:
            # Existing browser sessions must not survive role/status updates.
            conn.execute(update(sessions).where(
                sessions.c.user_id == user_id, sessions.c.revoked_at.is_(None)
            ).values(revoked_at=stamp))
        conn.execute(insert(audit).values(id=new_id(), actor_user_id=None,
                    action=action, target_id=user_id, created_at=stamp))
    print(f'{action}: user_id={user_id}')


if __name__ == '__main__':
    main()
