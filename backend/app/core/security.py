"""Password hashing and access tokens.

Passwords use scrypt from the standard library (memory-hard, per-user salt).
Access tokens are short-lived HS256 JWTs; the database is still consulted on
every request so deactivating a user or bumping token_version revokes access.
"""

import base64
import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_LEN = 2**14, 8, 1, 32
TOKEN_ALGORITHM = "HS256"
TOKEN_ISSUER = "agentforge"


class AuthSettings(BaseSettings):
    auth_secret_key: SecretStr = SecretStr("")
    auth_token_ttl_minutes: int = Field(default=480, ge=5, le=1440)
    app_env: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def auth_settings() -> AuthSettings:
    # Read per call so tests and operators can change the environment safely.
    return AuthSettings()


def is_production() -> bool:
    return auth_settings().app_env.strip().lower() == "production"


class AuthConfigurationError(RuntimeError):
    pass


def _secret() -> bytes:
    secret = auth_settings().auth_secret_key.get_secret_value()
    if len(secret) < 32:
        raise AuthConfigurationError("AUTH_SECRET_KEY must be set to at least 32 characters")
    return secret.encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R,
                            p=SCRYPT_P, dklen=SCRYPT_LEN)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = encoded.split("$")
        if scheme != "scrypt":
            return False
        expected = _unb64(digest)
        actual = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r),
                                p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Verifying against this keeps response time similar for unknown emails.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def burn_password_check(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def create_access_token(user_id: uuid.UUID, role: str, token_version: int) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=auth_settings().auth_token_ttl_minutes)
    claims = {"sub": str(user_id), "role": role, "ver": token_version, "iss": TOKEN_ISSUER,
              "iat": now, "exp": expires, "jti": secrets.token_hex(8)}
    return jwt.encode(claims, _secret(), algorithm=TOKEN_ALGORITHM), expires


def decode_access_token(token: str) -> dict:
    """Raise jwt.InvalidTokenError on any tampering, expiry, or malformed input."""
    return jwt.decode(token, _secret(), algorithms=[TOKEN_ALGORITHM], issuer=TOKEN_ISSUER,
                      options={"require": ["sub", "role", "ver", "exp", "iat"]})
