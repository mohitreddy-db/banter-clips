import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from .config import settings

JWT_ALG = "HS256"
SESSION_DAYS = 30
LOGIN_TOKEN_MINUTES = 15


def new_login_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hash). Only the hash is stored."""
    raw = secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def login_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=LOGIN_TOKEN_MINUTES)


def create_session_jwt(user_id: uuid.UUID) -> str:
    payload = {
        "sub": str(user_id),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALG)


def decode_session_jwt(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALG])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
