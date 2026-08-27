"""Registration verification behavior; fakes keep service tests deterministic."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest

from app.auth.models import User, VerificationChallenge
from app.auth.security import generate_verification_code
from app.auth.service import (
    InvalidVerificationCode,
    RegistrationService,
    ResendCooldown,
    VerificationAttemptsExceeded,
    VerificationCodeExpired,
    VerificationContextInvalid,
)


class FakeAuthRepository:
    def __init__(self) -> None:
        self.users: list[User] = []
        self.challenges: list[VerificationChallenge] = []

    def add_user(self, user: User) -> User:
        self.users.append(user)
        return user

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return next((user for user in self.users if user.id == user_id), None)

    def get_user_by_email(self, normalized_email: str) -> User | None:
        return next((user for user in self.users if user.email == normalized_email), None)

    def add_challenge(self, challenge: VerificationChallenge) -> VerificationChallenge:
        self.challenges.append(challenge)
        return challenge

    def get_current_challenge_for_update(
        self, *, context_digest: str, purpose: str
    ) -> VerificationChallenge | None:
        return next(
            (
                challenge
                for challenge in reversed(self.challenges)
                if challenge.context_digest == context_digest
                and challenge.purpose == purpose
                and challenge.consumed_at is None
                and challenge.invalidated_at is None
            ),
            None,
        )

    def get_current_challenge_for_user_for_update(
        self, *, user_id: uuid.UUID, purpose: str
    ) -> VerificationChallenge | None:
        return next(
            (
                challenge
                for challenge in reversed(self.challenges)
                if challenge.user_id == user_id
                and challenge.purpose == purpose
                and challenge.consumed_at is None
                and challenge.invalidated_at is None
            ),
            None,
        )


class FakeMailProvider:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, int]] = []

    def send_verification_code(
        self, *, recipient: str, code: str, expires_in_minutes: int
    ) -> None:
        self.messages.append((recipient, code, expires_in_minutes))


class MutableClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 8, 27, 8, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, **kwargs: int) -> None:
        self.current += timedelta(**kwargs)


def sequence(values: list[str]) -> Callable[[], str]:
    iterator: Iterator[str] = iter(values)
    return lambda: next(iterator)


@pytest.fixture
def protocol() -> tuple[RegistrationService, FakeAuthRepository, FakeMailProvider, MutableClock]:
    repository = FakeAuthRepository()
    mail = FakeMailProvider()
    clock = MutableClock()
    service = RegistrationService(
        repository=repository,
        mail_provider=mail,
        secret_key="test-only-verification-pepper-at-least-32-bytes",
        now=clock.now,
        code_factory=sequence(["123456", "654321", "222222"]),
        context_token_factory=sequence(["context-one", "context-two", "context-three"]),
    )
    return service, repository, mail, clock


def test_code_generator_returns_exactly_six_ascii_digits() -> None:
    for _ in range(100):
        code = generate_verification_code()
        assert len(code) == 6
        assert all("0" <= character <= "9" for character in code)


def test_register_hashes_password_and_stores_only_digests(
    protocol: tuple[RegistrationService, FakeAuthRepository, FakeMailProvider, MutableClock],
) -> None:
    service, repository, mail, clock = protocol

    dispatch = service.register(email="  Mina@Example.COM ", password="correct horse battery")

    user = repository.users[0]
    challenge = repository.challenges[0]
    assert user.email == "mina@example.com"
    assert user.role == "user"
    assert user.email_verified_at is None
    assert user.is_active is False
    assert user.password_hash.startswith("$argon2id$")
    assert user.password_hash != "correct horse battery"
    assert challenge.code_digest != "123456"
    assert challenge.context_digest != dispatch.context_token
    assert challenge.created_at == clock.current
    assert challenge.expires_at == clock.current + timedelta(minutes=10)
    assert challenge.resend_available_at == clock.current + timedelta(seconds=60)
    assert challenge.max_attempts == 5
    assert mail.messages == [("mina@example.com", "123456", 10)]
    assert dispatch.masked_email == "m***@example.com"
    assert "123456" not in repr(dispatch)


def test_context_never_exposes_full_email_or_code(
    protocol: tuple[RegistrationService, FakeAuthRepository, FakeMailProvider, MutableClock],
) -> None:
    service, _, _, _ = protocol
    dispatch = service.register(email="mina@example.com", password="correct horse battery")

    pending = service.get_context(dispatch.context_token)

    assert pending.masked_email == "m***@example.com"
    assert "mina@example.com" not in pending.model_dump_json()
    assert "123456" not in pending.model_dump_json()


def test_code_expires_after_ten_minutes(
    protocol: tuple[RegistrationService, FakeAuthRepository, FakeMailProvider, MutableClock],
) -> None:
    service, _, _, clock = protocol
    dispatch = service.register(email="mina@example.com", password="correct horse battery")
    clock.advance(minutes=10, seconds=1)

    with pytest.raises(VerificationCodeExpired):
        service.verify(context_token=dispatch.context_token, code="123456")


def test_fifth_wrong_attempt_exhausts_challenge(
    protocol: tuple[RegistrationService, FakeAuthRepository, FakeMailProvider, MutableClock],
) -> None:
    service, repository, _, _ = protocol
    dispatch = service.register(email="mina@example.com", password="correct horse battery")

    for _ in range(4):
        with pytest.raises(InvalidVerificationCode):
            service.verify(context_token=dispatch.context_token, code="000000")
    with pytest.raises(VerificationAttemptsExceeded):
        service.verify(context_token=dispatch.context_token, code="000000")
    with pytest.raises(VerificationAttemptsExceeded):
        service.verify(context_token=dispatch.context_token, code="123456")
    assert repository.challenges[0].attempts == 5


def test_resend_enforces_cooldown_and_newest_code_invalidates_old(
    protocol: tuple[RegistrationService, FakeAuthRepository, FakeMailProvider, MutableClock],
) -> None:
    service, repository, mail, clock = protocol
    first = service.register(email="mina@example.com", password="correct horse battery")

    with pytest.raises(ResendCooldown) as error:
        service.resend(first.context_token)
    assert error.value.retry_after == 60

    clock.advance(seconds=61)
    second = service.resend(first.context_token)

    assert repository.challenges[0].invalidated_at == clock.current
    assert mail.messages[-1] == ("mina@example.com", "654321", 10)
    with pytest.raises(VerificationContextInvalid):
        service.verify(context_token=first.context_token, code="123456")
    user = service.verify(context_token=second.context_token, code="654321")
    assert user.email_verified_at == clock.current
    assert user.is_active is True


def test_success_consumes_code_once_and_never_creates_a_session(
    protocol: tuple[RegistrationService, FakeAuthRepository, FakeMailProvider, MutableClock],
) -> None:
    service, repository, _, clock = protocol
    dispatch = service.register(email="mina@example.com", password="correct horse battery")

    result = service.verify(context_token=dispatch.context_token, code="123456")

    assert result.email_verified_at == clock.current
    assert repository.challenges[0].consumed_at == clock.current
    with pytest.raises(VerificationContextInvalid):
        service.verify(context_token=dispatch.context_token, code="123456")


def test_duplicate_registration_keeps_non_enumerating_dispatch_shape(
    protocol: tuple[RegistrationService, FakeAuthRepository, FakeMailProvider, MutableClock],
) -> None:
    service, repository, _, clock = protocol
    first = service.register(email="mina@example.com", password="correct horse battery")
    clock.advance(seconds=61)

    second = service.register(email="MINA@example.com", password="another valid password")

    assert len(repository.users) == 1
    assert first.masked_email == second.masked_email
    assert first.__class__ is second.__class__
