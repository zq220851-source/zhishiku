import os
from urllib.parse import urlparse
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    database_url: str
    app_origin: str
    tenant_id: str
    feishu_app_id: str
    feishu_app_secret: str
    cookie_secure: bool
    session_ttl_seconds: int
    feishu_api_base: str
    module_service_keys: dict[str, str] = field(default_factory=dict)
    mobile_origins: tuple[str, ...] = ("capacitor://localhost", "http://localhost", "http://localhost:5173")


def load_settings() -> Settings:
    url = os.environ.get('DATABASE_URL', '')
    if not url:
        raise RuntimeError('DATABASE_URL is required; run Alembic migrations before starting')
    origin = os.environ.get('APP_PUBLIC_ORIGIN', '').rstrip('/')
    if not origin or not (origin.startswith('https://') or origin.startswith('http://localhost:') or origin == 'http://localhost'):
        raise RuntimeError('APP_PUBLIC_ORIGIN must be an HTTPS origin (or localhost for local dev)')
    parsed = urlparse(origin)
    if (parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password or
        parsed.path not in ('', '/') or parsed.query or parsed.fragment or parsed.params):
        raise RuntimeError('APP_PUBLIC_ORIGIN must be a strict origin without path, query or credentials')
    if parsed.scheme == 'http' and parsed.hostname != 'localhost':
        raise RuntimeError('Only localhost may use HTTP')
    if parsed.scheme == 'https' and not url.startswith('postgresql+psycopg://'):
        raise RuntimeError('Public HTTPS deployment requires PostgreSQL, not SQLite')
    secure = os.environ.get('COOKIE_SECURE', 'true').lower() == 'true'
    if not secure and not origin.startswith('http://localhost'):
        raise RuntimeError('COOKIE_SECURE=false is allowed only for localhost development')
    tenant = os.environ.get('PLATFORM_TENANT_ID', '')
    if not tenant:
        raise RuntimeError('PLATFORM_TENANT_ID is required to bind Feishu users to one organization')
    service_keys = {
        module: os.environ.get(f'{module.upper()}_SERVICE_KEY', '').strip()
        for module in ('coach', 'review', 'daily')
    }
    for module, key in service_keys.items():
        if key and len(key) < 32:
            raise RuntimeError(f'{module.upper()}_SERVICE_KEY must be at least 32 characters')
    feishu_id = os.environ.get('FEISHU_APP_ID', '').strip()
    feishu_secret = os.environ.get('FEISHU_APP_SECRET', '').strip()
    if bool(feishu_id) != bool(feishu_secret):
        raise RuntimeError('FEISHU_APP_ID and FEISHU_APP_SECRET must be provided together')
    return Settings(
        database_url=url,
        app_origin=origin,
        tenant_id=os.environ.get('PLATFORM_TENANT_ID', ''),
        feishu_app_id=feishu_id,
        feishu_app_secret=feishu_secret,
        cookie_secure=secure,
        session_ttl_seconds=min(max(int(os.environ.get('SESSION_TTL_SECONDS', '28800')), 900), 86400),
        feishu_api_base='https://open.feishu.cn',
        module_service_keys={k: v for k, v in service_keys.items() if v},
        mobile_origins=tuple(x.strip() for x in os.environ.get(
            "MOBILE_ALLOWED_ORIGINS", "capacitor://localhost,http://localhost,http://localhost:5173"
        ).split(",") if x.strip()),
    )
