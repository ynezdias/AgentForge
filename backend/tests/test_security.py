import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core import security
from app.core.security import (AuthConfigurationError, create_access_token, decode_access_token,
                               hash_password, verify_password)


def test_password_hash_is_salted_and_verifiable():
    first, second = hash_password("246810-demo"), hash_password("246810-demo")
    assert first != second
    assert "246810-demo" not in first
    assert first.startswith("scrypt$")
    assert verify_password("246810-demo", first)
    assert not verify_password("246810-dem0", first)


@pytest.mark.parametrize("stored", ["", "plaintext", "bcrypt$1$2$3$4$5", "scrypt$x$8$1$aa$bb"])
def test_malformed_hash_never_verifies(stored):
    assert verify_password("anything", stored) is False


def test_token_round_trip_and_tampering():
    user_id = uuid.uuid4()
    token, expires = create_access_token(user_id, "company", 3)
    claims = decode_access_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["role"] == "company" and claims["ver"] == 3
    assert expires > datetime.now(timezone.utc)
    header, payload, signature = token.split(".")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(f"{header}.{payload}.{signature[::-1]}")


def test_expired_and_foreign_tokens_rejected():
    now = datetime.now(timezone.utc)
    secret = security._secret()
    expired = jwt.encode({"sub": "x", "role": "admin", "ver": 0, "iss": "agentforge", "jti": "t",
                          "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1)},
                         secret, algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired)
    forged = jwt.encode({"sub": "x", "role": "admin", "ver": 0, "iss": "agentforge", "jti": "t",
                         "iat": now, "exp": now + timedelta(hours=1)},
                        "a-different-secret-that-is-long-enough!!", algorithm="HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(forged)
    unsigned = jwt.encode({"sub": "x", "role": "admin", "ver": 0, "iss": "agentforge", "jti": "t",
                           "iat": now, "exp": now + timedelta(hours=1)}, None, algorithm="none")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(unsigned)


@pytest.mark.parametrize("secret", ["", "too-short"])
def test_missing_or_weak_secret_fails_closed(monkeypatch, secret):
    monkeypatch.setenv("AUTH_SECRET_KEY", secret)
    with pytest.raises(AuthConfigurationError):
        create_access_token(uuid.uuid4(), "admin", 0)


def test_token_without_id_is_rejected():
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": "x", "role": "admin", "ver": 0, "iss": "agentforge",
                        "iat": now, "exp": now + timedelta(hours=1)}, security._secret(), algorithm="HS256")
    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(token)  # Without a jti the token could never be revoked.
