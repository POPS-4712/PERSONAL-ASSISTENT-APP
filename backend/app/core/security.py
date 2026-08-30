"""Password hashing (Argon2id) and JWT access tokens.

Refresh tokens are opaque random strings (not JWTs) so they can be revoked
individually; only their SHA-256 is persisted. See app/services/auth.py.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets

import jwt
from argon2 import PasswordHasher

from app.config import get_settings

# Argon2id with sensible interactive params. argon2-cffi defaults to type=ID.
_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2)

# A precomputed hash of a random string. Verifying against it when a user does
# not exist keeps login timing roughly constant (no user-enumeration signal).
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        _hasher.verify(password_hash or _DUMMY_HASH, password)
        return password_hash is not None
    except Exception:  # noqa: BLE001 - any failure is an auth failure
        return False


def dummy_verify(password: str) -> None:
    """Burn the same time as a real verify; used on the user-not-found path."""
    try:
        _hasher.verify(_DUMMY_HASH, password)
    except Exception:  # noqa: BLE001
        pass


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except Exception:  # noqa: BLE001
        return False


# --- JWT access tokens ---------------------------------------------------------

def create_access_token(subject: str, *, extra: dict | None = None) -> tuple[str, int]:
    s = get_settings()
    now = dt.datetime.now(dt.timezone.utc)
    ttl = s.access_token_ttl_minutes * 60
    payload = {
        "sub": subject,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + ttl,
        "jti": secrets.token_urlsafe(8),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)
    return token, ttl


def decode_access_token(token: str) -> dict:
    s = get_settings()
    payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return payload


# --- Refresh tokens (opaque) --------------------------------------------------

def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
