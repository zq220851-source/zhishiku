"""Prune expired or long-revoked sessions without deleting active sessions.

Default is read-only. On --apply, clean old sessions in a single DB transaction.
This is not a substitute for audit retention, GDPR compliance, or session invalidation.
"""
import argparse
from sqlalchemy import delete, func, or_, select
from platform_core.config import load_settings
from platform_core.db import sessions, engine_for, ensure_schema
from platform_core.security import now


def prune_sessions(engine, *, apply: bool = False, retention_days: int = 30, timestamp: int | None = None):
    if not 1 <= retention_days <= 3650:
        raise ValueError('retention_days out of range')
    stamp = now() if timestamp is None else timestamp
    cutoff = stamp - retention_days * 86400
    eligible = or_(sessions.c.expires_at <= cutoff,
                   (sessions.c.revoked_at.is_not(None)) & (sessions.c.revoked_at <= cutoff))
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(sessions).where(eligible)).scalar_one()
        if apply:
            conn.execute(delete(sessions).where(eligible))
    return int(count)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--retention-days', type=int, default=30)
    args = parser.parse_args()
    engine = engine_for(load_settings().database_url)
    ensure_schema(engine)
    count = prune_sessions(engine, apply=args.apply, retention_days=args.retention_days)
    print(f'{"Deleted" if args.apply else "Would delete"} {count} expired/revoked old session(s).')
    if not args.apply:
        print('DRY RUN. Add --apply after review.')


if __name__ == '__main__':
    main()
