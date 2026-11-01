"""Read-only production configuration preflight. Reports flags ONLY, never secret values."""
import os
import sys
from urllib.parse import urlparse, unquote


def check_environment(env):
    checks = []
    def check(label, condition, hint):
        checks.append((label, bool(condition), hint))
    origin = env.get('APP_PUBLIC_ORIGIN', '')
    db = env.get('DATABASE_URL', '')
    parsed_origin = urlparse(origin)
    try:
        origin_port = parsed_origin.port
    except ValueError:
        origin_port = -1
    public_host = parsed_origin.hostname
    domain = env.get('APP_DOMAIN', '').strip().lower()
    check('HTTPS app origin', parsed_origin.scheme == 'https' and bool(public_host) and
          public_host not in ('localhost', '127.0.0.1') and not parsed_origin.username and
          not parsed_origin.password and parsed_origin.path in ('', '/') and not parsed_origin.query and
          not parsed_origin.fragment and origin_port in (None, 443),
          'Set a path-free public HTTPS origin; reverse proxy required')
    check('Caddy hostname matches HTTPS origin', bool(domain) and domain == public_host and
          '/' not in domain and ':' not in domain and domain not in ('coach-staging.example.com', 'example.com'),
          'Set APP_DOMAIN to the actual DNS host in APP_PUBLIC_ORIGIN')
    check('Secure session cookie', env.get('COOKIE_SECURE', 'true').lower() == 'true', 'Set COOKIE_SECURE=true')
    check('PostgreSQL production database', db.startswith('postgresql+psycopg://'),
          'Use a private PostgreSQL connection, not sqlite')
    check('Tenant ID', len(env.get('PLATFORM_TENANT_ID', '').strip()) >= 4,
          'Set stable tenant ID (never infer from browser)')
    check('Feishu app configured', bool(env.get('FEISHU_APP_ID', '').strip()) and
          len(env.get('FEISHU_APP_SECRET', '').strip()) >= 16,
          'Create enterprise app and store secrets only on backend')
    password = env.get('POSTGRES_PASSWORD', '')
    check('Strong DB password (>= 24 chars)', len(password) >= 24 and len(set(password)) >= 10 and
          password not in ('CHANGE_ME_TO_LONG_RANDOM_PASSWORD',),
          'Use a long generated password in the secret file')
    parsed_db = urlparse(db)
    check('DB URL password matches database', unquote(parsed_db.password or '') == password and parsed_db.hostname == 'db',
          'Database URL must match POSTGRES_PASSWORD and private Compose db hostname')
    check('Session TTL <= 24h', env.get('SESSION_TTL_SECONDS', '28800').isdigit() and
          900 <= int(env.get('SESSION_TTL_SECONDS', '28800')) <= 86400,
          'Use session TTL between 900 and 86400 seconds')
    return checks


def main():
    checks = check_environment(os.environ)
    for name, passed, hint in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name}" + ('' if passed else f' — {hint}'))
    if not all(c[1] for c in checks):
        print('PRE-FLIGHT FAILED. Do not publish this configuration.', file=sys.stderr)
        return 2
    print('Configuration preflight passed. This does NOT verify HTTPS, database access or authorization in production.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
