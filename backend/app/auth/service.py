"""Registration application protocol, independent of FastAPI and SQLAlchemy."""

from __future__ import annotations

import math
import hashlib
import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.auth.models import (
    AuthSession,
    ChallengePurpose,
    RefreshToken,
    User,
    UserRole,
    VerificationChallenge,
)
from app.auth.ports import AuthRepository
from app.auth.schemas import CurrentUserResponse, PublicUser, VerificationPendingResponse
from app.auth.security import (
    code_matches,
    derive_context_token,
    digest_code,
    digest_context,
    generate_verification_code,
    generate_refresh_token,
    hash_password,
    issue_access_token,
    password_matches,
    digest_refresh_token,
    verify_access_token,
)
from app.notifications.ports import MailProvider


VERIFICATION_EXPIRY = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_VERIFICATION_ATTEMPTS = 5
SESSION_EXPIRY = timedelta(days=30)
LOGIN_FAILURE_THRESHOLD = 5
LOGIN_ATTEMPT_WINDOW = timedelta(minutes=5)
LOGIN_LOCKOUT = timedelta(minutes=5)


class InvalidCredentials(ValueError):
    """Uniform login failure for unknown, wrong, unverified, and inactive users."""


class LoginRateLimited(ValueError):
    """Stable denial independent of whether the submitted principal exists."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("login rate limited")
        self.retry_after = retry_after


class AuthenticatedUserUnavailable(ValueError):
    """The signed subject no longer maps to an active authoritative user."""


@dataclass(frozen=True, slots=True)
class LoginResult:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class AuthenticationService:
    """Login and current-identity policy over a repository port."""

    def __init__(
        self,
        *,
        repository: AuthRepository,
        secret_key: str,
        issuer: str,
        audience: str,
        now: Callable[[], datetime] | None = None,
        commit: Callable[[], None] | None = None,
        rollback: Callable[[], None] | None = None,
    ) -> None:
        self._repository = repository
        self._secret_key = secret_key
        self._issuer = issuer
        self._audience = audience
        self._now = now or (lambda: datetime.now(UTC))
        self._commit = commit or (lambda: None)
        self._rollback = rollback or (lambda: None)

    def login(self, *, email: str, password: str, source: str) -> LoginResult:
        normalized_email = email.strip().lower()
        now = self._now()
        bucket_digests = self._login_bucket_digests(
            normalized_email=normalized_email, source=source
        )
        blocked_until = self._repository.get_login_blocked_until(
            bucket_digests=bucket_digests, now=now
        )
        if blocked_until is not None:
            raise LoginRateLimited(
                max(1, math.ceil((blocked_until - now).total_seconds()))
            )

        user = self._repository.get_user_by_email(normalized_email)
        password_valid = password_matches(
            password=password,
            password_hash=user.password_hash if user is not None else None,
        )
        if (
            user is None
            or not password_valid
            or user.email_verified_at is None
            or not user.is_active
        ):
            blocked_until = self._repository.record_login_failure(
                bucket_digests=bucket_digests,
                now=now,
                threshold=LOGIN_FAILURE_THRESHOLD,
                window=LOGIN_ATTEMPT_WINDOW,
                lockout=LOGIN_LOCKOUT,
            )
            try:
                self._commit()
            except Exception:
                self._rollback()
                raise
            if blocked_until is not None:
                raise LoginRateLimited(
                    max(1, math.ceil((blocked_until - now).total_seconds()))
                )
            raise InvalidCredentials("invalid credentials")

        self._repository.reset_login_attempts(bucket_digests=bucket_digests)
        session = self._repository.add_session(
            AuthSession(
                id=uuid.uuid4(),
                user_id=user.id,
                family_id=uuid.uuid4(),
                created_at=now,
                last_seen_at=now,
                expires_at=now + SESSION_EXPIRY,
                revoked_at=None,
                device_label=None,
            )
        )
        raw_refresh_token = generate_refresh_token()
        self._repository.add_refresh_token(
            RefreshToken(
                id=uuid.uuid4(),
                session_id=session.id,
                token_digest=digest_refresh_token(
                    secret_key=self._secret_key, refresh_token=raw_refresh_token
                ),
                issued_at=now,
                expires_at=session.expires_at,
                consumed_at=None,
                replaced_by_id=None,
                revoked_at=None,
            )
        )
        access_token, expires_in = issue_access_token(
            secret_key=self._secret_key,
            user_id=user.id,
            role=user.role,
            issuer=self._issuer,
            audience=self._audience,
            issued_at=now,
        )
        try:
            self._commit()
        except Exception:
            self._rollback()
            raise
        return LoginResult(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            token_type="bearer",
            expires_in=expires_in,
        )

    def _login_bucket_digests(
        self, *, normalized_email: str, source: str
    ) -> tuple[str, str]:
        def digest(value: str) -> str:
            return hmac.new(
                self._secret_key.encode("utf-8"),
                value.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

        return (
            digest(f"login-principal:v1:{normalized_email}"),
            digest(f"login-source:v1:{source}"),
        )

    def current_user(self, access_token: str) -> CurrentUserResponse:
        user_id = verify_access_token(
            token=access_token,
            secret_key=self._secret_key,
            issuer=self._issuer,
            audience=self._audience,
            now=self._now,
        )
        user = self._repository.get_user_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthenticatedUserUnavailable
        return CurrentUserResponse.model_validate(user)


class RegistrationError(Exception):
    """Base class translated to stable HTTP errors by the API layer."""


class VerificationContextInvalid(RegistrationError):
    pass


class InvalidVerificationCode(RegistrationError):
    pass


class VerificationCodeExpired(RegistrationError):
    pass


class VerificationAttemptsExceeded(RegistrationError):
    pass


class ResendCooldown(RegistrationError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"resend is available in {retry_after} seconds")
        self.retry_after = retry_after


@dataclass(frozen=True, slots=True)
class RegistrationDispatch:
    """Internal result: only the API may move context_token into an HttpOnly cookie."""

    context_token: str
    masked_email: str
    resend_available_at: datetime
    expires_at: datetime


class RegistrationService:
    def __init__(
        self,
        *,
        repository: AuthRepository,
        mail_provider: MailProvider,
        secret_key: str,
        now: Callable[[], datetime] | None = None,
        code_factory: Callable[[], str] = generate_verification_code,
        commit: Callable[[], None] | None = None,
        rollback: Callable[[], None] | None = None,
    ) -> None:
        self._repository = repository
        self._mail_provider = mail_provider
        self._secret_key = secret_key
        self._now = now or (lambda: datetime.now(UTC))
        self._code_factory = code_factory
        self._commit = commit or (lambda: None)
        self._rollback = rollback or (lambda: None)

    def register(self, *, email: str, password: str) -> RegistrationDispatch:
        normalized_email = email.strip().lower()
        now = self._now()
        user = self._repository.get_user_by_email(normalized_email)
        if user is None:
            user = User(
                id=uuid.uuid4(),
                email=normalized_email,
                password_hash=hash_password(password),
                role=UserRole.USER.value,
                is_active=False,
                email_verified_at=None,
                created_at=now,
                updated_at=now,
            )
            self._repository.add_user(user)

        current = self._repository.get_current_challenge_for_user_for_update(
            user_id=user.id, purpose=ChallengePurpose.REGISTRATION.value
        )
        if current is not None:
            if now < current.resend_available_at:
                # The external 202 shape remains uniform. This opaque context deliberately
                # maps back to the current row, so duplicate requests cannot enumerate an
                # account or bypass the cooldown.
                return RegistrationDispatch(
                    context_token=derive_context_token(
                        secret_key=self._secret_key, challenge_id=current.id
                    ),
                    masked_email=_mask_email(normalized_email),
                    resend_available_at=current.resend_available_at,
                    expires_at=current.expires_at,
                )
            current.invalidated_at = now

        return self._dispatch(user=user, now=now)

    def get_context(self, context_token: str) -> VerificationPendingResponse:
        challenge = self._current_challenge(context_token)
        user = self._user_for(challenge)
        return VerificationPendingResponse(
            masked_email=_mask_email(user.email),
            resend_available_at=challenge.resend_available_at,
            expires_at=challenge.expires_at,
        )

    def resend(self, context_token: str) -> RegistrationDispatch:
        now = self._now()
        challenge = self._current_challenge(context_token)
        if now < challenge.resend_available_at:
            retry_after = max(
                1, math.ceil((challenge.resend_available_at - now).total_seconds())
            )
            raise ResendCooldown(retry_after)
        user = self._user_for(challenge)
        challenge.invalidated_at = now
        return self._dispatch(user=user, now=now)

    def verify(self, *, context_token: str, code: str) -> PublicUser:
        now = self._now()
        challenge = self._current_challenge(context_token)
        if challenge.attempts >= challenge.max_attempts:
            raise VerificationAttemptsExceeded
        if now >= challenge.expires_at:
            raise VerificationCodeExpired
        if not code_matches(
            secret_key=self._secret_key,
            context_token=context_token,
            code=code,
            expected_digest=challenge.code_digest,
        ):
            challenge.attempts += 1
            self._commit()
            if challenge.attempts >= challenge.max_attempts:
                raise VerificationAttemptsExceeded
            raise InvalidVerificationCode

        user = self._user_for(challenge)
        challenge.consumed_at = now
        user.email_verified_at = now
        user.is_active = True
        user.updated_at = now
        self._commit()
        return PublicUser.model_validate(user)

    def _dispatch(self, *, user: User, now: datetime) -> RegistrationDispatch:
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
            purpose=ChallengePurpose.REGISTRATION.value,
            context_digest=digest_context(
                secret_key=self._secret_key, context_token=context_token
            ),
            code_digest=digest_code(
                secret_key=self._secret_key,
                context_token=context_token,
                code=code,
            ),
            created_at=now,
            expires_at=now + VERIFICATION_EXPIRY,
            attempts=0,
            max_attempts=MAX_VERIFICATION_ATTEMPTS,
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
        return RegistrationDispatch(
            context_token=context_token,
            masked_email=_mask_email(user.email),
            resend_available_at=challenge.resend_available_at,
            expires_at=challenge.expires_at,
        )

    def _current_challenge(self, context_token: str) -> VerificationChallenge:
        challenge = self._repository.get_current_challenge_for_update(
            context_digest=digest_context(
                secret_key=self._secret_key, context_token=context_token
            ),
            purpose=ChallengePurpose.REGISTRATION.value,
        )
        if challenge is None:
            raise VerificationContextInvalid
        return challenge

    def _user_for(self, challenge: VerificationChallenge) -> User:
        user = self._repository.get_user_by_id(challenge.user_id)
        if user is None:
            raise VerificationContextInvalid
        return user


def _mask_email(email: str) -> str:
    local, separator, domain = email.partition("@")
    if not separator:
        return "***"
    visible = local[0] if local else "*"
    return f"{visible}***@{domain}"
