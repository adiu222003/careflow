"""
Password hashing (argon2-cffi) and JWT (PyJWT) utilities.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

# ── Password hashing ─────────────────────────────────────────────────────────
# Argon2id — OWASP recommended; tuned for ≥1 second hash time on reference HW
_ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=2,
)


def hash_password(plain: str) -> str:
    """Return Argon2id hash of the plain-text password."""
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plain-text password against a stored Argon2id hash.
    Returns False (never raises) on mismatch.
    """
    try:
        return _ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def needs_rehash(hashed: str) -> bool:
    """Return True if the hash was created with outdated parameters."""
    return _ph.check_needs_rehash(hashed)


# ── JWT ──────────────────────────────────────────────────────────────────────

def create_access_token(subject: str, role: str) -> str:
    """
    Create a signed JWT.
    - sub: user UUID (string)
    - role: user role string
    - exp: configurable expiry (default 60 minutes)
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT.
    Raises jwt.PyJWTError on any validation failure.
    """
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
