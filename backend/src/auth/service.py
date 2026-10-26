import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from ..core.config import Settings

password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    return password_hasher.verify(password, stored_hash)


def create_access_token(
    user_id: UUID, settings: Settings, roles: list[str] | None = None
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "roles": ["RESEARCHER"] if roles is None else roles,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )


def read_access_token(token: str, settings: Settings) -> UUID:
    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
        options={"require": ["sub", "iat", "exp"]},
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Wrong token type")
    try:
        return UUID(payload["sub"])
    except (ValueError, TypeError) as exc:
        raise jwt.InvalidTokenError("Invalid user ID") from exc


def create_refresh_token() -> tuple[str, str]:
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return raw_token, token_hash


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def password_hash_version(password_hash: str | None) -> str:
    """Bind a reset token to the current password state, including Google-only users."""
    return hashlib.sha256((password_hash or "").encode("utf-8")).hexdigest()


def create_password_reset_token(
    user_id: UUID, password_hash: str | None, settings: Settings
) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "type": "password_reset",
            "pwd_ver": password_hash_version(password_hash),
            "iat": now,
            "exp": now + timedelta(minutes=15),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )


def read_password_reset_token(token: str, settings: Settings) -> tuple[UUID, str]:
    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
        options={"require": ["sub", "type", "pwd_ver", "iat", "exp"]},
    )
    if payload["type"] != "password_reset":
        raise jwt.InvalidTokenError("Wrong token type")

    try:
        return UUID(payload["sub"]), payload["pwd_ver"]
    except (ValueError, TypeError) as exc:
        raise jwt.InvalidTokenError("Invalid user ID") from exc
