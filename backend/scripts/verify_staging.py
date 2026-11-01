"""Unauthenticated external smoke test: verify HTTPS, auth boundary and internal-route lockdown.

Exits nonzero on failure. No credentials or real staff data are ever transmitted.
Usage: python scripts/verify_staging.py https://coach-staging.example.com
"""
import argparse
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def validate_base(base: str) -> str:
    parsed = urlparse(base)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
        or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
        raise ValueError('Provide a public HTTPS origin only (https://host), no paths or credentials')
    if parsed.hostname in ('localhost', '127.0.0.1'):
        raise ValueError('A public staging HTTPS hostname is required')
    return base.rstrip('/')


def probe(base: str, path: str, timeout: int = 8) -> tuple[int, dict]:
    request = Request(base + path, headers={'User-Agent': 'medrep-staging-smoke/1.0'})
    try:
        with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as result:
            return result.status, dict(result.headers.items())
    except HTTPError as exc:
        return exc.code, dict(exc.headers.items())


def assess(get):
    tests = [
        ('HTTPS public health endpoint', '/healthz', 200),
        ('No anonymous account profile', '/v1/auth/me', 401),
        ('No anonymous personal records', '/v1/me/records', 401),
        ('No anonymous team roster', '/v1/teams/11111111-1111-4111-8111-111111111111/members', 401),
        ('Internal service route hidden', '/v1/internal/records/owner?object_kind=session&external_ref=none', 404),
        ('Database readiness not public', '/readyz', 404),
        ('Unknown API endpoint stays private', '/v1/hidden-resource', 404),
    ]
    failures = []
    for name, path, wanted in tests:
        try:
            status, headers = get(path)
            passed = status == wanted
            # Profile and records responses contain no-store regardless of their status.
            if path in ('/v1/auth/me', '/v1/me/records') or path.startswith('/v1/teams/'):
                lower_headers = {k.lower(): str(v) for k, v in headers.items()}
                passed = passed and 'no-store' in lower_headers.get('cache-control', '').lower()
            print(f'{"PASS" if passed else "FAIL"}  {name} (HTTP {status}; expected {wanted})')
            if not passed:
                failures.append(name)
        except (URLError, TimeoutError, OSError) as exc:
            failures.append(name)
            print(f'FAIL  {name}: network/TLS error: {type(exc).__name__}')
    return not failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('origin')
    args = parser.parse_args()
    try:
        origin = validate_base(args.origin)
    except ValueError as exc:
        parser.error(str(exc))
    ok = assess(lambda p: probe(origin, p))
    print('Staging edge smoke tests passed (not a full business-system acceptance test).' if ok else
          'Staging edge smoke tests FAILED. Do not onboard real users.')
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
