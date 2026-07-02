from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import ExpiredTokenException, InvalidTokenException

# ── Password hashing ──────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def generate_random_password(length: int = 16) -> str:
    return secrets.token_urlsafe(length)


# ── JWT ───────────────────────────────────────────────────────────────────────
def create_access_token(
    subject: str | uuid.UUID,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.now(UTC) + (
        expires_delta
        or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": datetime.now(UTC),
        "exp": expire,
        "type": "access",
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str | uuid.UUID) -> str:
    expire = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": datetime.now(UTC),
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != expected_type:
            raise InvalidTokenException("Token type mismatch.")
        return payload
    except JWTError as exc:
        error_message = str(exc).lower()
        if "expired" in error_message:
            raise ExpiredTokenException() from exc
        raise InvalidTokenException() from exc


def create_verification_token(data: dict[str, Any], expires_hours: int = 24) -> str:
    expire = datetime.now(UTC) + timedelta(hours=expires_hours)
    payload = {**data, "exp": expire, "jti": str(uuid.uuid4())}
    return jwt.encode(payload, settings.APP_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_verification_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token, settings.APP_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError as exc:
        raise InvalidTokenException("Verification token is invalid or expired.") from exc


# ── Encryption ────────────────────────────────────────────────────────────────
def _get_fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    if not key:
        key = base64.urlsafe_b64encode(
            hashlib.sha256(settings.APP_SECRET_KEY.encode()).digest()
        ).decode()
    # Ensure key is valid Fernet key (32 url-safe base64-encoded bytes)
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        derived = base64.urlsafe_b64encode(
            hashlib.sha256(key.encode()).digest()
        )
        return Fernet(derived)


def encrypt_value(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    return _get_fernet().decrypt(encrypted.encode()).decode()


# ── HMAC / Webhook verification ───────────────────────────────────────────────
def verify_whatsapp_signature(payload: bytes, signature: str) -> bool:
    """Verify Meta WhatsApp webhook HMAC-SHA256 signature."""
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.WHATSAPP_APP_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature[7:])


# ── Tokens ────────────────────────────────────────────────────────────────────
def generate_otp(length: int = 6) -> str:
    return "".join([str(secrets.randbelow(10)) for _ in range(length)])


def generate_secure_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)
