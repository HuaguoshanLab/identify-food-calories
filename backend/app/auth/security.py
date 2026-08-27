"""Cryptographic primitives for auth; business policy remains in the service."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from base64 import urlsafe_b64encode

from pwdlib import PasswordHash


_PASSWORD_HASH = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _PASSWORD_HASH.hash(password)


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
