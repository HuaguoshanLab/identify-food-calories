"""Cryptographic primitives for auth; business policy remains in the service."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from base64 import urlsafe_b64encode
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash


_PASSWORD_HASH = PasswordHash.recommended()
_DUMMY_PASSWORD_HASH = _PASSWORD_HASH.hash(
    "dummy-password-used-only-to-equalize-unknown-account-work"
)
ACCESS_TOKEN_ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "JWT"
ACCESS_TOKEN_TTL = timedelta(minutes=15)


class InvalidAccessToken(ValueError):
    """Collapse all bearer validation failures into one non-sensitive result."""


def hash_password(password: str) -> str:
    return _PASSWORD_HASH.hash(password)


def password_matches(*, password: str, password_hash: str | None) -> bool:
    """Perform exactly one Argon2 verification, including for unknown accounts."""

    candidate_hash = password_hash or _DUMMY_PASSWORD_HASH
    try:
        return _PASSWORD_HASH.verify(password, candidate_hash)
    except Exception:
        # Corrupt stored hashes are authentication failures, never a plaintext fallback.
        return False


def issue_access_token(
    *,
    secret_key: str,
    user_id: uuid.UUID,
    role: str,
    issuer: str,
    audience: str,
    issued_at: datetime,
) -> tuple[str, int]:
    expires_at = issued_at + ACCESS_TOKEN_TTL
    claims = {
        "sub": str(user_id),
        "role": role,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": str(uuid.uuid4()),
        "iss": issuer,
        "aud": audience,
    }
    token = jwt.encode(
        claims,
        secret_key,
        algorithm=ACCESS_TOKEN_ALGORITHM,
        headers={"typ": ACCESS_TOKEN_TYPE},
    )
    return token, int(ACCESS_TOKEN_TTL.total_seconds())


def verify_access_token(
    *,
    token: str,
    secret_key: str,
    issuer: str,
    audience: str,
    now: Callable[[], datetime] | None = None,
) -> uuid.UUID:
    """Validate the complete access-token envelope and return only its subject."""

    current_time = (now or (lambda: datetime.now(UTC)))()
    try:
        decoded = jwt.decode_complete(
            token,
            secret_key,
            algorithms=[ACCESS_TOKEN_ALGORITHM],
            issuer=issuer,
            audience=audience,
            options={
                "require": ["sub", "role", "iat", "exp", "jti", "iss", "aud"],
                "strict_aud": True,
                # The injected clock keeps service tests deterministic. Time claims are
                # still validated below after PyJWT validates signature and claim types.
                "verify_exp": False,
                "verify_iat": False,
            },
        )
        header = decoded["header"]
        claims = decoded["payload"]
        if header != {"alg": ACCESS_TOKEN_ALGORITHM, "typ": ACCESS_TOKEN_TYPE}:
            raise InvalidAccessToken
        if set(claims) != {"sub", "role", "iat", "exp", "jti", "iss", "aud"}:
            raise InvalidAccessToken
        issued_at = _numeric_date(claims["iat"])
        expires_at = _numeric_date(claims["exp"])
        now_timestamp = current_time.timestamp()
        if issued_at > now_timestamp or expires_at <= now_timestamp or expires_at <= issued_at:
            raise InvalidAccessToken
        uuid.UUID(claims["jti"])
        if claims["role"] not in {"user", "admin"}:
            raise InvalidAccessToken
        return uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise InvalidAccessToken from error


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def digest_refresh_token(*, secret_key: str, refresh_token: str) -> str:
    return _hmac_digest(secret_key=secret_key, value=f"refresh:{refresh_token}")


def generate_verification_code() -> str:
    """Generate exactly six ASCII digits using the OS CSPRNG."""

    return f"{secrets.randbelow(1_000_000):06d}"


def derive_context_token(*, secret_key: str, challenge_id: uuid.UUID) -> str:
    """Rebuild an opaque context without storing it or exposing predictable row IDs."""

    digest = hmac.new(
        secret_key.encode("utf-8"),
        f"registration-context:{challenge_id}".encode("ascii"),
        hashlib.sha256,
    ).digest()
    return urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def digest_context(*, secret_key: str, context_token: str) -> str:
    return _hmac_digest(secret_key=secret_key, value=f"context:{context_token}")


def digest_code(*, secret_key: str, context_token: str, code: str) -> str:
    # Scope the six-digit value by its high-entropy context to prevent digest collisions.
    return _hmac_digest(secret_key=secret_key, value=f"code:{context_token}:{code}")


def code_matches(
    *, secret_key: str, context_token: str, code: str, expected_digest: str
) -> bool:
    candidate = digest_code(
        secret_key=secret_key, context_token=context_token, code=code
    )
    return hmac.compare_digest(candidate, expected_digest)


def _hmac_digest(*, secret_key: str, value: str) -> str:
    return hmac.new(
        secret_key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _numeric_date(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidAccessToken
    return float(value)
