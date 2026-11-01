"""Create a new private .env for staging; no secrets printed and no overwrite.

Usage: python scripts/init_staging_env.py --domain coach.example.cn --tenant-id org-coach
Then manually enter FEISHU_APP_ID and FEISHU_APP_SECRET in .env on the SERVER.
"""
import argparse
import os
import re
import secrets
from pathlib import Path


HOST_RE = re.compile(r'^(?=.{4,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])$')
TENANT_RE = re.compile(r'^[A-Za-z0-9_-]{4,64}$')


def create_env(destination: Path, *, domain: str, tenant_id: str):
    if (not HOST_RE.fullmatch(domain) or '.' not in domain or '..' in domain or
        domain.endswith('.example.com') or domain.endswith('.example.cn') or domain in ('localhost',)):
        raise ValueError('Provide your actual public DNS hostname, not a placeholder')
    if not TENANT_RE.fullmatch(tenant_id):
        raise ValueError('tenant-id must have 4-64 letters, numbers, hyphen, underscores')
    password = secrets.token_urlsafe(36)
    body = '\n'.join([
        '# Generated private STAGING configuration. Do not commit or share.',
        'POSTGRES_DB=medrep_platform',
        'POSTGRES_USER=medrep_app',
        f'POSTGRES_PASSWORD={password}',
        f'DATABASE_URL=postgresql+psycopg://medrep_app:{password}@db:5432/medrep_platform',
        f'APP_PUBLIC_ORIGIN=https://{domain}',
        f'APP_DOMAIN={domain}',
        'COOKIE_SECURE=true',
        'SESSION_TTL_SECONDS=28800',
        f'PLATFORM_TENANT_ID={tenant_id}',
        '# Fill these only in your controlled secrets environment after creating the enterprise app.',
        'FEISHU_APP_ID=',
        'FEISHU_APP_SECRET=',
        '# No module is enabled until explicitly connected and credentialed.',
        'COACH_SERVICE_KEY=',
        'REVIEW_SERVICE_KEY=',
        'DAILY_SERVICE_KEY=',
        '',
    ])
    # Exclusive creation prevents overwriting manually maintained secrets.
    with destination.open('x', encoding='utf-8') as handle:
        os.chmod(destination, 0o600)
        handle.write(body)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', required=True)
    parser.add_argument('--tenant-id', required=True)
    parser.add_argument('--output', default='.env')
    args = parser.parse_args()
    create_env(Path(args.output), domain=args.domain.lower(), tenant_id=args.tenant_id)
    print(f'Created private staging config at {args.output}; secrets have NOT been displayed.')
    print('Fill in Feishu app credentials securely, run preflight, then configure DNS/HTTPS.')


if __name__ == '__main__':
    main()
