import hashlib
import secrets
import time
import uuid

ROLES = {'employee', 'manager', 'medical_reviewer', 'admin'}
MODULES = {'coach', 'review', 'daily', 'ui'}


def now() -> int:
    return int(time.time())


def new_id() -> str:
    return str(uuid.uuid4())


def new_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()
