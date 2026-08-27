"""Registration verification behavior; fakes keep service tests deterministic."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth.api import get_registration_service
from app.auth.models import User, VerificationChallenge
from app.auth.repository import SqlAlchemyAuthRepository
from app.auth.security import generate_verification_code
from app.auth.service import (
    InvalidVerificationCode,
    RegistrationService,
    ResendCooldown,
    VerificationAttemptsExceeded,
    VerificationCodeExpired,
    VerificationContextInvalid,
)
from app.core.config import Settings
from app.main import create_app
from app.notifications.smtp import SMTPMailProvider


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
    clock.advance(minutes=10)

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


def test_duplicate_during_cooldown_reuses_valid_context_without_sending(
    protocol: tuple[RegistrationService, FakeAuthRepository, FakeMailProvider, MutableClock],
) -> None:
    service, repository, mail, _ = protocol
    first = service.register(email="mina@example.com", password="correct horse battery")

    duplicate = service.register(
        email="MINA@example.com", password="another valid password"
    )

    assert duplicate.context_token == first.context_token
    assert service.get_context(duplicate.context_token).masked_email == "m***@example.com"
    assert len(repository.challenges) == 1
    assert len(mail.messages) == 1


def make_client(service: RegistrationService) -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev",
        test_database_url=(
            "postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test"
        ),
        secret_key="test-only-verification-pepper-at-least-32-bytes",
        cors_origins=["http://localhost:5173"],
        smtp_host="localhost",
        smtp_from_email="noreply@local.test",
        _env_file=None,
    )
    application = create_app(settings)
    application.dependency_overrides[get_registration_service] = lambda: service
    return TestClient(application)


def test_registration_api_uses_httponly_context_and_safe_envelope(
    protocol: tuple[RegistrationService, FakeAuthRepository, FakeMailProvider, MutableClock],
) -> None:
    service, _, _, _ = protocol
    client = make_client(service)

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "mina@example.com", "password": "correct horse battery"},
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 202
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.json()["status"] == "CODE_DISPATCH_ACCEPTED"
    serialized = response.text
    assert "context-one" not in serialized
    assert "123456" not in serialized
    assert "mina@example.com" not in serialized
    set_cookie = response.headers["set-cookie"]
    assert "registration_context=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=strict" in set_cookie

    context = client.get("/api/v1/auth/register/context")
    assert context.status_code == 200
    assert context.json()["masked_email"] == "m***@example.com"


def test_registration_and_resend_keep_non_enumerating_202_shape(
    protocol: tuple[RegistrationService, FakeAuthRepository, FakeMailProvider, MutableClock],
) -> None:
    service, _, _, clock = protocol
    client = make_client(service)
    first = client.post(
        "/api/v1/auth/register",
        json={"email": "mina@example.com", "password": "correct horse battery"},
    )
    clock.advance(seconds=61)
    duplicate = client.post(
        "/api/v1/auth/register",
        json={"email": "MINA@example.com", "password": "another valid password"},
    )
    clock.advance(seconds=61)
    resent = client.post("/api/v1/auth/register/resend")

    assert first.status_code == duplicate.status_code == resent.status_code == 202
    assert set(first.json()) == set(duplicate.json()) == set(resent.json())
    assert first.json()["status"] == duplicate.json()["status"] == "CODE_DISPATCH_ACCEPTED"


def test_verification_api_maps_errors_and_clears_context_on_success(
    protocol: tuple[RegistrationService, FakeAuthRepository, FakeMailProvider, MutableClock],
) -> None:
    service, _, _, _ = protocol
    client = make_client(service)
    client.post(
        "/api/v1/auth/register",
        json={"email": "mina@example.com", "password": "correct horse battery"},
    )

    invalid = client.post("/api/v1/auth/register/verify", json={"code": "000000"})
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_VERIFICATION_CODE"
    assert set(invalid.json()["error"]) == {"code", "message", "request_id"}

    verified = client.post("/api/v1/auth/register/verify", json={"code": "123456"})
    assert verified.status_code == 200
    assert verified.json() == {
        "status": "EMAIL_VERIFIED",
        "message": "邮箱验证成功，请登录。",
        "next_action": "login",
    }
    assert "registration_context=\"\"" in verified.headers["set-cookie"]
    assert client.get("/api/v1/auth/register/context").status_code == 409


def test_api_enforces_ascii_code_cooldown_expiry_and_attempt_limit(
    protocol: tuple[RegistrationService, FakeAuthRepository, FakeMailProvider, MutableClock],
) -> None:
    service, _, _, clock = protocol
    client = make_client(service)
    client.post(
        "/api/v1/auth/register",
        json={"email": "mina@example.com", "password": "correct horse battery"},
    )

    unicode_digits = client.post(
        "/api/v1/auth/register/verify", json={"code": "１２３４５６"}
    )
    assert unicode_digits.status_code == 422
    assert unicode_digits.json()["error"]["code"] == "VALIDATION_ERROR"

    cooldown = client.post("/api/v1/auth/register/resend")
    assert cooldown.status_code == 429
    assert cooldown.json()["error"]["code"] == "RESEND_COOLDOWN"
    assert cooldown.json()["error"]["retry_after"] == 60

    clock.advance(minutes=10)
    expired = client.post("/api/v1/auth/register/verify", json={"code": "123456"})
    assert expired.status_code == 410
    assert expired.json()["error"]["code"] == "VERIFICATION_CODE_EXPIRED"

    clock.advance(seconds=1)
    assert client.post("/api/v1/auth/register/resend").status_code == 202
    for _ in range(4):
        invalid = client.post(
            "/api/v1/auth/register/verify", json={"code": "000000"}
        )
        assert invalid.status_code == 400
    exhausted = client.post(
        "/api/v1/auth/register/verify", json={"code": "000000"}
    )
    assert exhausted.status_code == 429
    assert exhausted.json()["error"]["code"] == "VERIFICATION_ATTEMPTS_EXCEEDED"


def test_openapi_exposes_routes_without_persistence_secrets(
    protocol: tuple[RegistrationService, FakeAuthRepository, FakeMailProvider, MutableClock],
) -> None:
    service, _, _, _ = protocol
    document = make_client(service).get("/api/openapi.json").json()

    assert {
        "/api/v1/auth/register",
        "/api/v1/auth/register/context",
        "/api/v1/auth/register/verify",
        "/api/v1/auth/register/resend",
    }.issubset(document["paths"])
    serialized = str(document)
    for forbidden in ("password_hash", "code_digest", "context_digest", "refresh_token"):
        assert forbidden not in serialized


def test_real_postgres_and_mailpit_registration_flow(db_session: object) -> None:
    """The product API hides the code while local SMTP proves delivery end to end."""

    import httpx

    repository = SqlAlchemyAuthRepository(db_session)  # type: ignore[arg-type]
    service = RegistrationService(
        repository=repository,
        mail_provider=SMTPMailProvider(
            host="localhost", port=1025, from_email="noreply@local.test"
        ),
        secret_key="test-only-verification-pepper-at-least-32-bytes",
        code_factory=lambda: "314159",
        commit=db_session.commit,  # type: ignore[attr-defined]
        rollback=db_session.rollback,  # type: ignore[attr-defined]
    )
    client = make_client(service)
    recipient = f"mailpit-{uuid.uuid4().hex}@example.com"

    registered = client.post(
        "/api/v1/auth/register",
        json={"email": recipient, "password": "correct horse battery"},
    )

    assert registered.status_code == 202
    assert "314159" not in registered.text
    messages = httpx.get("http://localhost:8025/api/v1/messages", timeout=5).json()[
        "messages"
    ]
    matching = [
        message
        for message in messages
        if any(address["Address"] == recipient for address in message["To"])
    ]
    assert matching
    delivered = httpx.get(
        f"http://localhost:8025/api/v1/message/{matching[0]['ID']}", timeout=5
    ).json()
    assert "314159" in delivered["Text"]

    verified = client.post("/api/v1/auth/register/verify", json={"code": "314159"})
    assert verified.status_code == 200
    db_session.expire_all()  # type: ignore[attr-defined]
    user = repository.get_user_by_email(recipient)
    assert user is not None and user.email_verified_at is not None and user.is_active
