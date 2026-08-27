"""Password recovery protocol with a single transaction for reset and session revocation."""

from __future__ import annotations

import math
import uuid
import hashlib
import hmac
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.accounts.ports import AccountRecoveryRepository, SessionFamilyRevoker
from app.accounts.schemas import RecoveryPendingResponse
from app.auth.models import ChallengePurpose, User, VerificationChallenge
from app.auth.security import (
    code_matches,
    derive_context_token,
    digest_code,
    digest_context,
    generate_verification_code,
    hash_password,
)
from app.notifications.ports import MailProvider


RECOVERY_EXPIRY = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_RECOVERY_ATTEMPTS = 5


class RecoveryError(ValueError):
    """Base recovery failure translated to stable HTTP codes by the API layer."""


class RecoveryContextInvalid(RecoveryError):
    pass


class InvalidRecoveryCode(RecoveryError):
    pass


class RecoveryCodeExpired(RecoveryError):
    pass


class RecoveryAttemptsExceeded(RecoveryError):
    pass


class ResendCooldown(RecoveryError):
    def __init__(self, retry_after: int) -> None:
        super().__init__("recovery resend is unavailable during cooldown")
        self.retry_after = retry_after


@dataclass(frozen=True, slots=True)
class RecoveryDispatch:
    """Internal-only context; the API puts it in an HttpOnly cookie, never JSON."""

    context_token: str
    masked_email: str
    resend_available_at: datetime
    expires_at: datetime


class RecoveryService:
    def __init__(
        self,
        *,
        repository: AccountRecoveryRepository,
        session_family_revoker: SessionFamilyRevoker,
        mail_provider: MailProvider,
        secret_key: str,
        now: Callable[[], datetime] | None = None,
        code_factory: Callable[[], str] = generate_verification_code,
        commit: Callable[[], None] | None = None,
        rollback: Callable[[], None] | None = None,
    ) -> None:
        self._repository = repository
        self._session_family_revoker = session_family_revoker
        self._mail_provider = mail_provider
        self._secret_key = secret_key
        self._now = now or (lambda: datetime.now(UTC))
        self._code_factory = code_factory
        self._commit = commit or (lambda: None)
        self._rollback = rollback or (lambda: None)

    def request_reset(self, *, email: str) -> RecoveryDispatch:
        """Dispatch a reset code without exposing whether the account exists."""

        now = self._now()
        user = self._repository.get_user_by_email(email.strip().lower())
        if user is None or not user.is_active or user.email_verified_at is None:
            # Keep body and cookie shapes indistinguishable. This context has no DB row,
            # hence cannot be used to verify or reset a password.
            return self._decoy_dispatch(now=now)

        current = self._repository.get_current_challenge_for_user_for_update(
            user_id=user.id, purpose=ChallengePurpose.PASSWORD_RESET.value
        )
        if current is not None:
            if now < current.resend_available_at:
                return self._dispatch_for_current(challenge=current, user=user)
            current.invalidated_at = now
        return self._dispatch(user=user, now=now)

    def get_context(self, context_token: str) -> RecoveryPendingResponse:
        try:
            self._current_challenge(context_token)
        except RecoveryContextInvalid:
            if self._decoy_context_is_valid(context_token):
                return RecoveryPendingResponse()
            raise
        # Even a masked email or precise deadline lets an attacker compare a real
        # cookie with a decoy. The UI gets only a fixed pending state; enforcement
        # remains server-side in the challenge row.
        return RecoveryPendingResponse()

    def resend(self, context_token: str) -> RecoveryDispatch:
        now = self._now()
        try:
            challenge = self._current_challenge(context_token)
        except RecoveryContextInvalid:
            if self._decoy_context_is_valid(context_token):
                return self._decoy_dispatch(now=now)
            raise
        if now < challenge.resend_available_at:
            raise ResendCooldown(
                max(1, math.ceil((challenge.resend_available_at - now).total_seconds()))
            )
        user = self._user_for(challenge)
        challenge.invalidated_at = now
        return self._dispatch(user=user, now=now)

    def verify(self, *, context_token: str, code: str) -> None:
        """Check a code without consuming it; reset remains the single use operation."""

        try:
            challenge = self._current_challenge(context_token)
        except RecoveryContextInvalid:
            if self._decoy_context_is_valid(context_token):
                raise InvalidRecoveryCode
            raise
        self._validate_code(challenge=challenge, context_token=context_token, code=code)

    def reset(self, *, context_token: str, code: str, new_password: str) -> None:
        """Consume challenge, update password, and revoke all sessions atomically."""

        now = self._now()
        try:
            challenge = self._current_challenge(context_token)
        except RecoveryContextInvalid:
            if self._decoy_context_is_valid(context_token):
                raise InvalidRecoveryCode
            raise
        self._validate_code(challenge=challenge, context_token=context_token, code=code)
        user = self._user_for(challenge)
        try:
            user.password_hash = hash_password(new_password)
            user.updated_at = now
            challenge.consumed_at = now
            self._session_family_revoker.revoke_all_session_families(
                user_id=user.id, revoked_at=now
            )
            self._commit()
        except Exception:
            self._rollback()
            raise

    def _validate_code(
        self, *, challenge: VerificationChallenge, context_token: str, code: str
    ) -> None:
        now = self._now()
        if challenge.attempts >= challenge.max_attempts:
            raise RecoveryAttemptsExceeded
        if now >= challenge.expires_at:
            raise RecoveryCodeExpired
        if code_matches(
            secret_key=self._secret_key,
            context_token=context_token,
            code=code,
            expected_digest=challenge.code_digest,
        ):
            return
        challenge.attempts += 1
        try:
            self._commit()
        except Exception:
            self._rollback()
            raise
        if challenge.attempts >= challenge.max_attempts:
            raise RecoveryAttemptsExceeded
        raise InvalidRecoveryCode

    def _dispatch(self, *, user: User, now: datetime) -> RecoveryDispatch:
        challenge_id = uuid.uuid4()
        context_token = derive_context_token(
            secret_key=self._secret_key, challenge_id=challenge_id
        )
        code = self._code_factory()
        if len(code) != 6 or any(character < "0" or character > "9" for character in code):
            raise ValueError("verification code factory must return six ASCII digits")
        challenge = VerificationChallenge(
            id=challenge_id,
            user_id=user.id,
            purpose=ChallengePurpose.PASSWORD_RESET.value,
            context_digest=digest_context(
                secret_key=self._secret_key, context_token=context_token
            ),
            code_digest=digest_code(
                secret_key=self._secret_key, context_token=context_token, code=code
            ),
            created_at=now,
            expires_at=now + RECOVERY_EXPIRY,
            attempts=0,
            max_attempts=MAX_RECOVERY_ATTEMPTS,
            resend_available_at=now + RESEND_COOLDOWN,
            consumed_at=None,
            invalidated_at=None,
        )
        self._repository.add_challenge(challenge)
        try:
            self._mail_provider.send_verification_code(
                recipient=user.email, code=code, expires_in_minutes=10
            )
            self._commit()
        except Exception:
            self._rollback()
            raise
        return self._dispatch_for_current(challenge=challenge, user=user)

    def _dispatch_for_current(
        self, *, challenge: VerificationChallenge, user: User
    ) -> RecoveryDispatch:
        return RecoveryDispatch(
            context_token=derive_context_token(
                secret_key=self._secret_key, challenge_id=challenge.id
            ),
            masked_email=_mask_email(user.email),
            resend_available_at=challenge.resend_available_at,
            expires_at=challenge.expires_at,
        )

    def _decoy_dispatch(self, *, now: datetime) -> RecoveryDispatch:
        # The server verifies this signed opaque value but never stores it in browser
        # storage or a URL. It gives unknown accounts the same cookie lifecycle
        # without reset capability or a nullable DB foreign key.
        issued_at = int(now.timestamp())
        nonce = uuid.uuid4().hex
        payload = f"recovery-decoy:v1:{issued_at}:{nonce}"
        signature = hmac.new(
            self._secret_key.encode("utf-8"), payload.encode("ascii"), hashlib.sha256
        ).hexdigest()
        return RecoveryDispatch(
            context_token=f"r1.{issued_at}.{nonce}.{signature}",
            masked_email="***",
            resend_available_at=now + RESEND_COOLDOWN,
            expires_at=now + RECOVERY_EXPIRY,
        )

    def _decoy_context_is_valid(self, context_token: str) -> bool:
        parts = context_token.split(".")
        if len(parts) != 4 or parts[0] != "r1":
            return False
        _, issued_at_text, nonce, signature = parts
        if len(nonce) != 32 or any(character not in "0123456789abcdef" for character in nonce):
            return False
        try:
            issued_at = int(issued_at_text)
        except ValueError:
            return False
        payload = f"recovery-decoy:v1:{issued_at}:{nonce}"
        expected = hmac.new(
            self._secret_key.encode("utf-8"), payload.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        now_timestamp = int(self._now().timestamp())
        return issued_at <= now_timestamp < issued_at + int(RECOVERY_EXPIRY.total_seconds())

    def _current_challenge(self, context_token: str) -> VerificationChallenge:
        challenge = self._repository.get_current_challenge_for_update(
            context_digest=digest_context(
                secret_key=self._secret_key, context_token=context_token
            ),
            purpose=ChallengePurpose.PASSWORD_RESET.value,
        )
        if challenge is None:
            raise RecoveryContextInvalid
        return challenge

    def _user_for(self, challenge: VerificationChallenge) -> User:
        user = self._repository.get_user_by_id(challenge.user_id)
        if user is None or not user.is_active:
            raise RecoveryContextInvalid
        return user


def _mask_email(email: str) -> str:
    local, separator, domain = email.partition("@")
    if not separator:
        return "***"
    return f"{local[0] if local else '*'}***@{domain}"
